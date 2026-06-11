import json
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class _MockHttpxResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class AliyunCommandApiTests(TenantTestMixin, APITestCase):
    endpoint = '/api/v1/commands/aliyun/'

    def setUp(self):
        self.user = User.objects.create_user(username='aliyun-command-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='阿里云指令测试角色', code='aliyun_command_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'commands_aliyun',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='workspace-1',
        ALIYUN_MM_APP_ID='test-app-id',
        ALIYUN_MM_DOMAIN_CODE='living-room',
        ALIYUN_MM_ACCESS_KEY_ID='test-access-key-id',
        ALIYUN_MM_ACCESS_KEY_SECRET='test-access-key-secret',
    )
    @patch('apps.resources.services.aliyun_commands.httpx.Client')
    def test_get_aliyun_commands_returns_normalized_items(self, client_cls):
        self.grant_permissions('commands.aliyun.view')
        client_cls.return_value.__enter__.return_value.post.return_value = _MockHttpxResponse(
            {
                'RequestId': 'req-1',
                'Data': {
                    'ToolInfoList': [
                        {
                            'DomainCode': 'living-room',
                            'DomainName': '客厅',
                            'ToolId': 'tool-1',
                            'ToolName': '打开灯光',
                            'ToolDescription': '打开客厅灯光',
                            'ToolExamples': ['打开客厅灯'],
                            'ToolParams': [{'name': 'brightness', 'type': 'integer'}],
                            'IgnoredField': 'ignored',
                        },
                        {
                            'domainCode': 'living-room',
                            'domainName': '客厅',
                            'toolId': 'tool-2',
                            'toolName': '关闭灯光',
                            'Description': '关闭客厅灯光',
                            'toolExamples': [],
                            'toolParams': [],
                        },
                    ]
                },
            }
        )

        response = self.client.get(self.endpoint)
        request_kwargs = client_cls.return_value.__enter__.return_value.post.call_args.kwargs
        request_payload = json.loads(request_kwargs['content'].decode('utf-8'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['message'], '获取阿里云指令列表成功')
        self.assertEqual(len(response.data['data']['items']), 2)
        self.assertEqual(
            request_payload,
            {
                'AppId': 'test-app-id',
                'DomainCode': 'living-room',
                'WorkspaceId': 'workspace-1',
                'PageNumber': 1,
                'PageSize': 100,
            },
        )
        self.assertEqual(
            response.data['data']['items'][0],
            {
                'domainCode': 'living-room',
                'domainName': '客厅',
                'toolId': 'tool-1',
                'toolName': '打开灯光',
                'description': '打开客厅灯光',
                'toolExamples': ['打开客厅灯'],
                'toolParams': [{'name': 'brightness', 'type': 'integer'}],
            },
        )
        self.assertEqual(response.data['data']['items'][1]['description'], '关闭客厅灯光')
        self.assertEqual(
            sorted(response.data['data']['items'][1].keys()),
            ['description', 'domainCode', 'domainName', 'toolExamples', 'toolId', 'toolName', 'toolParams'],
        )

    def test_get_aliyun_commands_requires_view_permission(self):
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_aliyun_commands_endpoint_is_get_only(self):
        self.grant_permissions('commands.aliyun.view')

        response = self.client.post(self.endpoint, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.data['status'], 'error')

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='',
        ALIYUN_MM_APP_ID='',
        ALIYUN_MM_DOMAIN_CODE='living-room',
        ALIYUN_MM_ACCESS_KEY_ID='test-access-key-id',
        ALIYUN_MM_ACCESS_KEY_SECRET='test-access-key-secret',
    )
    def test_get_aliyun_commands_returns_controlled_error_when_config_missing(self):
        self.grant_permissions('commands.aliyun.view')

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('阿里云指令配置缺失', response.data['message'])
        self.assertNotIn('test-access-key-id', response.data['message'])
        self.assertNotIn('test-access-key-secret', response.data['message'])

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='workspace-1',
        ALIYUN_MM_APP_ID='test-app-id',
        ALIYUN_MM_DOMAIN_CODE='living-room',
        ALIYUN_MM_ACCESS_KEY_ID='test-access-key-id',
        ALIYUN_MM_ACCESS_KEY_SECRET='test-access-key-secret',
    )
    @patch('apps.resources.services.aliyun_commands.httpx.Client')
    def test_get_aliyun_commands_maps_upstream_timeout_to_bad_gateway(self, client_cls):
        self.grant_permissions('commands.aliyun.view')
        client_cls.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException('timed out')

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('阿里云指令服务请求超时', response.data['message'])

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='workspace-1',
        ALIYUN_MM_APP_ID='test-app-id',
        ALIYUN_MM_DOMAIN_CODE='living-room',
        ALIYUN_MM_ACCESS_KEY_ID='test-access-key-id',
        ALIYUN_MM_ACCESS_KEY_SECRET='test-access-key-secret',
    )
    @patch('apps.resources.services.aliyun_commands.httpx.Client')
    def test_get_aliyun_commands_surfaces_signature_mismatch_as_config_hint(self, client_cls):
        self.grant_permissions('commands.aliyun.view')
        client_cls.return_value.__enter__.return_value.post.return_value = _MockHttpxResponse(
            {
                'Code': 'SignatureDoesNotMatch',
                'Message': 'Specified signature does not match our calculation.',
            },
            status_code=400,
        )

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('SignatureDoesNotMatch', response.data['message'])
        self.assertIn('ALIYUN_MM_ACCESS_KEY_ID / ALIYUN_MM_ACCESS_KEY_SECRET', response.data['message'])

    @override_settings(
        MULTIMODAL_WORKSPACE_ID='workspace-1',
        ALIYUN_MM_APP_ID='test-app-id',
        ALIYUN_MM_DOMAIN_CODE='living-room',
        ALIYUN_MM_ACCESS_KEY_ID='test-access-key-id',
        ALIYUN_MM_ACCESS_KEY_SECRET='test-access-key-secret',
    )
    @patch('apps.resources.services.aliyun_commands.httpx.Client')
    def test_get_aliyun_commands_rejects_malformed_payload(self, client_cls):
        self.grant_permissions('commands.aliyun.view')
        client_cls.return_value.__enter__.return_value.post.return_value = _MockHttpxResponse({'Data': {'Unknown': []}})

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('阿里云指令返回数据格式异常', response.data['message'])
