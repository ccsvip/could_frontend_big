from django.apps import apps
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()
HUAPENG_APPLICATION_ID = '8d697146-f9a2-11ef-89c4-86dcb2923f74'


class DummyThirdPartyClient:
    calls = []

    def __init__(self, responses):
        self.responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, **kwargs):
        self.calls.append({'method': method, 'url': url, 'kwargs': kwargs})
        if not self.responses:
            raise AssertionError('unexpected third-party request')
        return self.responses.pop(0)



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

    def create_chatbot(self, *, name='华鹏展厅机器人', tenant=None, is_active=True, with_integration=True):
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
        if with_integration:
            self.integration_model().objects.create(
                scheme_type='scheme_a',
                name=f'{name} 方案A',
                provider=provider,
                chatbot=chatbot,
                config=self.scheme_a_payload()['config'],
                is_active=True,
            )
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

    def test_company_only_sees_company_bound_third_party_chatbot_schemes(self):
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

    def test_company_options_hide_legacy_chatbot_without_scheme(self):
        legacy = self.create_chatbot(name='旧裸机器人', tenant=self.tenant, with_integration=False)
        self.grant_permissions('agent_applications.view')
        self.client.force_authenticate(self.tenant_user)

        response = self.client.get('/api/v1/ai-models/third-party-chatbots/options/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        chatbot_ids = [item['id'] for item in response.data['chatbots']]
        self.assertNotIn(legacy.id, chatbot_ids)

    def integration_model(self):
        return apps.get_model('ai_models', 'ThirdPartyChatbotIntegration')

    def scheme_a_payload(self, **overrides):
        payload = {
            'schemeType': 'scheme_a',
            'name': '华鹏方案A',
            'remark': '超管维护备注',
            'providerName': '华鹏 AI',
            'providerApiBaseUrl': 'https://ai.ihuapeng.cn/api',
            'providerApiKey': 'application-key',
            'chatbotName': '华鹏展厅机器人',
            'chatbotDescription': '售前接待',
            'externalApplicationId': HUAPENG_APPLICATION_ID,
            'config': {
                'steps': [
                    {
                        'key': 'open_chat',
                        'name': '打开会话',
                        'method': 'GET',
                        'path': '/application/{{externalApplicationId}}/chat/open',
                        'headers': [{'key': 'AUTHORIZATION', 'value': '{{apiKey}}'}],
                        'body': {},
                        'extract': [{'name': 'chat_id', 'path': '$.data'}],
                        'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 200},
                        'errorMessagePath': '$.message',
                    },
                    {
                        'key': 'send_message',
                        'name': '发送消息',
                        'method': 'POST',
                        'path': '/application/chat_message/{{chat_id}}',
                        'headers': [{'key': 'AUTHORIZATION', 'value': '{{apiKey}}'}],
                        'body': {'message': '{{message}}', 'stream': True},
                        'extract': [],
                        'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 200},
                        'errorMessagePath': '$.message',
                    },
                ],
                'answerPaths': ['$.data.content'],
            },
            'isActive': True,
            'tenantIds': [self.tenant.id],
        }
        payload.update(overrides)
        return payload

    def scheme_b_payload(self, **overrides):
        payload = {
            'schemeType': 'scheme_b',
            'name': 'FlowMesh 方案B',
            'remark': 'FlowMesh LLM 同步对话',
            'providerName': 'FlowMesh',
            'providerApiBaseUrl': 'https://flowmesh-api.kmyszkj.com/api/open/v1',
            'providerApiKey': 'flowmesh-key',
            'chatbotName': 'FlowMesh 助手',
            'chatbotDescription': '同步 LLM 问答',
            'externalApplicationId': 'zy-assistant',
            'config': {
                'schemeType': 'scheme_b',
                'steps': [
                    {
                        'key': 'send_message',
                        'name': '发送消息',
                        'method': 'POST',
                        'path': '/apps/{{externalApplicationId}}/chat',
                        'headers': [
                            {'key': 'Authorization', 'value': 'Bearer {{apiKey}}'},
                            {'key': 'Content-Type', 'value': 'application/json'},
                        ],
                        'body': {'query': '{{message}}'},
                        'extract': [{'name': 'sessionId', 'path': '$.data.sessionId'}],
                        'success': {'httpStatus': '200-299', 'bodyPath': '$.code', 'equals': 1},
                        'errorMessagePath': '$.message',
                    },
                ],
                'answerPaths': ['$.data.answer'],
            },
            'isActive': True,
            'tenantIds': [self.tenant.id],
        }
        payload.update(overrides)
        return payload

    def test_superuser_creates_scheme_a_integration_and_binds_company(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.post(
            '/api/v1/settings/third-party-chatbots/integrations/',
            self.scheme_a_payload(config={
                'steps': [
                    {
                        'key': 'send_message',
                        'name': '发送消息',
                        'method': 'POST',
                        'path': '/application/chat_message/{{chat_id}}',
                        'headers': [{'key': 'AUTHORIZATION', 'value': 'application-key'}],
                        'body': {'message': '{{message}}', 'stream': False, 'token': 'body-secret'},
                        'extract': [],
                        'success': {'httpStatus': '200-299'},
                    },
                ],
                'answerPaths': ['$.data.content'],
            }),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['schemeType'], 'scheme_a')
        self.assertEqual(response.data['authorizedTenantIds'], [self.tenant.id])
        self.assertNotIn('application-key', str(response.data))
        self.assertNotIn('body-secret', str(response.data))
        integration = self.integration_model().objects.select_related('provider', 'chatbot').get(pk=response.data['id'])
        self.assertEqual(integration.provider.api_key, 'application-key')
        self.assertEqual(integration.chatbot.external_application_id, HUAPENG_APPLICATION_ID)
        self.assertTrue(self.grant_model().objects.filter(tenant=self.tenant, chatbot=integration.chatbot, is_active=True).exists())

    def test_scheme_a_draft_test_runs_current_form_config(self):
        self.client.force_authenticate(self.superuser)
        DummyThirdPartyClient.calls = []
        responses = [
            httpx.Response(200, json={'code': 200, 'data': 'chat-1'}),
            httpx.Response(200, json={'code': 200, 'data': {'content': '测试回复'}}),
        ]

        with patch('apps.ai_models.services.third_party_chatbots.httpx.Client', return_value=DummyThirdPartyClient(responses)):
            response = self.client.post(
                '/api/v1/settings/third-party-chatbots/integrations/test/',
                {**self.scheme_a_payload(), 'question': '你好'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['answer'], '测试回复')
        self.assertEqual(len(response.data['steps']), 2)
        self.assertEqual(DummyThirdPartyClient.calls[0]['method'], 'GET')
        self.assertIn(HUAPENG_APPLICATION_ID, DummyThirdPartyClient.calls[0]['url'])
        self.assertEqual(DummyThirdPartyClient.calls[1]['kwargs']['json'], {'message': '你好', 'stream': True})

    def test_superuser_creates_scheme_b_flowmesh_integration(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.post(
            '/api/v1/settings/third-party-chatbots/integrations/',
            self.scheme_b_payload(),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['schemeType'], 'scheme_b')
        self.assertEqual(response.data['schemeTypeLabel'], '方案B')
        self.assertEqual(response.data['config']['answerPaths'], ['$.data.answer'])
        self.assertEqual(response.data['config']['steps'][0]['body'], {'query': '{{message}}'})
        integration = self.integration_model().objects.select_related('provider', 'chatbot').get(pk=response.data['id'])
        self.assertEqual(integration.provider.provider_type, 'configured_api_chatbot')
        self.assertEqual(integration.chatbot.external_application_id, 'zy-assistant')

    def test_scheme_b_draft_test_uses_flowmesh_single_step_without_stream(self):
        self.client.force_authenticate(self.superuser)
        DummyThirdPartyClient.calls = []
        responses = [
            httpx.Response(200, json={'code': 1, 'data': {'sessionId': 'session-1', 'answer': 'FlowMesh 回复'}}),
        ]

        with patch('apps.ai_models.services.third_party_chatbots.httpx.Client', return_value=DummyThirdPartyClient(responses)):
            response = self.client.post(
                '/api/v1/settings/third-party-chatbots/integrations/test/',
                {**self.scheme_b_payload(), 'question': '你好'},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['answer'], 'FlowMesh 回复')
        self.assertEqual(len(response.data['steps']), 1)
        self.assertEqual(DummyThirdPartyClient.calls[0]['method'], 'POST')
        self.assertTrue(DummyThirdPartyClient.calls[0]['url'].endswith('/apps/zy-assistant/chat'))
        self.assertEqual(DummyThirdPartyClient.calls[0]['kwargs']['json'], {'query': '你好'})
        self.assertEqual(DummyThirdPartyClient.calls[0]['kwargs']['headers']['Authorization'], 'Bearer flowmesh-key')


    def test_runtime_uses_scheme_a_config_body_and_answer_mapping(self):
        from apps.ai_models.models import ChatConversation
        from apps.ai_models.services.third_party_chatbots import send_chatbot_message

        chatbot = self.create_chatbot(tenant=self.tenant)
        integration = chatbot.integration
        conversation = ChatConversation.objects.create(user=self.tenant_user, tenant=self.tenant, third_party_chatbot=chatbot)
        DummyThirdPartyClient.calls = []
        responses = [
            httpx.Response(200, json={'code': 200, 'data': 'runtime-chat'}),
            httpx.Response(200, json={'code': 200, 'data': {'content': '运行时回复'}}),
        ]

        with patch('apps.ai_models.services.third_party_chatbots.httpx.Client', return_value=DummyThirdPartyClient(responses)):
            answer = send_chatbot_message(integration.chatbot, '介绍一下', conversation=conversation)

        self.assertEqual(answer, '运行时回复')
        self.assertEqual(DummyThirdPartyClient.calls[1]['kwargs']['json'], {'message': '介绍一下', 'stream': True})
        conversation.refresh_from_db()
        self.assertIn('runtime-chat', str(conversation.external_session))

    def test_runtime_uses_scheme_b_flowmesh_body_and_answer_mapping(self):
        from apps.ai_models.models import ChatConversation
        from apps.ai_models.services.third_party_chatbots import send_chatbot_message

        self.client.force_authenticate(self.superuser)
        create_response = self.client.post(
            '/api/v1/settings/third-party-chatbots/integrations/',
            self.scheme_b_payload(),
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        chatbot = self.chatbot_model().objects.get(pk=create_response.data['chatbotId'])
        conversation = ChatConversation.objects.create(user=self.tenant_user, tenant=self.tenant, third_party_chatbot=chatbot)
        DummyThirdPartyClient.calls = []
        responses = [
            httpx.Response(200, json={'code': 1, 'data': {'sessionId': 'session-2', 'answer': '运行时 FlowMesh 回复'}}),
        ]

        with patch('apps.ai_models.services.third_party_chatbots.httpx.Client', return_value=DummyThirdPartyClient(responses)):
            answer = send_chatbot_message(chatbot, '介绍一下', conversation=conversation)

        self.assertEqual(answer, '运行时 FlowMesh 回复')
        self.assertEqual(DummyThirdPartyClient.calls[0]['kwargs']['json'], {'query': '介绍一下'})
        conversation.refresh_from_db()
        self.assertIn('session-2', str(conversation.external_session))


    def test_scheme_a_update_preserves_masked_sensitive_values(self):
        self.client.force_authenticate(self.superuser)
        create_response = self.client.post(
            '/api/v1/settings/third-party-chatbots/integrations/',
            self.scheme_a_payload(config={
                'steps': [
                    {
                        'key': 'send_message',
                        'name': '发送消息',
                        'method': 'POST',
                        'path': '/application/chat_message/{{chat_id}}',
                        'headers': [{'key': 'AUTHORIZATION', 'value': 'application-key'}],
                        'body': {'message': '{{message}}', 'stream': False, 'token': 'body-secret'},
                        'extract': [],
                        'success': {'httpStatus': '200-299'},
                    },
                ],
                'answerPaths': ['$.data.content'],
            }),
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        masked_config = create_response.data['config']

        update_response = self.client.patch(
            f"/api/v1/settings/third-party-chatbots/integrations/{create_response.data['id']}/",
            {
                'remark': '更新备注',
                'providerApiKey': create_response.data['providerApiKeyMasked'],
                'config': masked_config,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        integration = self.integration_model().objects.select_related('provider').get(pk=create_response.data['id'])
        self.assertEqual(integration.provider.api_key, 'application-key')
        self.assertEqual(integration.config['steps'][0]['headers'][0]['value'], 'application-key')
        self.assertEqual(integration.config['steps'][0]['body']['token'], 'body-secret')
