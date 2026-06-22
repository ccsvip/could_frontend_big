from __future__ import annotations

import base64
import uuid

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteDevices, CanUpdateDevices, CanViewDevices, IsSuperUser
from apps.ai_models import llm_services
from apps.ai_models.services import asr as asr_services
from apps.ai_models.services import tts as tts_services
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.services import get_request_tenant
from config.request_id import get_request_id, get_trace_id

from .models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceGroup
from .services.authorization import (
    bind_device_authorization,
    ignore_device_authorization_request,
    publish_device_authorization_event,
    record_device_authorization_action,
    rename_authorization_device,
    revoke_device_authorization,
)
from .services.queries import (
    device_authorization_logs_queryset,
    device_authorization_requests_queryset,
    device_authorizations_queryset,
)
from .services.runtime import RuntimeDeviceError, get_runtime_device
from .serializers import (
    DeviceApplicationSerializer,
    DeviceActivationLogSerializer,
    DeviceAuthorizationCodeSerializer,
    DeviceAuthorizationRequestSerializer,
    DeviceBindSerializer,
    DeviceDetailSerializer,
    DeviceGroupSerializer,
    DeviceSerializer,
    DeviceStatsSerializer,
)

DEFAULT_DEVICE_NAME = '待修改'

def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class DevicePermissionMixin:
    def get_permissions(self):
        permission_map = {
            'list': [CanViewDevices],
            'retrieve': [CanViewDevices],
            'stats': [CanViewDevices],
            'create': [CanCreateDevices],
            'update': [CanUpdateDevices],
            'partial_update': [CanUpdateDevices],
            'destroy': [CanDeleteDevices],
        }
        permission_classes = permission_map.get(getattr(self, 'action', None), [CanViewDevices])
        if getattr(self, 'action', None) in {'create', 'update', 'partial_update', 'destroy'}:
            permission_classes = [CompanyDeviceWritePermission, *permission_classes]
        return [permission() for permission in permission_classes]


class CompanyDeviceWritePermission(BasePermission):
    message = '设备属于公司，请使用公司账号管理设备资源'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or user.is_superuser:
            return False
        return get_request_tenant(request) is not None


@extend_schema_view(
    list=extend_schema(tags=['Devices']),
    retrieve=extend_schema(tags=['Devices']),
    create=extend_schema(tags=['Devices']),
    update=extend_schema(tags=['Devices']),
    partial_update=extend_schema(tags=['Devices']),
    destroy=extend_schema(tags=['Devices']),
)
class DeviceViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Device.objects.select_related('application__agent_application', 'agent_application', 'group').all()
    lookup_field = 'code'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        return DeviceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter in {Device.STATUS_ONLINE, Device.STATUS_OFFLINE}:
            queryset = queryset.filter(status=status_filter)
        enabled_status = self.request.query_params.get('enabledStatus', '').strip()
        if enabled_status == 'enabled':
            queryset = queryset.filter(is_enabled=True)
        if enabled_status == 'disabled':
            queryset = queryset.filter(is_enabled=False)
        authorization_type = self.request.query_params.get('authorizationType', '').strip()
        if authorization_type in {Device.AUTHORIZATION_PERMANENT, Device.AUTHORIZATION_TRIAL}:
            queryset = queryset.filter(authorization_type=authorization_type)
        group_id = self.request.query_params.get('groupId', '').strip()
        if group_id.isdigit():
            queryset = queryset.filter(group_id=int(group_id))
        application_id = self.request.query_params.get('applicationId', '').strip()
        if application_id.isdigit():
            queryset = queryset.filter(application_id=int(application_id))
        return queryset

    @extend_schema(responses=DeviceStatsSerializer, tags=['Devices'])
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_superuser:
            scoped_tenant_id = self.superuser_tenant_filter()
            cache_key = (
                f'device_stats:scoped:{scoped_tenant_id}'
                if scoped_tenant_id is not None
                else 'device_stats:all'
            )
        else:
            tenant = self.request_tenant
            cache_key = f'device_stats:{tenant.id if tenant else "all"}'
        stats = cache.get(cache_key)
        if not stats:
            queryset = self.get_queryset()
            grouped = queryset.values('status').annotate(total=Count('id'))
            auth_grouped = queryset.values('authorization_type').annotate(total=Count('id'))
            stats = {
                'total': queryset.count(),
                'online': 0,
                'offline': 0,
                'trial': 0,
                'permanent': 0,
            }
            for item in grouped:
                if item['status'] in {'online', 'offline'}:
                    stats[item['status']] = item['total']
            for item in auth_grouped:
                if item['authorization_type'] == Device.AUTHORIZATION_TRIAL:
                    stats['trial'] = item['total']
                if item['authorization_type'] == Device.AUTHORIZATION_PERMANENT:
                    stats['permanent'] = item['total']
            cache.set(cache_key, stats, timeout=300)
        return Response(stats)


class DeviceGroupViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceGroup.objects.all()
    serializer_class = DeviceGroupSerializer


class DeviceApplicationViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceApplication.objects.select_related('agent_application').prefetch_related(
        'resources',
        'scrolling_texts__items',
        'voice_tones',
        'tts_voices',
        'model_assets',
        'command_groups',
    ).all()
    serializer_class = DeviceApplicationSerializer


class DeviceAuthorizationCodeViewSet(DevicePermissionMixin, TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = DeviceAuthorizationCode.objects.select_related('application', 'used_by_device').all()
    serializer_class = DeviceAuthorizationCodeSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        serializer.save(**self.tenant_create_kwargs())


class DeviceAuthorizationRequestViewSet(viewsets.GenericViewSet):
    permission_classes = [IsSuperUser]
    serializer_class = DeviceAuthorizationRequestSerializer
    lookup_field = 'code'
    lookup_value_regex = '[^/]+'
    queryset = Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'group').all()

    def get_queryset(self):
        return device_authorization_requests_queryset(self.request.query_params)

    def get_authorization_device(self, code) -> Device:
        devices = list(
            Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'group')
            .filter(code=code)
            .order_by('id')[:2]
        )
        if not devices:
            raise Http404
        if len(devices) > 1:
            conflict = APIException('设备码存在重复绑定，请先清理重复设备记录')
            conflict.status_code = status.HTTP_409_CONFLICT
            raise conflict
        return devices[0]

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='logs')
    def logs(self, request):
        queryset = device_authorization_logs_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceActivationLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceActivationLogSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='authorizations')
    def authorizations(self, request):
        queryset = device_authorizations_queryset(request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DeviceAuthorizationRequestSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = DeviceAuthorizationRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='bind')
    def bind(self, request, code=None):
        device = self.get_authorization_device(code)
        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = bind_device_authorization(device, serializer)
        self._log_platform_action(device, DeviceAuthLog.ACTION_BIND, '设备已绑定到公司', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_BIND)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='ignore')
    def ignore(self, request, code=None):
        device = self.get_authorization_device(code)
        device = ignore_device_authorization_request(device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_IGNORE, '设备授权请求已忽略', request)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='name')
    def rename(self, request, code=None):
        device = self.get_authorization_device(code)
        next_name = str(request.data.get('name') or '').strip()
        if not next_name:
            return Response({'name': '设备名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        device = rename_authorization_device(device, next_name)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='authorize')
    def authorize(self, request, code=None):
        device = self.get_authorization_device(code)
        serializer = DeviceBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = bind_device_authorization(device, serializer)
        self._log_platform_action(device, DeviceAuthLog.ACTION_AUTHORIZE, '设备已再次授权', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_AUTHORIZE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, code=None):
        device = self.get_authorization_device(code)
        device = revoke_device_authorization(device)
        self._log_platform_action(device, DeviceAuthLog.ACTION_REVOKE, '设备授权已撤销', request)
        self._publish_authorization_event(device, DeviceAuthLog.ACTION_REVOKE)
        return Response(DeviceAuthorizationRequestSerializer(device, context={'request': request}).data)

    @staticmethod
    def _log_platform_action(device, action, message, request):
        record_device_authorization_action(device, action, message, ip_address=_client_ip(request))

    @staticmethod
    def _publish_authorization_event(device, action):
        publish_device_authorization_event(device, action)


class DeviceActivationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=['Device Runtime'])
    @transaction.atomic
    def post(self, request):
        device_code = str(request.data.get('deviceCode') or request.data.get('device_code') or '').strip()
        if not device_code:
            self._log_activation(None, '', False, '设备码不能为空', request)
            return Response({'message': '设备码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        existing_devices = list(
            Device.objects.select_for_update()
            .filter(code=device_code)
            .order_by('id')[:2]
        )
        if len(existing_devices) > 1:
            self._log_activation(None, device_code, False, '设备码存在重复绑定，请联系后台处理', request)
            return Response({'message': '设备码存在重复绑定，请联系后台处理'}, status=status.HTTP_409_CONFLICT)

        now = timezone.now()
        device_info = request.data.get('deviceInfo') or request.data.get('device_info') or {}
        defaults = {
            'software_version': str(request.data.get('softwareVersion') or request.data.get('software_version') or '').strip(),
            'system_version': str(request.data.get('systemVersion') or request.data.get('system_version') or '').strip(),
            'mainboard_info': str(request.data.get('mainboardInfo') or request.data.get('mainboard_info') or '').strip(),
            'registered_at': now,
            'last_auth_at': now,
            'last_heartbeat': now,
            'authorization_ignored_at': None,
            'device_info': device_info,
        }
        if existing_devices:
            device = existing_devices[0]
            for field, value in defaults.items():
                setattr(device, field, value)
            device.save(update_fields=[*defaults.keys(), 'updated_at'])
            message = '设备上报成功'
        else:
            device = Device.objects.create(
                code=device_code,
                name=DEFAULT_DEVICE_NAME,
                authorization_type=Device.AUTHORIZATION_PERMANENT,
                is_enabled=True,
                **defaults,
            )
            message = '设备上报成功，待后台绑定公司'
        self._log_activation(device, device_code, True, message, request)
        return Response(
            {
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': self._application_payload(device.application),
                'agentApplication': self._agent_application_payload(device.agent_application),
                'bindingStatus': 'bound' if device.tenant_id else 'pending',
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _application_payload(application):
        if application is None:
            return None
        return {
            'id': application.id,
            'name': application.name,
            'code': application.code,
        }

    @staticmethod
    def _agent_application_payload(agent_application):
        if agent_application is None:
            return None
        return {
            'id': agent_application.id,
            'name': agent_application.name,
            'llmModelId': agent_application.llm_model_id,
            'llmModelName': agent_application.model_name,
        }

    @staticmethod
    def _log_activation(device, device_code, result, message, request):
        raw_device_info = request.data.get('deviceInfo') or request.data.get('device_info') or {}
        device_info = raw_device_info if isinstance(raw_device_info, dict) else {'raw': raw_device_info}
        device_info = {
            **device_info,
            'softwareVersion': request.data.get('softwareVersion') or request.data.get('software_version') or '',
            'systemVersion': request.data.get('systemVersion') or request.data.get('system_version') or '',
            'mainboardInfo': request.data.get('mainboardInfo') or request.data.get('mainboard_info') or '',
        }
        DeviceAuthLog.objects.create(
            tenant=getattr(device, 'tenant', None),
            application=getattr(device, 'application', None),
            agent_application=getattr(device, 'agent_application', None),
            device=device,
            code=device_code,
            action=DeviceAuthLog.ACTION_ACTIVATE,
            result=result,
            message=message,
            ip_address=_client_ip(request),
            device_info=device_info,
        )


class DeviceRuntimeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_device_code(self, request) -> str:
        return str(
            request.data.get('deviceCode')
            or request.data.get('device_code')
            or request.query_params.get('deviceCode')
            or request.query_params.get('device_code')
            or request.headers.get('X-Device-Code')
            or ''
        ).strip()

    def validate_device(self, request):
        try:
            return get_runtime_device(self.get_device_code(request)), None
        except RuntimeDeviceError as exc:
            return None, Response({'message': exc.message}, status=exc.status_code)


class DeviceRuntimeConfigView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def get(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        application = device.application
        agent_application = device.effective_agent_application
        if agent_application is None or not agent_application.is_active:
            return Response({'message': '设备未绑定可用智能体'}, status=status.HTTP_403_FORBIDDEN)
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=application,
            agent_application=agent_application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_CONFIG,
            result=True,
            message='配置拉取成功',
            ip_address=_client_ip(request),
        )
        return Response(
            {
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
                'device': DeviceSerializer(device, context={'request': request}).data,
                'application': (
                    {
                        'id': application.id,
                        'name': application.name,
                        'code': application.code,
                    }
                    if application is not None
                    else None
                ),
                'agentApplication': DeviceActivationView._agent_application_payload(agent_application),
                'resources': self._resources_payload(application, request),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _resources_payload(application: DeviceApplication | None, request):
        def file_url(file_field):
            if not file_field:
                return ''
            return request.build_absolute_uri(file_field.url)

        if application is None or not application.is_active:
            return {
                'images': [],
                'videos': [],
                'scrollingTexts': [],
                'voiceTones': [],
                'models': [],
                'commandGroups': [],
            }

        resources = application.resources.all()
        return {
            'images': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': item.cloud_url or file_url(item.file),
                    'category': item.category,
                }
                for item in resources
                if item.resource_type == item.TYPE_IMAGE
            ],
            'videos': [
                {
                    'id': item.id,
                    'name': item.name,
                    'url': item.cloud_url or file_url(item.file),
                    'category': item.category,
                }
                for item in resources
                if item.resource_type == item.TYPE_VIDEO
            ],
            'scrollingTexts': [
                {
                    'id': item.id,
                    'title': item.title,
                    'i18nScheme': item.i18n_scheme,
                    'items': [
                        {
                            'id': text_item.id,
                            'order': text_item.order,
                            'zh': text_item.zh_text,
                            'en': text_item.en_text,
                        }
                        for text_item in item.items.all()
                    ],
                }
                for item in application.scrolling_texts.filter(is_active=True).prefetch_related('items')
            ],
            'voiceTones': [
                {
                    'id': item.id,
                    'name': item.display_name,
                    'voiceCode': item.voice_code,
                    'audioUrl': '',
                    'iconUrl': request.build_absolute_uri(item.avatar_path) if item.avatar_path.startswith('/') else item.avatar_path,
                }
                for item in application.tts_voices.filter(is_active=True, is_visible=True, provider__is_active=True)
            ],
            'models': [
                {
                    'id': item.id,
                    'name': item.name,
                    'modelType': item.model_type,
                    'orientation': item.orientation,
                    'url': item.cloud_url or file_url(item.model_file),
                    'thumbnailUrl': file_url(item.thumbnail),
                }
                for item in application.model_assets.filter(is_visible=True)
            ],
            'commandGroups': [
                {
                    'id': item.id,
                    'name': item.name,
                    'groupType': item.group_type,
                }
                for item in application.command_groups.filter(is_active=True)
            ],
        }


class DeviceRuntimeHeartbeatView(DeviceRuntimeView):
    @extend_schema(tags=['Device Runtime'])
    def post(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        update_fields = ['last_heartbeat', 'updated_at']
        device.last_heartbeat = timezone.now()
        software_version = str(request.data.get('softwareVersion') or request.data.get('software_version') or '').strip()
        system_version = str(request.data.get('systemVersion') or request.data.get('system_version') or '').strip()
        if software_version:
            device.software_version = software_version
            update_fields.append('software_version')
        if system_version:
            device.system_version = system_version
            update_fields.append('system_version')
        device.save(update_fields=update_fields)
        DeviceAuthLog.objects.create(
            tenant=device.tenant,
            application=device.application,
            agent_application=device.agent_application,
            device=device,
            code=device.code,
            action=DeviceAuthLog.ACTION_HEARTBEAT,
            result=True,
            message='心跳成功',
            ip_address=_client_ip(request),
            device_info=request.data.get('deviceInfo') or request.data.get('device_info') or {},
        )
        return Response(
            {
                'status': 'success',
                'message': '心跳成功',
                'requestId': get_request_id(request),
                'traceId': get_trace_id(request),
            },
            status=status.HTTP_200_OK,
        )


class DeviceVoiceChatView(DeviceRuntimeView):
    parser_classes = [MultiPartParser, JSONParser]

    @extend_schema(tags=['Device Runtime'])
    def post(self, request):
        device, error = self.validate_device(request)
        if error is not None:
            return error
        if device.effective_agent_application is None or not device.effective_agent_application.is_active:
            return Response({'message': '设备未绑定可用智能体'}, status=status.HTTP_403_FORBIDDEN)

        question_text = self._request_question_text(request)
        if not question_text:
            audio_file = request.FILES.get('audio')
            if audio_file is None:
                return Response({'message': '请上传语音或输入文本'}, status=status.HTTP_400_BAD_REQUEST)
            audio_format = str(request.data.get('format') or 'pcm').strip().lower()
            if audio_format != 'pcm':
                return Response({'message': '语音问答接口暂只支持 16k PCM 音频'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
            sample_rate, sample_error = self._request_sample_rate(request)
            if sample_error is not None:
                return sample_error
            try:
                question_text = asr_services.transcribe_pcm_audio(
                    pcm=audio_file.read(),
                    sample_rate=sample_rate,
                )
            except Exception as exc:
                return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)
            if not question_text:
                return Response({'message': 'ASR 没有识别出有效内容'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            answer_text = self._generate_answer(device, question_text)
        except Exception as exc:
            return Response({'message': str(exc)[:200]}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'sessionId': str(request.data.get('sessionId') or uuid.uuid4()),
            'requestId': get_request_id(request),
            'traceId': get_trace_id(request),
            'deviceCode': device.code,
            'questionText': question_text,
            'answerText': answer_text,
            'audioBase64': None,
            'audioContentType': 'audio/wav',
        }
        try:
            payload['audioBase64'] = self._synthesize_answer_audio(device, answer_text)
        except Exception as exc:
            payload['ttsError'] = str(exc)[:200]
        return Response(payload, status=status.HTTP_200_OK)

    @staticmethod
    def _request_question_text(request) -> str:
        return str(
            request.data.get('text')
            or request.data.get('questionText')
            or request.data.get('question')
            or ''
        ).strip()

    @staticmethod
    def _request_sample_rate(request):
        raw_sample_rate = request.data.get('sampleRate') or request.data.get('sample_rate') or 16000
        try:
            sample_rate = int(raw_sample_rate)
        except (TypeError, ValueError):
            return None, Response({'message': 'sampleRate 必须是整数'}, status=status.HTTP_400_BAD_REQUEST)
        if sample_rate <= 0 or sample_rate > 48000:
            return None, Response({'message': 'sampleRate 超出支持范围'}, status=status.HTTP_400_BAD_REQUEST)
        return sample_rate, None

    @staticmethod
    def _generate_answer(device: Device, question_text: str) -> str:
        agent_application = device.effective_agent_application
        model = agent_application.llm_model if agent_application is not None else None
        if model is None:
            settings = llm_services.get_tenant_llm_settings(device.tenant)
            model = settings.default_model if settings is not None else None
        if not llm_services.is_llm_model_effective_for_tenant(device.tenant, model):
            raise RuntimeError('请先为设备绑定智能体配置可用 LLM 模型')

        system_prompt = (
            agent_application.system_prompt.strip()
            if agent_application is not None and agent_application.system_prompt.strip()
            else '你是数字人设备的中文语音问答助手。回答要自然、简洁，适合直接转成语音播报。'
        )
        if agent_application is not None:
            system_prompt += f' 当前设备智能体：{agent_application.name}。'
        if device.application is not None:
            system_prompt += f' 当前设备资源应用：{device.application.name}。'
        return llm_services.run_llm_chat_completion(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': question_text},
            ],
            temperature=agent_application.temperature if agent_application is not None else 0.7,
            max_tokens=None if agent_application is not None and agent_application.max_tokens_unlimited else (agent_application.max_tokens if agent_application is not None else 1000),
        )

    @staticmethod
    def _synthesize_answer_audio(device: Device, answer_text: str) -> str:
        provider = tts_services.get_aliyun_tts_provider()
        config = tts_services.get_effective_tts_config(provider)
        voice = tts_services.get_effective_tts_voice_for_tenant(device.tenant, provider)
        if voice is None:
            raise RuntimeError('请先配置默认音色')
        pcm = tts_services.synthesize_tts_pcm(text=answer_text, voice=voice, config=config)
        wav = tts_services.pcm_to_wav(pcm, sample_rate=config.sample_rate)
        return base64.b64encode(wav).decode('ascii')
