from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import LLMProvider

User = get_user_model()


class LLMProviderApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='llm-tester', password='test123456')
        self.role = Role.objects.create(name='LLM测试角色', code='llm_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

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
        self.role.permission_points.set(permission_points)

    def test_list_llm_providers_requires_view_permission(self):
        response = self.client.get('/api/v1/ai-models/llm-providers/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_existing_llm_provider_success(self):
        self.grant_permissions('ai_models.llm.view')
        provider = LLMProvider.objects.create(
            name='OpenAI 主账号',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-key',
            models_config=[{'name': 'gpt-4.1', 'isDefault': True}],
            is_active=True,
        )

        response = self.client.get(f'/api/v1/ai-models/llm-providers/{provider.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], provider.id)
        self.assertEqual(response.data['name'], 'OpenAI 主账号')
        self.assertEqual(response.data['providerType'], 'openai')
        self.assertEqual(response.data['modelsConfig'], [{'name': 'gpt-4.1', 'isDefault': True}])

    def test_test_connection_returns_friendly_message_when_models_missing(self):
        self.grant_permissions('ai_models.llm.view')
        provider = LLMProvider.objects.create(
            name='空模型供应商',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-key',
            models_config=[],
            is_active=True,
        )

        response = self.client.post(f'/api/v1/ai-models/llm-providers/{provider.id}/test-connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                'success': False,
                'message': '该供应商未配置任何模型',
                'latencyMs': 0,
            },
        )
