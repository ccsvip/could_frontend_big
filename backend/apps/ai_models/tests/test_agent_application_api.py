from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import (
    ChatConversation,
    ChatMessage,
    LLMModel,
    LLMProvider,
    TenantLLMModelGrant,
    TenantLLMSettings,
)
from apps.knowledge_base.models import KnowledgeDocument
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class AgentApplicationAccessDataTests(TestCase):
    def test_seed_adds_application_menu_and_permissions_to_existing_tenants(self):
        default_tenant = Tenant.objects.filter(code='default').first()

        self.assertIsNotNone(default_tenant)
        self.assertTrue(default_tenant.menus.filter(path='/ai-models/applications').exists())
        self.assertTrue(
            {
                'agent_applications.view',
                'agent_applications.create',
                'agent_applications.update',
            }.issubset(set(default_tenant.permission_points.values_list('code', flat=True)))
        )

    def test_seed_adds_delete_permission_to_existing_tenants(self):
        default_tenant = Tenant.objects.filter(code='default').first()

        self.assertIsNotNone(default_tenant)
        self.assertIn(
            'agent_applications.delete',
            set(default_tenant.permission_points.values_list('code', flat=True)),
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
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    @staticmethod
    def agent_application_model():
        return apps.get_model('ai_models', 'AgentApplication')

    def create_provider(self) -> LLMProvider:
        return LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://api.openai.com/v1',
            api_key='secret-key',
            is_active=True,
        )

    def create_model(self, provider: LLMProvider, *, default=False) -> LLMModel:
        model = LLMModel.objects.create(
            provider=provider,
            name='gpt-4.1',
            display_name='GPT 4.1',
            is_active=True,
        )
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        if default:
            TenantLLMSettings.objects.update_or_create(
                tenant=self.tenant,
                defaults={'default_model': model},
            )
        return model

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
        model = self.create_model(provider)
        document = self.create_document(title='Gold support playbook')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Gold support agent',
                'description': 'Handles refund and exchange questions',
                'llmModelId': model.id,
                'systemPrompt': 'Answer as a careful support specialist.',
                'temperature': 0.8,
                'maxTokens': 1200,
                'knowledgeDocumentIds': [document.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Gold support agent')
        self.assertEqual(response.data['llmModelId'], model.id)
        self.assertEqual(response.data['llmModelName'], 'gpt-4.1')
        self.assertEqual(response.data['llmProviderName'], provider.name)
        self.assertEqual(response.data['knowledgeDocumentIds'], [document.id])

        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.get(pk=response.data['id'])
        self.assertEqual(application.tenant_id, self.tenant.id)
        self.assertEqual(application.llm_model_id, model.id)
        self.assertEqual(application.system_prompt, 'Answer as a careful support specialist.')
        self.assertEqual(list(application.knowledge_documents.values_list('id', flat=True)), [document.id])

    def test_create_agent_application_rejects_foreign_knowledge_document(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        provider = self.create_provider()
        model = self.create_model(provider)
        foreign_tenant = Tenant.objects.create(name='Foreign tenant', code='foreign-tenant')
        foreign_document = self.create_document(tenant=foreign_tenant, title='Foreign playbook')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Unsafe agent',
                'llmModelId': model.id,
                'knowledgeDocumentIds': [foreign_document.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('对象不存在', response.data['message'])

    def test_create_debug_conversation_copies_application_chat_config(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create', 'ai_models.chat.create')
        provider = self.create_provider()
        model = self.create_model(provider)
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Code diagnosis agent',
            description='Finds likely bugs in code snippets',
            llm_model=model,
            system_prompt='Diagnose code carefully.',
            temperature=0.5,
            max_tokens=1600,
        )

        response = self.client.post(f'/api/v1/ai-models/applications/{application.id}/conversations/')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation = ChatConversation.objects.get(pk=response.data['id'])
        self.assertEqual(conversation.application_id, application.id)
        self.assertEqual(conversation.llm_model_id, model.id)
        self.assertEqual(conversation.system_prompt, 'Diagnose code carefully.')
        self.assertEqual(conversation.temperature, 0.5)
        self.assertEqual(conversation.max_tokens, 1600)

    def test_create_agent_application_without_model_uses_default_model(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        provider = self.create_provider()
        model = self.create_model(provider, default=True)

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Default model agent',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['llmModelId'], model.id)
        self.assertEqual(response.data['llmModelName'], 'gpt-4.1')

    def test_create_agent_application_without_model_and_no_default_model_succeeds(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'No model agent',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['llmModelId'])

    def test_create_agent_application_rejects_duplicate_name_in_same_tenant(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        AgentApplication = self.agent_application_model()
        AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='智能客服助理',
        )

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': '智能客服助理',
                'description': 'Duplicate template name',
                'temperature': 0.7,
                'maxTokens': 1000,
                'systemPrompt': '',
                'openingMessageEnabled': True,
                'openingMessage': '',
                'suggestedQuestions': [],
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('同名智能体已存在，请更换名称', response.data['message'])

    def test_create_agent_application_defaults_conversation_settings(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {'name': '样芋量'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['openingMessageEnabled'])
        self.assertEqual(
            response.data['openingMessage'],
            '你好，我是样芋量，很高兴见到你，有什么我可以帮你的吗？',
        )
        self.assertEqual(response.data['suggestedQuestions'], [])
        self.assertFalse(response.data['voiceInputEnabled'])
        self.assertFalse(response.data['replyPlaybackEnabled'])

    def test_update_agent_application_accepts_conversation_settings(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.update')
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Conversation agent',
        )

        response = self.client.patch(
            f'/api/v1/ai-models/applications/{application.id}/',
            {
                'openingMessageEnabled': True,
                'openingMessage': '你好，我是客服助手。',
                'suggestedQuestions': ['你能做什么？', '如何使用知识库？'],
                'voiceInputEnabled': True,
                'replyPlaybackEnabled': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['openingMessage'], '你好，我是客服助手。')
        self.assertEqual(response.data['suggestedQuestions'], ['你能做什么？', '如何使用知识库？'])
        self.assertTrue(response.data['voiceInputEnabled'])
        self.assertTrue(response.data['replyPlaybackEnabled'])

    def test_update_agent_application_rejects_duplicate_name_in_same_tenant(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.update')
        AgentApplication = self.agent_application_model()
        first = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Existing agent',
        )
        second = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Editable agent',
        )

        response = self.client.patch(
            f'/api/v1/ai-models/applications/{second.id}/',
            {'name': first.name},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('同名智能体已存在，请更换名称', response.data['message'])

    def test_suggested_questions_limit_is_ten(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Too many questions',
                'suggestedQuestions': [f'问题 {index}' for index in range(11)],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('suggestedQuestions', response.data['message'])

    def test_suggested_questions_reject_blank_item(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create')

        response = self.client.post(
            '/api/v1/ai-models/applications/',
            {
                'name': 'Blank question',
                'suggestedQuestions': ['正常问题', '   '],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('suggestedQuestions', response.data['message'])

    def test_delete_agent_application_deletes_its_conversations_and_messages(self):
        self.grant_permissions(
            'agent_applications.view',
            'agent_applications.create',
            'agent_applications.delete',
        )
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Disposable toolbox',
        )
        document = self.create_document(title='Shared document')
        provider = self.create_provider()
        model = self.create_model(provider)
        application.knowledge_documents.set([document])
        conversation = ChatConversation.objects.create(
            user=self.user,
            application=application,
            tenant=self.tenant,
            llm_model=model,
        )
        message = ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.ROLE_ASSISTANT,
            content='This history belongs to the agent.',
        )

        response = self.client.delete(f'/api/v1/ai-models/applications/{application.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AgentApplication.objects.filter(id=application.id).exists())
        self.assertFalse(ChatConversation.objects.filter(id=conversation.id).exists())
        self.assertFalse(ChatMessage.objects.filter(id=message.id).exists())
        self.assertTrue(KnowledgeDocument.objects.filter(id=document.id).exists())
        self.assertTrue(LLMModel.objects.filter(id=model.id).exists())

    def test_agent_application_stats_action(self):
        self.grant_permissions('agent_applications.view', 'agent_applications.create', 'ai_models.chat.view')
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Stats Test Agent',
        )

        # Create debug conversation
        conversation = ChatConversation.objects.create(
            title='Test conversation',
            user=self.user,
            application=application,
            tenant=self.tenant,
        )

        # Create some messages
        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.ROLE_USER,
            content='Hello',
        )
        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.ROLE_ASSISTANT,
            content='Hi there!',
            feedback=ChatMessage.FEEDBACK_UP,
        )

        response = self.client.get(f'/api/v1/ai-models/applications/{application.id}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['conversationCount'], 1)
        self.assertEqual(response.data['messageCount'], 2)
        self.assertEqual(response.data['userMessageCount'], 1)
        self.assertEqual(response.data['assistantMessageCount'], 1)
        self.assertEqual(response.data['upCount'], 1)
        self.assertEqual(response.data['downCount'], 0)
        self.assertIn('dailyTrends', response.data)

    def test_list_conversations_filtered_by_application(self):
        self.grant_permissions('agent_applications.view', 'ai_models.chat.view')
        AgentApplication = self.agent_application_model()
        app1 = AgentApplication.objects.create(tenant=self.tenant, created_by=self.user, name='App 1')
        app2 = AgentApplication.objects.create(tenant=self.tenant, created_by=self.user, name='App 2')

        conv1 = ChatConversation.objects.create(user=self.user, application=app1, tenant=self.tenant)
        conv2 = ChatConversation.objects.create(user=self.user, application=app2, tenant=self.tenant)

        # Filter by app1
        response = self.client.get('/api/v1/ai-models/chat/conversations/', {'application': app1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data['results']]
        self.assertIn(conv1.id, ids)
        self.assertNotIn(conv2.id, ids)

    def test_knowledge_base_retrieval_and_injection(self):
        from apps.ai_models.services.agent_knowledge import retrieve_knowledge_context, inject_knowledge_context
        self.grant_permissions('agent_applications.view', 'agent_applications.create')
        provider = self.create_provider()
        model = self.create_model(provider)
        
        AgentApplication = self.agent_application_model()
        application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Knowledge Agent',
            llm_model=model,
        )

        # Create approved txt document
        doc1 = self.create_document(title='Refund policy')
        # Write some content to the doc file
        from django.core.files.base import ContentFile
        doc1.file.save('Refund policy.txt', ContentFile(b'Refunds are processed within 5 business days.'))
        doc1.file_extension = 'txt'
        doc1.processing_status = KnowledgeDocument.STATUS_APPROVED
        doc1.save()

        # Create unapproved txt document
        doc2 = self.create_document(title='Shipping policy')
        doc2.file.save('Shipping policy.txt', ContentFile(b'Shipping takes 3 days.'))
        doc2.file_extension = 'txt'
        doc2.processing_status = KnowledgeDocument.STATUS_PENDING
        doc2.save()

        # Create approved pdf document
        doc3 = self.create_document(title='Pricing guide')
        doc3.file.save('Pricing guide.pdf', ContentFile(b'Pricing starts at $10.'))
        doc3.file_extension = 'pdf'
        doc3.processing_status = KnowledgeDocument.STATUS_APPROVED
        doc3.save()

        # Bind them
        application.knowledge_documents.set([doc1, doc2, doc3])

        # Test retrieve_knowledge_context
        context = retrieve_knowledge_context(application, 'How long for refund?')
        self.assertIn('Refunds are processed within 5 business days.', context)
        self.assertNotIn('Shipping takes 3 days.', context)
        self.assertNotIn('Pricing starts at $10.', context)

        # Test inject_knowledge_context
        conversation = ChatConversation.objects.create(
            user=self.user,
            application=application,
            tenant=self.tenant,
        )
        api_messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'How long for refund?'}
        ]
        injected = inject_knowledge_context(conversation, api_messages, 'How long for refund?')
        
        self.assertEqual(len(injected), 3)
        self.assertEqual(injected[0]['content'], 'You are a helpful assistant.')
        self.assertIn('Refunds are processed within 5 business days.', injected[1]['content'])
        self.assertEqual(injected[2]['content'], 'How long for refund?')

        # Clean up files
        doc1.file.delete()
        doc2.file.delete()
        doc3.file.delete()
