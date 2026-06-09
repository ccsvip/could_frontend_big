from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ChatConversation
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
    def company_grant_model():
        return apps.get_model('ai_models', 'CompanyLLMGrant')

    @staticmethod
    def company_settings_model():
        return apps.get_model('ai_models', 'CompanyLLMSettings')

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
        Grant = self.company_grant_model()
        return Grant.objects.create(tenant=self.tenant, model=model, is_active=is_active)

    def company_settings(self, *, default_model=None):
        Settings = self.company_settings_model()
        return Settings.objects.create(tenant=self.tenant, default_model=default_model)

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
        self.assertIn('defaultModelId', resp.data)

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
            {'modelId': self.other_model.id},
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
                'modelId': self.other_model.id,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('modelId', resp.data)
