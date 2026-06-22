import json
import logging

import httpx
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.db import transaction
from django.db import connections
from django.db.models import F, Q
from django.utils import timezone
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    CanCreateAgentApplications,
    CanViewASR,
    CanUpdateTTS,
    CanCreateChat,
    CanDeleteAgentApplications,
    CanDeleteChat,
    CanUpdateAgentApplications,
    CanViewAgentApplications,
    CanUpdateLLMProviders,
    CanViewCompanyLLMOptions,
    CanViewCompanyTTSOptions,
    CanViewChat,
    CanViewLLMProviders,
    CanViewTTS,
    IsSuperUser,
)
from apps.devices.models import Device
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device
from apps.resources.views import PermissionMappedModelViewSet
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.models import Tenant
from config.request_id import get_request_id, get_trace_id

from . import llm_services
from .llm_services import (
    get_effective_llm_model_for_tenant,
    get_effective_llm_models_for_tenant,
    get_tenant_llm_settings,
    is_llm_model_effective_for_tenant,
    llm_model_has_active_company_authorization,
    llm_provider_has_active_company_authorization,
)
from .models import (
    ASRReplacementRule,
    AgentAnnotation,
    AgentApplication,
    ChatConversation,
    ChatMessage,
    EmbeddingModel,
    LLMModel,
    LLMProvider,
    LLMTestSettings,
    RerankModel,
    TenantKnowledgeModelSettings,
    TenantLLMModelGrant,
    TenantLLMSettings,
    TenantTTSSettings,
    TTSProvider,
    TTSVoice,
)
from .realtime_asr import resolve_asr_device_connection
from .serializers import (
    ASRConfigSerializer,
    AgentAnnotationCreateFromMessageSerializer,
    AgentAnnotationSerializer,
    ASRReplacementRuleSerializer,
    AgentApplicationSerializer,
    ChatConversationConfigSerializer,
    ChatConversationCreateSerializer,
    ChatConversationDetailSerializer,
    ChatConversationListSerializer,
    ChatMessageSerializer,
    ChatMessageFeedbackSerializer,
    ChatSendSerializer,
    LLMTestSettingsSerializer,
    KnowledgeModelSettingsSerializer,
    KnowledgeModelSettingsWriteSerializer,
    PlatformLLMModelSerializer,
    PlatformLLMModelWriteSerializer,
    PlatformLLMProviderSerializer,
    PlatformLLMProviderWriteSerializer,
    PlatformTTSProviderSummarySerializer,
    PlatformTTSSettingsSerializer,
    PlatformTTSSettingsWriteSerializer,
    CompanyTTSVoiceSerializer,
    TenantKnowledgeModelSettingsSerializer,
    TenantLLMAuthorizationSerializer,
    mask_knowledge_api_key,
)
from .services import tts as tts_services
from .services.asr import (
    get_effective_asr_config,
    serialize_asr_settings,
    serialize_asr_status,
    test_asr_connection,
)

logger = logging.getLogger(__name__)


def _build_llm_request_payload(
    *,
    model_name: str,
    messages: list[dict],
    stream: bool,
    temperature: float,
    max_tokens: int,
    max_tokens_unlimited: bool,
    enable_web_search: bool = False,
) -> dict:
    payload = {
        'model': model_name,
        'messages': messages,
        'stream': stream,
        'temperature': temperature,
    }
    if not max_tokens_unlimited:
        payload['max_tokens'] = max_tokens
    if enable_web_search:
        payload['enable_search'] = True
    return payload


class ASRSettingsView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        return Response(serialize_asr_settings(get_effective_asr_config()))

    def patch(self, request):
        from .models import ASRConfig

        instance = ASRConfig.load()
        serializer = ASRConfigSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serialize_asr_settings(get_effective_asr_config()))


class ASRSettingsTestView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request):
        return Response(test_asr_connection())


class ASRStatusView(APIView):
    permission_classes = [CanViewASR]

    def get(self, request):
        return Response(serialize_asr_status())


class ASRDeviceStatusView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        device_code = str(request.headers.get('X-Device-Code') or '').strip()
        if not device_code:
            return Response({'message': '设备号不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        connection = resolve_asr_device_connection(device_code)
        if connection is None:
            return Response({'message': '设备未绑定公司或不可用'}, status=status.HTTP_403_FORBIDDEN)

        device = Device.objects.select_related('tenant', 'application__agent_application', 'agent_application').get(id=connection['device_id'])
        agent_application = device.effective_agent_application
        return Response({
            **serialize_asr_status(),
            'requestId': get_request_id(request),
            'traceId': get_trace_id(request),
            'deviceCode': device.code,
            'deviceId': device.id,
            'tenantId': device.tenant_id,
            'tenantName': device.tenant.name if device.tenant else '',
            'applicationId': device.application_id,
            'applicationName': device.application.name if device.application else '',
            'agentApplicationId': agent_application.id if agent_application else None,
            'agentApplicationName': agent_application.name if agent_application else '',
        })


class ASRTestView(APIView):
    permission_classes = [CanViewASR]

    def post(self, request):
        return Response(test_asr_connection())


class ASRReplacementRuleViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    queryset = ASRReplacementRule.objects.all()
    serializer_class = ASRReplacementRuleSerializer
    permission_map = {
        'list': [CanViewASR],
        'retrieve': [CanViewASR],
        'create': [CanViewASR],
        'partial_update': [CanViewASR],
        'update': [CanViewASR],
        'destroy': [CanViewASR],
    }

    def tenant_create_kwargs(self) -> dict:
        user = getattr(self.request, 'user', None)
        if user is not None and user.is_superuser:
            tenant_id = self.superuser_tenant_filter()
            if tenant_id is not None:
                tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
                if tenant is not None:
                    return {'tenant': tenant}
            raise ValidationError({'tenant': ['超管请先具体到某家公司后再保存替换词']})

        tenant = self.request_tenant
        if tenant is None:
            raise ValidationError({'tenant': ['当前账号未归属公司，无法保存替换词']})
        return {'tenant': tenant}


def _tts_audio_response(*, pcm: bytes, config, voice: TTSVoice, wrap_wav: bool) -> HttpResponse:
    if wrap_wav:
        response = HttpResponse(
            tts_services.pcm_to_wav(pcm, sample_rate=config.sample_rate),
            content_type='audio/wav',
        )
    else:
        response = HttpResponse(pcm, content_type='audio/pcm')
    response['X-Audio-Source-Format'] = tts_services.PCM_SOURCE_FORMAT
    response['X-Audio-Sample-Rate'] = str(config.sample_rate)
    response['X-Audio-Channels'] = '1'
    response['X-TTS-Voice'] = voice.voice_code
    return response


def _request_wav_audio(request) -> bool:
    raw_wrap_wav = request.data.get('wrapWav', request.data.get('wrap_wav', False))
    raw_format = str(request.data.get('format') or request.data.get('audioFormat') or request.data.get('audio_format') or '').strip().lower()
    return raw_wrap_wav is True or str(raw_wrap_wav).strip().lower() == 'true' or raw_format == 'wav'


def _select_platform_tts_voice(provider, raw_voice_id=None) -> TTSVoice | None:
    if raw_voice_id not in (None, ''):
        try:
            voice_id = int(raw_voice_id)
        except (TypeError, ValueError):
            raise ValidationError({'voiceId': '音色不能为空'})
        voice = provider.voices.filter(id=voice_id).first()
        if voice is None:
            raise ValidationError({'voiceId': '音色不存在'})
        return voice
    return tts_services.get_default_tts_voice(provider)


def _select_company_tts_voice(tenant, provider, raw_voice_id=None) -> TTSVoice | None:
    if raw_voice_id not in (None, ''):
        try:
            voice_id = int(raw_voice_id)
        except (TypeError, ValueError):
            raise ValidationError({'voiceId': '音色不能为空'})
        return tts_services.get_available_tts_voices(provider).filter(id=voice_id).first()
    return tts_services.get_effective_tts_voice_for_tenant(tenant, provider)


def _get_platform_tts_provider(provider_code: str | None = None) -> TTSProvider:
    if provider_code is None:
        return tts_services.get_aliyun_tts_provider()
    return get_object_or_404(TTSProvider, code=provider_code)


def _build_company_tts_options_payload(tenant, request=None):
    provider = tts_services.get_aliyun_tts_provider()
    config = tts_services.get_effective_tts_config(provider)
    selected_voice = tts_services.get_effective_tts_voice_for_tenant(tenant, provider)
    voices = tts_services.get_available_tts_voices(provider)
    return {
        'provider': {
            'code': provider.code,
            'name': provider.name,
            'isActive': provider.is_active,
        },
        'defaultVoiceId': selected_voice.id if selected_voice else None,
        'sampleRate': config.sample_rate,
        'defaultTestText': config.default_test_text,
        'voices': CompanyTTSVoiceSerializer(
            voices,
            many=True,
            context={
                'default_voice_id': selected_voice.id if selected_voice else None,
                'request': request,
            },
        ).data,
    }


class TTSProviderListView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        tts_services.get_aliyun_tts_provider()
        providers = TTSProvider.objects.select_related('default_voice').prefetch_related('voices').order_by('id')
        return Response(PlatformTTSProviderSummarySerializer(providers, many=True).data)


class TTSSettingsView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request, provider_code=None):
        provider = _get_platform_tts_provider(provider_code)
        return Response(PlatformTTSSettingsSerializer(provider, context={'request': request}).data)

    def patch(self, request, provider_code=None):
        provider = _get_platform_tts_provider(provider_code)
        serializer = PlatformTTSSettingsWriteSerializer(provider, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        provider = serializer.save()
        return Response(PlatformTTSSettingsSerializer(provider, context={'request': request}).data)


class TTSSettingsTestView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request, provider_code=None):
        provider = _get_platform_tts_provider(provider_code)
        config = tts_services.get_effective_tts_config(provider)
        voice = _select_platform_tts_voice(provider, request.data.get('voiceId'))
        if voice is None:
            return Response({'voiceId': '请先配置默认音色'}, status=status.HTTP_400_BAD_REQUEST)
        text = tts_services.normalize_tts_text(request.data.get('text'), config)
        try:
            pcm = tts_services.synthesize_tts_pcm(text=text, voice=voice, config=config)
        except Exception as exc:
            return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)
        return _tts_audio_response(pcm=pcm, config=config, voice=voice, wrap_wav=True)


