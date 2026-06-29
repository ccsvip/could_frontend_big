import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Menu, PermissionPoint, Role, UserRole
from apps.ai_models.models import AgentAnnotation, AgentApplication, ChatConversation, ChatMessage, LLMModel, LLMProvider, TenantLLMModelGrant
from apps.ai_models.views import _build_chat_completions_url, _build_llm_request_payload
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


def _read_streaming_body(response) -> str:
    """Drain an async StreamingHttpResponse into a single decoded string.

    The chat ``send`` endpoint returns a ``StreamingHttpResponse`` wrapping an
    ``async`` generator, so ``streaming_content`` is an async generator and
    cannot be iterated synchronously. We consume it via ``async_to_sync`` so
    the generator body (which also persists assistant messages / title /
    summary) actually runs.
    """

    async def _drain():
        return [chunk async for chunk in response.streaming_content]

    chunks = async_to_sync(_drain)()
    return ''.join(
        chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
        for chunk in chunks
    )


def _sse_content(streamed_body: str) -> str:
    """解析 SSE ``data:`` 行，拼接解码后的 ``content`` 字段。

    视图用 json.dumps 默认 ensure_ascii=True 输出，中文在 wire 上是 \\uXXXX 转义
    （前端 JSON.parse 后等价于原文，不影响功能）。故按语义比对：json.loads 解码
    回真中文再断言，而不是断言转义后的 wire 字节。只取 content 字段，忽略
    title/summary/[DONE]。
    """
    parts = []
    for line in streamed_body.splitlines():
        line = line.strip()
        if not line.startswith('data:'):
            continue
        payload = line[len('data:'):].strip()
        if payload == '[DONE]':
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get('content'), str):
            parts.append(obj['content'])
    return ''.join(parts)


class ChatAccessDataTests(TestCase):
    def test_standalone_chat_room_menu_is_not_seeded(self):
        self.assertFalse(Menu.objects.filter(key='/ai-models/chat').exists())
        self.assertFalse(Menu.objects.filter(path='/ai-models/chat').exists())


