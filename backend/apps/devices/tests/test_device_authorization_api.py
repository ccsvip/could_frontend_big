from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.devices.models import Device, DeviceApplication, DeviceAuthorizationCode, DeviceGroup
from apps.resources.models import ScrollingText, ScrollingTextItem
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
        self.grant_all_scope_to_tenant()

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
        auth_code = self.create_code(code='AUTH-TEXT-0001', application=application)
        activate_response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'authCode': auth_code.code, 'deviceCode': 'ANDROID-TEXT-001'},
            format='json',
        )
        config_response = self.client.get(
            '/api/v1/device-runtime/config/',
            HTTP_AUTHORIZATION=f"Bearer {activate_response.data['token']}",
            format='json',
        )

        self.assertEqual(config_response.status_code, status.HTTP_200_OK)
        scrolling_texts = config_response.data['resources']['scrollingTexts']
        self.assertEqual(len(scrolling_texts), 1)
        self.assertEqual(scrolling_texts[0]['title'], '大厅公告')
        self.assertEqual(scrolling_texts[0]['items'][0]['zh'], '欢迎光临')

    def test_activate_consumes_single_use_code_and_creates_device(self):
        auth_code = self.create_code()
        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {
                'authCode': auth_code.code,
                'deviceCode': 'ANDROID-BOARD-001',
                'deviceName': 'Lobby Android',
                'softwareVersion': '1.2.3',
                'systemVersion': 'Android 14',
                'mainboardInfo': 'rk3588',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        device = Device.objects.get(code='ANDROID-BOARD-001', tenant=self.tenant)
        auth_code.refresh_from_db()
        self.assertEqual(device.application_id, self.application.id)
        self.assertEqual(device.name, 'Lobby Android')
        self.assertEqual(device.software_version, '1.2.3')
        self.assertEqual(device.system_version, 'Android 14')
        self.assertEqual(device.mainboard_info, 'rk3588')
        self.assertEqual(device.authorization_type, Device.AUTHORIZATION_TRIAL)
        self.assertEqual(auth_code.status, DeviceAuthorizationCode.STATUS_USED)
        self.assertEqual(auth_code.used_by_device_id, device.id)

    def test_activate_rejects_used_code_for_another_device(self):
        auth_code = self.create_code()
        self.client.post(
            '/api/v1/device-auth/activate/',
            {'authCode': auth_code.code, 'deviceCode': 'ANDROID-001'},
            format='json',
        )

        response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'authCode': auth_code.code, 'deviceCode': 'ANDROID-002'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Device.objects.filter(tenant=self.tenant).count(), 1)

    def test_device_list_filters_by_name_and_device_code(self):
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Lobby')
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            group=group,
            name='Lobby Android',
            code='ANDROID-BOARD-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        Device.objects.create(
            tenant=self.tenant,
            application=self.application,
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

    def test_device_patch_only_updates_name_and_group(self):
        group = DeviceGroup.objects.create(tenant=self.tenant, name='Lobby')
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
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
                'groupId': group.id,
                'deviceCode': 'SHOULD-NOT-CHANGE',
                'softwareVersion': '9.9.9',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.name, 'New Name')
        self.assertEqual(device.group_id, group.id)
        self.assertEqual(device.code, 'ANDROID-BOARD-001')
        self.assertEqual(device.software_version, '1.0.0')

    def test_heartbeat_marks_device_online(self):
        auth_code = self.create_code()
        activate_response = self.client.post(
            '/api/v1/device-auth/activate/',
            {'authCode': auth_code.code, 'deviceCode': 'ANDROID-BOARD-001'},
            format='json',
        )
        token = activate_response.data['token']

        response = self.client.post(
            '/api/v1/device-runtime/heartbeat/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device = Device.objects.get(code='ANDROID-BOARD-001')
        self.assertEqual(device.status, Device.STATUS_ONLINE)
        self.assertIsNotNone(device.last_heartbeat)
