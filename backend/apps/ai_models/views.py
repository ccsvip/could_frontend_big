import json
import logging
import time

import httpx
from asgiref.sync import sync_to_async
from django.db import connections
from django.db.models import Q
from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    CanViewASR,
    CanCreateChat,
    CanCreateLLMProviders,
    CanDeleteChat,
    CanDeleteLLMProviders,
    CanUpdateLLMProviders,
    CanViewChat,
    CanViewLLMProviders,
    IsSuperUser,
)
from apps.devices.models import Device
from apps.resources.views import PermissionMappedModelViewSet
from apps.tenants.mixins import TenantScopedQuerysetMixin
from apps.tenants.models import Tenant

from .models import ASRReplacementRule, ChatConversation, ChatMessage, LLMProvider
from .realtime_asr import resolve_asr_device_connection
from .serializers import (
    ASRConfigSerializer,
    ASRReplacementRuleSerializer,
    ChatConversationConfigSerializer,
    ChatConversationCreateSerializer,
    ChatConversationDetailSerializer,
    ChatConversationListSerializer,
    ChatMessageSerializer,
    ChatMessageFeedbackSerializer,
    ChatSendSerializer,
    LLMProviderSerializer,
)
from .services.asr import (
    get_effective_asr_config,
    serialize_asr_settings,
    serialize_asr_status,
    test_asr_connection,
)

