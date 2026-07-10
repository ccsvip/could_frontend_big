from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync, sync_to_async
from asgiref.testing import ApplicationCommunicator
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import AgentAnnotation, AgentApplication, ChatConversation, LLMModel, LLMProvider, TenantLLMModelGrant, TenantLLMSettings, TenantTTSSettings, TTSProvider, TTSVoice
from apps.ai_models import realtime_tts
from apps.devices.models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceChatLog, DeviceGroup, WakeWord
from apps.devices.services.authorization import record_device_authorization_action
from apps.devices.services.queries import device_authorization_requests_queryset
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device
from apps.devices.serializers import DeviceActivationLogSerializer
from apps.devices.views import DeviceVoiceChatView
from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk
from apps.resources.models import ModelAsset, Resource, ScrollingText, ScrollingTextItem
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()
HUAPENG_APPLICATION_ID = '8d697146-f9a2-11ef-89c4-86dcb2923f74'


class DeviceAuthorizationApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='device-admin', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='Device Admin', code='device_admin')
        UserRole.objects.create(user=self.user, role=self.role)
        self.grant_permissions('devices.view', 'devices.create', 'devices.update')
        self.client.force_authenticate(user=self.user)
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Lobby App',
            code='lobby-app',
        )
        self.agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Lobby Agent',
            system_prompt='你是大厅数字人。',
        )

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'devices',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def create_code(self, code='AUTH-0001', **overrides):
        defaults = {
            'tenant': self.tenant,
            'application': self.application,
            'code': code,
            'authorization_type': Device.AUTHORIZATION_TRIAL,
            'expires_at': timezone.now() + timedelta(days=7),
        }
        defaults.update(overrides)
        return DeviceAuthorizationCode.objects.create(**defaults)

    def create_third_party_chatbot(self):
        Provider = apps.get_model('ai_models', 'ThirdPartyChatbotProvider')
        Chatbot = apps.get_model('ai_models', 'ThirdPartyChatbotApplication')
        Grant = apps.get_model('ai_models', 'TenantThirdPartyChatbotGrant')
        Integration = apps.get_model('ai_models', 'ThirdPartyChatbotIntegration')
        provider = Provider.objects.create(
            name='华鹏 AI',
            provider_type='ihuapeng_chatbot',
            api_base_url='https://ai.ihuapeng.cn/api',
            api_key='application-key',
            is_active=True,
        )
        chatbot = Chatbot.objects.create(
            provider=provider,
            name='华鹏展厅机器人',
            external_application_id=HUAPENG_APPLICATION_ID,
            is_active=True,
        )
        Grant.objects.create(tenant=self.tenant, chatbot=chatbot, is_active=True)
        Integration.objects.create(
            scheme_type='scheme_a',
            name='华鹏方案A',
            provider=provider,
            chatbot=chatbot,
            config={
                'steps': [
                    {
                        'key': 'send_message',
                        'name': '发送消息',
                        'method': 'POST',
                        'path': '/application/chat_message/{{chat_id}}',
                        'headers': [{'key': 'AUTHORIZATION', 'value': '{{apiKey}}'}],
                        'body': {'message': '{{message}}', 'stream': False},
                        'extract': [],
                        'success': {'httpStatus': '200-299'},
                    },
                ],
                'answerPaths': ['$.data.content'],
            },
            is_active=True,
        )
        return chatbot
    def test_authorization_request_query_filters_pending_bound_and_ignored_devices(self):
        pending = Device.objects.create(name='Pending Device', code='ANDROID-QUERY-PENDING')
        bound = Device.objects.create(tenant=self.tenant, name='Bound Device', code='ANDROID-QUERY-BOUND')
        ignored = Device.objects.create(
            name='Ignored Device',
            code='ANDROID-QUERY-IGNORED',
            authorization_ignored_at=timezone.now(),
        )
        for device in (pending, bound, ignored):
            DeviceAuthLog.objects.create(
                device=device,
                code=device.code,
                action=DeviceAuthLog.ACTION_ACTIVATE,
                result=True,
                message='设备上报成功',
                device_info={},
            )

        self.assertEqual(
            list(device_authorization_requests_queryset({'bindingStatus': 'pending'}).values_list('code', flat=True)),
            ['ANDROID-QUERY-PENDING'],
        )
        self.assertEqual(
            list(device_authorization_requests_queryset({'bindingStatus': 'bound'}).values_list('code', flat=True)),
            ['ANDROID-QUERY-BOUND'],
        )
        self.assertEqual(
            list(device_authorization_requests_queryset({'bindingStatus': 'ignored'}).values_list('code', flat=True)),
            ['ANDROID-QUERY-IGNORED'],
        )

    def test_authorization_service_records_device_snapshot_in_log(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Android',
            code='ANDROID-AUTH-SERVICE-001',
            authorization_type=Device.AUTHORIZATION_TRIAL,
            expires_at=timezone.now() + timedelta(days=1),
            is_enabled=True,
        )

        log = record_device_authorization_action(
            device,
            DeviceAuthLog.ACTION_AUTHORIZE,
            '设备已再次授权',
            ip_address='127.0.0.1',
        )

        self.assertEqual(log.tenant_id, self.tenant.id)
        self.assertEqual(log.application_id, self.application.id)
        self.assertEqual(log.device_id, device.id)
        self.assertEqual(log.device_info['tenantId'], self.tenant.id)
        self.assertEqual(log.device_info['applicationId'], self.application.id)
        self.assertEqual(log.device_info['agentApplicationId'], self.agent_application.id)
        self.assertEqual(log.device_info['authorizationType'], Device.AUTHORIZATION_TRIAL)
        self.assertTrue(log.device_info['isEnabled'])


    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_create_wake_word_persists_encoded_keyword_line_and_bindings(self, mock_encode):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-DEVICE-001',
            name='Wake Device',
        )

        response = self.client.post(
            '/api/v1/wake-words/',
            {
                'text': '你好小德',
                'boost': '2.5',
                'threshold': '0.35',
                'deviceIds': [device.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['text'], '你好小德')
        self.assertEqual(response.data['encodedText'], 'n ǐ h ǎo x iǎo d é')
        self.assertEqual(response.data['keywordLine'], 'n ǐ h ǎo x iǎo d é @你好小德 :2.5 #0.35')
        self.assertEqual(response.data['deviceIds'], [device.id])
        self.assertEqual(response.data['devices'][0]['deviceCode'], 'WAKE-DEVICE-001')
        mock_encode.assert_called_once_with('你好小德')
        wake_word = WakeWord.objects.get(text='你好小德')
        self.assertEqual(wake_word.tenant, self.tenant)
        self.assertEqual(list(wake_word.devices.values_list('id', flat=True)), [device.id])

    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_wake_word_allows_same_text_for_different_devices_in_same_tenant(self, _mock_encode):
        invalid_response = self.client.post('/api/v1/wake-words/', {'text': '小德你好'}, format='json')
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('你好', str(invalid_response.data))

        first_device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-DUP-DEVICE-001',
            name='Wake Duplicate Device 1',
        )
        second_device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-DUP-DEVICE-002',
            name='Wake Duplicate Device 2',
        )

        first_response = self.client.post(
            '/api/v1/wake-words/',
            {'text': '你好小德', 'deviceIds': [first_device.id]},
            format='json',
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        duplicate_for_other_device_response = self.client.post(
            '/api/v1/wake-words/',
            {'text': '你好小德', 'deviceIds': [second_device.id]},
            format='json',
        )
        self.assertEqual(duplicate_for_other_device_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WakeWord.objects.filter(tenant=self.tenant, text='你好小德').count(), 2)

    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_wake_word_rejects_duplicate_text_on_same_device(self, _mock_encode):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-DUP-SAME-DEVICE-001',
            name='Wake Duplicate Same Device',
        )

        first_response = self.client.post(
            '/api/v1/wake-words/',
            {'text': '你好小德', 'deviceIds': [device.id]},
            format='json',
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        duplicate_for_same_device_response = self.client.post(
            '/api/v1/wake-words/',
            {'text': '你好小德', 'deviceIds': [device.id]},
            format='json',
        )
        self.assertEqual(duplicate_for_same_device_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('同一设备内唤醒词不能重复', str(duplicate_for_same_device_response.data))

    @patch('apps.devices.views.publish_device_event_sync')
    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_wake_word_create_publishes_runtime_config_change_event(self, _mock_encode, mock_publish):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-EVENT-CREATE-001',
            name='Wake Event Create Device',
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/v1/wake-words/',
                {'text': '你好小德', 'deviceIds': [device.id]},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_publish.assert_called_once()
        payload = mock_publish.call_args.args[0]
        self.assertEqual(payload['type'], 'device.wake_words.changed')
        self.assertEqual(payload['action'], 'wakeWordsChanged')
        self.assertEqual(payload['operation'], 'create')
        self.assertEqual(payload['tenantId'], self.tenant.id)
        self.assertEqual(payload['deviceCodes'], [device.code])
        self.assertEqual(payload['refresh']['endpoint'], '/api/v1/device-runtime/config/')
        self.assertNotIn('runtimeConfigByDeviceCode', payload)
        self.assertNotIn('wakeWords', payload)
        self.assertNotIn('wakeWordLines', payload)

    @patch('apps.devices.views.publish_device_event_sync')
    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_wake_word_update_notifies_old_and_new_bound_devices(self, _mock_encode, mock_publish):
        old_device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-EVENT-OLD-001',
            name='Wake Event Old Device',
        )
        new_device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-EVENT-NEW-001',
            name='Wake Event New Device',
        )
        wake_word = WakeWord.objects.create(
            tenant=self.tenant,
            text='你好小德',
            encoded_text='n ǐ h ǎo x iǎo d é',
        )
        wake_word.devices.add(old_device)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f'/api/v1/wake-words/{wake_word.id}/',
                {'deviceIds': [new_device.id]},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = mock_publish.call_args.args[0]
        self.assertEqual(payload['type'], 'device.wake_words.changed')
        self.assertEqual(payload['action'], 'wakeWordsChanged')
        self.assertEqual(payload['operation'], 'update')
        self.assertEqual(set(payload['deviceCodes']), {old_device.code, new_device.code})
        self.assertNotIn('runtimeConfigByDeviceCode', payload)

    @patch('apps.devices.views.publish_device_event_sync')
    def test_wake_word_delete_publishes_runtime_config_change_event(self, mock_publish):
        self.grant_permissions('devices.view', 'devices.create', 'devices.update', 'devices.delete')
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='WAKE-EVENT-DELETE-001',
            name='Wake Event Delete Device',
        )
        wake_word = WakeWord.objects.create(
            tenant=self.tenant,
            text='你好小德',
            encoded_text='n ǐ h ǎo x iǎo d é',
        )
        wake_word.devices.add(device)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f'/api/v1/wake-words/{wake_word.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        payload = mock_publish.call_args.args[0]
        self.assertEqual(payload['type'], 'device.wake_words.changed')
        self.assertEqual(payload['action'], 'wakeWordsChanged')
        self.assertEqual(payload['operation'], 'delete')
        self.assertEqual(payload['tenantId'], self.tenant.id)
        self.assertEqual(payload['deviceCodes'], [device.code])
        self.assertEqual(payload['refresh']['endpoint'], '/api/v1/device-runtime/config/')
        self.assertNotIn('runtimeConfigByDeviceCode', payload)
        self.assertNotIn('wakeWords', payload)
        self.assertNotIn('wakeWordLines', payload)

    @patch('apps.devices.serializers.encode_wake_word_text', return_value='n ǐ h ǎo x iǎo d é')
    def test_wake_word_rejects_cross_tenant_device_binding(self, _mock_encode):
        other_tenant = Tenant.objects.create(name='Other Tenant', code='other-tenant')
        other_device = Device.objects.create(
            tenant=other_tenant,
            code='OTHER-WAKE-DEVICE',
            name='Other Device',
        )

        response = self.client.post(
            '/api/v1/wake-words/',
            {'text': '你好小德', 'deviceIds': [other_device.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('同公司', str(response.data))
        self.assertFalse(WakeWord.objects.filter(text='你好小德').exists())

    @patch('apps.devices.serializers.encode_wake_word_text', side_effect=['n ǐ h ǎo x iǎo d é', 'n ǐ h ǎo x iǎo zh ì'])
    def test_device_runtime_config_returns_bound_wake_word_lines(self, _mock_encode):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            code='RUNTIME-WAKE-001',
            name='Runtime Wake Device',
            is_enabled=True,
        )
        first = WakeWord.objects.create(
            tenant=self.tenant,
            text='你好小德',
            encoded_text='n ǐ h ǎo x iǎo d é',
            boost='2.0',
            threshold='0.25',
        )
        second = WakeWord.objects.create(
            tenant=self.tenant,
            text='你好小智',
            encoded_text='n ǐ h ǎo x iǎo zh ì',
            boost='2.5',
            threshold='0.35',
        )
        first.devices.add(device)
        second.devices.add(device)

        response = self.client.get('/api/v1/device-runtime/config/', HTTP_X_DEVICE_CODE='RUNTIME-WAKE-001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['wakeWordLines'],
            [
                'n ǐ h ǎo x iǎo d é @你好小德 :2.0 #0.25',
                'n ǐ h ǎo x iǎo zh ì @你好小智 :2.5 #0.35',
            ],
        )
        self.assertEqual(response.data['wakeWords'][0]['text'], '你好小德')
        self.assertEqual(response.data['wakeWords'][1]['keywordLine'], 'n ǐ h ǎo x iǎo zh ì @你好小智 :2.5 #0.35')

    def test_authorization_log_serializer_uses_agent_application_snapshot(self):
        original_agent = self.agent_application
        next_agent = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Updated Agent',
            system_prompt='你是更新后的数字人。',
        )
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=original_agent,
            name='Snapshot Android',
            code='ANDROID-AUTH-SNAPSHOT-001',
        )
        log = record_device_authorization_action(
            device,
            DeviceAuthLog.ACTION_AUTHORIZE,
            '设备已再次授权',
        )
        device.agent_application = next_agent
        device.save(update_fields=['agent_application', 'updated_at'])

        data = DeviceActivationLogSerializer(log).data

        self.assertEqual(data['agentApplicationId'], original_agent.id)
        self.assertEqual(data['agentApplicationName'], original_agent.name)

    def test_device_code_is_globally_unique(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Android A',
            code='ANDROID-DUPLICATE-001',
        )
        other_tenant = Tenant.objects.create(name='Other Company', code='other-company')

        with self.assertRaises(IntegrityError):
            Device.objects.create(
                tenant=other_tenant,
                application=self.application,
                agent_application=self.agent_application,
                name='Runtime Android B',
                code='ANDROID-DUPLICATE-001',
            )

    def test_device_create_rejects_duplicate_device_code(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Existing Android',
            code='ANDROID-DUPLICATE-API-001',
            is_enabled=True,
        )

        response = self.client.post(
            '/api/v1/devices/',
            {'deviceCode': 'ANDROID-DUPLICATE-API-001', 'name': 'Duplicate Android'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '设备码已存在，不能重复绑定')

    def test_runtime_device_lookup_rejects_unbound_company(self):
        Device.objects.create(
            name='Pending Android',
            code='ANDROID-PENDING-001',
            is_enabled=True,
        )

        with self.assertRaises(RuntimeDeviceError) as context:
            get_runtime_device('ANDROID-PENDING-001', require_tenant=True)

        self.assertEqual(context.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(context.exception.message, '设备未绑定公司')
        self.assertEqual(context.exception.code, 'DEVICE_TENANT_UNBOUND')
        self.assertEqual(context.exception.business_status_code, 44011)

    def test_runtime_config_expired_device_returns_stable_error_code(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Expired Android',
            code='ANDROID-EXPIRED-001',
            is_enabled=True,
            authorization_type=Device.AUTHORIZATION_TRIAL,
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(
            '/api/v1/device-runtime/config/',
            HTTP_X_DEVICE_CODE='ANDROID-EXPIRED-001',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'DEVICE_EXPIRED')
        self.assertEqual(response.data['statusCode'], 44014)
        self.assertEqual(response.data['message'], '设备授权已过期')

    def test_device_status_choices_match_android_runtime_states(self):
        self.assertEqual(
            {value for value, _label in Device.STATUS_CHOICES},
            {Device.STATUS_ONLINE, Device.STATUS_OFFLINE},
        )

    def test_superuser_cannot_create_company_owned_device_application(self):
        superuser = User.objects.create_superuser(
            username='platform-admin',
            password='test123456',
            email='platform@example.com',
        )
        self.client.force_authenticate(user=superuser)

        response = self.client.post(
            '/api/v1/device-applications/',
            {'name': 'Orphan App', 'code': 'orphan-app'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(DeviceApplication.objects.filter(code='orphan-app').exists())

    def test_create_authorization_requires_user_supplied_code(self):
        expires_at = timezone.now() + timedelta(days=7)

        response = self.client.post(
            '/api/v1/device-authorization-codes/',
            {
                'applicationId': self.application.id,
                'authorizationType': Device.AUTHORIZATION_TRIAL,
                'expiresAt': expires_at.isoformat(),
                'remark': 'Lobby trial',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(DeviceAuthorizationCode.objects.filter(application=self.application).exists())

    def test_create_authorization_uses_user_supplied_code(self):
        expires_at = timezone.now() + timedelta(days=7)

        response = self.client.post(
            '/api/v1/device-authorization-codes/',
            {
                'code': 'AUTH-CUSTOM-001',
                'applicationId': self.application.id,
                'authorizationType': Device.AUTHORIZATION_TRIAL,
                'expiresAt': expires_at.isoformat(),
                'remark': 'Lobby trial',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'AUTH-CUSTOM-001')
        auth_code = DeviceAuthorizationCode.objects.get(id=response.data['id'])
        self.assertEqual(auth_code.code, 'AUTH-CUSTOM-001')
        self.assertEqual(auth_code.tenant_id, self.tenant.id)
        self.assertEqual(auth_code.application_id, self.application.id)
        self.assertEqual(auth_code.created_by_id, self.user.id)

    def test_application_can_bind_scrolling_texts_and_runtime_config_returns_them(self):
        scrolling_text = ScrollingText.objects.create(title='大厅公告', tenant=self.tenant, is_active=True)
        ScrollingTextItem.objects.create(
            scrolling_text=scrolling_text,
            order=1,
            zh_text='欢迎光临',
            en_text='Welcome',
        )

        create_response = self.client.post(
            '/api/v1/device-applications/',
            {
                'name': 'Lobby Text App',
                'code': 'lobby-text-app',
                'agentApplicationId': self.agent_application.id,
                'scrollingTextIds': [scrolling_text.id],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data.get('agentApplicationId'), self.agent_application.id)
        self.assertEqual(create_response.data.get('scrollingTextIds'), [scrolling_text.id])
        application = DeviceApplication.objects.get(code='lobby-text-app', tenant=self.tenant)
        Device.objects.create(
            tenant=self.tenant,
            application=application,
            name='Lobby Text Device',
            code='ANDROID-TEXT-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        activate_response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-TEXT-001'},
            format='json',
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-TEXT-001',
            HTTP_X_REQUEST_ID='req-runtime-config-1',
            HTTP_X_TRACE_ID='trace-runtime-config-1',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        self.assertEqual(config_response['X-Request-ID'], 'req-runtime-config-1')
        self.assertEqual(config_response['X-Trace-ID'], 'trace-runtime-config-1')
        self.assertEqual(config_response.data['requestId'], 'req-runtime-config-1')
        self.assertEqual(config_response.data['traceId'], 'trace-runtime-config-1')
        self.assertEqual(config_response.data['agentApplication']['id'], self.agent_application.id)
        scrolling_texts = config_response.data['resources']['scrollingTexts']
        self.assertEqual(len(scrolling_texts), 1)
        self.assertEqual(scrolling_texts[0]['title'], '大厅公告')
        self.assertEqual(scrolling_texts[0]['items'][0]['zh'], '欢迎光临')

    def test_device_can_bind_tts_voice_and_runtime_config_returns_current_voice(self):
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        other_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Dylan')
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=other_voice)

        create_response = self.client.post(
            '/api/v1/device-applications/',
            {
                'name': 'Lobby Voice App',
                'code': 'lobby-voice-app',
                'agentApplicationId': self.agent_application.id,
                'voiceToneIds': [other_voice.id],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data.get('voiceToneIds'), [other_voice.id])
        application = DeviceApplication.objects.get(code='lobby-voice-app', tenant=self.tenant)
        Device.objects.create(
            tenant=self.tenant,
            application=application,
            tts_voice=voice,
            tts_voice_config={'speech_rate': 1.35, 'pitch_rate': 0.9, 'volume': 72},
            name='Lobby Voice Device',
            code='ANDROID-VOICE-CONFIG-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-VOICE-CONFIG-001',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        voice_tones = config_response.data['resources']['voiceTones']
        self.assertEqual(len(voice_tones), 1)
        self.assertEqual(voice_tones[0]['id'], voice.id)
        self.assertEqual(voice_tones[0]['name'], 'Cherry')
        self.assertEqual(voice_tones[0]['voiceCode'], 'Cherry')
        self.assertEqual(voice_tones[0]['speechRate'], 1.35)
        self.assertEqual(voice_tones[0]['pitchRate'], 0.9)
        self.assertEqual(voice_tones[0]['volume'], 72)

    def test_runtime_config_uses_company_default_voice_when_device_has_no_voice(self):
        tts_provider = TTSProvider.objects.get(code='aliyun')
        default_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Dylan')
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=default_voice)
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Default Voice Device',
            code='ANDROID-DEFAULT-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-DEFAULT-VOICE-001',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        voice_tones = config_response.data['resources']['voiceTones']
        self.assertEqual(len(voice_tones), 1)
        self.assertEqual(voice_tones[0]['id'], default_voice.id)
        self.assertEqual(voice_tones[0]['voiceCode'], 'Dylan')

    def test_realtime_tts_voice_resolution_uses_device_voice_before_default_voice(self):
        tts_provider = TTSProvider.objects.get(code='aliyun')
        device_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        default_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Dylan')
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=default_voice)
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            tts_voice=device_voice,
            name='Realtime Device Voice',
            code='ANDROID-REALTIME-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        resolved_voice = realtime_tts.resolve_tts_voice(
            {
                'device_id': device.id,
                'device_code': device.code,
                'tenant_id': self.tenant.id,
                'is_superuser': False,
            },
            None,
            tts_provider,
        )

        self.assertEqual(resolved_voice.id, device_voice.id)

    @patch('apps.devices.views.publish_device_event_sync')
    def test_device_voice_update_publishes_full_runtime_config_change_event(self, mock_publish):
        self.agent_application.publish()
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Voice Device',
            code='ANDROID-VOICE-UPDATE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        with self.captureOnCommitCallbacks(execute=True):
            update_response = self.client.patch(
                f'/api/v1/devices/{device.code}/',
                {
                    'voiceToneId': voice.id,
                    'voiceToneConfig': {
                        'speechRate': 1.25,
                        'pitchRate': 0.85,
                        'volume': 66,
                    },
                },
                format='json',
            )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['voiceToneId'], voice.id)
        self.assertEqual(update_response.data['voiceToneCode'], 'Cherry')
        self.assertEqual(update_response.data['voiceToneConfig']['speechRate'], 1.25)
        self.assertEqual(update_response.data['voiceToneConfig']['pitchRate'], 0.85)
        self.assertEqual(update_response.data['voiceToneConfig']['volume'], 66)
        mock_publish.assert_called_once()
        payload = mock_publish.call_args.args[0]
        self.assertEqual(payload['type'], 'device.voice_configuration.changed')
        self.assertEqual(payload['action'], 'voiceConfigurationChanged')
        self.assertEqual(payload['deviceCode'], device.code)
        self.assertEqual(payload['deviceCodes'], [device.code])
        self.assertEqual(payload['refresh']['endpoint'], '/api/v1/device-runtime/config/')

        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            format='json',
            HTTP_X_DEVICE_CODE=device.code,
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        voice_tones = config_response.data['resources']['voiceTones']
        self.assertEqual(len(voice_tones), 1)
        self.assertEqual(voice_tones[0]['id'], voice.id)
        self.assertEqual(voice_tones[0]['voiceCode'], 'Cherry')
        self.assertEqual(voice_tones[0]['speechRate'], 1.25)
        self.assertEqual(voice_tones[0]['pitchRate'], 0.85)
        self.assertEqual(voice_tones[0]['volume'], 66)

    def test_websocket_device_voice_bind_binds_voice_from_android_voice_object(self):
        self.agent_application.publish()
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='WS Voice Bind Device',
            code='ANDROID-WS-VOICE-BIND-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {'type': 'websocket', 'path': '/ws/realtime/', 'query_string': b'', 'headers': []},
            )
            await communicator.send_input({'type': 'websocket.connect'})
            self.assertEqual((await communicator.receive_output(timeout=1))['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.voice.bind',
                    'id': 'voice-bind-1',
                    'payload': {
                        'deviceCode': device.code,
                        'voice': {
                            'id': voice.id,
                            'name': voice.display_name,
                            'voiceCode': voice.voice_code,
                            'audioUrl': '',
                            'iconUrl': voice.avatar_path,
                            'speechRate': 1.45,
                            'pitchRate': 0.75,
                            'volume': 88,
                        },
                    },
                }),
            })
            response = await communicator.receive_output(timeout=1)
            payload = json.loads(response['text'])
            self.assertEqual(payload['type'], 'device.voice.bound')
            self.assertEqual(payload['id'], 'voice-bind-1')
            self.assertEqual(payload['payload']['deviceCode'], device.code)
            self.assertEqual(payload['payload']['voiceId'], voice.id)
            self.assertEqual(payload['payload']['voiceCode'], 'Cherry')
            self.assertEqual(payload['payload']['voiceConfig']['speechRate'], 1.45)
            self.assertEqual(payload['payload']['voiceConfig']['pitchRate'], 0.75)
            self.assertEqual(payload['payload']['voiceConfig']['volume'], 88)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertEqual(device.tts_voice_id, voice.id)
        self.assertEqual(device.tts_voice_config['speech_rate'], 1.45)
        self.assertEqual(device.tts_voice_config['pitch_rate'], 0.75)
        self.assertEqual(device.tts_voice_config['volume'], 88)

    def test_websocket_device_voice_bind_with_null_voice_unbinds(self):
        self.agent_application.publish()
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            tts_voice=voice,
            tts_voice_config={'speech_rate': 1.2, 'pitch_rate': 0.8, 'volume': 60},
            name='WS Voice Unbind Device',
            code='ANDROID-WS-VOICE-UNBIND-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {'type': 'websocket', 'path': '/ws/realtime/', 'query_string': b'', 'headers': []},
            )
            await communicator.send_input({'type': 'websocket.connect'})
            self.assertEqual((await communicator.receive_output(timeout=1))['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.voice.bind',
                    'id': 'voice-unbind-1',
                    'payload': {'deviceCode': device.code, 'voice': None},
                }),
            })
            response = await communicator.receive_output(timeout=1)
            payload = json.loads(response['text'])
            self.assertEqual(payload['type'], 'device.voice.bound')
            self.assertEqual(payload['payload']['voiceId'], None)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertIsNone(device.tts_voice_id)
        self.assertEqual(device.tts_voice_config, {})

    def test_websocket_device_voice_bind_rejects_inactive_voice(self):
        self.agent_application.publish()
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        voice.is_active = False
        voice.save(update_fields=['is_active'])
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='WS Voice Inactive Device',
            code='ANDROID-WS-VOICE-INACTIVE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {'type': 'websocket', 'path': '/ws/realtime/', 'query_string': b'', 'headers': []},
            )
            await communicator.send_input({'type': 'websocket.connect'})
            self.assertEqual((await communicator.receive_output(timeout=1))['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.voice.bind',
                    'id': 'voice-inactive-1',
                    'payload': {'deviceCode': device.code, 'voice': {'id': voice.id}},
                }),
            })
            response = await communicator.receive_output(timeout=1)
            payload = json.loads(response['text'])
            self.assertEqual(payload['type'], 'error')
            self.assertEqual(payload['id'], 'voice-inactive-1')
            self.assertEqual(payload['error']['code'], 'voice_not_found')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertIsNone(device.tts_voice_id)

    def test_runtime_resources_post_returns_bound_application_resource_slices_by_device_code(self):
        self.application.agent_application = self.agent_application
        self.application.save(update_fields=['agent_application', 'updated_at'])
        image = Resource.objects.create(
            tenant=self.tenant,
            name='Lobby Background',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            cloud_url='https://cdn.example.com/bg.jpg',
        )
        video = Resource.objects.create(
            tenant=self.tenant,
            name='Welcome Video',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_VERTICAL,
            cloud_url='https://cdn.example.com/welcome.mp4',
        )
        model = ModelAsset.objects.create(
            tenant=self.tenant,
            name='Digital Human A',
            model_type=ModelAsset.TYPE_FEMALE,
            orientation=ModelAsset.ORIENTATION_VERTICAL,
            cloud_url='https://cdn.example.com/model.glb',
        )
        tts_provider = TTSProvider.objects.get(code='aliyun')
        voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        self.application.resources.add(image, video)
        self.application.model_assets.add(model)
        self.application.tts_voices.add(voice)
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            tts_voice=voice,
            name='Runtime Resource Device',
            code='ANDROID-RUNTIME-RESOURCES-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        response = self.client.post(
            '/api/v1/device-runtime/resources/',
            {'resourceType': 'voiceTones'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-RUNTIME-RESOURCES-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resourceType'], 'voiceTones')
        self.assertEqual(response.data['items'][0]['voiceCode'], 'Cherry')
        self.assertNotIn('device', response.data)
        self.assertNotIn('application', response.data)
        self.assertNotIn('agentApplication', response.data)
        self.assertNotIn('resourcesSummary', response.data)

        resource_expectations = {
            'images': 'https://cdn.example.com/bg.jpg',
            'models': 'https://cdn.example.com/model.glb',
            'videos': 'https://cdn.example.com/welcome.mp4',
        }
        for resource_type, expected_url in resource_expectations.items():
            with self.subTest(resource_type=resource_type):
                slice_response = self.client.post(
                    '/api/v1/device-runtime/resources/',
                    {'resourceType': resource_type},
                    format='json',
                    HTTP_X_DEVICE_CODE='ANDROID-RUNTIME-RESOURCES-001',
                )
                self.assertEqual(slice_response.status_code, status.HTTP_200_OK)
                self.assertEqual(slice_response.data['resourceType'], resource_type)
                self.assertEqual(slice_response.data['items'][0]['url'], expected_url)

        application_response = self.client.post(
            '/api/v1/device-runtime/resources/',
            {'resourceType': 'application'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-RUNTIME-RESOURCES-001',
        )
        self.assertEqual(application_response.status_code, status.HTTP_200_OK)
        self.assertEqual(application_response.data['application']['name'], 'Lobby App')
        self.assertEqual(application_response.data['agentApplication']['name'], 'Lobby Agent')
        self.assertEqual(application_response.data['agentApplication']['openingMessage'], self.agent_application.opening_message)
        self.assertEqual(application_response.data['agentApplication']['suggestedQuestions'], self.agent_application.suggested_questions)
        self.assertEqual(len(application_response.data['resources']['voiceTones']), 1)

    def test_runtime_resource_slices_read_resource_management_records_by_tenant(self):
        self.application.agent_application = self.agent_application
        self.application.save(update_fields=['agent_application', 'updated_at'])
        other_tenant = Tenant.objects.create(name='Other Company', code='other-runtime-company')
        Resource.objects.create(
            tenant=other_tenant,
            name='Other Background',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            cloud_url='https://cdn.example.com/other-bg.jpg',
        )
        ScrollingText.objects.create(
            tenant=other_tenant,
            title='Other Notice',
            is_active=True,
        )
        image = Resource.objects.create(
            tenant=self.tenant,
            name='Managed Background',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            cloud_url='https://cdn.example.com/managed-bg.jpg',
        )
        video = Resource.objects.create(
            tenant=self.tenant,
            name='Managed Video',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_VERTICAL,
            cloud_url='https://cdn.example.com/managed-video.mp4',
        )
        model = ModelAsset.objects.create(
            tenant=self.tenant,
            name='Managed Digital Human',
            model_type=ModelAsset.TYPE_FEMALE,
            orientation=ModelAsset.ORIENTATION_VERTICAL,
            cloud_url='https://cdn.example.com/managed-model.glb',
        )
        scrolling_text = ScrollingText.objects.create(
            tenant=self.tenant,
            title='Managed Notice',
            is_active=True,
        )
        ScrollingTextItem.objects.create(
            scrolling_text=scrolling_text,
            order=1,
            zh_text='欢迎参观',
            en_text='Welcome',
        )
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            name='Runtime Managed Resource Device',
            code='ANDROID-RUNTIME-MANAGED-RESOURCES-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        expectations = {
            'images': (image.id, 'https://cdn.example.com/managed-bg.jpg'),
            'models': (model.id, 'https://cdn.example.com/managed-model.glb'),
            'videos': (video.id, 'https://cdn.example.com/managed-video.mp4'),
        }
        for resource_type, (expected_id, expected_url) in expectations.items():
            with self.subTest(resource_type=resource_type):
                response = self.client.post(
                    '/api/v1/device-runtime/resources/',
                    {'resourceType': resource_type},
                    format='json',
                    HTTP_X_DEVICE_CODE='ANDROID-RUNTIME-MANAGED-RESOURCES-001',
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['items'][0]['id'], expected_id)
                self.assertEqual(response.data['items'][0]['url'], expected_url)
                self.assertEqual(len(response.data['items']), 1)

        text_response = self.client.post(
            '/api/v1/device-runtime/resources/',
            {'resourceType': 'scrollingTexts'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-RUNTIME-MANAGED-RESOURCES-001',
        )

        self.assertEqual(text_response.status_code, status.HTTP_200_OK)
        self.assertEqual(text_response.data['items'][0]['id'], scrolling_text.id)
        self.assertEqual(text_response.data['items'][0]['title'], 'Managed Notice')
        self.assertEqual(text_response.data['items'][0]['items'][0]['zh'], '欢迎参观')
        self.assertEqual(len(text_response.data['items']), 1)

    def test_device_voice_chat_path_exists_without_trailing_slash(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Device',
            code='ANDROID-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        response = self.client.post(
            '/api/v1/device/voice-chat',
            {'text': '你好'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-VOICE-001',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('绑定智能体配置可用 LLM 模型', response.data['message'])

    def test_device_voice_chat_accepts_pcm_audio_for_bound_device(self):
        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'llm_provider', 'model_name', 'updated_at'])
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        TenantLLMSettings.objects.create(tenant=self.tenant, default_model=model)
        tts_provider, _ = TTSProvider.objects.update_or_create(
            code='aliyun',
            defaults={
                'name': 'Aliyun TTS',
                'api_key': 'tts-secret',
                'base_url': 'wss://tts.example/realtime',
                'model': 'tts-model',
                'is_active': True,
            },
        )
        voice = TTSVoice.objects.create(
            provider=tts_provider,
            display_name='默认音色',
            voice_code='voice-001',
            is_active=True,
            is_visible=True,
        )
        tts_provider.default_voice = voice
        tts_provider.save(update_fields=['default_voice'])
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Device',
            code='ANDROID-VOICE-002',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        captured_messages = []

        def fake_run_llm_chat_completion(**kwargs):
            captured_messages.append(kwargs['messages'])
            return '欢迎来到数字人展厅。'

        with (
            patch('apps.devices.views.asr_services.transcribe_pcm_audio', return_value='介绍一下展厅'),
            patch('apps.devices.views.llm_services.run_llm_chat_completion', fake_run_llm_chat_completion),
            patch('apps.devices.views.tts_services.synthesize_tts_pcm', return_value=b'\x01\x02'),
        ):
            response = self.client.post(
                '/api/v1/device/voice-chat',
                {
                    'format': 'pcm',
                    'sampleRate': '16000',
                    'audio': SimpleUploadedFile('voice.pcm', b'\x00\x01\x00\x01', content_type='application/octet-stream'),
                },
                format='multipart',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-002',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(captured_messages), 1)
        system_prompt = captured_messages[0][0]['content']
        self.assertEqual(system_prompt, '你是大厅数字人。')
        self.assertNotIn('Lobby Agent', system_prompt)
        self.assertNotIn('Lobby App', system_prompt)
        self.assertNotIn('Voice Device', system_prompt)
        self.assertEqual(response.data['questionText'], '介绍一下展厅')
        self.assertEqual(response.data['answerText'], '欢迎来到数字人展厅。')
        self.assertTrue(response.data['audioBase64'])
        chat_log = DeviceChatLog.objects.get(code='ANDROID-VOICE-002')
        self.assertEqual(chat_log.source, DeviceChatLog.SOURCE_HTTP)
        self.assertEqual(chat_log.tenant, self.tenant)
        self.assertEqual(chat_log.application, self.application)
        self.assertEqual(chat_log.agent_application, self.agent_application)
        self.assertEqual(chat_log.question_text, '介绍一下展厅')
        self.assertEqual(chat_log.answer_text, '欢迎来到数字人展厅。')
        self.assertEqual(chat_log.model_name, 'qwen/qwen3-32b')

    def test_device_voice_chat_uses_bound_device_voice_before_company_default(self):
        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'updated_at'])
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        TenantLLMSettings.objects.create(tenant=self.tenant, default_model=model)
        tts_provider = TTSProvider.objects.get(code='aliyun')
        default_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Cherry')
        device_voice = TTSVoice.objects.get(provider=tts_provider, voice_code='Elias')
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=default_voice)
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Bound Device',
            code='ANDROID-VOICE-BOUND-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
            tts_voice=device_voice,
        )

        with (
            patch('apps.devices.views.llm_services.run_llm_chat_completion', return_value='设备绑定音色回答'),
            patch('apps.devices.views.tts_services.synthesize_tts_pcm', return_value=b'\x01\x02') as synthesize_tts_pcm,
        ):
            response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '使用哪个音色？'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-BOUND-001',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['voice'].id, device_voice.id)
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['voice'].voice_code, 'Elias')

    def test_device_voice_chat_generates_server_session_id_before_first_turn_and_reuses_history(self):
        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'updated_at'])
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Device',
            code='ANDROID-VOICE-SESSION-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        captured_messages = []

        def fake_run_llm_chat_completion(**kwargs):
            captured_messages.append([dict(message) for message in kwargs['messages']])
            return '第一轮回答' if len(captured_messages) == 1 else '第二轮回答'

        with (
            patch('apps.devices.views.llm_services.run_llm_chat_completion', fake_run_llm_chat_completion),
            patch.object(DeviceVoiceChatView, '_synthesize_answer_audio', return_value=''),
        ):
            first_response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '介绍一下展厅'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-SESSION-001',
            )
            returned_session_id = first_response.data.get('sessionId')
            second_response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '继续介绍', 'sessionId': returned_session_id},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-SESSION-001',
            )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertTrue(returned_session_id)
        self.assertNotEqual(returned_session_id, 'None')
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data['sessionId'], returned_session_id)
        self.assertEqual(len(captured_messages), 2)
        self.assertEqual(captured_messages[0][-1], {'role': 'user', 'content': '介绍一下展厅'})
        self.assertIn({'role': 'user', 'content': '介绍一下展厅'}, captured_messages[1])
        self.assertIn({'role': 'assistant', 'content': '第一轮回答'}, captured_messages[1])
        self.assertEqual(captured_messages[1][-1], {'role': 'user', 'content': '继续介绍'})
        self.assertEqual(
            set(
                DeviceChatLog.objects
                .filter(code='ANDROID-VOICE-SESSION-001')
                .values_list('runtime_session_id', flat=True)
            ),
            {returned_session_id},
        )

    def test_device_voice_chat_returns_media_annotation_blocks_with_absolute_urls(self):
        image = Resource.objects.create(
            tenant=self.tenant,
            resource_type=Resource.TYPE_IMAGE,
            name='展厅图片',
            category=Resource.CATEGORY_HORIZONTAL,
            file=SimpleUploadedFile('hall.png', b'image-content', content_type='image/png'),
        )
        video = Resource.objects.create(
            tenant=self.tenant,
            resource_type=Resource.TYPE_VIDEO,
            name='展厅视频',
            category=Resource.CATEGORY_HORIZONTAL,
            file=SimpleUploadedFile('hall.mp4', b'video-content', content_type='video/mp4'),
        )
        AgentAnnotation.objects.create(
            tenant=self.tenant,
            application=self.agent_application,
            question='展示素材',
            answer='这是展厅素材',
            answer_blocks=[
                {'type': 'text', 'text': '这是展厅素材'},
                {'type': 'image', 'resourceId': image.id},
                {'type': 'video', 'resourceId': video.id},
            ],
            created_by=self.user,
        )
        self.agent_application.publish()
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Device',
            code='ANDROID-MEDIA-ANNOTATION-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        with (
            patch.object(DeviceVoiceChatView, '_synthesize_answer_audio', return_value=''),
            patch('apps.devices.views.record_device_chat_log', return_value=None),
        ):
            response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '展示素材'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-MEDIA-ANNOTATION-001',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['answerText'], '这是展厅素材')
        self.assertEqual(response.data['answerBlocks'][0], {'type': 'text', 'text': '这是展厅素材'})
        image_block = response.data['answerBlocks'][1]
        video_block = response.data['answerBlocks'][2]
        self.assertEqual(image_block['type'], 'image')
        self.assertEqual(image_block['resourceId'], image.id)
        self.assertEqual(image_block['resourceName'], '展厅图片')
        self.assertTrue(image_block['url'].startswith('http://testserver/media/'))
        self.assertFalse(image_block['missing'])
        self.assertEqual(video_block['type'], 'video')
        self.assertEqual(video_block['resourceId'], video.id)
        self.assertEqual(video_block['resourceName'], '展厅视频')
        self.assertTrue(video_block['url'].startswith('http://testserver/media/'))
        self.assertFalse(video_block['missing'])

    def test_device_voice_chat_third_party_backend_keeps_android_response_shape(self):
        chatbot = self.create_third_party_chatbot()
        self.agent_application.runtime_backend_type = 'third_party_chatbot'
        self.agent_application.third_party_chatbot = chatbot
        self.agent_application.save(update_fields=['runtime_backend_type', 'third_party_chatbot', 'updated_at'])
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Third-party Voice Device',
            code='ANDROID-THIRD-PARTY-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        with patch(
            'apps.devices.views.third_party_chatbots.send_chatbot_message',
            return_value='第三方机器人回答',
        ) as send_chatbot_message:
            response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '介绍一下展厅', 'sessionId': 'android-session-1'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-THIRD-PARTY-VOICE-001',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sessionId'], 'android-session-1')
        self.assertEqual(response.data['answerText'], '第三方机器人回答')
        self.assertEqual(response.data['answerBlocks'], [{'type': 'text', 'text': '第三方机器人回答'}])
        self.assertNotIn('chat_id', str(response.data))
        send_chatbot_message.assert_called_once()

    def test_device_voice_chat_third_party_backend_reuses_runtime_conversation(self):
        chatbot = self.create_third_party_chatbot()
        self.agent_application.runtime_backend_type = 'third_party_chatbot'
        self.agent_application.third_party_chatbot = chatbot
        self.agent_application.save(update_fields=['runtime_backend_type', 'third_party_chatbot', 'updated_at'])
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Third-party Voice Device',
            code='ANDROID-THIRD-PARTY-VOICE-002',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        conversations = []

        def fake_send_chatbot_message(*args, **kwargs):
            conversations.append(kwargs.get('conversation'))
            return '第三方机器人回答'

        with patch('apps.devices.views.third_party_chatbots.send_chatbot_message', fake_send_chatbot_message):
            first_response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '一句话介绍你自己。'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-THIRD-PARTY-VOICE-002',
            )
            returned_session_id = first_response.data.get('sessionId')
            second_response = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': '我问了你什么问题？', 'sessionId': returned_session_id},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-THIRD-PARTY-VOICE-002',
            )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data['sessionId'], returned_session_id)
        self.assertEqual(len(conversations), 2)
        self.assertIsNotNone(conversations[0])
        self.assertEqual(conversations[0].id, conversations[1].id)
        conversation = ChatConversation.objects.get(pk=conversations[0].id)
        self.assertEqual(conversation.external_session.get('runtimeSessionId'), returned_session_id)
        self.assertEqual(conversation.third_party_chatbot_id, chatbot.id)

    def test_device_voice_chat_uses_published_agent_knowledge_base(self):
        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'updated_at'])
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)

        kb_a = KnowledgeBase.objects.create(tenant=self.tenant, name='A 知识库', created_by=self.user)
        doc_a = KnowledgeDocument.objects.create(
            tenant=self.tenant,
            knowledge_base=kb_a,
            uploaded_by=self.user,
            title='A 文档',
        )
        doc_a.file.save('a.txt', ContentFile(b'A knowledge answer: old hall.'))
        KnowledgeDocumentChunk.objects.create(
            tenant=self.tenant,
            document=doc_a,
            chunk_index=0,
            content='same question answer is A old hall',
            content_hash='a' * 64,
            embedding_model='keyword',
        )
        kb_b = KnowledgeBase.objects.create(tenant=self.tenant, name='B 知识库', created_by=self.user)
        doc_b = KnowledgeDocument.objects.create(
            tenant=self.tenant,
            knowledge_base=kb_b,
            uploaded_by=self.user,
            title='B 文档',
        )
        doc_b.file.save('b.txt', ContentFile(b'B knowledge answer: new hall.'))
        KnowledgeDocumentChunk.objects.create(
            tenant=self.tenant,
            document=doc_b,
            chunk_index=0,
            content='same question answer is B new hall',
            content_hash='b' * 64,
            embedding_model='keyword',
        )
        self.agent_application.knowledge_bases.set([kb_a])
        self.agent_application.publish()
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Voice Device',
            code='ANDROID-VOICE-KB-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        captured_messages = []

        def fake_run_llm_chat_completion(**kwargs):
            captured_messages.append(kwargs['messages'])
            return '知识库回答'

        with patch('apps.devices.views.llm_services.run_llm_chat_completion', fake_run_llm_chat_completion):
            response_a = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': 'same question'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-KB-001',
            )
            self.agent_application.knowledge_bases.set([kb_b])
            response_draft_b = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': 'same question'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-KB-001',
            )
            self.agent_application.publish()
            response_published_b = self.client.post(
                '/api/v1/device/voice-chat',
                {'text': 'same question'},
                format='json',
                HTTP_X_DEVICE_CODE='ANDROID-VOICE-KB-001',
            )

        self.assertEqual(response_a.status_code, status.HTTP_200_OK)
        self.assertEqual(response_draft_b.status_code, status.HTTP_200_OK)
        self.assertEqual(response_published_b.status_code, status.HTTP_200_OK)
        first_message_text = '\n'.join(item['content'] for item in captured_messages[0])
        draft_message_text = '\n'.join(item['content'] for item in captured_messages[1])
        published_message_text = '\n'.join(item['content'] for item in captured_messages[2])
        self.assertIn('A old hall', first_message_text)
        self.assertNotIn('B new hall', first_message_text)
        self.assertIn('A old hall', draft_message_text)
        self.assertNotIn('B new hall', draft_message_text)
        self.assertIn('B new hall', published_message_text)
        self.assertNotIn('A old hall', published_message_text)

    def test_realtime_agent_memory_key_changes_only_after_publish(self):
        from config.realtime import _agent_memory_key

        kb_a = KnowledgeBase.objects.create(tenant=self.tenant, name='A 知识库', created_by=self.user)
        kb_b = KnowledgeBase.objects.create(tenant=self.tenant, name='B 知识库', created_by=self.user)
        self.agent_application.knowledge_bases.set([kb_a])
        self.agent_application.publish()
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Realtime Device',
            code='ANDROID-REALTIME-KB-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        key_a = _agent_memory_key(device, self.agent_application)
        self.agent_application.knowledge_bases.set([kb_b])
        key_draft_b = _agent_memory_key(device, self.agent_application)
        self.agent_application.publish()
        key_published_b = _agent_memory_key(device, self.agent_application)

        self.assertEqual(key_a, key_draft_b)
        self.assertNotEqual(key_a, key_published_b)

    def test_realtime_llm_session_uses_published_agent_prompt(self):
        from config.realtime import _prepare_device_llm_session

        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.system_prompt = 'A prompt for published runtime.'
        self.agent_application.save(update_fields=['llm_model', 'system_prompt', 'updated_at'])
        self.agent_application.publish()
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Realtime Prompt Device',
            code='ANDROID-REALTIME-PROMPT-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        session_a = _prepare_device_llm_session('ANDROID-REALTIME-PROMPT-001', '你好')
        self.agent_application.system_prompt = 'B prompt draft only.'
        self.agent_application.save(update_fields=['system_prompt', 'updated_at'])
        session_draft_b = _prepare_device_llm_session('ANDROID-REALTIME-PROMPT-001', '你好')
        self.agent_application.publish()
        session_published_b = _prepare_device_llm_session('ANDROID-REALTIME-PROMPT-001', '你好')

        self.assertIn('A prompt for published runtime.', session_a['messages'][0]['content'])
        self.assertIn('A prompt for published runtime.', session_draft_b['messages'][0]['content'])
        self.assertNotIn('B prompt draft only.', session_draft_b['messages'][0]['content'])
        self.assertIn('B prompt draft only.', session_published_b['messages'][0]['content'])
        self.assertNotIn('Lobby Agent', session_published_b['messages'][0]['content'])
        self.assertNotIn('Lobby App', session_published_b['messages'][0]['content'])
        self.assertNotIn('Realtime Prompt Device', session_published_b['messages'][0]['content'])

    def test_realtime_llm_done_and_chat_logs_include_non_annotation_media_blocks(self):
        from apps.ai_models.models import ChatConversation
        from config.realtime import _run_llm_session_body

        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'updated_at'])
        self.agent_application.publish()
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Realtime Media Device',
            code='ANDROID-REALTIME-MEDIA-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        image = Resource.objects.create(
            tenant=self.tenant,
            resource_type=Resource.TYPE_IMAGE,
            name='展厅图片',
            cloud_url='https://cdn.example.com/hall.jpg',
        )
        video = Resource.objects.create(
            tenant=self.tenant,
            resource_type=Resource.TYPE_VIDEO,
            name='展厅视频',
            cloud_url='https://cdn.example.com/hall.mp4',
        )

        async def fake_stream_llm_chat_completion(**kwargs):
            yield '非标注回答'

        async def run_llm():
            messages = []

            async def send(event):
                messages.append(json.loads(event['text']))

            await _run_llm_session_body(
                send,
                'android-llm-media',
                {
                    'id': 'android-llm-media',
                    'payload': {
                        'deviceCode': 'ANDROID-REALTIME-MEDIA-001',
                        'text': '请展示展厅素材',
                        'requestId': 'req-realtime-media',
                        'traceId': 'trace-realtime-media',
                    },
                },
            )
            return messages

        self.assertEqual(ChatConversation.objects.count(), 0)

        with (
            patch(
                'apps.ai_models.services.agent_knowledge.retrieve_knowledge_context_with_media',
                return_value=(
                    '素材上下文',
                    [
                        {'type': 'image', 'resourceId': image.id},
                        {'type': 'video', 'resourceId': video.id},
                    ],
                ),
            ),
            patch('config.realtime.llm_services.stream_llm_chat_completion', new=fake_stream_llm_chat_completion),
        ):
            messages = async_to_sync(run_llm)()

        done = next(item for item in messages if item['type'] == 'llm.done')
        answer_blocks = done['payload']['answerBlocks']
        self.assertEqual(answer_blocks[0], {'type': 'text', 'text': '非标注回答'})
        self.assertEqual(answer_blocks[1]['type'], 'image')
        self.assertEqual(answer_blocks[1]['resourceId'], image.id)
        self.assertEqual(answer_blocks[1]['resourceName'], '展厅图片')
        self.assertEqual(answer_blocks[1]['url'], 'https://cdn.example.com/hall.jpg')
        self.assertFalse(answer_blocks[1]['missing'])
        self.assertEqual(answer_blocks[2]['type'], 'video')
        self.assertEqual(answer_blocks[2]['resourceId'], video.id)
        self.assertEqual(answer_blocks[2]['resourceName'], '展厅视频')
        self.assertEqual(answer_blocks[2]['url'], 'https://cdn.example.com/hall.mp4')
        self.assertFalse(answer_blocks[2]['missing'])

        chat_log = DeviceChatLog.objects.get(request_id='req-realtime-media')
        self.assertIsNone(chat_log.conversation_id)
        self.assertEqual(chat_log.answer_blocks, answer_blocks)
        self.assertEqual(ChatConversation.objects.count(), 0)

        response = self.client.get('/api/v1/devices/chat-logs/', {'agentApplicationId': self.agent_application.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['answerBlocks'], answer_blocks)

    def test_device_chat_logs_endpoint_filters_by_agent_application(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Chat Log Device',
            code='ANDROID-CHAT-LOG-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        other_agent = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Other Agent',
            system_prompt='其它智能体。',
        )
        DeviceChatLog.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            device=device,
            code=device.code,
            source=DeviceChatLog.SOURCE_WEBSOCKET,
            question_text='运行时问题',
            answer_text='运行时回答',
            request_id='req-chat-log',
            trace_id='trace-chat-log',
            model_name='runtime-model',
        )
        DeviceChatLog.objects.create(
            tenant=self.tenant,
            agent_application=other_agent,
            code='ANDROID-OTHER-CHAT-LOG-001',
            source=DeviceChatLog.SOURCE_WEBSOCKET,
            question_text='其它问题',
            answer_text='其它回答',
        )

        response = self.client.get('/api/v1/devices/chat-logs/', {'agentApplicationId': self.agent_application.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['code'], 'ANDROID-CHAT-LOG-001')
        self.assertEqual(response.data['results'][0]['questionText'], '运行时问题')
        self.assertEqual(response.data['results'][0]['answerText'], '运行时回答')
        self.assertEqual(response.data['results'][0]['agentApplicationId'], self.agent_application.id)

    def test_activate_updates_bound_device_by_device_code(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Old Name',
            code='ANDROID-BOARD-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {
                'deviceCode': 'ANDROID-BOARD-001',
                'deviceName': 'Lobby Android',
                'softwareVersion': '1.2.3',
                'systemVersion': 'Android 14',
                'mainboardInfo': 'rk3588',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('token', response.data)
        self.assertEqual(response.data['bindingStatus'], 'bound')
        device = Device.objects.get(code='ANDROID-BOARD-001', tenant=self.tenant)
        self.assertEqual(device.application_id, self.application.id)
        self.assertEqual(device.name, 'Old Name')
        self.assertEqual(device.software_version, '1.2.3')
        self.assertEqual(device.system_version, 'Android 14')
        self.assertEqual(device.mainboard_info, 'rk3588')
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_PERMANENT)

    def test_activate_accepts_device_code_from_header(self):
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {
                'softwareVersion': 'runtime-api-console-html',
                'systemVersion': 'Android 14',
                'mainboardInfo': 'rk3588',
            },
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-HEADER-ACTIVATE-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bindingStatus'], 'pending')
        device = Device.objects.get(code='ANDROID-HEADER-ACTIVATE-001')
        self.assertIsNone(device.tenant_id)
        self.assertEqual(device.software_version, 'runtime-api-console-html')
        self.assertEqual(device.system_version, 'Android 14')
        self.assertEqual(device.mainboard_info, 'rk3588')

    def test_activate_company_bound_device_without_agent_reports_bound(self):
        Device.objects.create(
            tenant=self.tenant,
            name='Company Bound Device',
            code='ANDROID-COMPANY-BOUND-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-COMPANY-BOUND-001'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bindingStatus'], 'bound')
        self.assertIsNone(response.data['device']['applicationId'])
        self.assertIsNone(response.data['device']['agentApplicationId'])

    def test_activate_unknown_device_creates_pending_device(self):
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-NEW-001'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bindingStatus'], 'pending')
        device = Device.objects.get(code='ANDROID-NEW-001')
        self.assertIsNone(device.tenant_id)
        self.assertIsNone(device.application_id)
        self.assertEqual(device.name, '待修改')

    def test_activate_ignores_android_supplied_device_name(self):
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-NAME-001', 'deviceName': 'Android Supplied Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device = Device.objects.get(code='ANDROID-NAME-001')
        self.assertEqual(device.name, '待修改')

    def test_activate_same_device_code_is_repeatable(self):
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-001', 'deviceName': 'First Name'},
            format='json',
        )
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-001', 'deviceName': 'Second Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Device.objects.filter(code='ANDROID-001').count(), 1)
        self.assertEqual(Device.objects.get(code='ANDROID-001').name, '待修改')

    def test_device_list_filters_by_name_and_device_code(self):
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Lobby')
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            group=group,
            name='Lobby Android',
            code='ANDROID-BOARD-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Meeting Room',
            code='ANDROID-BOARD-002',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        by_name = self.client.get('/api/v1/devices/', {'keyword': 'Lobby'})
        by_code = self.client.get('/api/v1/devices/', {'keyword': '002'})

        self.assertEqual(by_name.status_code, status.HTTP_200_OK)
        self.assertEqual([item['deviceCode'] for item in by_name.data['results']], ['ANDROID-BOARD-001'])
        self.assertEqual(by_code.status_code, status.HTTP_200_OK)
        self.assertEqual([item['deviceCode'] for item in by_code.data['results']], ['ANDROID-BOARD-002'])

    def test_device_list_filters_by_enabled_status(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Normal Android',
            code='ANDROID-NORMAL-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            is_enabled=True,
            registered_at=timezone.now(),
        )
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Disabled Android',
            code='ANDROID-DISABLED-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            is_enabled=False,
            registered_at=timezone.now(),
        )

        enabled_response = self.client.get('/api/v1/devices/', {'enabledStatus': 'enabled'})
        disabled_response = self.client.get('/api/v1/devices/', {'enabledStatus': 'disabled'})

        self.assertEqual(enabled_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['deviceCode'] for item in enabled_response.data['results']], ['ANDROID-NORMAL-001'])
        self.assertEqual(disabled_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['deviceCode'] for item in disabled_response.data['results']], ['ANDROID-DISABLED-001'])

    def test_device_patch_updates_application_but_ignores_agent_binding(self):
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Lobby')
        next_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Meeting App',
            code='meeting-app',
        )
        next_agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Meeting Agent',
            system_prompt='你是会议室数字人。',
        )
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Old Name',
            code='ANDROID-BOARD-001',
            software_version='1.0.0',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        response = self.client.patch(
            f'/api/v1/devices/{device.code}/',
            {
                'name': 'New Name',
                'location': 'New Location',
                'groupId': group.id,
                'applicationId': next_application.id,
                'agentApplicationId': next_agent_application.id,
                'deviceCode': 'SHOULD-NOT-CHANGE',
                'softwareVersion': '9.9.9',
                'authorizationType': Device.AUTHORIZATION_TRIAL,
                'expiresAt': (timezone.now() + timedelta(days=1)).isoformat(),
                'isEnabled': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.name, 'New Name')
        self.assertEqual(device.location, 'New Location')
        self.assertEqual(device.group_id, group.id)
        self.assertEqual(device.application_id, next_application.id)
        self.assertEqual(device.agent_application_id, self.agent_application.id)
        self.assertEqual(device.code, 'ANDROID-BOARD-001')
        self.assertEqual(device.software_version, '1.0.0')
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_PERMANENT)
        self.assertIsNone(device.expires_at)
        self.assertTrue(device.is_enabled)

    def test_device_name_update_is_reflected_in_runtime_config(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Old Name',
            code='ANDROID-CONFIG-NAME-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        update_response = self.client.patch(
            f'/api/v1/devices/{device.code}/',
            {'name': 'New Runtime Name'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['name'], 'New Runtime Name')

        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            HTTP_X_DEVICE_CODE='ANDROID-CONFIG-NAME-001',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        self.assertEqual(config_response.data['device']['name'], 'New Runtime Name')
        self.assertEqual(config_response.data['device']['deviceCode'], 'ANDROID-CONFIG-NAME-001')

    def test_device_group_can_be_deleted(self):
        self.grant_permissions('devices.view', 'devices.create', 'devices.update', 'devices.delete')
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Temporary Group')

        response = self.client.delete(f'/api/v1/device-groups/{group.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeviceGroup.objects.filter(id=group.id).exists())

    def test_activation_request_appears_in_superuser_request_list(self):
        activate_response = self.client.post(
            '/api/v1/device-auth/activate/',
            {
                'deviceCode': 'ANDROID-PENDING-001',
                'deviceName': 'Pending Android',
                'softwareVersion': '1.0.9',
                'systemVersion': 'Android 14',
                'mainboardInfo': 'rk3588',
            },
            format='json',
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

        superuser = User.objects.create_superuser(
            username='platform-device-admin',
            password='test123456',
            email='platform-device-admin@example.com',
        )
        self.client.force_authenticate(user=superuser)
        response = self.client.get('/api/v1/device-authorization-requests/', {'bindingStatus': 'pending'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [item['deviceCode'] for item in response.data['results']]
        self.assertIn('ANDROID-PENDING-001', codes)
        row = next(item for item in response.data['results'] if item['deviceCode'] == 'ANDROID-PENDING-001')
        self.assertEqual(row['bindingStatus'], 'pending')
        self.assertEqual(row['latestActivationDeviceInfo']['softwareVersion'], '1.0.9')

    def test_superuser_binds_activation_request_to_company_without_company_owned_resources(self):
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-BIND-001', 'deviceName': 'Bind Android'},
            format='json',
        )
        expires_at = timezone.now() + timedelta(days=30)
        superuser = User.objects.create_superuser(
            username='platform-binder',
            password='test123456',
            email='platform-binder@example.com',
        )
        self.client.force_authenticate(user=superuser)
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Front Desk')

        response = self.client.post(
            '/api/v1/device-authorization-requests/ANDROID-BIND-001/bind/',
            {
                'tenantId': self.tenant.id,
                'applicationId': self.application.id,
                'agentApplicationId': self.agent_application.id,
                'groupId': group.id,
                'authorizationType': Device.AUTHORIZATION_TRIAL,
                'expiresAt': expires_at.isoformat(),
                'isEnabled': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tenantId'], self.tenant.id)
        self.assertEqual(response.data['tenantName'], self.tenant.name)
        self.assertEqual(response.data['bindingStatus'], 'bound')
        device = Device.objects.get(code='ANDROID-BIND-001')
        self.assertEqual(device.tenant_id, self.tenant.id)
        self.assertIsNone(device.application_id)
        self.assertIsNone(device.agent_application_id)
        self.assertIsNone(device.group_id)
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_TRIAL)
        self.assertIsNotNone(device.expires_at)

        logs = self.client.get('/api/v1/device-authorization-requests/logs/', {'keyword': 'ANDROID-BIND-001'})
        self.assertEqual(logs.status_code, status.HTTP_200_OK)
        actions = [item['action'] for item in logs.data['results']]
        self.assertIn('bind', actions)

    def test_superuser_updates_authorization_request_device_name(self):
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-RENAME-001'},
            format='json',
        )
        superuser = User.objects.create_superuser(
            username='platform-rename',
            password='test123456',
            email='platform-rename@example.com',
        )
        self.client.force_authenticate(user=superuser)

        response = self.client.patch(
            '/api/v1/device-authorization-requests/ANDROID-RENAME-001/name/',
            {'name': 'Front Desk Android'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Front Desk Android')
        device = Device.objects.get(code='ANDROID-RENAME-001')
        self.assertEqual(device.name, 'Front Desk Android')

    def test_superuser_ignores_activation_request_and_reactivation_restores_pending(self):
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-IGNORE-001', 'deviceName': 'Ignore Android'},
            format='json',
        )
        superuser = User.objects.create_superuser(
            username='platform-ignore',
            password='test123456',
            email='platform-ignore@example.com',
        )
        self.client.force_authenticate(user=superuser)

        ignore_response = self.client.post('/api/v1/device-authorization-requests/ANDROID-IGNORE-001/ignore/')
        self.assertEqual(ignore_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ignore_response.data['bindingStatus'], 'ignored')
        pending_response = self.client.get('/api/v1/device-authorization-requests/', {'bindingStatus': 'pending'})
        pending_codes = [item['deviceCode'] for item in pending_response.data['results']]
        self.assertNotIn('ANDROID-IGNORE-001', pending_codes)

        logs = self.client.get('/api/v1/device-authorization-requests/logs/', {'keyword': 'ANDROID-IGNORE-001'})
        self.assertIn('ignore', [item['action'] for item in logs.data['results']])

        self.client.force_authenticate(user=None)
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-IGNORE-001', 'deviceName': 'Ignore Android Again'},
            format='json',
        )
        self.client.force_authenticate(user=superuser)
        restored = self.client.get('/api/v1/device-authorization-requests/', {'bindingStatus': 'pending'})
        restored_codes = [item['deviceCode'] for item in restored.data['results']]
        self.assertIn('ANDROID-IGNORE-001', restored_codes)

    def test_superuser_reauthorizes_and_revokes_authorized_device(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Authorized Android',
            code='ANDROID-AUTHZ-001',
            status=Device.STATUS_ONLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        superuser = User.objects.create_superuser(
            username='platform-authz',
            password='test123456',
            email='platform-authz@example.com',
        )
        self.client.force_authenticate(user=superuser)

        list_response = self.client.get('/api/v1/device-authorization-requests/authorizations/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertIn(device.code, [item['deviceCode'] for item in list_response.data['results']])

        expires_at = timezone.now() + timedelta(days=10)
        authorize_response = self.client.post(
            f'/api/v1/device-authorization-requests/{device.code}/authorize/',
            {
                'tenantId': self.tenant.id,
                'applicationId': self.application.id,
                'agentApplicationId': self.agent_application.id,
                'authorizationType': Device.AUTHORIZATION_TRIAL,
                'expiresAt': expires_at.isoformat(),
                'isEnabled': True,
            },
            format='json',
        )
        self.assertEqual(authorize_response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_TRIAL)
        self.assertIsNotNone(device.expires_at)

        revoke_response = self.client.post(f'/api/v1/device-authorization-requests/{device.code}/revoke/')
        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertFalse(device.is_enabled)
        self.assertEqual(device.status, Device.STATUS_OFFLINE)
        logs = self.client.get('/api/v1/device-authorization-requests/logs/', {'keyword': device.code})
        actions = [item['action'] for item in logs.data['results']]
        self.assertIn('authorize', actions)
        self.assertIn('revoke', actions)

    def test_heartbeat_updates_last_seen_but_does_not_mark_device_online(self):
        activate_response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-BOARD-001'},
            format='json',
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            '/api/v1/device-runtime/heartbeat/',
            {'deviceCode': 'ANDROID-BOARD-001'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device = Device.objects.get(code='ANDROID-BOARD-001')
        self.assertEqual(device.status, Device.STATUS_OFFLINE)
        self.assertIsNotNone(device.last_heartbeat)

    def test_unified_device_status_command_marks_online_until_disconnect(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='WebSocket Android',
            code='ANDROID-WS-001',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.status.start',
                    'id': 'device-status-1',
                    'payload': {'deviceCode': 'ANDROID-WS-001'},
                }),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(message['text'])['type'], 'device.status.started')

            online_status = await sync_to_async(
                lambda: Device.objects.get(id=device.id).status,
                thread_sensitive=True,
            )()
            self.assertEqual(online_status, Device.STATUS_ONLINE)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertEqual(device.status, Device.STATUS_OFFLINE)

    def test_device_status_command_receives_runtime_config_change_events(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Config Online Android',
            code='ANDROID-RUNTIME-CONFIG-WS-001',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.status.start',
                    'id': 'device-status-runtime-config',
                    'payload': {'deviceCode': device.code},
                }),
            })
            started = json.loads((await communicator.receive_output(timeout=1))['text'])
            self.assertEqual(started['type'], 'device.status.started')

            await publish_device_event(
                {
                    'type': 'device.wake_words.changed',
                    'action': 'wakeWordsChanged',
                    'tenantId': self.tenant.id,
                    'deviceCodes': ['ANDROID-RUNTIME-CONFIG-OTHER'],
                    'refresh': {'endpoint': '/api/v1/device-runtime/config/'},
                }
            )
            await publish_device_event(
                {
                    'type': 'device.wake_words.changed',
                    'action': 'wakeWordsChanged',
                    'tenantId': self.tenant.id,
                    'deviceCodes': [device.code],
                    'refresh': {
                        'endpoint': '/api/v1/device-runtime/config/',
                        'reason': 'wakeWordsChanged',
                    },
                }
            )

            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['type'], 'devices.event')
            self.assertEqual(payload['id'], 'device-status-runtime-config')
            self.assertEqual(payload['payload']['type'], 'device.wake_words.changed')
            self.assertEqual(payload['payload']['deviceCodes'], [device.code])
            self.assertEqual(payload['payload']['refresh']['endpoint'], '/api/v1/device-runtime/config/')
            self.assertNotIn('runtimeConfigByDeviceCode', payload['payload'])

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_llm_session_start_streams_agent_answer_deltas(self):
        provider = LLMProvider.objects.create(
            name='OpenAI compatible',
            provider_type='openai',
            api_base_url='https://example.com/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='qwen/qwen3-32b', is_active=True)
        self.agent_application.llm_model = model
        self.agent_application.save(update_fields=['llm_model', 'updated_at'])
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='LLM WebSocket Android',
            code='ANDROID-LLM-WS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def fake_stream_llm_chat_completion(**kwargs):
            yield '欢迎'
            yield '来到展厅'

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            with patch('config.realtime.llm_services.stream_llm_chat_completion', fake_stream_llm_chat_completion):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'llm.session.start',
                        'id': 'llm-suite-1',
                        'payload': {'deviceCode': 'ANDROID-LLM-WS-001', 'text': '介绍一下展厅'},
                    }),
                })

                started = json.loads((await communicator.receive_output(timeout=1))['text'])
                first_delta = json.loads((await communicator.receive_output(timeout=1))['text'])
                second_delta = json.loads((await communicator.receive_output(timeout=1))['text'])
                tts_segment = json.loads((await communicator.receive_output(timeout=1))['text'])
                done = json.loads((await communicator.receive_output(timeout=1))['text'])

            self.assertEqual(started['type'], 'llm.started')
            self.assertEqual(first_delta['type'], 'llm.delta')
            self.assertEqual(first_delta['payload']['text'], '欢迎')
            self.assertEqual(second_delta['type'], 'llm.delta')
            self.assertEqual(second_delta['payload']['text'], '来到展厅')
            self.assertEqual(tts_segment['type'], 'llm.tts_segment')
            self.assertEqual(tts_segment['payload']['text'], '欢迎来到展厅')
            self.assertEqual(done['type'], 'llm.done')
            self.assertEqual(done['payload']['answerText'], '欢迎来到展厅')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_llm_session_start_uses_third_party_backend_with_existing_event_shape(self):
        chatbot = self.create_third_party_chatbot()
        self.agent_application.runtime_backend_type = 'third_party_chatbot'
        self.agent_application.third_party_chatbot = chatbot
        self.agent_application.save(update_fields=['runtime_backend_type', 'third_party_chatbot', 'updated_at'])
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Third-party WebSocket Android',
            code='ANDROID-THIRD-PARTY-WS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            with patch(
                'config.realtime.third_party_chatbots.send_chatbot_message',
                return_value='第三方 WebSocket 回答',
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'llm.session.start',
                        'id': 'third-party-llm-suite-1',
                        'payload': {'deviceCode': 'ANDROID-THIRD-PARTY-WS-001', 'text': '介绍一下展厅'},
                    }),
                })

                started = json.loads((await communicator.receive_output(timeout=1))['text'])
                delta = json.loads((await communicator.receive_output(timeout=1))['text'])
                tts_segment = json.loads((await communicator.receive_output(timeout=1))['text'])
                done = json.loads((await communicator.receive_output(timeout=1))['text'])

            self.assertEqual(started['type'], 'llm.started')
            self.assertEqual(delta['type'], 'llm.delta')
            self.assertEqual(delta['payload']['text'], '第三方 WebSocket 回答')
            self.assertEqual(tts_segment['type'], 'llm.tts_segment')
            self.assertEqual(done['type'], 'llm.done')
            self.assertEqual(done['payload']['answerText'], '第三方 WebSocket 回答')
            self.assertNotIn('chat_id', str(done))

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_device_events_command_sends_same_tenant_events(self):
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-1',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-WS-EVENT-001',
                    'status': Device.STATUS_ONLINE,
                }
            )
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['type'], 'devices.event')
            self.assertEqual(payload['payload']['deviceCode'], 'ANDROID-WS-EVENT-001')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_device_events_command_filters_other_tenant_events(self):
        other_tenant = Tenant.objects.create(name='Other Company', code='other-company')
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-filter',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': other_tenant.id,
                    'deviceCode': 'ANDROID-OTHER-001',
                    'status': Device.STATUS_ONLINE,
                }
            )
            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-SAME-001',
                    'status': Device.STATUS_ONLINE,
                }
            )
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['payload']['deviceCode'], 'ANDROID-SAME-001')
            self.assertNotEqual(payload['payload']['deviceCode'], 'ANDROID-OTHER-001')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_runtime_config_events_command_filters_by_device_code(self):
        self.agent_application.publish()
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Config Event Device',
            code='RUNTIME-CONFIG-EVENT-001',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.runtime_config.subscribe',
                    'id': 'runtime-config-sub',
                    'payload': {'deviceCode': device.code},
                }),
            })
            initial_message = await communicator.receive_output(timeout=1)
            self.assertEqual(initial_message['type'], 'websocket.send')
            initial_payload = json.loads(initial_message['text'])
            self.assertEqual(initial_payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(initial_payload['id'], 'runtime-config-sub')
            self.assertEqual(initial_payload['payload']['deviceCode'], device.code)
            self.assertEqual(initial_payload['payload']['tenantId'], self.tenant.id)
            self.assertEqual(initial_payload['payload']['action'], 'initial')
            config = initial_payload['payload']['config']
            self.assertEqual(config['device']['deviceCode'], device.code)
            self.assertIn('application', config)
            self.assertIn('agentApplication', config)
            self.assertIn('wakeWords', config)
            self.assertIn('wakeWordLines', config)
            self.assertIn('voiceConfiguration', config)
            self.assertIn('scrollingTexts', config)
            self.assertNotIn('resources', config)
            self.assertIsInstance(config['agentApplication']['publishedAt'], str)

            await publish_device_event(
                {
                    'type': 'device.wake_words.changed',
                    'action': 'update',
                    'tenantId': self.tenant.id,
                    'deviceCodes': ['RUNTIME-CONFIG-OTHER-001'],
                }
            )
            await publish_device_event(
                {
                    'type': 'device.wake_words.changed',
                    'action': 'update',
                    'tenantId': self.tenant.id,
                    'deviceCodes': [device.code],
                    'refresh': {'endpoint': '/api/v1/device-runtime/config/'},
                }
            )

            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(payload['id'], 'runtime-config-sub')
            self.assertEqual(payload['payload']['action'], 'wakeWordsChanged')
            self.assertEqual(payload['payload']['deviceCode'], device.code)
            changed_config = payload['payload']['config']
            self.assertEqual(changed_config['device']['deviceCode'], device.code)
            self.assertIn('wakeWords', changed_config)
            self.assertIn('voiceConfiguration', changed_config)
            self.assertIn('scrollingTexts', changed_config)
            self.assertNotIn('resources', changed_config)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_runtime_config_subscribed_receives_tenant_level_config_changes(self):
        self.agent_application.publish()
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Config Tenant Event Device',
            code='RUNTIME-CONFIG-TENANT-001',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.runtime_config.subscribe',
                    'id': 'runtime-config-sub',
                    'payload': {'deviceCode': device.code},
                }),
            })
            initial_message = await communicator.receive_output(timeout=1)
            initial_payload = json.loads(initial_message['text'])
            self.assertEqual(initial_payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(initial_payload['payload']['action'], 'initial')
            self.assertIn('scrollingTexts', initial_payload['payload']['config'])
            self.assertIn('voiceConfiguration', initial_payload['payload']['config'])

            # tenant 级滚动文本变更 → 推送 subscribed(action=scrollingTextsChanged)
            await publish_device_event({
                'type': 'device.scrolling_texts.changed',
                'tenantId': self.tenant.id,
                'refresh': {'endpoint': '/api/v1/device-runtime/config/', 'reason': 'scrollingTextsChanged'},
            })
            scrolling_message = await communicator.receive_output(timeout=1)
            scrolling_payload = json.loads(scrolling_message['text'])
            self.assertEqual(scrolling_payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(scrolling_payload['payload']['action'], 'scrollingTextsChanged')
            self.assertEqual(scrolling_payload['payload']['deviceCode'], device.code)
            self.assertIn('scrollingTexts', scrolling_payload['payload']['config'])

            # tenant 级音色变更 → 推送 subscribed(action=voiceConfigurationChanged)
            await publish_device_event({
                'type': 'device.voice_configuration.changed',
                'tenantId': self.tenant.id,
                'refresh': {'endpoint': '/api/v1/device-runtime/config/', 'reason': 'voiceConfigurationChanged'},
            })
            voice_message = await communicator.receive_output(timeout=1)
            voice_payload = json.loads(voice_message['text'])
            self.assertEqual(voice_payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(voice_payload['payload']['action'], 'voiceConfigurationChanged')
            self.assertIn('voiceConfiguration', voice_payload['payload']['config'])

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_device_events_command_allows_superuser_scoped_tenant(self):
        superuser = User.objects.create_superuser(
            username='platform-realtime',
            password='test123456',
            email='platform-realtime@example.com',
        )
        other_tenant = Tenant.objects.create(name='Other Company', code='other-company')
        token = str(AccessToken.for_user(superuser))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-superuser',
                    'payload': {'token': token, 'tenantId': self.tenant.id},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            await publish_device_event(
                {
                    'type': 'device.authorization',
                    'action': 'bind',
                    'tenantId': other_tenant.id,
                    'deviceCode': 'ANDROID-OTHER-001',
                }
            )

            await publish_device_event(
                {
                    'type': 'device.authorization',
                    'action': 'bind',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-SCOPED-001',
                }
            )
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['payload']['deviceCode'], 'ANDROID-SCOPED-001')
            self.assertNotEqual(payload['payload']['deviceCode'], 'ANDROID-OTHER-001')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
