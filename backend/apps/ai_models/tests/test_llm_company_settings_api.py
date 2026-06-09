from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class LLMCompanySettingsApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.tenant_user = User.objects.create_user(username='company-llm-user', password='test123456')
        self.setup_tenant(self.tenant_user)
        self.role = Role.objects.create(name='Company LLM role', code='company_llm_role')
        UserRole.objects.create(user=self.tenant_user, role=self.role)
        self.provider = self.create_platform_provider()
        self.model = self.create_model(provider=self.provider, name='gpt-4.1')
        self.grant_model(self.model)
        self.settings = self.company_settings(default_model=self.model)

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
    def llm_test_settings_model():
        return apps.get_model('ai_models', 'LLMTestSettings')

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
            'provider': provider or self.provider,
            'display_name': 'GPT 4.1',
            'name': 'gpt-4.1',
            'is_active': True,
        }
        data.update(overrides)
        return LLMModel.objects.create(**data)

    def grant_model(self, model, *, tenant=None, is_active=True):
        Grant = self.tenant_grant_model()
        return Grant.objects.create(tenant=tenant or self.tenant, model=model, is_active=is_active)

    def company_settings(self, *, tenant=None, default_model=None, last_tested_at=None):
        Settings = self.tenant_settings_model()
        return Settings.objects.create(
            tenant=tenant or self.tenant,
            default_model=default_model,
            last_tested_at=last_tested_at,
        )

    def configure_test_settings(self, **overrides):
        Settings = self.llm_test_settings_model()
        data = {
            'test_prompt': 'Say hello in one sentence.',
            'test_timeout_seconds': 10,
            'test_max_tokens': 128,
            'test_cooldown_seconds': 30,
        }
        data.update(overrides)
        return Settings.objects.create(**data)

    def test_company_only_sees_effective_authorized_models_without_secrets(self):
        self.grant_permissions('ai_models.llm.view')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.get('/api/v1/ai-models/llm/options/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('apiKey', str(resp.data))
        self.assertNotIn('apiBaseUrl', str(resp.data))
        self.assertEqual(resp.data['providers'][0]['models'][0]['id'], self.model.id)

    def test_unauthorized_models_are_invisible(self):
        self.grant_permissions('ai_models.llm.view')
        unauthorized_model = self.create_model(name='gpt-4.1-mini', display_name='GPT 4.1 Mini')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.get('/api/v1/ai-models/llm/options/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        model_ids = [
            model['id']
            for provider in resp.data['providers']
            for model in provider['models']
        ]
        self.assertIn(self.model.id, model_ids)
        self.assertNotIn(unauthorized_model.id, model_ids)

    def test_provider_disabled_makes_authorized_model_invisible(self):
        self.grant_permissions('ai_models.llm.view')
        self.provider.is_active = False
        self.provider.save(update_fields=['is_active'])
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.get('/api/v1/ai-models/llm/options/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['providers'], [])

    def test_model_disabled_makes_grant_ineffective(self):
        self.grant_permissions('ai_models.llm.view')
        self.model.is_active = False
        self.model.save(update_fields=['is_active'])
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.get('/api/v1/ai-models/llm/options/')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['providers'], [])

    def test_company_can_set_default_only_to_effective_model(self):
        self.grant_permissions('ai_models.llm.update')
        unauthorized_model = self.create_model(name='gpt-4.1-mini', display_name='GPT 4.1 Mini')
        self.client.force_authenticate(self.tenant_user)

        denied_resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': unauthorized_model.id},
            format='json',
        )
        allowed_resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': self.model.id},
            format='json',
        )

        self.assertEqual(denied_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(allowed_resp.status_code, status.HTTP_200_OK)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.default_model_id, self.model.id)

    def test_company_cannot_set_default_to_granted_model_when_provider_disabled(self):
        self.grant_permissions('ai_models.llm.update')
        disabled_provider = self.create_platform_provider(name='Disabled provider', is_active=False)
        disabled_provider_model = self.create_model(
            provider=disabled_provider,
            name='disabled-provider-model',
            display_name='Disabled Provider Model',
        )
        self.grant_model(disabled_provider_model)
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': disabled_provider_model.id},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('defaultModelId', resp.data)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.default_model_id, self.model.id)

    def test_company_cannot_set_default_to_granted_model_when_model_disabled(self):
        self.grant_permissions('ai_models.llm.update')
        disabled_model = self.create_model(
            name='disabled-model',
            display_name='Disabled Model',
            is_active=False,
        )
        self.grant_model(disabled_model)
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': disabled_model.id},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('defaultModelId', resp.data)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.default_model_id, self.model.id)

    def test_user_with_view_permission_can_test_but_cannot_set_default(self):
        self.grant_permissions('ai_models.llm.view')
        self.configure_test_settings(test_cooldown_seconds=0)
        self.client.force_authenticate(self.tenant_user)

        with patch(
            'apps.ai_models.llm_services.run_llm_model_test',
            return_value={'success': True, 'message': 'ok', 'latencyMs': 12},
        ):
            test_resp = self.client.post(
                f'/api/v1/ai-models/llm/models/{self.model.id}/test/',
                format='json',
            )
        default_resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': self.model.id},
            format='json',
        )

        self.assertEqual(test_resp.status_code, status.HTTP_200_OK)
        self.assertIn('success', test_resp.data)
        self.assertEqual(default_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_update_permission_can_set_default(self):
        self.grant_permissions('ai_models.llm.update')
        self.client.force_authenticate(self.tenant_user)

        resp = self.client.patch(
            '/api/v1/ai-models/llm/default-model/',
            {'defaultModelId': self.model.id},
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.default_model_id, self.model.id)

    def test_test_cooldown_is_enforced_and_configurable(self):
        self.grant_permissions('ai_models.llm.view')
        self.configure_test_settings(test_cooldown_seconds=60)
        self.settings.last_tested_at = timezone.now()
        self.settings.save(update_fields=['last_tested_at'])
        self.client.force_authenticate(self.tenant_user)

        blocked_resp = self.client.post(
            f'/api/v1/ai-models/llm/models/{self.model.id}/test/',
            format='json',
        )

        self.assertEqual(blocked_resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        test_settings = self.llm_test_settings_model().load()
        test_settings.test_cooldown_seconds = 0
        test_settings.save(update_fields=['test_cooldown_seconds'])

        with patch(
            'apps.ai_models.llm_services.run_llm_model_test',
            return_value={'success': True, 'message': 'ok', 'latencyMs': 12},
        ):
            allowed_resp = self.client.post(
                f'/api/v1/ai-models/llm/models/{self.model.id}/test/',
                format='json',
            )

        self.assertEqual(allowed_resp.status_code, status.HTTP_200_OK)
