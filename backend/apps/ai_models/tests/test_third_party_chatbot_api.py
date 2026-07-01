from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()
HUAPENG_APPLICATION_ID = '8d697146-f9a2-11ef-89c4-86dcb2923f74'


class ThirdPartyChatbotApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='third-party-platform-admin',
            password='test123456',
            email='third-party-admin@example.com',
        )
        self.tenant_user = User.objects.create_user(username='third-party-tenant-user', password='test123456')
        self.setup_tenant(self.tenant_user)
        self.role = Role.objects.create(name='Third-party tenant role', code='third_party_tenant_role')
        UserRole.objects.create(user=self.tenant_user, role=self.role)

    @staticmethod
    def provider_model():
        return apps.get_model('ai_models', 'ThirdPartyChatbotProvider')

    @staticmethod
    def chatbot_model():
        return apps.get_model('ai_models', 'ThirdPartyChatbotApplication')

    @staticmethod
    def grant_model():
        return apps.get_model('ai_models', 'TenantThirdPartyChatbotGrant')

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'agent_applications',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def create_chatbot(self, *, name='华鹏展厅机器人', tenant=None, is_active=True):
        provider = self.provider_model().objects.create(
            name='华鹏 AI',
            provider_type='ihuapeng_chatbot',
            api_base_url='https://ai.ihuapeng.cn/api',
            api_key='application-key',
            is_active=True,
        )
        chatbot = self.chatbot_model().objects.create(
            provider=provider,
            name=name,
            external_application_id=HUAPENG_APPLICATION_ID,
            is_active=is_active,
        )
        if tenant is not None:
            self.grant_model().objects.create(tenant=tenant, chatbot=chatbot, is_active=True)
        return chatbot

    def test_superuser_configures_chatbot_and_binds_it_to_one_company(self):
        self.client.force_authenticate(self.superuser)

        provider_resp = self.client.post(
            '/api/v1/settings/third-party-chatbots/providers/',
            {
                'name': '华鹏 AI',
                'providerType': 'ihuapeng_chatbot',
                'apiBaseUrl': 'https://ai.ihuapeng.cn/api',
                'apiKey': '`application-key`',
                'isActive': True,
            },
            format='json',
        )
        self.assertEqual(provider_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(provider_resp.data['apiKeyConfigured'])
        self.assertNotIn('application-key', str(provider_resp.data))
        provider = self.provider_model().objects.get(pk=provider_resp.data['id'])
        self.assertEqual(provider.api_key, 'application-key')

        chatbot_resp = self.client.post(
            '/api/v1/settings/third-party-chatbots/applications/',
            {
                'providerId': provider_resp.data['id'],
                'name': '华鹏展厅机器人',
                'externalApplicationId': HUAPENG_APPLICATION_ID,
                'isActive': True,
            },
            format='json',
        )
        self.assertEqual(chatbot_resp.status_code, status.HTTP_201_CREATED)

        grant_resp = self.client.put(
            f'/api/v1/settings/third-party-chatbots/tenants/{self.tenant.id}/authorization/',
            {
                'chatbotGrants': [
                    {'chatbotId': chatbot_resp.data['id'], 'isActive': True},
                ],
            },
            format='json',
        )
        self.assertEqual(grant_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(grant_resp.data['chatbots'][0]['grantIsActive'], True)

    def test_provider_rejects_bearer_prefixed_api_key(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.post(
            '/api/v1/settings/third-party-chatbots/providers/',
            {
                'name': '华鹏 AI',
                'providerType': 'ihuapeng_chatbot',
                'apiBaseUrl': 'https://ai.ihuapeng.cn/api',
                'apiKey': 'Bearer application-key',
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Bearer', str(response.data))

    def test_ihuapeng_application_requires_uuid_external_application_id(self):
        self.client.force_authenticate(self.superuser)
        provider = self.provider_model().objects.create(
            name='华鹏 AI',
            provider_type='ihuapeng_chatbot',
            api_base_url='https://ai.ihuapeng.cn/api',
            api_key='application-key',
            is_active=True,
        )

        response = self.client.post(
            '/api/v1/settings/third-party-chatbots/applications/',
            {
                'providerId': provider.id,
                'name': '售前',
                'externalApplicationId': '售前AI助手',
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('UUID', str(response.data))

    def test_company_only_sees_company_bound_third_party_chatbots(self):
        granted = self.create_chatbot(name='本公司机器人', tenant=self.tenant)
        other_tenant = Tenant.objects.create(name='Other company', code='other-company')
        hidden = self.create_chatbot(name='其他公司机器人', tenant=other_tenant)
        self.grant_permissions('agent_applications.view')
        self.client.force_authenticate(self.tenant_user)

        response = self.client.get('/api/v1/ai-models/third-party-chatbots/options/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        chatbot_ids = [item['id'] for item in response.data['chatbots']]
        self.assertIn(granted.id, chatbot_ids)
        self.assertNotIn(hidden.id, chatbot_ids)
        self.assertNotIn('apiKey', str(response.data))
        self.assertNotIn('apiBaseUrl', str(response.data))
