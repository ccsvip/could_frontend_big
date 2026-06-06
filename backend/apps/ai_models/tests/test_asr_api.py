from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import ASRReplacementRule
from apps.devices.models import Device
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class ASRApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='asr-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='ASR Test Role', code='asr_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'ai_models_asr',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.grant_all_scope_to_tenant()

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='env-workspace',
        MULTIMODAL_API_KEY='env-secret',
        ASR_BASE_URL='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        ASR_MODEL='qwen3-asr-flash-realtime',
    )
    def test_superuser_can_read_and_update_asr_settings(self):
        superuser = User.objects.create_superuser(username='root', password='test123456')
        self.client.force_authenticate(user=superuser)

        read_response = self.client.get('/api/v1/settings/asr/')

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['workspaceId'], 'env-workspace')
        self.assertEqual(read_response.data['apiKey'], '********cret')

        update_response = self.client.patch(
            '/api/v1/settings/asr/',
            {
                'workspaceId': 'new-workspace',
                'apiKey': 'new-secret',
                'baseUrl': 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
                'model': 'qwen3-asr-flash-realtime',
                'isActive': False,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['workspaceId'], 'new-workspace')
        self.assertEqual(update_response.data['apiKey'], '********cret')
        self.assertFalse(update_response.data['isActive'])

    def test_non_superuser_cannot_update_asr_settings(self):
        self.grant_permissions('ai_models.asr.view')

        response = self.client.patch('/api/v1/settings/asr/', {'model': 'x'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='env-workspace',
        MULTIMODAL_API_KEY='env-secret',
        ASR_BASE_URL='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        ASR_MODEL='qwen3-asr-flash-realtime',
    )
    def test_user_with_asr_view_can_read_status_without_secret(self):
        self.grant_permissions('ai_models.asr.view')

        response = self.client.get('/api/v1/ai-models/asr/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['configured'])
        self.assertEqual(response.data['workspaceId'], 'env-workspace')
        self.assertEqual(response.data['model'], 'qwen3-asr-flash-realtime')
        self.assertNotIn('apiKey', response.data)
        self.assertNotIn('env-secret', str(response.data))

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='env-workspace',
        MULTIMODAL_API_KEY='env-secret',
        ASR_BASE_URL='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        ASR_MODEL='qwen3-asr-flash-realtime',
    )
    @patch('apps.ai_models.services.asr.websocket.create_connection')
    def test_asr_test_uses_masked_response_and_mocked_success(self, create_connection):
        self.grant_permissions('ai_models.asr.view')
        ws = create_connection.return_value
        ws.recv.return_value = '{"type":"session.updated"}'

        response = self.client.post('/api/v1/ai-models/asr/test/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('latencyMs', response.data)
        self.assertNotIn('env-secret', str(response.data))
        create_connection.assert_called_once()
        call_kwargs = create_connection.call_args.kwargs
        self.assertIn('Authorization: Bearer env-secret', call_kwargs['header'])
        self.assertIn('X-DashScope-WorkSpace: env-workspace', call_kwargs['header'])
        ws.close.assert_called_once()

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='',
        MULTIMODAL_API_KEY='',
        ASR_BASE_URL='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        ASR_MODEL='qwen3-asr-flash-realtime',
    )
    def test_asr_test_reports_missing_required_config(self):
        self.grant_permissions('ai_models.asr.view')

        response = self.client.post('/api/v1/ai-models/asr/test/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        self.assertIn('missing', response.data['message'].lower())

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='env-workspace',
        MULTIMODAL_API_KEY='env-secret',
        ASR_BASE_URL='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        ASR_MODEL='qwen3-asr-flash-realtime',
    )
    def test_android_device_status_uses_device_code_header_without_login(self):
        self.client.force_authenticate(user=None)
        device = Device.objects.create(
            tenant=self.tenant,
            name='ASR Header Device',
            code='ANDROID-ASR-HEADER',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        response = self.client.get(
            '/api/v1/ai-models/asr/device-status/',
            HTTP_X_DEVICE_CODE='ANDROID-ASR-HEADER',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deviceCode'], device.code)
        self.assertEqual(response.data['tenantId'], self.tenant.id)
        self.assertEqual(response.data['tenantName'], self.tenant.name)
        self.assertTrue(response.data['configured'])
        self.assertTrue(response.data['isActive'])
        self.assertNotIn('apiKey', response.data)
        self.assertNotIn('env-secret', str(response.data))

    def test_android_device_status_rejects_unbound_device(self):
        self.client.force_authenticate(user=None)
        Device.objects.create(
            name='ASR Pending Device',
            code='ANDROID-ASR-PENDING',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        response = self.client.get(
            '/api/v1/ai-models/asr/device-status/',
            HTTP_X_DEVICE_CODE='ANDROID-ASR-PENDING',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_asr_permission_can_manage_replacement_rules_for_own_tenant(self):
        self.grant_permissions('ai_models.asr.view')

        create_response = self.client.post(
            '/api/v1/ai-models/asr/replacement-rules/',
            {'sourceText': '小明', 'replacementText': '小张', 'isActive': True},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['sourceText'], '小明')
        self.assertEqual(create_response.data['replacementText'], '小张')
        self.assertTrue(create_response.data['isActive'])
        self.assertEqual(create_response.data['tenantId'], self.tenant.id)

        list_response = self.client.get('/api/v1/ai-models/asr/replacement-rules/')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['sourceText'], '小明')

        update_response = self.client.patch(
            f"/api/v1/ai-models/asr/replacement-rules/{create_response.data['id']}/",
            {'replacementText': '小王', 'isActive': False},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['replacementText'], '小王')
        self.assertFalse(update_response.data['isActive'])

        delete_response = self.client.delete(
            f"/api/v1/ai-models/asr/replacement-rules/{create_response.data['id']}/",
        )

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ASRReplacementRule.objects.filter(tenant=self.tenant).exists())

    def test_replacement_rules_are_tenant_scoped(self):
        self.grant_permissions('ai_models.asr.view')
        other_tenant = Tenant.objects.create(name='其他公司', code='other-company')
        ASRReplacementRule.objects.create(
            tenant=other_tenant,
            source_text='其他',
            replacement_text='隐藏',
        )

        response = self.client.get('/api/v1/ai-models/asr/replacement-rules/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_superuser_can_create_replacement_rule_for_selected_tenant(self):
        superuser = User.objects.create_superuser(username='asr-root', password='test123456')
        self.client.force_authenticate(user=superuser)

        response = self.client.post(
            f'/api/v1/ai-models/asr/replacement-rules/?tenant={self.tenant.id}',
            {'sourceText': '小明', 'replacementText': '小张', 'isActive': True, 'sortOrder': 0},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tenantId'], self.tenant.id)
        self.assertTrue(
            ASRReplacementRule.objects.filter(
                tenant=self.tenant,
                source_text='小明',
                replacement_text='小张',
            ).exists(),
        )

    def test_superuser_without_selected_tenant_gets_clear_replacement_rule_error(self):
        superuser = User.objects.create_superuser(username='asr-root-no-tenant', password='test123456')
        self.client.force_authenticate(user=superuser)

        response = self.client.post(
            '/api/v1/ai-models/asr/replacement-rules/',
            {'sourceText': '小明', 'replacementText': '小张', 'isActive': True, 'sortOrder': 0},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '超管请先具体到某家公司后再保存替换词')
