from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ChatConversation, LLMProvider
from apps.knowledge_base.models import KnowledgeDocument
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class AgentApplicationAccessDataTests(TestCase):
    def test_seed_adds_application_menu_and_permissions_to_existing_tenants(self):
        default_tenant = Tenant.objects.filter(code='default').first()

        self.assertIsNotNone(default_tenant)
        self.assertTrue(default_tenant.menus.filter(path='/applications').exists())
        self.assertTrue(
            {
                'agent_applications.view',
                'agent_applications.create',
                'agent_applications.update',
            }.issubset(set(default_tenant.permission_points.values_list('code', flat=True)))
        )


class AgentApplicationApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agent-app-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='Agent app tester', code='agent_app_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

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
        self.grant_all_scope_to_tenant()
        self.role.permission_points.set(permission_points)

    @staticmethod
    def agent_application_model():
        return apps.get_model('ai_models', 'AgentApplication')

    def create_provider(self) -> LLMProvider:
        return LLMProvider.objects.create(
            tenant=self.tenant,
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-key',
            models_config=[{'name': 'gpt-4.1', 'isDefault': True}],
            is_active=True,
        )

    def create_document(self, *, tenant=None, title='Refund policy') -> KnowledgeDocument:
        return KnowledgeDocument.objects.create(
            tenant=tenant or self.tenant,
            title=title,
            file=f'knowledge-base/{title}.txt',
            processing_status=KnowledgeDocument.STATUS_APPROVED,
        )

    def test_list_agent_applications_requires_view_permission(self):
        self.tenant.permission_points.clear()

        response = self.client.get('/api/v1/ai-models/applications/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_agent_application_persists_model_config_and_knowledge_documents(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        provider = self.create_provider()
        document = self.create_document(title='Gold support playbook')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Gold support agent',
                'description': 'Handles refund and exchange questions',
                'llmProviderId': provider.id,
                'modelName': 'gpt-4.1',
                'systemPrompt': 'Answer as a careful support specialist.',
                'temperature': 0.8,
                'maxTokens': 1200,
                'knowledgeDocumentIds': [document.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Gold support agent')
        self.assertEqual(response.data['llmProviderId'], provider.id)
        self.assertEqual(response.data['knowledgeDocumentIds'], [document.id])

        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.get(pk=response.data['id'])
        self.assertEqual(application.tenant_id, self.tenant.id)
        self.assertEqual(application.llm_provider_id, provider.id)
        self.assertEqual(application.model_name, 'gpt-4.1')
        self.assertEqual(application.system_prompt, 'Answer as a careful support specialist.')
        self.assertEqual(list(application.knowledge_documents.values_list('id', flat=True)), [document.id])

    def test_create_agent_application_rejects_foreign_knowledge_document(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        self.create_provider()
        foreign_tenant = Tenant.objects.create(name='Foreign tenant', code='foreign-tenant')
        foreign_document = self.create_document(tenant=foreign_tenant, title='Foreign playbook')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Unsafe agent',
                'knowledgeDocumentIds': [foreign_document.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('对象不存在', response.data['message'])

    def test_create_debug_conversation_copies_application_chat_config(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create', 'ai_models.chat.create')
        provider = self.create_provider()
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Code diagnosis agent',
            description='Finds likely bugs in code snippets',
            llm_provider=provider,
            model_name='gpt-4.1',
            system_prompt='Diagnose code carefully.',
            temperature=0.5,
            max_tokens=1600,
        )

        response = self.client.post(f'/api/v1/ai-models/applications/{application.id}/conversations/')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation = ChatConversation.objects.get(pk=response.data['id'])
        self.assertEqual(conversation.application_id, application.id)
        self.assertEqual(conversation.llm_provider_id, provider.id)
        self.assertEqual(conversation.model_name, 'gpt-4.1')
        self.assertEqual(conversation.system_prompt, 'Diagnose code carefully.')
        self.assertEqual(conversation.temperature, 0.5)
        self.assertEqual(conversation.max_tokens, 1600)
