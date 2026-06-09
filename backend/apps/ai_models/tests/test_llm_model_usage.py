from unittest.mock import MagicMock, patch

from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.llm_services import (
    get_effective_llm_model_for_tenant,
    get_effective_llm_models_for_tenant,
    get_tenant_llm_settings,
    is_llm_model_effective_for_tenant,
    llm_model_has_usage,
    llm_provider_has_usage,
    mask_api_key,
    run_llm_model_test,
    validate_llm_test_settings_values,
)
from apps.ai_models.models import ChatConversation, LLMTestSettings
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class LLMModelUsageTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.tenant_user = User.objects.create_user(username='llm-usage-user', password='test123456')
        self.setup_tenant(self.tenant_user)
        self.role = Role.objects.create(name='LLM usage role', code='llm_usage_role')
        UserRole.objects.create(user=self.tenant_user, role=self.role)
        self.provider = self.create_platform_provider()
        self.default_model = self.create_model(provider=self.provider, name='gpt-4.1')
        self.other_model = self.create_model(provider=self.provider, name='gpt-4.1-mini')
        self.grant_model(self.default_model)
        self.settings = self.company_settings(default_model=self.default_model)

    @staticmethod
    def provider_model():
        return apps.get_model('ai_models', 'LLMProvider')

    @staticmethod
    def llm_model_model():
        return apps.get_model('ai_models', 'LLMModel')

    @staticmethod
    def tenant_grant_model():
        return apps.get_model('ai_models', 'TenantLLMModelGrant')

    @staticmethod
    def tenant_settings_model():
        return apps.get_model('ai_models', 'TenantLLMSettings')

    @staticmethod
    def agent_application_model():
        return apps.get_model('ai_models', 'AgentApplication')

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
        self.grant_all_scope_to_tenant()
        self.role.permission_points.set(permission_points)

    def create_platform_provider(self, **overrides):
        Provider = self.provider_model()
        data = {
            'name': 'OpenAI Platform',
            'provider_type': 'openai',
            'api_base_url': 'https://api.openai.com/v1',
            'api_key': 'sk-secret',
            'is_active': True,
        }
        data.update(overrides)
        return Provider.objects.create(**data)

    def create_model(self, provider=None, **overrides):
        LLMModel = self.llm_model_model()
        data = {
            'provider': provider or self.provider,
            'display_name': 'GPT 4.1',
            'name': 'gpt-4.1',
            'is_active': True,
        }
        data.update(overrides)
        return LLMModel.objects.create(**data)

    def grant_model(self, model, *, is_active=True):
        Grant = self.tenant_grant_model()
        return Grant.objects.create(tenant=self.tenant, model=model, is_active=is_active)

    def company_settings(self, *, default_model=None):
        Settings = self.tenant_settings_model()
        return Settings.objects.create(tenant=self.tenant, default_model=default_model)

    def test_mask_api_key_keeps_only_safe_edges(self):
        self.assertEqual(mask_api_key(''), '')
        self.assertEqual(mask_api_key('shortkey'), '****')
        self.assertEqual(mask_api_key('sk-1234567890'), 'sk-...7890')

    def test_effective_models_include_only_active_granted_models_for_tenant(self):
        inactive_provider = self.create_platform_provider(name='Inactive Provider', is_active=False)
        inactive_provider_model = self.create_model(provider=inactive_provider, name='inactive-provider-model')
        inactive_model = self.create_model(provider=self.provider, name='inactive-model', is_active=False)
        inactive_grant_model = self.create_model(provider=self.provider, name='inactive-grant-model')
        self.grant_model(inactive_provider_model)
        self.grant_model(inactive_model)
        self.grant_model(inactive_grant_model, is_active=False)

        effective_ids = list(get_effective_llm_models_for_tenant(self.tenant).values_list('id', flat=True))

        self.assertEqual(effective_ids, [self.default_model.id])
        self.assertEqual(get_effective_llm_model_for_tenant(self.tenant, self.default_model.id), self.default_model)
        self.assertIsNone(get_effective_llm_model_for_tenant(self.tenant, self.other_model.id))
        self.assertFalse(get_effective_llm_models_for_tenant(None).exists())

    def test_tenant_settings_service_creates_company_settings_once(self):
        self.settings.delete()

        created = get_tenant_llm_settings(self.tenant)
        loaded = get_tenant_llm_settings(self.tenant)

        self.assertEqual(created, loaded)
        self.assertIsNone(created.default_model)
        self.assertIsNone(get_tenant_llm_settings(None))

    def test_llm_model_effective_service_returns_boolean(self):
        self.assertTrue(is_llm_model_effective_for_tenant(self.tenant, self.default_model))
        self.assertFalse(is_llm_model_effective_for_tenant(self.tenant, self.other_model))
        self.assertFalse(is_llm_model_effective_for_tenant(None, self.default_model))
        self.assertFalse(is_llm_model_effective_for_tenant(self.tenant, None))

    def test_usage_helpers_detect_model_and_provider_references(self):
        unused_provider = self.create_platform_provider(name='Unused Provider')
        unused_model = self.create_model(provider=unused_provider, name='unused-model')

        self.assertTrue(llm_model_has_usage(self.default_model))
        self.assertFalse(llm_model_has_usage(unused_model))
        self.assertFalse(llm_model_has_usage(None))
        self.assertTrue(llm_provider_has_usage(self.provider))
        self.assertFalse(llm_provider_has_usage(unused_provider))
        self.assertFalse(llm_provider_has_usage(None))

    def test_validate_llm_test_settings_values_rejects_out_of_range_values(self):
        validate_llm_test_settings_values(
            prompt='连接测试',
            cooldown=0,
            timeout=1,
            max_tokens=1,
        )

        invalid_cases = [
            ({'prompt': '   ', 'cooldown': 0, 'timeout': 1, 'max_tokens': 1}, 'testPrompt'),
            ({'prompt': 'x' * 2001, 'cooldown': 0, 'timeout': 1, 'max_tokens': 1}, 'testPrompt'),
            ({'prompt': '连接测试', 'cooldown': 3601, 'timeout': 1, 'max_tokens': 1}, 'testCooldownSeconds'),
            ({'prompt': '连接测试', 'cooldown': 0, 'timeout': 0, 'max_tokens': 1}, 'testTimeoutSeconds'),
            ({'prompt': '连接测试', 'cooldown': 0, 'timeout': 1, 'max_tokens': 513}, 'testMaxTokens'),
        ]
        for values, field in invalid_cases:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as ctx:
                    validate_llm_test_settings_values(**values)
                self.assertIn(field, ctx.exception.detail)

    def test_llm_test_settings_load_uses_singleton_row(self):
        first = LLMTestSettings.load()
        second = LLMTestSettings.load()

        self.assertEqual(first.pk, 1)
        self.assertEqual(first, second)

    @patch('apps.ai_models.llm_services.httpx.Client')
    def test_run_llm_model_test_posts_safe_openai_compatible_request(self, mock_client_class):
        settings = LLMTestSettings(
            test_prompt='请回复连接成功',
            test_timeout_seconds=7,
            test_max_tokens=12,
        )
        response = MagicMock(status_code=200)
        client = mock_client_class.return_value.__enter__.return_value
        client.post.return_value = response

        result = run_llm_model_test(model=self.default_model, settings=settings)

        self.assertTrue(result['success'])
        self.assertEqual(result['message'], '连接成功')
        self.assertIsInstance(result['latencyMs'], int)
        self.assertIn('testedAt', result)
        mock_client_class.assert_called_once_with(timeout=7)
        client.post.assert_called_once()
        api_url = client.post.call_args.args[0]
        self.assertEqual(api_url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(client.post.call_args.kwargs['json'], {
            'model': 'gpt-4.1',
            'messages': [{'role': 'user', 'content': '请回复连接成功'}],
            'stream': False,
            'temperature': 0,
            'max_tokens': 12,
        })
        self.assertEqual(client.post.call_args.kwargs['headers']['Authorization'], 'Bearer sk-secret')
        self.assertNotIn('sk-secret', str(result))
        self.assertNotIn('https://api.openai.com', str(result))

    @patch('apps.ai_models.llm_services.httpx.Client')
    def test_run_llm_model_test_returns_safe_failure_summary(self, mock_client_class):
        settings = LLMTestSettings(
            test_prompt='请回复连接成功',
            test_timeout_seconds=7,
            test_max_tokens=12,
        )
        response = MagicMock(status_code=401)
        client = mock_client_class.return_value.__enter__.return_value
        client.post.return_value = response

        result = run_llm_model_test(model=self.default_model, settings=settings)

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], '连接失败 (HTTP 401)')
        self.assertIsInstance(result['latencyMs'], int)
        self.assertIn('testedAt', result)
        self.assertNotIn('sk-secret', str(result))
        self.assertNotIn('https://api.openai.com', str(result))

    @patch('apps.ai_models.llm_services.LLMTestSettings.load')
    @patch('apps.ai_models.llm_services.httpx.Client')
    def test_run_llm_model_test_loads_global_settings_when_none(self, mock_client_class, mock_load):
        mock_load.return_value = LLMTestSettings(
            test_prompt='全局连接测试',
            test_timeout_seconds=5,
            test_max_tokens=8,
        )
        response = MagicMock(status_code=200)
        client = mock_client_class.return_value.__enter__.return_value
        client.post.return_value = response

        result = run_llm_model_test(model=self.default_model, settings=None)

        self.assertTrue(result['success'])
        mock_load.assert_called_once_with()
        mock_client_class.assert_called_once_with(timeout=5)
        self.assertEqual(client.post.call_args.kwargs['json']['messages'], [
            {'role': 'user', 'content': '全局连接测试'},
        ])
        self.assertEqual(client.post.call_args.kwargs['json']['max_tokens'], 8)

    def test_chat_creation_snapshots_company_default_model(self):
        self.grant_permissions('ai_models.chat.create')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.post('/api/v1/ai-models/chat/conversations/', {'title': '新对话'}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        conversation = ChatConversation.objects.get(id=resp.data['id'])
        self.assertEqual(conversation.llm_model_id, self.default_model.id)

    def test_no_explicit_model_and_no_company_default_returns_400(self):
        self.grant_permissions('ai_models.chat.create')
        self.settings.default_model = None
        self.settings.save(update_fields=['default_model'])
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.post('/api/v1/ai-models/chat/conversations/', {'title': '新对话'}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('llmModelId', resp.data)

    def test_update_chat_config_rejects_unauthorized_model(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            user=self.tenant_user,
            title='Configured conversation',
            llm_model=self.default_model,
        )
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.patch(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/update-config/',
            {'llmModelId': self.other_model.id},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        conversation.refresh_from_db()
        self.assertEqual(conversation.llm_model_id, self.default_model.id)

    def test_send_rejects_disabled_or_unauthorized_bound_model_without_fallback(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.create')
        disabled_model = self.create_model(provider=self.provider, name='disabled-model', is_active=False)
        self.grant_model(disabled_model)
        conversation = ChatConversation.objects.create(
            tenant=self.tenant,
            user=self.tenant_user,
            title='Disabled model conversation',
            llm_model=disabled_model,
        )
        self.client.force_authenticate(self.tenant_user)

        disabled_resp = self.client.post(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
            {'content': '你好', 'stream': False},
            format='json',
        )

        self.assertEqual(disabled_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('LLM 模型不可用', disabled_resp.data['message'])
        conversation.refresh_from_db()
        self.assertEqual(conversation.llm_model_id, disabled_model.id)

        conversation.llm_model = self.other_model
        conversation.save(update_fields=['llm_model'])
        unauthorized_resp = self.client.post(
            f'/api/v1/ai-models/chat/conversations/{conversation.id}/send/',
            {'content': '你好', 'stream': False},
            format='json',
        )

        self.assertEqual(unauthorized_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('LLM 模型不可用', unauthorized_resp.data['message'])
        conversation.refresh_from_db()
        self.assertEqual(conversation.llm_model_id, self.other_model.id)

    def test_application_creation_snapshots_company_default_model(self):
        self.grant_permissions('agent_applications.create')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Default model app',
                'description': 'Uses company default model',
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        application = self.agent_application_model().objects.get(id=resp.data['id'])
        self.assertEqual(application.llm_model_id, self.default_model.id)

    def test_application_model_selection_rejects_unauthorized_model(self):
        self.grant_permissions('agent_applications.create')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Unsafe app',
                'llmModelId': self.other_model.id,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('llmModelId', resp.data)
