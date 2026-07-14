from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import CommandGroup, ControlCommand
from apps.tenants.models import Membership, Tenant
from apps.tenants.test_utils import TenantTestMixin


User = get_user_model()


class ControlCommandReplyApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='control-command-reply-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='控制指令回复测试角色', code='control_command_reply_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)
        self.grant_permissions(
            'commands.groups.create',
            'commands.control.create',
            'commands.control.view',
            'commands.control.update',
        )

    def grant_permissions(self, *codes: str):
        points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'control_command_reply_api',
                    'description': code,
                    'is_active': True,
                },
            )
            points.append(permission_point)
        self.role.permission_points.set(points)
        self.tenant.permission_points.set(points)

    def create_control_group(self) -> int:
        response = self.client.post(
            '/api/v1/commands/groups/',
            {'name': '控制指令分组', 'groupType': 'control', 'isActive': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data['id']

    def test_create_returns_execution_reply_and_defaults_reply_strategy_to_fixed(self):
        response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': self.create_control_group(),
                'name': '打开会议室屏幕',
                'command': 'MEETING_SCREEN_ON',
                'ip': '192.168.1.100',
                'port': 8080,
                'callMethod': 'TCP',
                'executionReply': '会议室屏幕已打开。',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['executionReply'], '会议室屏幕已打开。')
        self.assertEqual(response.data['replyStrategy'], 'fixed')
        self.assertFalse(response.data['backendSendEnabled'])

        update_response = self.client.patch(
            f"/api/v1/commands/control/{response.data['id']}/",
            {'backendSendEnabled': True},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(update_response.data['backendSendEnabled'])

    def test_patch_trims_empty_execution_reply_and_uses_generated_strategy(self):
        create_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': self.create_control_group(),
                'name': '关闭会议室屏幕',
                'command': 'MEETING_SCREEN_OFF',
                'ip': '192.168.1.101',
                'port': 8081,
                'callMethod': 'TCP',
                'executionReply': '原有回复',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        response = self.client.patch(
            f"/api/v1/commands/control/{create_response.data['id']}/",
            {'executionReply': '   ', 'replyStrategy': 'generated'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['executionReply'], '')
        self.assertEqual(response.data['replyStrategy'], 'generated')

    def test_rejects_unknown_reply_strategy(self):
        response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': self.create_control_group(),
                'name': '未知策略指令',
                'command': 'UNKNOWN_REPLY_STRATEGY',
                'ip': '192.168.1.102',
                'port': 8082,
                'callMethod': 'UDP',
                'replyStrategy': 'later',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('不是合法选项', response.data['message'])

    def test_same_command_code_is_allowed_in_different_tenants(self):
        first_group_id = self.create_control_group()
        first_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': first_group_id,
                'name': '公司 A 指令',
                'command': 'SHARED_COMMAND',
                'ip': '192.168.1.103',
                'port': 8083,
                'callMethod': 'UDP',
            },
            format='json',
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        other_tenant = Tenant.objects.create(name='公司 B', code='control-command-other-tenant')
        other_user = User.objects.create_user(username='control-command-other-user', password='test123456')
        Membership.objects.create(user=other_user, tenant=other_tenant, is_tenant_admin=True)
        UserRole.objects.create(user=other_user, role=self.role)
        other_tenant.permission_points.set(self.role.permission_points.all())
        other_group = CommandGroup.objects.create(
            tenant=other_tenant,
            name='公司 B 控制指令分组',
            group_type=CommandGroup.TYPE_CONTROL,
        )

        self.client.force_authenticate(user=other_user)
        cross_tenant_group_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': first_group_id,
                'name': '跨公司分组指令',
                'command': 'CROSS_TENANT_GROUP_COMMAND',
                'ip': '192.168.2.102',
                'port': 8082,
                'callMethod': 'UDP',
            },
            format='json',
        )
        self.assertEqual(cross_tenant_group_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cross_tenant_group_response.data['message'], '请选择当前公司的控制指令管理')

        second_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': other_group.id,
                'name': '公司 B 指令',
                'command': 'SHARED_COMMAND',
                'ip': '192.168.2.103',
                'port': 8083,
                'callMethod': 'UDP',
            },
            format='json',
        )

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        duplicate_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': other_group.id,
                'name': '公司 B 重复指令',
                'command': 'SHARED_COMMAND',
                'ip': '192.168.2.104',
                'port': 8084,
                'callMethod': 'UDP',
            },
            format='json',
        )
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_response.data['message'], '该指令已存在')

    def test_cannot_read_or_update_other_tenant_reply_preferences(self):
        other_tenant = Tenant.objects.create(name='其他公司', code='other-control-command-reply-tenant')
        other_group = CommandGroup.objects.create(
            tenant=other_tenant,
            name='其他公司控制分组',
            group_type=CommandGroup.TYPE_CONTROL,
        )
        other_command = ControlCommand.objects.create(
            tenant=other_tenant,
            group=other_group,
            name='其他公司屏幕开机',
            command_code='OTHER_TENANT_SCREEN_ON',
            host='192.168.2.100',
            port=8080,
            execution_reply='其他公司回复。',
            reply_strategy=ControlCommand.REPLY_STRATEGY_GENERATED,
        )

        retrieve_response = self.client.get(f'/api/v1/commands/control/{other_command.id}/')
        update_response = self.client.patch(
            f'/api/v1/commands/control/{other_command.id}/',
            {'executionReply': '越权修改。'},
            format='json',
        )

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
