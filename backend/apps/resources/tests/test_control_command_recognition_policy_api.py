from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import ControlCommandRecognitionPolicy
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin


User = get_user_model()


class ControlCommandRecognitionPolicyApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='control-command-policy-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='控制指令策略测试角色', code='control_command_policy_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)
        self.grant_permissions('commands.control.view', 'commands.control.update')

    def grant_permissions(self, *codes: str):
        points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'control_command_recognition_policy_api',
                    'description': code,
                    'is_active': True,
                },
            )
            points.append(permission_point)
        self.role.permission_points.set(points)
        self.tenant.permission_points.set(points)

    def test_reading_current_company_policy_returns_default_thresholds(self):
        response = self.client.get('/api/v1/commands/control-recognition-policy/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fixedExecutionReply'], '')
        self.assertEqual(response.data['directExecutionThreshold'], '0.90')
        self.assertEqual(response.data['llmConfirmationThreshold'], '0.70')

    def test_updates_fixed_execution_reply_for_current_company(self):
        response = self.client.patch(
            '/api/v1/commands/control-recognition-policy/',
            {'fixedExecutionReply': '好的，已为您执行。'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fixedExecutionReply'], '好的，已为您执行。')
        self.assertEqual(response.data['directExecutionThreshold'], '0.90')

    def test_deleting_current_company_policy_restores_only_default_thresholds(self):
        update_response = self.client.patch(
            '/api/v1/commands/control-recognition-policy/',
            {
                'fixedExecutionReply': '好的，已为您执行。',
                'directExecutionThreshold': '0.95',
                'llmConfirmationThreshold': '0.80',
            },
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        delete_response = self.client.delete('/api/v1/commands/control-recognition-policy/')
        read_response = self.client.get('/api/v1/commands/control-recognition-policy/')

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(read_response.data['fixedExecutionReply'], '好的，已为您执行。')
        self.assertEqual(read_response.data['directExecutionThreshold'], '0.90')
        self.assertEqual(read_response.data['llmConfirmationThreshold'], '0.70')

    def test_rejects_invalid_threshold_order_and_precision(self):
        ordered_response = self.client.patch(
            '/api/v1/commands/control-recognition-policy/',
            {'directExecutionThreshold': '0.90', 'llmConfirmationThreshold': '0.91'},
            format='json',
        )
        precision_response = self.client.patch(
            '/api/v1/commands/control-recognition-policy/',
            {'directExecutionThreshold': '0.901', 'llmConfirmationThreshold': '0.70'},
            format='json',
        )

        self.assertEqual(ordered_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('不能高于直接执行阈值', ordered_response.data['message'])
        self.assertEqual(precision_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('不超过 2 个小数位', precision_response.data['message'])

    def test_reading_and_updating_policy_stays_within_current_company(self):
        other_tenant = Tenant.objects.create(name='其他公司', code='other-control-command-policy-tenant')
        other_policy = ControlCommandRecognitionPolicy.objects.create(
            tenant=other_tenant,
            fixed_execution_reply='其他公司固定回复。',
            direct_execution_threshold='0.99',
            llm_confirmation_threshold='0.80',
        )

        read_response = self.client.get('/api/v1/commands/control-recognition-policy/')
        update_response = self.client.patch(
            '/api/v1/commands/control-recognition-policy/',
            {'directExecutionThreshold': '0.95', 'llmConfirmationThreshold': '0.75'},
            format='json',
        )
        other_policy.refresh_from_db()

        self.assertEqual(read_response.data['directExecutionThreshold'], '0.90')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_policy.fixed_execution_reply, '其他公司固定回复。')
        self.assertEqual(str(other_policy.direct_execution_threshold), '0.99')
        self.assertEqual(str(other_policy.llm_confirmation_threshold), '0.80')
