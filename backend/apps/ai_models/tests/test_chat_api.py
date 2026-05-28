import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ChatConversation, ChatMessage, LLMProvider
from apps.ai_models.views import _build_chat_completions_url

User = get_user_model()


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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        return self._stream_response

    async def post(self, *args, **kwargs):
        if not self._post_responses:
            return None
        return self._post_responses.pop(0)


class ChatApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chat-tester', password='test123456')
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

    def test_update_config_updates_selected_provider_and_model(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider_a = LLMProvider.objects.create(
            name='默认 OpenAI',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-a',
            models_config=[{'name': 'gpt-4.1', 'isDefault': True}],
            is_active=True,
        )
        provider_b = LLMProvider.objects.create(
            name='兼容供应商',
            provider_type='other',
            api_base_url='https://example.com/v1',
            api_key='secret-b',
            models_config=[{'name': 'chat-model-pro', 'isDefault': True}],
            is_active=True,
        )
        conversation = ChatConversation.objects.create(
            title='测试会话',
            user=self.user,
            llm_provider=provider_a,
            model_name='gpt-4.1',
        )

        response = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/update-config/',
            {
                'llmProviderId': provider_b.id,
                'modelName': 'chat-model-pro',
                'systemPrompt': '请用更正式的语气回复',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation.refresh_from_db()
        self.assertEqual(conversation.llm_provider_id, provider_b.id)
        self.assertEqual(conversation.model_name, 'chat-model-pro')
        self.assertEqual(conversation.system_prompt, '请用更正式的语气回复')
        self.assertEqual(response.data['llmProviderId'], provider_b.id)
        self.assertEqual(response.data['modelName'], 'chat-model-pro')
        self.assertEqual(response.data['systemPrompt'], '请用更正式的语气回复')

    def test_send_accepts_openai_compatible_non_stream_json_response(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        provider = LLMProvider.objects.create(
            name='标准兼容模式',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-key',
            models_config=[{'name': 'gpt-4.1', 'isDefault': True}],
            is_active=True,
        )
        conversation = ChatConversation.objects.create(
            title='兼容模式测试',
            user=self.user,
            llm_provider=provider,
            model_name='gpt-4.1',
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

        with patch(
            'apps.ai_models.views.httpx.Client',
            return_value=_DummyHttpxClient(_DummyStreamResponse([plain_json_response])),
        ):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        streamed_body = ''.join(
            chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        self.assertIn('这是兼容模式返回的完整回复', streamed_body)

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
        provider = LLMProvider.objects.create(
            name='LongCat 流式',
            provider_type='openai',
            api_base_url='https://api.longcat.chat/openai/v1',
            api_key='secret-key',
            models_config=[{'name': 'LongCat-Flash-Chat', 'isDefault': True}],
            is_active=True,
        )
        conversation = ChatConversation.objects.create(
            title='LongCat 流式测试',
            user=self.user,
            llm_provider=provider,
            model_name='LongCat-Flash-Chat',
        )

        sse_lines = [
            'data:{"choices":[{"delta":{"role":"assistant","content":""},"index":0}]}',
            'data:{"choices":[{"delta":{"content":"你好"},"index":0}]}',
            'data:{"choices":[{"delta":{"content":"！"},"index":0}]}',
            'data:[DONE]',
        ]

        with patch(
            'apps.ai_models.views.httpx.Client',
            return_value=_DummyHttpxClient(_DummyStreamResponse(sse_lines, headers={'content-type': 'text/event-stream'})),
        ):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        streamed_body = ''.join(
            chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        self.assertIn('data: {"content": "你好"}', streamed_body)
        self.assertIn('data: {"content": "\\uff01"}', streamed_body)

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
        provider = LLMProvider.objects.create(
            name='LongCat 非流式',
            provider_type='openai',
            api_base_url='https://api.longcat.chat/openai',
            api_key='secret-key',
            models_config=[{'name': 'LongCat-Flash-Chat', 'isDefault': True}],
            is_active=True,
        )
        conversation = ChatConversation.objects.create(
            title='LongCat 非流式测试',
            user=self.user,
            llm_provider=provider,
            model_name='LongCat-Flash-Chat',
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

        with patch(
            'apps.ai_models.views.httpx.Client',
            return_value=_DummyHttpxClient(post_response=_DummyJsonResponse(payload)),
        ):
            response = self.client.post(
                f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
                {'content': '你好', 'stream': False},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        streamed_body = ''.join(
            chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        self.assertIn('这是关闭流式后的完整回答', streamed_body)

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
        provider = LLMProvider.objects.create(
            name='标题生成模型',
            provider_type='openai',
            api_base_url='https://api.longcat.chat/openai/v1',
            api_key='secret-key',
            models_config=[{'name': 'LongCat-Flash-Chat', 'isDefault': True}],
            is_active=True,
        )
        conversation = ChatConversation.objects.create(
            title='新对话',
            user=self.user,
            llm_provider=provider,
            model_name='LongCat-Flash-Chat',
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, '数据库选型建议')
        self.assertEqual(conversation.summary, '比较 MySQL 与 PostgreSQL 的选型差异')

    def test_update_feedback_updates_latest_assistant_feedback(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        conversation = ChatConversation.objects.create(
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
