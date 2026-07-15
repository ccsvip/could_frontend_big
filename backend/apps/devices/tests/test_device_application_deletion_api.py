from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.devices.models import Device, DeviceApplication, DeviceAuthorizationCode
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin


User = get_user_model()


class DeviceApplicationDeletionApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='device-delete-admin', password='test123456')
        self.setup_tenant(self.user)
        role = Role.objects.create(name='Device Delete Admin', code='device_delete_admin')
        UserRole.objects.create(user=self.user, role=role)
        permission_points = []
        for code in ('devices.view', 'devices.delete'):
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'devices', 'description': code, 'is_active': True},
            )
            permission_points.append(point)
        role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)
        self.client.force_authenticate(user=self.user)
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Lobby App',
            code='lobby-app-delete',
        )

    def test_deleting_device_application_unbinds_devices_and_preserves_authorization_codes(self):
        device = Device.objects.create(
            tenant=self.tenant,
            code='DELETE-APP-DEVICE-001',
            name='Delete App Device',
            application=self.application,
        )
        authorization_code = DeviceAuthorizationCode.objects.create(
            tenant=self.tenant,
            application=self.application,
            code='DELETE-APP-AUTH-001',
            authorization_type=Device.AUTHORIZATION_TRIAL,
            expires_at=timezone.now() + timedelta(days=7),
        )

        preview_response = self.client.get(f'/api/v1/device-applications/{self.application.id}/deletion-impact/')

        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        self.assertEqual(preview_response.data, {'deviceCount': 1, 'authorizationCodeCount': 1})

        delete_response = self.client.delete(f'/api/v1/device-applications/{self.application.id}/')

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        device.refresh_from_db()
        authorization_code.refresh_from_db()
        self.assertIsNone(device.application_id)
        self.assertIsNone(authorization_code.application_id)

    def test_device_application_deletion_impact_is_tenant_scoped(self):
        other_tenant = Tenant.objects.create(name='Other Company', code='other-company-delete')
        other_application = DeviceApplication.objects.create(
            tenant=other_tenant,
            name='Other App',
            code='other-app-delete',
        )

        response = self.client.get(f'/api/v1/device-applications/{other_application.id}/deletion-impact/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
