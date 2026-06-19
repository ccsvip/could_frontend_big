from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync, sync_to_async
from asgiref.testing import ApplicationCommunicator
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import AgentApplication, LLMModel, LLMProvider, TenantLLMModelGrant, TenantLLMSettings, TTSProvider, TTSVoice
from apps.devices.models import Device, DeviceApplication, DeviceAuthLog, DeviceAuthorizationCode, DeviceGroup
from apps.devices.services.authorization import record_device_authorization_action
from apps.devices.services.queries import device_authorization_requests_queryset
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device
from apps.devices.serializers import DeviceActivationLogSerializer
from apps.resources.models import ScrollingText, ScrollingTextItem
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


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

    def test_runtime_device_lookup_reports_duplicate_device_code(self):
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Android A',
            code='ANDROID-DUPLICATE-001',
        )
        other_tenant = Tenant.objects.create(name='Other Company', code='other-company')
        Device.objects.create(
            tenant=other_tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Runtime Android B',
            code='ANDROID-DUPLICATE-001',
        )

        with self.assertRaises(RuntimeDeviceError) as context:
            get_runtime_device('ANDROID-DUPLICATE-001')

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.message, '设备码存在重复绑定，请联系后台处理')

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
                'scrollingTextIds': [scrolling_text.id],
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data.get('scrollingTextIds'), [scrolling_text.id])
        application = DeviceApplication.objects.get(code='lobby-text-app', tenant=self.tenant)
        Device.objects.create(
            tenant=self.tenant,
            application=application,
            agent_application=self.agent_application,
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
            {'deviceCode': 'ANDROID-TEXT-001'},
            format='json',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        scrolling_texts = config_response.data['resources']['scrollingTexts']
        self.assertEqual(len(scrolling_texts), 1)
        self.assertEqual(scrolling_texts[0]['title'], '大厅公告')
        self.assertEqual(scrolling_texts[0]['items'][0]['zh'], '欢迎光临')

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
            {'deviceCode': 'ANDROID-VOICE-001', 'text': '你好'},
            format='json',
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

        with (
            patch('apps.devices.views.asr_services.transcribe_pcm_audio', return_value='介绍一下展厅'),
            patch('apps.devices.views.llm_services.run_llm_chat_completion', return_value='欢迎来到数字人展厅。'),
            patch('apps.devices.views.tts_services.synthesize_tts_pcm', return_value=b'\x01\x02'),
        ):
            response = self.client.post(
                '/api/v1/device/voice-chat',
                {
                    'deviceCode': 'ANDROID-VOICE-002',
                    'format': 'pcm',
                    'sampleRate': '16000',
                    'audio': SimpleUploadedFile('voice.pcm', b'\x00\x01\x00\x01', content_type='application/octet-stream'),
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['questionText'], '介绍一下展厅')
        self.assertEqual(response.data['answerText'], '欢迎来到数字人展厅。')
        self.assertTrue(response.data['audioBase64'])

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

    def test_device_patch_only_updates_name_and_group(self):
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
        self.assertEqual(device.agent_application_id, next_agent_application.id)
        self.assertEqual(device.code, 'ANDROID-BOARD-001')
        self.assertEqual(device.software_version, '1.0.0')
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_PERMANENT)
        self.assertIsNone(device.expires_at)
        self.assertTrue(device.is_enabled)

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

    def test_superuser_binds_activation_request_to_company(self):
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'deviceCode': 'ANDROID-BIND-001', 'deviceName': 'Bind Android'},
            format='json',
        )
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Front Desk')
        expires_at = timezone.now() + timedelta(days=30)
        superuser = User.objects.create_superuser(
            username='platform-binder',
            password='test123456',
            email='platform-binder@example.com',
        )
        self.client.force_authenticate(user=superuser)

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
        self.assertEqual(device.application_id, self.application.id)
        self.assertEqual(device.agent_application_id, self.agent_application.id)
        self.assertEqual(device.group_id, group.id)
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