logger = logging.getLogger(__name__)


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

        device = Device.objects.select_related('tenant', 'application').get(id=connection['device_id'])
        return Response({
            **serialize_asr_status(),
            'deviceCode': device.code,
            'deviceId': device.id,
            'tenantId': device.tenant_id,
            'tenantName': device.tenant.name if device.tenant else '',
            'applicationId': device.application_id,
            'applicationName': device.application.name if device.application else '',
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


def _build_chat_completions_url(raw_url: str) -> str:
    api_url = raw_url.rstrip('/')
    if api_url.endswith('/chat/completions'):
        return api_url
    if api_url.endswith('/openai'):
        return f'{api_url}/v1/chat/completions'
    if api_url.endswith('/v1'):
        return f'{api_url}/chat/completions'
    return f'{api_url}/chat/completions'


def _get_provider_default_model_name(provider: LLMProvider | None) -> str:
    if not provider:
        return ''

    models_config = provider.models_config or []
    default_model = next((m for m in models_config if m.get('isDefault')), None)
    if not default_model and models_config:
        default_model = models_config[0]
    return default_model.get('name', '').strip() if default_model else ''


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
        json={
            'model': model_name,
            'messages': [
                {'role': ChatMessage.ROLE_SYSTEM, 'content': title_prompt},
                {
                    'role': ChatMessage.ROLE_USER,
                    'content': f'用户问题：{user_message}\n助手回答：{assistant_message}',
                },
            ],
            'stream': False,
            'max_tokens': 32,
            'temperature': 0.2,
        },
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
        json={
            'model': model_name,
            'messages': [
                {'role': ChatMessage.ROLE_SYSTEM, 'content': summary_prompt},
                {'role': ChatMessage.ROLE_USER, 'content': f'用户问题：{user_message}\n助手回答：{assistant_message}'},
            ],
            'stream': False,
            'max_tokens': 48,
            'temperature': 0.2,
        },
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


class LLMProviderViewSet(TenantScopedQuerysetMixin, PermissionMappedModelViewSet):
    queryset = LLMProvider.objects.all()
    serializer_class = LLMProviderSerializer
    parser_classes = [MultiPartParser, JSONParser]
    permission_map = {
        'list': [CanViewLLMProviders],
        'retrieve': [CanViewLLMProviders],
        'create': [CanCreateLLMProviders],
        'update': [CanUpdateLLMProviders],
        'partial_update': [CanUpdateLLMProviders],
        'destroy': [CanDeleteLLMProviders],
        'test_connection': [CanViewLLMProviders],
    }

    def get_queryset(self):
        qs = super().get_queryset()
        keyword = self.request.query_params.get('keyword')
        provider_type = self.request.query_params.get('provider_type')
        is_active = self.request.query_params.get('is_active')

        if keyword:
            qs = qs.filter(name__icontains=keyword)
        if provider_type:
            qs = qs.filter(provider_type=provider_type)
        if is_active in ('true', 'false'):
            qs = qs.filter(is_active=is_active == 'true')
        return qs

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        provider = self.get_object()
        models_config = provider.models_config or []
        default_model = next((m for m in models_config if m.get('isDefault')), None)
        if not default_model and models_config:
            default_model = models_config[0]

        if not default_model:
            return Response({
                'success': False,
                'message': '该供应商未配置任何模型',
                'latencyMs': 0,
            })

        model_name = default_model.get('name', '')
        api_url = _build_chat_completions_url(provider.api_base_url)

        payload = {
            'model': model_name,
            'messages': [{'role': 'user', 'content': 'Hi'}],
            'max_tokens': 5,
        }
        headers = {
            'Authorization': f'Bearer {provider.api_key}',
            'Content-Type': 'application/json',
        }

        start = time.time()
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(api_url, json=payload, headers=headers)
            latency = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                return Response({
                    'success': True,
                    'message': '连接成功',
                    'latencyMs': latency,
                })
            else:
                body = resp.text[:200]
                return Response({
                    'success': False,
                    'message': f'HTTP {resp.status_code}: {body}',
                    'latencyMs': latency,
                })
        except httpx.TimeoutException:
            latency = int((time.time() - start) * 1000)
            return Response({
                'success': False,
                'message': '请求超时（15秒）',
                'latencyMs': latency,
            })
        except Exception as exc:
            latency = int((time.time() - start) * 1000)
            return Response({
                'success': False,
                'message': str(exc)[:200],
                'latencyMs': latency,
            })


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
    queryset = ChatConversation.objects.all()
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
        provider_id = serializer.validated_data.get('llmProviderId')
        provider = None
        if provider_id:
            # provider 限定在本租户内，防止绑定到别家公司的供应商。
            provider_qs = LLMProvider.objects.all()
            if tenant is not None:
                provider_qs = provider_qs.for_tenant(tenant)
            provider = provider_qs.filter(pk=provider_id).first()
        conversation = ChatConversation.objects.create(
            title=serializer.validated_data.get('title', '新对话'),
            user=request.user,
            llm_provider=provider,
            model_name=serializer.validated_data.get('modelName', ''),
            summary='',
            system_prompt=serializer.validated_data.get('systemPrompt', ''),
            temperature=serializer.validated_data.get('temperature', 0.7),
            max_tokens=serializer.validated_data.get('max_tokens', 1000),
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

        provider_id = serializer.validated_data.get('llmProviderId')
        provider = None
        if provider_id:
            # 限定在本公司范围内，防止绑定到别家公司的供应商。
            provider = (
                LLMProvider.objects.for_tenant(conversation.tenant)
                .filter(pk=provider_id, is_active=True)
                .first()
            )

        conversation.llm_provider = provider
        conversation.model_name = serializer.validated_data.get('modelName', '')
        conversation.system_prompt = serializer.validated_data.get('systemPrompt', '')
        conversation.temperature = serializer.validated_data.get('temperature', 0.7)
        conversation.max_tokens = serializer.validated_data.get('max_tokens', 1000)
        conversation.save(
            update_fields=['llm_provider', 'model_name', 'system_prompt', 'temperature', 'max_tokens', 'updated_at'],
        )

        logger.info(
            'chat.conversation.config_updated conversation_id=%s user_id=%s provider_id=%s model_name=%s system_prompt_length=%s temperature=%s max_tokens=%s',
            conversation.id,
            request.user.id,
            provider.id if provider else None,
            conversation.model_name or '',
            len(conversation.system_prompt or ''),
            conversation.temperature,
            conversation.max_tokens,
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
            'chat.send.received conversation_id=%s user_id=%s content_length=%s use_stream=%s regenerate_message_id=%s bound_provider_id=%s bound_model_name=%s',
            conversation.id,
            request.user.id,
            len(content),
            use_stream,
            regenerate_message_id,
            conversation.llm_provider_id,
            conversation.model_name or '',
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

        # Resolve provider & model
        provider = conversation.llm_provider
        if not provider or not provider.is_active:
            logger.warning(
                'chat.send.provider_fallback conversation_id=%s user_id=%s previous_provider_id=%s previous_provider_active=%s',
                conversation.id,
                request.user.id,
                conversation.llm_provider_id,
                bool(provider and provider.is_active),
            )
            # 仅在本公司范围内回退；for_tenant(None) 返回空集，绝不跨租户拿别家供应商（含其 API Key）。
            provider = LLMProvider.objects.for_tenant(conversation.tenant).filter(is_active=True).first()

        if not provider:
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.ROLE_ASSISTANT,
                content='暂无可用的 LLM 供应商，请联系管理员配置。',
            )
            return Response({
                'status': 'error',
                'message': '暂无可用的 LLM 供应商',
                'code': 400,
            }, status=status.HTTP_400_BAD_REQUEST)

        model_name = conversation.model_name
        if not model_name:
            model_name = _get_provider_default_model_name(provider)
            logger.info(
                'chat.send.model_defaulted conversation_id=%s user_id=%s provider_id=%s model_name=%s',
                conversation.id,
                request.user.id,
                provider.id,
                model_name,
            )

        if not model_name:
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.ROLE_ASSISTANT,
                content='该供应商未配置任何模型，请先在 LLM 管理中添加模型。',
            )
            return Response({
                'status': 'error',
                'message': '该供应商未配置任何模型',
                'code': 400,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Build messages history
        history_messages = list(
            conversation.messages.order_by('created_at').values_list('role', 'content')
        )
        api_messages = []
        if conversation.system_prompt:
            api_messages.append({'role': ChatMessage.ROLE_SYSTEM, 'content': conversation.system_prompt})
        api_messages.extend({'role': role, 'content': msg} for role, msg in history_messages)

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
                            json={
                                'model': model_name,
                                'messages': api_messages,
                                'stream': False,
                                'temperature': conversation.temperature,
                                'max_tokens': conversation.max_tokens,
                            },
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
                        json={
                            'model': model_name,
                            'messages': api_messages,
                            'stream': True,
                            'temperature': conversation.temperature,
                            'max_tokens': conversation.max_tokens,
                        },
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
