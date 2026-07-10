from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ChatConversation
from apps.devices.models import Device, DeviceApplication, DeviceChatLog
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin


User = get_user_model()


class DeviceChatSessionApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='device-history-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='Device history tester', code='device_history_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

        AgentApplication = apps.get_model('ai_models', 'AgentApplication')
        self.agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Runtime history agent',
        )
        self.device_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            agent_application=self.agent_application,
            name='Runtime device app',
            code='runtime-history-app',
        )
        self.device = Device.objects.create(
            tenant=self.tenant,
            application=self.device_application,
            agent_application=self.agent_application,
            name='Lobby device',
            code='DEVICE-HISTORY-001',
        )

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

    def create_log(self, *, question: str, answer: str, conversation=None, runtime_session_id=''):
        return DeviceChatLog.objects.create(
            tenant=self.tenant,
            application=self.device_application,
            agent_application=self.agent_application,
            device=self.device,
            conversation=conversation,
            runtime_session_id=runtime_session_id,
            code=self.device.code,
            source=DeviceChatLog.SOURCE_WEBSOCKET,
            question_text=question,
            answer_text=answer,
        )

    def test_list_paginates_device_runtime_conversations_after_grouping(self):
        self.grant_permissions('ai_models.chat.view')
        first_conversation = ChatConversation.objects.create(
            user=self.user,
            tenant=self.tenant,
            application=self.agent_application,
            title='First runtime conversation',
        )
        second_conversation = ChatConversation.objects.create(
            user=self.user,
            tenant=self.tenant,
            application=self.agent_application,
            title='Second runtime conversation',
        )
        self.create_log(question='First question', answer='First answer', conversation=first_conversation)
        self.create_log(question='Second question', answer='Second answer', conversation=first_conversation)
        latest_log = self.create_log(
            question='Latest question',
            answer='Latest answer',
            conversation=second_conversation,
        )

        response = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': self.agent_application.id, 'page': 1, 'page_size': 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], latest_log.id)
        self.assertEqual(response.data['results'][0]['messageCount'], 2)
        self.assertEqual(response.data['results'][0]['lastMessage'], 'Latest answer')

    def test_list_groups_device_logs_by_device_scoped_runtime_session_id(self):
        self.grant_permissions('ai_models.chat.view')
        self.create_log(
            question='Turn one',
            answer='Answer one',
            runtime_session_id='runtime-session-a',
        )
        self.create_log(
            question='Turn two',
            answer='Answer two',
            runtime_session_id='runtime-session-a',
        )
        self.create_log(
            question='Another session',
            answer='Another answer',
            runtime_session_id='runtime-session-b',
        )

        response = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': self.agent_application.id, 'page_size': 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        sessions = {item['runtimeSessionId']: item for item in response.data['results']}
        self.assertEqual(sessions['runtime-session-a']['messageCount'], 4)
        self.assertEqual(sessions['runtime-session-a']['lastMessage'], 'Answer two')

    def test_same_runtime_session_id_on_different_devices_remains_separate(self):
        self.grant_permissions('ai_models.chat.view')
        self.create_log(
            question='Lobby question',
            answer='Lobby answer',
            runtime_session_id='shared-runtime-session-id',
        )
        other_device = Device.objects.create(
            tenant=self.tenant,
            application=self.device_application,
            agent_application=self.agent_application,
            name='Showroom device',
            code='DEVICE-HISTORY-002',
        )
        DeviceChatLog.objects.create(
            tenant=self.tenant,
            application=self.device_application,
            agent_application=self.agent_application,
            device=other_device,
            runtime_session_id='shared-runtime-session-id',
            code=other_device.code,
            source=DeviceChatLog.SOURCE_HTTP,
            question_text='Showroom question',
            answer_text='Showroom answer',
        )

        response = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': self.agent_application.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(
            {item['deviceCode'] for item in response.data['results']},
            {'DEVICE-HISTORY-001', 'DEVICE-HISTORY-002'},
        )

    def test_retrieve_returns_complete_device_runtime_conversation(self):
        self.grant_permissions('ai_models.chat.view')
        first_log = self.create_log(
            question='Turn one',
            answer='Answer one',
            runtime_session_id='runtime-session-detail',
        )
        self.create_log(
            question='Turn two',
            answer='Answer two',
            runtime_session_id='runtime-session-detail',
        )

        response = self.client.get(f'/api/v1/device-chat-sessions/{first_log.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], first_log.id)
        self.assertEqual(response.data['runtimeSessionId'], 'runtime-session-detail')
        self.assertEqual(
            [(message['role'], message['content']) for message in response.data['messages']],
            [
                ('user', 'Turn one'),
                ('assistant', 'Answer one'),
                ('user', 'Turn two'),
                ('assistant', 'Answer two'),
            ],
        )

    def test_delete_removes_one_device_runtime_conversation(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.delete')
        active_conversation = ChatConversation.objects.create(
            user=self.user,
            tenant=self.tenant,
            application=self.agent_application,
            title='Active runtime context',
            external_session={
                'runtimeSessionId': 'runtime-session-delete',
                'upstreamSessionId': 'upstream-context-must-survive',
            },
        )
        target_log = self.create_log(
            question='Delete me',
            answer='Deleted answer',
            conversation=active_conversation,
            runtime_session_id='runtime-session-delete',
        )
        self.create_log(
            question='Delete me too',
            answer='Deleted answer two',
            conversation=active_conversation,
            runtime_session_id='runtime-session-delete',
        )
        retained_log = self.create_log(
            question='Keep me',
            answer='Retained answer',
            runtime_session_id='runtime-session-keep',
        )

        delete_response = self.client.delete(f'/api/v1/device-chat-sessions/{target_log.id}/')
        list_response = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': self.agent_application.id},
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['id'], retained_log.id)
        self.assertTrue(ChatConversation.objects.filter(id=active_conversation.id).exists())

    def test_delete_requires_chat_delete_permission(self):
        self.grant_permissions('ai_models.chat.view')
        target_log = self.create_log(
            question='Protected question',
            answer='Protected answer',
            runtime_session_id='runtime-session-protected',
        )

        response = self.client.delete(f'/api/v1/device-chat-sessions/{target_log.id}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_cannot_access_another_tenants_device_session(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.delete')
        other_tenant = Tenant.objects.create(name='Other company', code='other-device-history-company')
        AgentApplication = apps.get_model('ai_models', 'AgentApplication')
        other_agent = AgentApplication.objects.create(
            tenant=other_tenant,
            created_by=self.user,
            name='Foreign runtime history agent',
        )
        other_device_application = DeviceApplication.objects.create(
            tenant=other_tenant,
            agent_application=other_agent,
            name='Foreign runtime device app',
            code='foreign-runtime-history-app',
        )
        foreign_log = DeviceChatLog.objects.create(
            tenant=other_tenant,
            application=other_device_application,
            agent_application=other_agent,
            runtime_session_id='foreign-runtime-session',
            code='FOREIGN-DEVICE-HISTORY',
            source=DeviceChatLog.SOURCE_HTTP,
            question_text='Foreign question',
            answer_text='Foreign answer',
        )

        response = self.client.delete(f'/api/v1/device-chat-sessions/{foreign_log.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(DeviceChatLog.objects.filter(id=foreign_log.id).exists())

    def test_delete_collection_clears_only_the_selected_agent_application(self):
        self.grant_permissions('ai_models.chat.view', 'ai_models.chat.delete')
        self.create_log(
            question='Clear this app',
            answer='Clear this answer',
            runtime_session_id='runtime-session-clear',
        )
        AgentApplication = apps.get_model('ai_models', 'AgentApplication')
        other_agent = AgentApplication.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name='Other runtime history agent',
        )
        other_device_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            agent_application=other_agent,
            name='Other runtime device app',
            code='other-runtime-history-app',
        )
        other_device = Device.objects.create(
            tenant=self.tenant,
            application=other_device_application,
            agent_application=other_agent,
            name='Other device',
            code='DEVICE-HISTORY-OTHER',
        )
        DeviceChatLog.objects.create(
            tenant=self.tenant,
            application=other_device_application,
            agent_application=other_agent,
            device=other_device,
            runtime_session_id='runtime-session-other',
            code=other_device.code,
            source=DeviceChatLog.SOURCE_HTTP,
            question_text='Keep other app',
            answer_text='Keep other answer',
        )

        clear_response = self.client.delete(
            f'/api/v1/device-chat-sessions/?agentApplicationId={self.agent_application.id}',
        )
        target_list = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': self.agent_application.id},
        )
        other_list = self.client.get(
            '/api/v1/device-chat-sessions/',
            {'agentApplicationId': other_agent.id},
        )

        self.assertEqual(clear_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(target_list.data['count'], 0)
        self.assertEqual(other_list.data['count'], 1)
