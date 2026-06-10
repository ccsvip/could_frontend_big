from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ChatConversation
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class LLMPlatformSettingsApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='platform-admin',
            password='test123456',
            email='admin@example.com',
        )
        self.tenant_user = User.objects.create_user(username='tenant-user', password='test123456')
        self.setup_tenant(self.tenant_user)
        self.role = Role.objects.create(name='LLM tenant role', code='llm_tenant_role')
        UserRole.objects.create(user=self.tenant_user, role=self.role)

    @staticmethod
    def provider_model():
        return apps.get_model('ai_models', 'LLMProvider')

    @staticmethod
    def llm_model_model():
        return apps.get_model('ai_models', 'LLMModel')

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'ai_models_llm',
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
            'provider': provider or self.create_platform_provider(),
            'display_name': 'GPT 4.1',
            'name': 'gpt-4.1',
            'is_active': True,
        }
        data.update(overrides)
        return LLMModel.objects.create(**data)

    def test_superuser_can_create_platform_provider_without_returning_raw_key(self):
        self.client.force_authenticate(self.superuser)

        resp = self.client.post('/api/v1/settings/llm/providers/', {
            'name': 'OpenAI Platform',
            'providerType': 'openai',
            'apiBaseUrl': 'https://api.openai.com/v1',
            'apiKey': 'sk-secret',
            'isActive': True,
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['name'], 'OpenAI Platform')
        self.assertNotIn('sk-secret', str(resp.data))
        self.assertTrue(resp.data['apiKeyConfigured'])
        self.assertTrue(resp.data['apiKeyMasked'].startswith('sk-'))

    def test_superuser_can_create_platform_provider_without_provider_type(self):
        self.client.force_authenticate(self.superuser)

        resp = self.client.post('/api/v1/settings/llm/providers/', {
            'name': 'OpenAI Compatible',
            'apiBaseUrl': 'https://api.compatible.example/v1',
            'apiKey': 'sk-compatible-secret',
            'isActive': True,
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['providerType'], 'openai')
        provider = self.provider_model().objects.get(id=resp.data['id'])
        self.assertEqual(provider.provider_type, 'openai')

    def test_non_superuser_cannot_call_platform_provider_settings(self):
        self.grant_permissions('ai_models.llm.view', 'ai_models.llm.create', 'ai_models.llm.update')
        self.client.force_authenticate(self.tenant_user)

        list_resp = self.client.get('/api/v1/settings/llm/providers/')
        create_resp = self.client.post('/api/v1/settings/llm/providers/', {
            'name': 'Tenant OpenAI',
            'providerType': 'openai',
            'apiBaseUrl': 'https://api.openai.com/v1',
            'apiKey': 'sk-tenant-secret',
            'isActive': True,
        }, format='json')

        self.assertEqual(list_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_create_model_under_provider(self):
        provider = self.create_platform_provider()
        self.client.force_authenticate(self.superuser)

        resp = self.client.post(
            f'/api/v1/settings/llm/providers/{provider.id}/models/',
            {
                'displayName': 'GPT 4.1',
                'name': 'gpt-4.1',
                'contextWindow': 128000,
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['providerId'], provider.id)
        self.assertEqual(resp.data['displayName'], 'GPT 4.1')
        self.assertEqual(resp.data['name'], 'gpt-4.1')
        self.assertTrue(resp.data['isActive'])

    def test_used_model_real_name_cannot_be_changed(self):
        provider = self.create_platform_provider()
        model = self.create_model(provider=provider, name='gpt-4.1')
        ChatConversation.objects.create(
            tenant=self.tenant,
            user=self.tenant_user,
            title='Used model conversation',
            llm_model=model,
        )
        self.client.force_authenticate(self.superuser)

        resp = self.client.patch(
            f'/api/v1/settings/llm/models/{model.id}/',
            {'name': 'gpt-4.1-mini', 'displayName': 'GPT 4.1 Mini'},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        model.refresh_from_db()
        self.assertEqual(model.name, 'gpt-4.1')
        self.assertIn('name', resp.data)

    def test_used_provider_and_model_cannot_be_hard_deleted(self):
        provider = self.create_platform_provider()
        model = self.create_model(provider=provider)
        ChatConversation.objects.create(
            tenant=self.tenant,
            user=self.tenant_user,
            title='Used model conversation',
            llm_model=model,
        )
        self.client.force_authenticate(self.superuser)

        model_resp = self.client.delete(f'/api/v1/settings/llm/models/{model.id}/')
        provider_resp = self.client.delete(f'/api/v1/settings/llm/providers/{provider.id}/')

        self.assertEqual(model_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(provider_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(self.llm_model_model().objects.filter(id=model.id).exists())
        self.assertTrue(self.provider_model().objects.filter(id=provider.id).exists())

    def test_test_settings_validation_rejects_invalid_bounds(self):
        self.client.force_authenticate(self.superuser)
        cases = [
            (
                {'testPrompt': '', 'testTimeoutSeconds': 10, 'testMaxTokens': 128, 'testCooldownSeconds': 30},
                'testPrompt',
            ),
            (
                {'testPrompt': 'x' * 2001, 'testTimeoutSeconds': 10, 'testMaxTokens': 128, 'testCooldownSeconds': 30},
                'testPrompt',
            ),
            (
                {'testPrompt': 'Say hello', 'testTimeoutSeconds': 0, 'testMaxTokens': 128, 'testCooldownSeconds': 30},
                'testTimeoutSeconds',
            ),
            (
                {'testPrompt': 'Say hello', 'testTimeoutSeconds': 61, 'testMaxTokens': 128, 'testCooldownSeconds': 30},
                'testTimeoutSeconds',
            ),
            (
                {'testPrompt': 'Say hello', 'testTimeoutSeconds': 10, 'testMaxTokens': 0, 'testCooldownSeconds': 30},
                'testMaxTokens',
            ),
            (
                {'testPrompt': 'Say hello', 'testTimeoutSeconds': 10, 'testMaxTokens': 513, 'testCooldownSeconds': 30},
                'testMaxTokens',
            ),
        ]

        for payload, field in cases:
            with self.subTest(field=field, payload=payload):
                resp = self.client.patch('/api/v1/settings/llm/test-settings/', payload, format='json')
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, resp.data)