class _DummyStreamResponse:
    def __init__(self, lines, status_code=200, headers=None):
        self._lines = lines
        self.status_code = status_code
        self.headers = headers or {'content-type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        yield from self._lines

    def iter_text(self):
        yield from self._lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return ''.join(self._lines).encode('utf-8')


class _DummyJsonResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {'content-type': 'application/json'}
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _DummyHttpxClient:
    def __init__(self, stream_response=None, post_response=None):
        self._stream_response = stream_response
        self._post_responses = (
            post_response if isinstance(post_response, list) else [post_response] if post_response is not None else []
        )
        self.post_calls = []
        self.stream_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        self.stream_calls.append((args, kwargs))
        return self._stream_response

    async def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        if not self._post_responses:
            return None
        return self._post_responses.pop(0)


class ChatApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chat-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='聊天测试角色', code='chat_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'ai_models_chat',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def create_provider(self, **overrides) -> LLMProvider:
        data = {
            'name': 'OpenAI compatible',
            'provider_type': 'openai',
            'api_base_url': 'https://api.openai.com/v1',
            'api_key': 'secret-key',
            'is_active': True,
        }
        data.update(overrides)
        return LLMProvider.objects.create(**data)

    def create_model(self, provider: LLMProvider, **overrides) -> LLMModel:
        data = {
            'provider': provider,
            'name': 'gpt-4.1',
            'display_name': 'GPT 4.1',
            'is_active': True,
        }
        data.update(overrides)
        return LLMModel.objects.create(**data)

    def grant_model(self, model: LLMModel):
        return TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)

    def test_build_chat_completions_url_normalizes_longcat_style_base_url(self):
        self.assertEqual(
            _build_chat_completions_url('https://api.longcat.chat/openai'),
            'https://api.longcat.chat/openai/v1/chat/completions',
        )
        self.assertEqual(
            _build_chat_completions_url('https://api.longcat.chat/openai/v1'),
            'https://api.longcat.chat/openai/v1/chat/completions',
        )
        self.assertEqual(
            _build_chat_completions_url('https://api.longcat.chat/openai/v1/chat/completions'),
            'https://api.longcat.chat/openai/v1/chat/completions',
        )

    def test_build_llm_request_payload_adds_search_param_only_when_enabled(self):
        base_payload = _build_llm_request_payload(
            model_name='qwen-plus',
            messages=[{'role': 'user', 'content': '你好'}],
            stream=False,
            temperature=0.7,
            max_tokens=1000,
            max_tokens_unlimited=False,
        )
        search_payload = _build_llm_request_payload(
            model_name='qwen-plus',
            messages=[{'role': 'user', 'content': '你好'}],
            stream=False,
            temperature=0.7,
            max_tokens=1000,
            max_tokens_unlimited=False,
            enable_web_search=True,
        )

        self.assertNotIn('enable_search', base_payload)
        self.assertTrue(search_payload['enable_search'])

    def test_update_config_updates_selected_provider_and_model(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider_a = self.create_provider(name='默认 OpenAI', api_key='secret-a')
        model_a = self.create_model(provider_a, name='gpt-4.1', display_name='GPT 4.1')
        self.grant_model(model_a)
        provider_b = self.create_provider(
            name='兼容供应商',
            provider_type='other',
            api_base_url='https://example.com/v1',
            api_key='secret-b',
        )
        model_b = self.create_model(provider_b, name='chat-model-pro', display_name='Chat Model Pro')
        self.grant_model(model_b)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='测试会话',
            user=self.user,
            llm_model=model_a,
        )

        response = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/update-config/',
            {
                'llmModelId': model_b.id,
                'systemPrompt': '请用更正式的语气回复',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation.refresh_from_db()
        self.assertEqual(conversation.llm_model_id, model_b.id)
        self.assertEqual(conversation.system_prompt, '请用更正式的语气回复')
        self.assertEqual(response.data['llmModelId'], model_b.id)
        self.assertEqual(response.data['llmModelName'], 'chat-model-pro')
        self.assertEqual(response.data['llmProviderName'], provider_b.name)
        self.assertEqual(response.data['systemPrompt'], '请用更正式的语气回复')

    def test_update_config_supports_unlimited_max_tokens(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = self.create_provider()
        model = self.create_model(provider)
        self.grant_model(model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='测试会话',
            user=self.user,
            llm_model=model,
            max_tokens=1000,
            max_tokens_unlimited=False,
        )

        response = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/update-config/',
            {
                'maxTokens': 500000,
                'maxTokensUnlimited': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation.refresh_from_db()
        self.assertEqual(conversation.max_tokens, 500000)
        self.assertTrue(conversation.max_tokens_unlimited)
        self.assertEqual(response.data['maxTokens'], 500000)
        self.assertTrue(response.data['maxTokensUnlimited'])

    def test_send_accepts_openai_compatible_non_stream_json_response(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = self.create_provider(
            name='标准兼容模式',
        )
        model = self.create_model(provider, name='gpt-4.1')
        self.grant_model(model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='兼容模式测试',
            user=self.user,
            llm_model=model,
            max_tokens_unlimited=True,
        )
        plain_json_response = json.dumps(
            {
                'id': 'chatcmpl-123',
                'object': 'chat.completion',
                'choices': [
                    {
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': '这是兼容模式返回的完整回复',
                        },
                    }
                ],
            }
        )
        summary_payload = {
            'choices': [{'message': {'role': 'assistant', 'content': '兼容模式自动摘要'}}]
        }

        dummy_client = _DummyHttpxClient(
            _DummyStreamResponse([plain_json_response]),
            post_response=_DummyJsonResponse(summary_payload),
        )
        with patch('apps.ai_models.views.httpx.AsyncClient', return_value=dummy_client):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好'},
                format='json',
            )
            streamed_body = _read_streaming_body(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('这是兼容模式返回的完整回复', _sse_content(streamed_body))
        self.assertNotIn('max_tokens', dummy_client.stream_calls[0][1]['json'])

        messages = list(conversation.messages.order_by('created_at').values_list('role', 'content'))
        self.assertEqual(
            messages,
            [
                (ChatMessage.ROLE_USER, '你好'),
                (ChatMessage.ROLE_ASSISTANT, '这是兼容模式返回的完整回复'),
            ],
        )

    def test_send_accepts_sse_lines_without_space_after_data_prefix(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = self.create_provider(
            name='LongCat 流式',
            api_base_url='https://api.longcat.chat/openai/v1',
        )
        model = self.create_model(provider, name='LongCat-Flash-Chat', display_name='LongCat Flash Chat')
        self.grant_model(model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='LongCat 流式测试',
            user=self.user,
            llm_model=model,
            max_tokens_unlimited=True,
        )

        sse_lines = [
            'data:{"choices":[{"delta":{"role":"assistant","content":""},"index":0}]}',
            'data:{"choices":[{"delta":{"content":"你好"},"index":0}]}',
            'data:{"choices":[{"delta":{"content":"！"},"index":0}]}',
            'data:[DONE]',
        ]
        summary_payload = {
            'choices': [{'message': {'role': 'assistant', 'content': 'LongCat 流式自动摘要'}}]
        }

        dummy_client = _DummyHttpxClient(
            _DummyStreamResponse(sse_lines, headers={'content-type': 'text/event-stream'}),
            post_response=_DummyJsonResponse(summary_payload),
        )
        with patch('apps.ai_models.views.httpx.AsyncClient', return_value=dummy_client):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好'},
                format='json',
            )
            streamed_body = _read_streaming_body(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 语义断言：LongCat 的无空格 data:{...} chunk 必须被正确解析、不被丢弃，
        # 拼接出完整回复「你好！」（wire 上中文是 \uXXXX 转义，前端 JSON.parse 后等价）。
        self.assertEqual(_sse_content(streamed_body), '你好！')
        self.assertNotIn('max_tokens', dummy_client.stream_calls[0][1]['json'])

        messages = list(conversation.messages.order_by('created_at').values_list('role', 'content'))
        self.assertEqual(
            messages,
            [
                (ChatMessage.ROLE_USER, '你好'),
                (ChatMessage.ROLE_ASSISTANT, '你好！'),
            ],
        )

    def test_send_can_request_non_stream_mode(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = self.create_provider(
            name='LongCat 非流式',
            api_base_url='https://api.longcat.chat/openai',
        )
        model = self.create_model(provider, name='LongCat-Flash-Chat', display_name='LongCat Flash Chat')
        self.grant_model(model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='LongCat 非流式测试',
            user=self.user,
            llm_model=model,
            max_tokens_unlimited=True,
        )
        payload = {
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': '这是关闭流式后的完整回答',
                    },
                }
            ],
        }
        summary_payload = {
            'choices': [{'message': {'role': 'assistant', 'content': '非流式自动摘要'}}]
        }

        dummy_client = _DummyHttpxClient(
            post_response=[_DummyJsonResponse(payload), _DummyJsonResponse(summary_payload)],
        )
        with patch('apps.ai_models.views.httpx.AsyncClient', return_value=dummy_client):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好', 'stream': False},
                format='json',
            )
            streamed_body = _read_streaming_body(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('这是关闭流式后的完整回答', _sse_content(streamed_body))
        self.assertNotIn('max_tokens', dummy_client.post_calls[0][1]['json'])

        messages = list(conversation.messages.order_by('created_at').values_list('role', 'content'))
        self.assertEqual(
            messages,
            [
                (ChatMessage.ROLE_USER, '你好'),
                (ChatMessage.ROLE_ASSISTANT, '这是关闭流式后的完整回答'),
            ],
        )

    def test_send_generates_title_with_current_model_after_first_reply(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = self.create_provider(
            name='标题生成模型',
            api_base_url='https://api.longcat.chat/openai/v1',
        )
        model = self.create_model(provider, name='LongCat-Flash-Chat', display_name='LongCat Flash Chat')
        self.grant_model(model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='新对话',
            user=self.user,
            llm_model=model,
        )
        sse_lines = [
            'data:{"choices":[{"delta":{"content":"这是"},"index":0}]}',
            'data:{"choices":[{"delta":{"content":"关于数据库选型的建议"},"index":0}]}',
            'data:[DONE]',
        ]
        title_payload = {
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': '数据库选型建议',
                    },
                }
            ],
        }
        summary_payload = {
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': '比较 MySQL 与 PostgreSQL 的选型差异',
                    },
                }
            ],
        }

        with patch(
            'apps.ai_models.views.httpx.AsyncClient',
            return_value=_DummyHttpxClient(
                stream_response=_DummyStreamResponse(sse_lines, headers={'content-type': 'text/event-stream'}),
                post_response=[_DummyJsonResponse(title_payload), _DummyJsonResponse(summary_payload)],
            ),
        ):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '帮我比较 MySQL 和 PostgreSQL'},
                format='json',
            )
            # Drive the async streaming generator so its body runs: it persists the
            # assistant reply and then generates+writes the title and summary.
            _read_streaming_body(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, '数据库选型建议')
        self.assertEqual(conversation.summary, '比较 MySQL 与 PostgreSQL 的选型差异')

    def test_update_feedback_updates_latest_assistant_feedback(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='反馈测试',
            user=self.user,
        )
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.ROLE_ASSISTANT,
            content='一条助手回复',
        )

        response = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/messages/{assistant_message.id}/feedback/',
            {'feedback': ChatMessage.FEEDBACK_UP},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assistant_message.refresh_from_db()
        self.assertEqual(assistant_message.feedback, ChatMessage.FEEDBACK_UP)

    def test_send_returns_annotation_without_calling_model(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='标注客服',
        )
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            title='标注命中测试',
            user=self.user,
            application=application,
        )
        annotation = AgentAnnotation.objects.create(
            tenant=self.tenant,
            application=application,
            question='营业时间？',
            answer='我们的服务时间为周一至周五 09:00 - 18:00。',
        )

        with patch('apps.ai_models.views.httpx.AsyncClient') as client_mock:
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '营业时间。'},
                format='json',
            )
            streamed_body = _read_streaming_body(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(_sse_content(streamed_body), '我们的服务时间为周一至周五 09:00 - 18:00。')
        client_mock.assert_not_called()
        annotation.refresh_from_db()
        self.assertEqual(annotation.hit_count, 1)
        messages = list(conversation.messages.order_by('created_at').values_list('role', 'content'))
        self.assertEqual(
            messages,
            [
                (ChatMessage.ROLE_USER, '营业时间。'),
                (ChatMessage.ROLE_ASSISTANT, '我们的服务时间为周一至周五 09:00 - 18:00。'),
            ],
        )