class CompanyTTSOptionsView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanViewCompanyTTSOptions]

    def get_permissions(self):
        if str(self.request.headers.get('X-Device-Code') or '').strip():
            return [AllowAny()]
        return super().get_permissions()

    def get(self, request):
        device_code = str(request.headers.get('X-Device-Code') or '').strip()
        if device_code:
            try:
                device = get_runtime_device(device_code, require_tenant=True)
            except RuntimeDeviceError as exc:
                return Response({'message': exc.message}, status=exc.status_code)
            return Response(_build_company_tts_options_payload(device.tenant, request))
        return Response(_build_company_tts_options_payload(self.request_tenant, request))


class CompanyTTSDefaultVoiceView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanUpdateTTS]

    def patch(self, request):
        tenant = self.request_tenant
        if tenant is None:
            return Response({'tenant': '当前账号未归属公司'}, status=status.HTTP_400_BAD_REQUEST)
        raw_voice_id = request.data.get('voiceId')
        try:
            voice_id = int(raw_voice_id)
        except (TypeError, ValueError):
            return Response({'voiceId': '音色不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        provider = tts_services.get_aliyun_tts_provider()
        voice = tts_services.get_available_tts_voices(provider).filter(id=voice_id).first()
        if voice is None:
            return Response({'voiceId': '所选音色不可用'}, status=status.HTTP_400_BAD_REQUEST)

        TenantTTSSettings.objects.update_or_create(
            tenant=tenant,
            defaults={'default_voice': voice},
        )
        return Response(_build_company_tts_options_payload(tenant, request))


class CompanyTTSTestView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanViewTTS]

    def post(self, request):
        tenant = self.request_tenant
        provider = tts_services.get_aliyun_tts_provider()
        config = tts_services.get_effective_tts_config(provider)
        voice = _select_company_tts_voice(tenant, provider, request.data.get('voiceId'))
        if voice is None:
            return Response({'voiceId': '请先配置默认音色'}, status=status.HTTP_400_BAD_REQUEST)
        text = tts_services.normalize_tts_text(request.data.get('text'), config)
        try:
            pcm = tts_services.synthesize_tts_pcm(text=text, voice=voice, config=config)
        except Exception as exc:
            return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)
        return _tts_audio_response(pcm=pcm, config=config, voice=voice, wrap_wav=True)


class TTSRuntimeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        device_code = str(request.headers.get('X-Device-Code') or '').strip()
        if not device_code:
            return Response({'message': '设备号不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        connection = resolve_asr_device_connection(device_code)
        if connection is None:
            return Response({'message': '设备未绑定公司或不可用'}, status=status.HTTP_403_FORBIDDEN)

        device = Device.objects.select_related('tenant').get(id=connection['device_id'])
        provider = tts_services.get_aliyun_tts_provider()
        config = tts_services.get_effective_tts_config(provider)
        voice = _select_company_tts_voice(device.tenant, provider, request.data.get('voiceId'))
        if voice is None:
            return Response({'voiceId': '请先配置默认音色'}, status=status.HTTP_400_BAD_REQUEST)
        text = tts_services.normalize_tts_text(request.data.get('text'), config)
        try:
            pcm = tts_services.synthesize_tts_pcm(text=text, voice=voice, config=config)
        except Exception as exc:
            return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)
        return _tts_audio_response(pcm=pcm, config=config, voice=voice, wrap_wav=_request_wav_audio(request))


_PLATFORM_LLM_PERMISSION_MAP = {
    'list': [IsSuperUser],
    'retrieve': [IsSuperUser],
    'create': [IsSuperUser],
    'update': [IsSuperUser],
    'partial_update': [IsSuperUser],
    'destroy': [IsSuperUser],
    'test': [IsSuperUser],
}


class PlatformLLMProviderViewSet(PermissionMappedModelViewSet):
    queryset = LLMProvider.objects.all().order_by('sort_order', 'id')
    parser_classes = [MultiPartParser, JSONParser]
    permission_map = _PLATFORM_LLM_PERMISSION_MAP

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return PlatformLLMProviderWriteSerializer
        return PlatformLLMProviderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        provider = serializer.save()
        return Response(
            PlatformLLMProviderSerializer(provider, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        provider = serializer.save()
        return Response(PlatformLLMProviderSerializer(provider, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        if llm_provider_has_active_company_authorization(instance):
            raise ValidationError({'detail': '该厂商仍有公司启用授权，不能删除，请先取消授权'})
        return super().perform_destroy(instance)


class PlatformLLMProviderModelsView(APIView):
    permission_classes = [IsSuperUser]
    parser_classes = [JSONParser]

    def get_provider(self, provider_id):
        return get_object_or_404(LLMProvider, pk=provider_id)

    def get(self, request, provider_id):
        provider = self.get_provider(provider_id)
        models = provider.models.select_related('provider').order_by('sort_order', 'id')
        return Response(PlatformLLMModelSerializer(models, many=True).data)

    def post(self, request, provider_id):
        provider = self.get_provider(provider_id)
        data = request.data.copy()
        data['providerId'] = provider.id
        serializer = PlatformLLMModelWriteSerializer(
            data=data,
            context={'provider': provider},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        model = serializer.save()
        return Response(PlatformLLMModelSerializer(model).data, status=status.HTTP_201_CREATED)


class PlatformLLMModelViewSet(PermissionMappedModelViewSet):
    queryset = LLMModel.objects.select_related('provider').order_by('provider__sort_order', 'provider__id', 'sort_order', 'id')
    permission_map = _PLATFORM_LLM_PERMISSION_MAP

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return PlatformLLMModelWriteSerializer
        return PlatformLLMModelSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        model = serializer.save()
        return Response(PlatformLLMModelSerializer(model).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        model = serializer.save()
        return Response(PlatformLLMModelSerializer(model).data)

    def perform_destroy(self, instance):
        if llm_model_has_active_company_authorization(instance):
            raise ValidationError({'detail': '该模型仍有公司启用授权，不能删除，请先取消授权'})
        return super().perform_destroy(instance)

    @action(detail=True, methods=['post'], url_path='test')
    def test(self, request, pk=None):
        model = self.get_object()
        return Response(llm_services.run_llm_model_test(model=model, settings=LLMTestSettings.load()))


class LLMTestSettingsView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        return Response(LLMTestSettingsSerializer(LLMTestSettings.load()).data)

    def patch(self, request):
        instance = LLMTestSettings.load()
        serializer = LLMTestSettingsSerializer(instance, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class TenantLLMAuthorizationView(APIView):
    permission_classes = [IsSuperUser]

    def _get_tenant(self, tenant_id):
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        if tenant is None:
            raise ValidationError({'tenantId': '公司不存在或已停用'})
        return tenant

    def _response_payload(self, tenant):
        settings, _ = TenantLLMSettings.objects.get_or_create(tenant=tenant)
        grant_map = {
            grant.model_id: grant
            for grant in TenantLLMModelGrant.objects.filter(tenant=tenant).select_related('model')
        }
        providers = []
        for provider in LLMProvider.objects.order_by('sort_order', 'id'):
            models = []
            for model in provider.models.order_by('sort_order', 'id'):
                grant = grant_map.get(model.id)
                models.append({
                    'id': model.id,
                    'providerId': provider.id,
                    'name': model.name,
                    'displayName': model.display_name,
                    'isActive': model.is_active,
                    'sortOrder': model.sort_order,
                    'grantIsActive': bool(grant and grant.is_active),
                })
            providers.append({
                'id': provider.id,
                'name': provider.name,
                'providerType': provider.provider_type,
                'providerTypeLabel': provider.get_provider_type_display(),
                'isActive': provider.is_active,
                'sortOrder': provider.sort_order,
                'models': models,
            })
        return {
            'tenant': {
                'id': tenant.id,
                'name': tenant.name,
                'isActive': tenant.is_active,
            },
            'providers': providers,
            'defaultModelId': settings.default_model_id,
        }

    def get(self, request, tenant_id):
        tenant = self._get_tenant(tenant_id)
        return Response(self._response_payload(tenant))

    def put(self, request, tenant_id):
        serializer = TenantLLMAuthorizationSerializer(
            data=request.data,
            context={'tenant_id': tenant_id},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        tenant = serializer.validated_data['tenant']
        grants = serializer.validated_data['modelGrants']
        default_model_id = serializer.validated_data.get('defaultModelId')

        with transaction.atomic():
            for item in grants:
                TenantLLMModelGrant.objects.update_or_create(
                    tenant=tenant,
                    model_id=int(item['modelId']),
                    defaults={'is_active': bool(item.get('isActive'))},
                )
            TenantLLMSettings.objects.update_or_create(
                tenant=tenant,
                defaults={'default_model_id': default_model_id},
            )

        return Response(self._response_payload(tenant))


def _get_embedding_model() -> EmbeddingModel:
    return EmbeddingModel.load_aliyun()


def _get_rerank_model() -> RerankModel:
    return RerankModel.load_aliyun()


def _knowledge_model_payload(model, model_type: str) -> dict:
    payload = {
        'id': model.id,
        'type': model_type,
        'alias': model.name,
        'model': model.model,
        'baseUrl': model.base_url,
        'apiKeyMasked': mask_knowledge_api_key(model.api_key),
        'apiKeyConfigured': bool(model.api_key),
        'isActive': model.is_active,
        'updated_at': model.updated_at,
    }
    if model_type == 'embedding':
        payload['dimensions'] = model.dimensions
    return payload


def _knowledge_settings_payload() -> dict:
    embedding = _get_embedding_model()
    rerank = _get_rerank_model()
    return {
        'embedding': _knowledge_model_payload(embedding, 'embedding'),
        'rerank': _knowledge_model_payload(rerank, 'rerank'),
    }


class PlatformKnowledgeModelSettingsView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        return Response(KnowledgeModelSettingsSerializer(_knowledge_settings_payload()).data)

    def patch(self, request):
        serializer = KnowledgeModelSettingsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        if 'embedding' in payload:
            embedding = _get_embedding_model()
            for field, value in payload['embedding'].items():
                if field == 'api_key' and value == '':
                    continue
                setattr(embedding, field, value)
            embedding.save()

        if 'rerank' in payload:
            rerank = _get_rerank_model()
            for field, value in payload['rerank'].items():
                if field == 'api_key' and value == '':
                    continue
                setattr(rerank, field, value)
            rerank.save()

        return Response(KnowledgeModelSettingsSerializer(_knowledge_settings_payload()).data)


class TenantKnowledgeModelAuthorizationView(APIView):
    permission_classes = [IsSuperUser]

    def _get_tenant(self, tenant_id):
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        if tenant is None:
            raise ValidationError({'tenantId': '公司不存在或已停用'})
        return tenant

    def _response_payload(self, tenant):
        settings, _ = TenantKnowledgeModelSettings.objects.get_or_create(tenant=tenant)
        embedding = _get_embedding_model()
        rerank = _get_rerank_model()
        return {
            'tenant': {
                'id': tenant.id,
                'name': tenant.name,
                'isActive': tenant.is_active,
            },
            'models': {
                'embedding': {
                    'id': embedding.id,
                    'alias': embedding.name,
                    'isActive': embedding.is_active,
                    'grantIsActive': settings.is_active and settings.embedding_model_id == embedding.id,
                },
                'rerank': {
                    'id': rerank.id,
                    'alias': rerank.name,
                    'isActive': rerank.is_active,
                    'grantIsActive': settings.is_active and settings.rerank_model_id == rerank.id,
                },
            },
            'embeddingModelId': settings.embedding_model_id,
            'rerankModelId': settings.rerank_model_id,
            'isActive': settings.is_active,
        }

    def get(self, request, tenant_id):
        tenant = self._get_tenant(tenant_id)
        return Response(self._response_payload(tenant))

    def put(self, request, tenant_id):
        serializer = TenantKnowledgeModelSettingsSerializer(data=request.data, context={'tenant_id': tenant_id})
        serializer.is_valid(raise_exception=True)
        tenant = serializer.validated_data['tenant']
        TenantKnowledgeModelSettings.objects.update_or_create(
            tenant=tenant,
            defaults={
                'embedding_model_id': serializer.validated_data.get('embeddingModelId'),
                'rerank_model_id': serializer.validated_data.get('rerankModelId'),
                'is_active': serializer.validated_data.get('isActive', True),
            },
        )
        return Response(self._response_payload(tenant))


def _build_company_llm_options_payload(tenant, request):
    settings = get_tenant_llm_settings(tenant)
    test_settings = LLMTestSettings.load()
    models = list(get_effective_llm_models_for_tenant(tenant))
    effective_model_ids = {model.id for model in models}
    default_model_id = (
        settings.default_model_id
        if settings is not None and settings.default_model_id in effective_model_ids
        else None
    )

    providers = []
    provider_map = {}
    for model in models:
        provider = model.provider
        provider_payload = provider_map.get(provider.id)
        if provider_payload is None:
            avatar_url = None
            if provider.avatar:
                avatar_url = request.build_absolute_uri(provider.avatar.url)
            provider_payload = {
                'id': provider.id,
                'name': provider.name,
                'providerType': provider.provider_type,
                'providerTypeLabel': provider.get_provider_type_display(),
                'avatarUrl': avatar_url,
                'models': [],
            }
            provider_map[provider.id] = provider_payload
            providers.append(provider_payload)
        provider_payload['models'].append({
            'id': model.id,
            'name': model.name,
            'displayName': model.display_name,
            'isDefault': model.id == default_model_id,
        })

    return {
        'defaultModelId': default_model_id,
        'testSettings': LLMTestSettingsSerializer(test_settings).data,
        'providers': providers,
    }


class CompanyLLMOptionsView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanViewCompanyLLMOptions]

    def get(self, request):
        return Response(_build_company_llm_options_payload(self.request_tenant, request))


class CompanyLLMDefaultModelView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanUpdateLLMProviders]

    def patch(self, request):
        tenant = self.request_tenant
        raw_model_id = request.data.get('modelId')
        try:
            model_id = int(raw_model_id)
        except (TypeError, ValueError):
            return Response({'modelId': '模型不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        model = get_effective_llm_model_for_tenant(tenant, model_id)
        if model is None:
            return Response({'modelId': '所选模型不可用或未授权'}, status=status.HTTP_400_BAD_REQUEST)

        settings = get_tenant_llm_settings(tenant)
        if settings is None:
            return Response({'tenant': '当前账号未归属公司'}, status=status.HTTP_400_BAD_REQUEST)
        settings.default_model = model
        settings.save(update_fields=['default_model', 'updated_at'])
        return Response(_build_company_llm_options_payload(tenant, request))


class CompanyLLMModelTestView(TenantScopedQuerysetMixin, APIView):
    permission_classes = [CanViewLLMProviders]

    def post(self, request, model_id):
        tenant = self.request_tenant
        model = get_effective_llm_model_for_tenant(tenant, model_id)
        if model is None:
            return Response({'modelId': '所选模型不可用或未授权'}, status=status.HTTP_400_BAD_REQUEST)

        test_settings = LLMTestSettings.load()
        cache_key = f'llm-test:{request.user.id}:{model.id}'
        if test_settings.test_cooldown_seconds > 0:
            if cache.get(cache_key):
                return Response(
                    {'detail': f'测速过于频繁，请 {test_settings.test_cooldown_seconds} 秒后再试'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            cache.set(cache_key, True, timeout=test_settings.test_cooldown_seconds)

        return Response(llm_services.run_llm_model_test(model=model, settings=test_settings))


def _build_chat_completions_url(raw_url: str) -> str:
    api_url = raw_url.rstrip('/')
    if api_url.endswith('/chat/completions'):
        return api_url
    if api_url.endswith('/openai'):
        return f'{api_url}/v1/chat/completions'
    if api_url.endswith('/v1'):
        return f'{api_url}/chat/completions'
    return f'{api_url}/chat/completions'


def _resolve_tenant_llm_model(tenant, model_id=None, *, use_default: bool = False) -> LLMModel:
    if model_id is not None:
        model = get_effective_llm_model_for_tenant(tenant, model_id)
        if model is None:
            raise ValidationError({'llmModelId': '所选模型不可用或未授权'})
        return model

    if use_default:
        settings = get_tenant_llm_settings(tenant)
        model = settings.default_model if settings is not None else None
        if is_llm_model_effective_for_tenant(tenant, model):
            return model

    raise ValidationError({'llmModelId': '请先选择模型或设置公司默认模型'})


def _coerce_openai_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get('text')
            if isinstance(text, str):
                chunks.append(text)
                continue
            inner_text = item.get('content')
            if isinstance(inner_text, str):
                chunks.append(inner_text)
        return ''.join(chunks)
    return ''


def _extract_openai_completion_text(payload: dict, *, stream_chunk: bool) -> str:
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    if stream_chunk:
        delta = first_choice.get('delta') if isinstance(first_choice, dict) else {}
        if not isinstance(delta, dict):
            return ''
        return _coerce_openai_content_to_text(delta.get('content'))

    if isinstance(first_choice, dict):
        message = first_choice.get('message')
        if isinstance(message, dict):
            content = _coerce_openai_content_to_text(message.get('content'))
            if content:
                return content
        return _coerce_openai_content_to_text(first_choice.get('text'))
    return ''


def _extract_openai_error_message(payload: dict) -> str:
    error = payload.get('error')
    if isinstance(error, dict):
        message = error.get('message')
        if isinstance(message, str):
            return message
    return ''


def _parse_sse_data_line(line: str) -> str | None:
    if not line.startswith('data:'):
        return None
    return line[5:].lstrip()


def _normalize_generated_title(raw_title: str) -> str:
    title = raw_title.strip().strip('\'"“”‘’`')
    title = title.replace('\r', ' ').replace('\n', ' ').strip()
    if len(title) > 30:
        title = title[:30].rstrip()
    return title or '新对话'


async def _generate_conversation_title(
    *,
    client: httpx.AsyncClient,
    api_url: str,
    provider: LLMProvider,
    model_name: str,
    enable_web_search: bool,
    user_message: str,
    assistant_message: str,
) -> str | None:
    title_prompt = (
        '你是一个聊天标题生成器。'
        '请根据用户首轮提问和助手首轮回答，生成一个简短、明确、适合侧边栏展示的中文标题。'
        '要求：1. 只输出标题本身；2. 不要使用引号、句号、序号；3. 控制在12个汉字以内。'
    )
    response = await client.post(
        api_url,
        json=_build_llm_request_payload(
            model_name=model_name,
            messages=[
                {'role': ChatMessage.ROLE_SYSTEM, 'content': title_prompt},
                {
                    'role': ChatMessage.ROLE_USER,
                    'content': f'用户问题：{user_message}\n助手回答：{assistant_message}',
                },
            ],
            stream=False,
            max_tokens=32,
            max_tokens_unlimited=False,
            temperature=0.2,
            enable_web_search=enable_web_search,
        ),
        headers={
            'Authorization': f'Bearer {provider.api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
    )
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    title = _extract_openai_completion_text(payload, stream_chunk=False)
    normalized_title = _normalize_generated_title(title)
    return normalized_title if normalized_title and normalized_title != '新对话' else None


async def _generate_conversation_summary(
    *,
    client: httpx.AsyncClient,
    api_url: str,
    provider: LLMProvider,
    model_name: str,
    enable_web_search: bool,
    user_message: str,
    assistant_message: str,
) -> str | None:
    summary_prompt = (
        '你是一个会话摘要生成器。'
        '请基于用户首轮提问和助手首轮回答，生成一句简短中文摘要，用于侧边栏副标题展示。'
        '要求：1. 只输出摘要本身；2. 控制在28个汉字以内；3. 不要使用引号、句号、序号。'
    )
    response = await client.post(
        api_url,
        json=_build_llm_request_payload(
            model_name=model_name,
            messages=[
                {'role': ChatMessage.ROLE_SYSTEM, 'content': summary_prompt},
                {'role': ChatMessage.ROLE_USER, 'content': f'用户问题：{user_message}\n助手回答：{assistant_message}'},
            ],
            stream=False,
            max_tokens=48,
            max_tokens_unlimited=False,
            temperature=0.2,
            enable_web_search=enable_web_search,
        ),
        headers={
            'Authorization': f'Bearer {provider.api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
    )
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    summary = _extract_openai_completion_text(payload, stream_chunk=False).strip().replace('\r', ' ').replace('\n', ' ')
    if len(summary) > 60:
        summary = summary[:60].rstrip()
    return summary or None


@extend_schema_view(
    list=extend_schema(tags=['Agent Applications']),
    retrieve=extend_schema(tags=['Agent Applications']),
    create=extend_schema(tags=['Agent Applications']),
    update=extend_schema(tags=['Agent Applications']),
    partial_update=extend_schema(tags=['Agent Applications']),
    destroy=extend_schema(tags=['Agent Applications']),
    annotations=extend_schema(tags=['Agent Applications']),
    create_annotation=extend_schema(tags=['Agent Applications']),
    update_annotation=extend_schema(tags=['Agent Applications']),
    create_conversation=extend_schema(tags=['Agent Applications']),
)
class AgentApplicationViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    queryset = (
        AgentApplication.objects
        .select_related('llm_model__provider', 'created_by')
        .prefetch_related('knowledge_documents', 'knowledge_bases')
    )
    serializer_class = AgentApplicationSerializer
    permission_map = {
        'list': [CanViewAgentApplications],
        'retrieve': [CanViewAgentApplications],
        'create': [CanCreateAgentApplications],
        'update': [CanUpdateAgentApplications],
        'partial_update': [CanUpdateAgentApplications],
        'destroy': [CanDeleteAgentApplications],
        'annotations': [CanViewAgentApplications],
        'create_annotation': [CanUpdateAgentApplications],
        'update_annotation': [CanUpdateAgentApplications],
        'create_conversation': [CanViewAgentApplications, CanCreateChat],
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = self.request_tenant
        return context

    def get_permissions(self):
        if self.action == 'annotations' and self.request.method == 'POST':
            return [CanUpdateAgentApplications()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            if 'llmModelId' in serializer.errors:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            raise ValidationError(serializer.errors)
        try:
            self.perform_create(serializer)
        except ValidationError as exc:
            detail = getattr(exc, 'detail', None)
            if isinstance(detail, dict) and 'llmModelId' in detail:
                return Response(detail, status=status.HTTP_400_BAD_REQUEST)
            raise
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        llm_model = serializer.validated_data.get('llm_model')
        if llm_model is None:
            try:
                llm_model = _resolve_tenant_llm_model(self.request_tenant, use_default=True)
            except ValidationError:
                llm_model = None
        serializer.save(created_by=self.request.user, llm_model=llm_model, **self.tenant_create_kwargs())

    def perform_update(self, serializer):
        save_kwargs = {}
        if 'llm_model' in serializer.validated_data and serializer.validated_data['llm_model'] is None:
            try:
                save_kwargs['llm_model'] = _resolve_tenant_llm_model(self.request_tenant, use_default=True)
            except ValidationError:
                save_kwargs['llm_model'] = None
        serializer.save(**save_kwargs)

    @action(detail=True, methods=['post'], url_path='conversations')
    def create_conversation(self, request, pk=None):
        application = self.get_object()
        conversation = ChatConversation.objects.create(
            title=f'{application.name} 调试会话',
            user=request.user,
            llm_model=application.llm_model,
            summary='',
            system_prompt=application.system_prompt,
            temperature=application.temperature,
            max_tokens=application.max_tokens,
            max_tokens_unlimited=application.max_tokens_unlimited,
            application=application,
            tenant=application.tenant,
        )
        return Response(ChatConversationDetailSerializer(conversation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='annotations')
    def annotations(self, request, pk=None):
        application = self.get_object()
        if request.method == 'GET':
            queryset = application.annotations.select_related('created_by').order_by('-updated_at', '-id')
            keyword = request.query_params.get('keyword', '').strip()
            if keyword:
                queryset = queryset.filter(Q(question__icontains=keyword) | Q(answer__icontains=keyword))
            return Response(AgentAnnotationSerializer(queryset, many=True).data)

        serializer = AgentAnnotationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        annotation, created = AgentAnnotation.objects.update_or_create(
            application=application,
            question=serializer.validated_data['question'],
            defaults={
                'tenant': application.tenant,
                'answer': serializer.validated_data['answer'],
                'is_active': serializer.validated_data.get('is_active', True),
                'created_by': request.user,
            },
        )
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(AgentAnnotationSerializer(annotation).data, status=status_code)

    @action(detail=True, methods=['post'], url_path='annotations/from-message')
    def create_annotation(self, request, pk=None):
        application = self.get_object()
        serializer = AgentAnnotationCreateFromMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatMessage.objects.select_related('conversation').filter(
            id=serializer.validated_data['messageId'],
            role=ChatMessage.ROLE_ASSISTANT,
            conversation__application=application,
            conversation__tenant=application.tenant,
        ).first()
        if message is None:
            return Response(
                {'status': 'error', 'message': '目标助手回复不存在', 'code': 404},
                status=status.HTTP_404_NOT_FOUND,
            )

        annotation, created = AgentAnnotation.objects.update_or_create(
            application=application,
            question=serializer.validated_data['question'],
            defaults={
                'tenant': application.tenant,
                'answer': serializer.validated_data['answer'],
                'source_message': message,
                'is_active': True,
                'created_by': request.user,
            },
        )
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(AgentAnnotationSerializer(annotation).data, status=status_code)

    @action(detail=True, methods=['patch', 'delete'], url_path='annotations/(?P<annotation_id>[^/.]+)')
    def update_annotation(self, request, pk=None, annotation_id=None):
        application = self.get_object()
        annotation = application.annotations.filter(id=annotation_id).first()
        if annotation is None:
            return Response(
                {'status': 'error', 'message': '标注不存在', 'code': 404},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.method == 'DELETE':
            annotation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AgentAnnotationSerializer(annotation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AgentAnnotationSerializer(annotation).data)

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        import datetime
        from django.utils import timezone
        
        application = self.get_object()
        
        conversations = ChatConversation.objects.filter(application=application, tenant=application.tenant)
        messages = ChatMessage.objects.filter(conversation__application=application, conversation__tenant=application.tenant)
        
        user_message_count = messages.filter(role=ChatMessage.ROLE_USER).count()
        assistant_message_count = messages.filter(role=ChatMessage.ROLE_ASSISTANT).count()
        up_count = messages.filter(role=ChatMessage.ROLE_ASSISTANT, feedback=ChatMessage.FEEDBACK_UP).count()
        down_count = messages.filter(role=ChatMessage.ROLE_ASSISTANT, feedback=ChatMessage.FEEDBACK_DOWN).count()
        
        today = timezone.localdate()
        daily_trends = []
        for i in range(6, -1, -1):
            date = today - datetime.timedelta(days=i)
            count = conversations.filter(created_at__date=date).count()
            daily_trends.append({
                'date': date.strftime('%m-%d'),
                'count': count
            })
            
        data = {
            'conversationCount': conversations.count(),
            'messageCount': messages.count(),
            'userMessageCount': user_message_count,
            'assistantMessageCount': assistant_message_count,
            'upCount': up_count,
            'downCount': down_count,
            'dailyTrends': daily_trends,
            'updatedAt': application.updated_at
        }
        return Response(data)


@extend_schema_view(
    list=extend_schema(tags=['AI Chat']),
    retrieve=extend_schema(tags=['AI Chat']),
    create=extend_schema(tags=['AI Chat']),
    destroy=extend_schema(tags=['AI Chat']),
    send=extend_schema(tags=['AI Chat']),
    update_title=extend_schema(tags=['AI Chat']),
    update_config=extend_schema(tags=['AI Chat']),
)
class ChatConversationViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    queryset = ChatConversation.objects.select_related('llm_model__provider', 'application')
    serializer_class = ChatConversationListSerializer
    permission_map = {
        'list': [CanViewChat],
        'retrieve': [CanViewChat],
        'create': [CanCreateChat],
        'destroy': [CanDeleteChat],
        'send': [CanCreateChat],
        'update_title': [CanCreateChat],
        'update_config': [CanCreateChat],
        'update_feedback': [CanCreateChat],
    }

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)
        application_id = self.request.query_params.get('application')
        if application_id:
            qs = qs.filter(application_id=application_id)
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword)
                | Q(messages__content__icontains=keyword)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ChatConversationDetailSerializer
        if self.action == 'create':
            return ChatConversationCreateSerializer
        return ChatConversationListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = self.request_tenant
        try:
            llm_model = _resolve_tenant_llm_model(
                tenant,
                serializer.validated_data.get('llmModelId'),
                use_default=True,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        conversation = ChatConversation.objects.create(
            title=serializer.validated_data.get('title', '新对话'),
            user=request.user,
            llm_model=llm_model,
            summary='',
            system_prompt=serializer.validated_data.get('systemPrompt', ''),
            temperature=serializer.validated_data.get('temperature', 0.7),
            max_tokens=serializer.validated_data.get('max_tokens', 1000),
            max_tokens_unlimited=serializer.validated_data.get('max_tokens_unlimited', False),
            tenant=tenant,
        )
        output_serializer = ChatConversationListSerializer(conversation)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        conversation = self.get_object()
        serializer = ChatConversationDetailSerializer(conversation)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='update-title')
    def update_title(self, request, pk=None):
        conversation = self.get_object()
        title = request.data.get('title', '').strip()
        if not title:
            return Response(
                {'status': 'error', 'message': '标题不能为空', 'code': 400},
                status=status.HTTP_400_BAD_REQUEST,
            )
        conversation.title = title
        conversation.save(update_fields=['title', 'updated_at'])
        return Response(ChatConversationListSerializer(conversation).data)

    @action(detail=True, methods=['patch'], url_path='update-config')
    def update_config(self, request, pk=None):
        conversation = self.get_object()
        serializer = ChatConversationConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        update_fields = ['system_prompt', 'temperature', 'max_tokens', 'max_tokens_unlimited', 'updated_at']
        if 'llmModelId' in serializer.validated_data:
            conversation.llm_model = _resolve_tenant_llm_model(
                conversation.tenant,
                serializer.validated_data.get('llmModelId'),
            )
            update_fields.insert(0, 'llm_model')

        conversation.system_prompt = serializer.validated_data.get('systemPrompt', '')
        conversation.temperature = serializer.validated_data.get('temperature', 0.7)
        conversation.max_tokens = serializer.validated_data.get('max_tokens', 1000)
        conversation.max_tokens_unlimited = serializer.validated_data.get('max_tokens_unlimited', False)
        conversation.save(update_fields=update_fields)

        logger.info(
            'chat.conversation.config_updated conversation_id=%s user_id=%s model_id=%s model_name=%s system_prompt_length=%s temperature=%s max_tokens=%s max_tokens_unlimited=%s',
            conversation.id,
            request.user.id,
            conversation.llm_model_id,
            conversation.llm_model.name if conversation.llm_model else '',
            len(conversation.system_prompt or ''),
            conversation.temperature,
            conversation.max_tokens,
            conversation.max_tokens_unlimited,
        )

        return Response(ChatConversationDetailSerializer(conversation).data)

    @action(detail=True, methods=['patch'], url_path='messages/(?P<message_id>[^/.]+)/feedback')
    def update_feedback(self, request, pk=None, message_id=None):
        conversation = self.get_object()
        target_message = conversation.messages.filter(
            id=message_id,
            role=ChatMessage.ROLE_ASSISTANT,
        ).first()
        if not target_message:
            return Response(
                {'status': 'error', 'message': '目标消息不存在', 'code': 404},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChatMessageFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_message.feedback = serializer.validated_data['feedback']
        target_message.save(update_fields=['feedback'])

        return Response(ChatMessageSerializer(target_message).data)

    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        conversation = self.get_object()
        serializer = ChatSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data['content']
        use_stream = serializer.validated_data.get('stream', True)
        regenerate_message_id = serializer.validated_data.get('regenerateMessageId')

        logger.info(
            'chat.send.received conversation_id=%s user_id=%s content_length=%s use_stream=%s regenerate_message_id=%s bound_model_id=%s bound_model_name=%s',
            conversation.id,
            request.user.id,
            len(content),
            use_stream,
            regenerate_message_id,
            conversation.llm_model_id,
            conversation.llm_model.name if conversation.llm_model else '',
        )

        if regenerate_message_id is not None:
            target_message = conversation.messages.filter(
                id=regenerate_message_id,
                role=ChatMessage.ROLE_ASSISTANT,
            ).first()
            if not target_message:
                return Response(
                    {'status': 'error', 'message': '要重生成的回复不存在', 'code': 404},
                    status=status.HTTP_404_NOT_FOUND,
                )
            latest_assistant = conversation.messages.filter(role=ChatMessage.ROLE_ASSISTANT).order_by('-created_at').first()
            if not latest_assistant or latest_assistant.id != target_message.id:
                return Response(
                    {'status': 'error', 'message': '当前仅支持重生成最后一条助手回复', 'code': 400},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            previous_user_message = conversation.messages.filter(
                role=ChatMessage.ROLE_USER,
                created_at__lte=target_message.created_at,
            ).order_by('-created_at').first()
            if not previous_user_message:
                return Response(
                    {'status': 'error', 'message': '缺少可重生成的用户消息', 'code': 400},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            content = previous_user_message.content
            target_message.delete()
            conversation.save(update_fields=['updated_at'])
        else:
            # Save user message
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.ROLE_USER,
                content=content,
            )
            conversation.save(update_fields=['updated_at'])

        normalized_content = content.strip()
        annotation = None
        if regenerate_message_id is None and conversation.application_id and normalized_content:
            annotation = (
                AgentAnnotation.objects
                .filter(
                    application=conversation.application,
                    tenant=conversation.tenant,
                    is_active=True,
                    question=normalized_content,
                )
                .first()
            )
        if annotation is not None:
            now = timezone.now()
            AgentAnnotation.objects.filter(id=annotation.id).update(hit_count=F('hit_count') + 1, last_hit_at=now)
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.ROLE_ASSISTANT,
                content=annotation.answer,
            )
            conversation.save(update_fields=['updated_at'])

            async def annotation_event_stream():
                yield f"data: {json.dumps({'content': annotation.answer})}\n\n"
                yield "data: [DONE]\n\n"

            logger.info(
                'chat.send.annotation_hit conversation_id=%s user_id=%s application_id=%s annotation_id=%s',
                conversation.id,
                request.user.id,
                conversation.application_id,
                annotation.id,
            )
            response = StreamingHttpResponse(annotation_event_stream(), content_type='text/event-stream')
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

        model = conversation.llm_model
        if not is_llm_model_effective_for_tenant(conversation.tenant, model):
            logger.warning(
                'chat.send.model_unavailable conversation_id=%s user_id=%s bound_model_id=%s',
                conversation.id,
                request.user.id,
                conversation.llm_model_id,
            )
            return Response({
                'status': 'error',
                'message': 'LLM 模型不可用，请重新选择可用模型',
                'code': 400,
            }, status=status.HTTP_400_BAD_REQUEST)

        provider = model.provider
        model_name = model.name
        enable_web_search = model.enable_web_search

        # Build messages history
        history_messages = list(
            conversation.messages.order_by('created_at').values_list('role', 'content')
        )
        api_messages = []
        if conversation.system_prompt:
            api_messages.append({'role': ChatMessage.ROLE_SYSTEM, 'content': conversation.system_prompt})
        api_messages.extend({'role': role, 'content': msg} for role, msg in history_messages)

        # Inject knowledge base context if configured
        from apps.ai_models.services.agent_knowledge import inject_knowledge_context
        api_messages = inject_knowledge_context(conversation, api_messages, content)

        api_url = _build_chat_completions_url(provider.api_base_url)

        logger.info(
            'chat.send.dispatch conversation_id=%s user_id=%s provider_id=%s provider_name=%s model_name=%s api_url=%s message_count=%s use_stream=%s temperature=%s max_tokens=%s',
            conversation.id,
            request.user.id,
            provider.id,
            provider.name,
            model_name,
            api_url,
            len(api_messages),
            use_stream,
            conversation.temperature,
            conversation.max_tokens,
        )

        def _ensure_db():
            """Ensure DB connection is alive inside the streaming generator."""
            connections['default'].ensure_connection()

        def _save_assistant_message(content: str, *, update_conversation: bool = False):
            _ensure_db()
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.ROLE_ASSISTANT,
                content=content,
            )
            if update_conversation:
                conversation.save(update_fields=['updated_at'])

        def _update_conversation_title(new_title: str):
            _ensure_db()
            conversation.title = new_title
            conversation.save(update_fields=['title', 'updated_at'])

        def _update_conversation_summary(new_summary: str):
            _ensure_db()
            conversation.summary = new_summary
            conversation.save(update_fields=['summary', 'updated_at'])

        async def event_stream():
            full_content = ''
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    if not use_stream:
                        response = await client.post(
                            api_url,
                            json=_build_llm_request_payload(
                                model_name=model_name,
                                messages=api_messages,
                                stream=False,
                                temperature=conversation.temperature,
                                max_tokens=conversation.max_tokens,
                                max_tokens_unlimited=conversation.max_tokens_unlimited,
                                enable_web_search=enable_web_search,
                            ),
                            headers={
                                'Authorization': f'Bearer {provider.api_key}',
                                'Accept': 'application/json',
                                'Content-Type': 'application/json',
                            },
                        )
                        logger.info(
                            'chat.send.non_stream_response conversation_id=%s user_id=%s status_code=%s content_type=%s',
                            conversation.id,
                            request.user.id,
                            response.status_code,
                            response.headers.get('content-type', ''),
                        )
                        if response.status_code != 200:
                            error_body = response.text
                            logger.warning(
                                'chat.send.non_stream_http_error conversation_id=%s user_id=%s status_code=%s error_preview=%s',
                                conversation.id,
                                request.user.id,
                                response.status_code,
                                error_body[:200].replace('\n', ' '),
                            )
                            yield f"data: {json.dumps({'error': True, 'content': f'LLM 请求失败 (HTTP {response.status_code})'})}\n\n"
                            yield "data: [DONE]\n\n"
                            await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                f'LLM 请求失败 (HTTP {response.status_code}): {error_body[:200]}'
                            )
                            return

                        try:
                            payload = response.json()
                        except json.JSONDecodeError:
                            payload = None

                        if isinstance(payload, dict):
                            error_message = _extract_openai_error_message(payload)
                            if error_message:
                                logger.warning(
                                    'chat.send.non_stream_json_error conversation_id=%s user_id=%s provider_id=%s error_message=%s',
                                    conversation.id,
                                    request.user.id,
                                    provider.id,
                                    error_message[:200],
                                )
                                yield f"data: {json.dumps({'error': True, 'content': error_message})}\n\n"
                                yield "data: [DONE]\n\n"
                                await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                    error_message[:500]
                                )
                                return

                            text = _extract_openai_completion_text(payload, stream_chunk=False)
                            if text:
                                full_content = text
                                logger.info(
                                    'chat.send.completed_non_stream conversation_id=%s user_id=%s provider_id=%s response_length=%s',
                                    conversation.id,
                                    request.user.id,
                                    provider.id,
                                    len(full_content),
                                )
                                yield f"data: {json.dumps({'content': text})}\n\n"

                        if full_content:
                            await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                full_content,
                                update_conversation=True,
                            )
                            if conversation.title == '新对话':
                                generated_title = await _generate_conversation_title(
                                    client=client,
                                    api_url=api_url,
                                    provider=provider,
                                    model_name=model_name,
                                    enable_web_search=enable_web_search,
                                    user_message=content,
                                    assistant_message=full_content,
                                )
                                if generated_title:
                                    logger.info(
                                        'chat.title.generated conversation_id=%s user_id=%s title=%s',
                                        conversation.id,
                                        request.user.id,
                                        generated_title,
                                    )
                                    await sync_to_async(_update_conversation_title, thread_sensitive=True)(
                                        generated_title
                                    )
                                    yield f"data: {json.dumps({'title': generated_title})}\n\n"
                            if not conversation.summary:
                                generated_summary = await _generate_conversation_summary(
                                    client=client,
                                    api_url=api_url,
                                    provider=provider,
                                    model_name=model_name,
                                    enable_web_search=enable_web_search,
                                    user_message=content,
                                    assistant_message=full_content,
                                )
                                if generated_summary:
                                    logger.info(
                                        'chat.summary.generated conversation_id=%s user_id=%s summary=%s',
                                        conversation.id,
                                        request.user.id,
                                        generated_summary,
                                    )
                                    await sync_to_async(_update_conversation_summary, thread_sensitive=True)(
                                        generated_summary
                                    )
                                    yield f"data: {json.dumps({'summary': generated_summary})}\n\n"

                        yield "data: [DONE]\n\n"
                        return

                    async with client.stream(
                        'POST',
                        api_url,
                        json=_build_llm_request_payload(
                            model_name=model_name,
                            messages=api_messages,
                            stream=True,
                            temperature=conversation.temperature,
                            max_tokens=conversation.max_tokens,
                            max_tokens_unlimited=conversation.max_tokens_unlimited,
                            enable_web_search=enable_web_search,
                        ),
                        headers={
                            'Authorization': f'Bearer {provider.api_key}',
                            'Accept': 'text/event-stream',
                            'Content-Type': 'application/json',
                        },
                    ) as resp:
                        logger.info(
                            'chat.send.response_opened conversation_id=%s user_id=%s status_code=%s content_type=%s',
                            conversation.id,
                            request.user.id,
                            resp.status_code,
                            resp.headers.get('content-type', ''),
                        )
                        if resp.status_code != 200:
                            error_body = (await resp.aread()).decode('utf-8', errors='ignore')
                            logger.warning(
                                'chat.send.http_error conversation_id=%s user_id=%s status_code=%s error_preview=%s',
                                conversation.id,
                                request.user.id,
                                resp.status_code,
                                error_body[:200].replace('\n', ' '),
                            )
                            yield f"data: {json.dumps({'error': True, 'content': f'LLM 请求失败 (HTTP {resp.status_code})'})}\n\n"
                            yield "data: [DONE]\n\n"
                            await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                f'LLM 请求失败 (HTTP {resp.status_code}): {error_body[:200]}'
                            )
                            return

                        saw_sse_data = False
                        buffered_plain_lines: list[str] = []
                        chunk_count = 0
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            if not saw_sse_data:
                                buffered_plain_lines.append(line)
                            data_str = _parse_sse_data_line(line)
                            if data_str is not None:
                                saw_sse_data = True
                                buffered_plain_lines.clear()
                                if data_str.strip() == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    text = _extract_openai_completion_text(chunk, stream_chunk=True)
                                    if text:
                                        chunk_count += 1
                                        full_content += text
                                        yield f"data: {json.dumps({'content': text})}\n\n"
                                except json.JSONDecodeError:
                                    continue

                        if not full_content and not saw_sse_data and buffered_plain_lines:
                            raw_text = ''.join(buffered_plain_lines).strip()
                            try:
                                payload = json.loads(raw_text)
                            except json.JSONDecodeError:
                                payload = None

                            if isinstance(payload, dict):
                                error_message = _extract_openai_error_message(payload)
                                if error_message:
                                    logger.warning(
                                        'chat.send.plain_json_error conversation_id=%s user_id=%s provider_id=%s error_message=%s',
                                        conversation.id,
                                        request.user.id,
                                        provider.id,
                                        error_message[:200],
                                    )
                                    yield f"data: {json.dumps({'error': True, 'content': error_message})}\n\n"
                                    yield "data: [DONE]\n\n"
                                    await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                        error_message[:500]
                                    )
                                    return

                                text = _extract_openai_completion_text(payload, stream_chunk=False)
                                if text:
                                    full_content = text
                                    logger.info(
                                        'chat.send.completed_plain_json conversation_id=%s user_id=%s provider_id=%s response_length=%s',
                                        conversation.id,
                                        request.user.id,
                                        provider.id,
                                        len(full_content),
                                    )
                                    yield f"data: {json.dumps({'content': text})}\n\n"

                        if saw_sse_data:
                            logger.info(
                                'chat.send.completed_sse conversation_id=%s user_id=%s provider_id=%s chunk_count=%s response_length=%s',
                                conversation.id,
                                request.user.id,
                                provider.id,
                                chunk_count,
                                len(full_content),
                            )

                        if full_content:
                            await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                                full_content,
                                update_conversation=True,
                            )
                            if conversation.title == '新对话':
                                generated_title = await _generate_conversation_title(
                                    client=client,
                                    api_url=api_url,
                                    provider=provider,
                                    model_name=model_name,
                                    enable_web_search=enable_web_search,
                                    user_message=content,
                                    assistant_message=full_content,
                                )
                                if generated_title:
                                    logger.info(
                                        'chat.title.generated conversation_id=%s user_id=%s title=%s',
                                        conversation.id,
                                        request.user.id,
                                        generated_title,
                                    )
                                    await sync_to_async(_update_conversation_title, thread_sensitive=True)(
                                        generated_title
                                    )
                                    yield f"data: {json.dumps({'title': generated_title})}\n\n"
                            if not conversation.summary:
                                generated_summary = await _generate_conversation_summary(
                                    client=client,
                                    api_url=api_url,
                                    provider=provider,
                                    model_name=model_name,
                                    enable_web_search=enable_web_search,
                                    user_message=content,
                                    assistant_message=full_content,
                                )
                                if generated_summary:
                                    logger.info(
                                        'chat.summary.generated conversation_id=%s user_id=%s summary=%s',
                                        conversation.id,
                                        request.user.id,
                                        generated_summary,
                                    )
                                    await sync_to_async(_update_conversation_summary, thread_sensitive=True)(
                                        generated_summary
                                    )
                                    yield f"data: {json.dumps({'summary': generated_summary})}\n\n"

                yield "data: [DONE]\n\n"

            except httpx.TimeoutException:
                logger.warning(
                    'chat.send.timeout conversation_id=%s user_id=%s provider_id=%s partial_response_length=%s',
                    conversation.id,
                    request.user.id,
                    provider.id,
                    len(full_content),
                )
                if full_content:
                    await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                        full_content + '\n\n[请求超时，回复可能不完整]'
                    )
                yield f"data: {json.dumps({'error': True, 'content': '请求超时'})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                logger.exception(
                    'chat.send.exception conversation_id=%s user_id=%s provider_id=%s model_name=%s',
                    conversation.id,
                    request.user.id,
                    provider.id,
                    model_name,
                )
                if full_content:
                    await sync_to_async(_save_assistant_message, thread_sensitive=True)(
                        full_content + f'\n\n[发生错误: {str(exc)[:100]}]'
                    )
                yield f"data: {json.dumps({'error': True, 'content': str(exc)[:200]})}\n\n"
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
