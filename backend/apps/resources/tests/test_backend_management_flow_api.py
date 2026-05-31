import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import Resource
from apps.resources.services.feishu import send_feishu_text
from apps.resources.tasks import notify_command_event_task
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


def build_upload(name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


class BackendManagementFlowApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()
        # 指令通知投递在业务流测试中默认隔离，避免测试环境依赖真实 Celery broker。
        self.command_notification_delay_patcher = patch('apps.resources.tasks.notify_command_event_task.delay')
        self.command_notification_delay = self.command_notification_delay_patcher.start()
        self.command_change_delay_patcher = patch('apps.resources.tasks.notify_command_change_task.delay')
        self.command_change_delay = self.command_change_delay_patcher.start()
        self.user = User.objects.create_user(username='flow-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='flow tester', code='flow_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.command_change_delay_patcher.stop()
        self.command_notification_delay_patcher.stop()
        self.override_media_root.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def grant_permissions(self, *codes: str):
        points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'backend_management_flow',
                    'description': code,
                    'is_active': True,
                },
            )
            points.append(permission_point)
        self.role.permission_points.set(points)

    def create_group(self, group_type: str, name: str, export_enabled: bool = False) -> int:
        response = self.client.post(
            '/api/v1/commands/groups/',
            {
                'name': name,
                'groupType': group_type,
                'exportEnabled': export_enabled,
                'isActive': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data['id']

    def test_point_management_only_requires_name_command_and_enabled_state(self):
        self.grant_permissions('commands.points.create', 'commands.points.view')

        response = self.client.post(
            '/api/v1/commands/points/',
            {
                'name': 'Hall Screen',
                'command': 'WELCOME_SCENE',
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Hall Screen')
        self.assertEqual(response.data['command'], 'WELCOME_SCENE')
        self.assertTrue(response.data['isActive'])
        self.assertNotIn('lookupKey', response.data)
        self.assertNotIn('steps', response.data)

    def test_point_management_allows_anonymous_access(self):
        anonymous_client = APIClient()

        create_response = anonymous_client.post(
            '/api/v1/commands/points/',
            {
                'name': 'Anonymous Hall Screen',
                'command': 'ANON_WELCOME_SCENE',
                'isActive': True,
            },
            format='json',
        )
        list_response = anonymous_client.get('/api/v1/commands/points/')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

    def test_control_command_uses_html_fields_under_control_group(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.control.create',
            'commands.control.view',
        )
        group_id = self.create_group('control', 'Central Control')

        response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': group_id,
                'name': 'Open Hall Screen',
                'command': 'POWER_ON',
                'commandValueType': 'hex',
                'ip': '192.168.1.100',
                'port': 8080,
                'callMethod': 'TCP',
                'isActive': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['command'], 'POWER_ON')
        self.assertEqual(response.data['commandValueType'], 'hex')
        self.assertEqual(response.data['ip'], '192.168.1.100')
        self.assertEqual(response.data['callMethod'], 'TCP')
        self.assertNotIn('payloadJson', response.data)
        self.assertNotIn('category', response.data)

    def test_control_command_notification_uses_authenticated_operator(self):
        self.grant_permissions('commands.groups.create', 'commands.control.create')

        with patch('apps.resources.tasks.notify_command_change_task.delay') as delay_task:
            group_id = self.create_group('control', 'Notify Control')
            delay_task.reset_mock()
            response = self.client.post(
                '/api/v1/commands/control/',
                {
                    'groupId': group_id,
                    'name': 'Notify Power On',
                    'command': 'NOTIFY_POWER_ON',
                    'commandValueType': 'hex',
                    'ip': '192.168.1.102',
                    'port': 8082,
                    'callMethod': 'TCP',
                    'isActive': True,
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 卡片任务签名：(action, user_label, command_type, name_before, name_after, code_before, code_after, group_name)
        task_args = delay_task.call_args.args
        self.assertEqual(task_args[0], 'create')
        self.assertEqual(task_args[1], 'flow-tester')
        self.assertEqual(task_args[2], '控制指令')
        self.assertEqual(task_args[3], '')  # name_before
        self.assertEqual(task_args[4], 'Notify Power On')  # name_after
        self.assertEqual(task_args[5], '')  # code_before
        self.assertEqual(task_args[6], 'NOTIFY_POWER_ON')  # code_after

    def test_group_and_task_command_mutations_send_feishu_notifications(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.groups.update',
            'commands.groups.delete',
            'commands.tasks.create',
            'commands.tasks.update',
            'commands.tasks.delete',
        )

        with (
            patch('apps.resources.tasks.notify_command_event_task.delay') as event_delay_task,
            patch('apps.resources.tasks.notify_command_change_task.delay') as change_delay_task,
        ):
            group_id = self.create_group('task', 'Notify Task Group')
            group_update_response = self.client.patch(
                f'/api/v1/commands/groups/{group_id}/',
                {'name': 'Notify Task Group Updated', 'groupType': 'task'},
                format='json',
            )
            task_create_response = self.client.post(
                '/api/v1/commands/tasks/',
                {
                    'groupId': group_id,
                    'name': 'Notify Task',
                    'command': 'NOTIFY_TASK',
                    'isActive': True,
                    'tasks': [{'order': 1, 'type': 'text', 'text': 'hello'}],
                },
                format='json',
            )
            task_id = task_create_response.data['id']
            task_update_response = self.client.patch(
                f'/api/v1/commands/tasks/{task_id}/',
                {
                    'groupId': group_id,
                    'name': 'Notify Task Updated',
                    'command': 'NOTIFY_TASK_UPDATED',
                    'isActive': True,
                    'tasks': [{'order': 1, 'type': 'text', 'text': 'updated'}],
                },
                format='json',
            )
            task_delete_response = self.client.delete(f'/api/v1/commands/tasks/{task_id}/')
            group_delete_response = self.client.delete(f'/api/v1/commands/groups/{group_id}/')

        self.assertEqual(group_update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(task_create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(task_update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(task_delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(group_delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # 指令分组依旧走文本通知（notify_command_event_task）。
        group_actions = [call.args[0] for call in event_delay_task.call_args_list]
        group_names = [call.args[3] for call in event_delay_task.call_args_list]
        self.assertEqual(group_actions, ['create', 'update', 'delete'])
        self.assertEqual(
            group_names,
            ['Notify Task Group', 'Notify Task Group Updated', 'Notify Task Group Updated'],
        )

        # 任务指令的 CRUD 走卡片通知（notify_command_change_task），且包含名称变更前后值。
        change_actions = [call.args[0] for call in change_delay_task.call_args_list]
        self.assertEqual(change_actions, ['create', 'update', 'delete'])
        # create: name_before='', name_after='Notify Task'
        create_args = change_delay_task.call_args_list[0].args
        self.assertEqual(create_args[3], '')
        self.assertEqual(create_args[4], 'Notify Task')
        self.assertEqual(create_args[5], '')
        self.assertEqual(create_args[6], 'NOTIFY_TASK')
        # update: name 与 command_code 双双变化
        update_args = change_delay_task.call_args_list[1].args
        self.assertEqual(update_args[3], 'Notify Task')
        self.assertEqual(update_args[4], 'Notify Task Updated')
        self.assertEqual(update_args[5], 'NOTIFY_TASK')
        self.assertEqual(update_args[6], 'NOTIFY_TASK_UPDATED')
        # delete: name_after / code_after 为空
        delete_args = change_delay_task.call_args_list[2].args
        self.assertEqual(delete_args[3], 'Notify Task Updated')
        self.assertEqual(delete_args[4], '')
        self.assertEqual(delete_args[5], 'NOTIFY_TASK_UPDATED')
        self.assertEqual(delete_args[6], '')

    def test_command_group_create_does_not_wait_for_feishu_delivery(self):
        self.grant_permissions('commands.groups.create')

        with (
            patch('apps.resources.tasks.notify_command_event_task.delay', side_effect=RuntimeError('broker down')) as delay_task,
            patch('apps.resources.services.feishu.send_feishu_text', side_effect=RuntimeError('network timeout')) as send_text,
        ):
            response = self.client.post(
                '/api/v1/commands/groups/',
                {
                    'name': 'Async Notify Group',
                    'groupType': 'control',
                    'exportEnabled': False,
                    'isActive': True,
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Async Notify Group')
        self.assertTrue(delay_task.called)
        self.assertFalse(send_text.called)

    def test_command_notification_task_delivers_feishu_message(self):
        with patch('apps.resources.tasks.notify_command_event', return_value=True) as notify_event:
            result = notify_command_event_task.run(
                'create',
                'flow-tester',
                '控制指令',
                'Power On',
                'POWER_ON',
                ['分组类型：控制指令'],
            )

        self.assertEqual(result, 'command_event_notified:create:True')
        notify_event.assert_called_once_with(
            'create',
            'flow-tester',
            '控制指令',
            'Power On',
            'POWER_ON',
            ['分组类型：控制指令'],
        )

    def test_feishu_text_appends_configured_server_ip(self):
        captured_payload = {}

        class FakeResponse:
            status_code = 200
            text = '{"code":0}'

            def json(self):
                return {'code': 0}

        class FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def post(self, url, json):
                captured_payload['url'] = url
                captured_payload['json'] = json
                return FakeResponse()

        with (
            override_settings(
                FEISHU_WEBHOOK_URL='https://feishu.example/webhook',
                FEISHU_WEBHOOK_SECRET='',
                FEISHU_SERVER_IP='10.0.0.8',
            ),
            patch('apps.resources.services.feishu.httpx.Client', FakeClient),
        ):
            sent = send_feishu_text('测试通知')

        self.assertTrue(sent)
        self.assertEqual(captured_payload['url'], 'https://feishu.example/webhook')
        self.assertIn('服务器IP：10.0.0.8', captured_payload['json']['content']['text'])

    def test_feishu_text_converts_localhost_ip_to_localhost(self):
        """本地回环地址和容器网络地址应被转换为 localhost。"""
        captured_payload = {}

        class FakeResponse:
            status_code = 200
            text = '{"code":0}'

            def json(self):
                return {'code': 0}

        class FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def post(self, url, json):
                captured_payload['url'] = url
                captured_payload['json'] = json
                return FakeResponse()

        # 测试 127.0.0.1 被转换为 localhost
        with (
            override_settings(
                FEISHU_WEBHOOK_URL='https://feishu.example/webhook',
                FEISHU_WEBHOOK_SECRET='',
                FEISHU_SERVER_IP='127.0.0.1',
            ),
            patch('apps.resources.services.feishu.httpx.Client', FakeClient),
        ):
            send_feishu_text('测试通知')
        self.assertIn('服务器IP：localhost', captured_payload['json']['content']['text'])

        # 测试 172.x 容器网络地址被转换为 localhost
        with (
            override_settings(
                FEISHU_WEBHOOK_URL='https://feishu.example/webhook',
                FEISHU_WEBHOOK_SECRET='',
                FEISHU_SERVER_IP='172.18.0.5',
            ),
            patch('apps.resources.services.feishu.httpx.Client', FakeClient),
        ):
            send_feishu_text('测试通知')
        self.assertIn('服务器IP：localhost', captured_payload['json']['content']['text'])

        # 测试 198.18.x 容器网络地址被转换为 localhost
        with (
            override_settings(
                FEISHU_WEBHOOK_URL='https://feishu.example/webhook',
                FEISHU_WEBHOOK_SECRET='',
                FEISHU_SERVER_IP='198.18.0.1',
            ),
            patch('apps.resources.services.feishu.httpx.Client', FakeClient),
        ):
            send_feishu_text('测试通知')
        self.assertIn('服务器IP：localhost', captured_payload['json']['content']['text'])

    def test_control_command_accepts_ascii_value_type_and_runtime_returns_ascii(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.control.create',
            'commands.control.view',
        )
        group_id = self.create_group('control', 'Ascii Control')

        create_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': group_id,
                'name': 'Ascii Command',
                'command': 'ASCII_POWER_ON',
                'commandValueType': 'ascii',
                'ip': '192.168.1.101',
                'port': 8081,
                'callMethod': 'UDP',
                'isActive': True,
            },
            format='json',
        )
        runtime_response = APIClient().get('/api/v1/commands/data/', {'command': 'ASCII_POWER_ON', 'tenant': 'test-tenant'})

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['commandValueType'], 'ascii')
        self.assertEqual(runtime_response.status_code, status.HTTP_200_OK)
        self.assertEqual(runtime_response.data['data']['commandValueType'], 'ascii')

    def test_runtime_lookup_uses_point_command_and_returns_scene_task_steps(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.control.create',
            'commands.tasks.create',
            'commands.points.create',
            'commands.tasks.view',
        )
        control_group_id = self.create_group('control', 'Central Control')
        task_group_id = self.create_group('task', 'Scene Task Orchestration', export_enabled=True)
        point_response = self.client.post(
            '/api/v1/commands/points/',
            {'name': 'Hall Screen', 'command': 'WELCOME_SCENE', 'isActive': True},
            format='json',
        )
        self.assertEqual(point_response.status_code, status.HTTP_201_CREATED)

        control_response = self.client.post(
            '/api/v1/commands/control/',
            {
                'groupId': control_group_id,
                'name': 'Open Hall Screen',
                'command': 'POWER_ON',
                'commandValueType': 'hex',
                'ip': '192.168.1.100',
                'port': 8080,
                'callMethod': 'UDP',
                'isActive': True,
            },
            format='json',
        )
        self.assertEqual(control_response.status_code, status.HTTP_201_CREATED)

        image = Resource.objects.create(
            name='Welcome Image',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_UNCATEGORIZED,
            file=build_upload('welcome.png', b'image-bytes', 'image/png'),
            tenant=self.tenant,
        )
        video = Resource.objects.create(
            name='Intro Video',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_UNCATEGORIZED,
            file=build_upload('intro.mp4', b'video-bytes', 'video/mp4'),
            tenant=self.tenant,
        )
        cloud_video = Resource.objects.create(
            name='Cloud Intro Video',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_UNCATEGORIZED,
            cloud_url='https://cdn.example.com/videos/cloud-intro.mp4',
            tenant=self.tenant,
        )

        task_response = self.client.post(
            '/api/v1/commands/tasks/',
            {
                'groupId': task_group_id,
                'name': 'Welcome Scene Task',
                'command': 'WELCOME_SCENE',
                'isActive': True,
                'tasks': [
                    {'order': 1, 'type': 'command', 'controlCommandId': control_response.data['id'], 'delaySeconds': 30},
                    {'order': 2, 'type': 'navigation', 'pointId': point_response.data['id']},
                    {'order': 3, 'type': 'image', 'resourceId': image.id, 'imageText': 'Library image caption'},
                    {'order': 4, 'type': 'video', 'resourceId': video.id},
                    {'order': 5, 'type': 'video', 'resourceId': cloud_video.id},
                    {'order': 6, 'type': 'text', 'text': 'Welcome to the hall'},
                ],
            },
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(task_response.data['tasks'][2]['imageText'], 'Library image caption')
        self.assertEqual(task_response.data['tasks'][3]['imageText'], '')

        response = APIClient().get('/api/v1/commands/data/', {'command': 'WELCOME_SCENE', 'tenant': 'test-tenant'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['commandType'], 'task')
        self.assertEqual(response.data['data']['command'], 'WELCOME_SCENE')
        self.assertEqual(
            [item['type'] for item in response.data['data']['tasks']],
            ['command', 'navigation', 'image', 'video', 'video', 'text'],
        )
        self.assertEqual(response.data['data']['tasks'][0]['content']['command'], 'POWER_ON')
        self.assertEqual(response.data['data']['tasks'][0]['content']['commandValueType'], 'hex')
        self.assertEqual(response.data['data']['tasks'][0]['delaySeconds'], 30)
        self.assertEqual(response.data['data']['tasks'][1]['delaySeconds'], 0)
        self.assertEqual(response.data['data']['tasks'][1]['content']['command'], 'WELCOME_SCENE')
        self.assertTrue(response.data['data']['tasks'][2]['content']['url'].startswith('http://testserver/media/'))
        self.assertEqual(response.data['data']['tasks'][2]['content']['imageText'], 'Library image caption')
        self.assertTrue(response.data['data']['tasks'][3]['content']['url'].startswith('http://testserver/media/'))
        self.assertEqual(response.data['data']['tasks'][4]['content']['url'], 'https://cdn.example.com/videos/cloud-intro.mp4')
        self.assertNotIn('imageText', response.data['data']['tasks'][4]['content'])
        self.assertEqual(response.data['data']['tasks'][5]['content']['text'], 'Welcome to the hall')

    def test_image_task_step_returns_empty_image_text_when_omitted(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.tasks.create',
            'commands.tasks.view',
        )
        task_group_id = self.create_group('task', 'Image Task Orchestration', export_enabled=True)
        image = Resource.objects.create(
            name='Plain Image',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_UNCATEGORIZED,
            file=build_upload('plain.png', b'image-bytes', 'image/png'),
            tenant=self.tenant,
        )

        task_response = self.client.post(
            '/api/v1/commands/tasks/',
            {
                'groupId': task_group_id,
                'name': 'Plain Image Task',
                'command': 'PLAIN_IMAGE',
                'isActive': True,
                'tasks': [
                    {'order': 1, 'type': 'image', 'resourceId': image.id},
                ],
            },
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(task_response.data['tasks'][0]['imageText'], '')

        response = APIClient().get('/api/v1/commands/data/', {'command': 'PLAIN_IMAGE', 'tenant': 'test-tenant'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['tasks'][0]['content']['imageText'], '')

    def test_runtime_lookup_can_return_task_steps_by_task_command_query(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.tasks.create',
            'commands.tasks.view',
        )
        task_group_id = self.create_group('task', 'Scene Task Orchestration', export_enabled=True)
        task_response = self.client.post(
            '/api/v1/commands/tasks/',
            {
                'groupId': task_group_id,
                'name': 'Junjie Scene Task',
                'command': 'junjie',
                'isActive': True,
                'tasks': [
                    {'order': 1, 'type': 'text', 'text': 'junjie task content', 'delaySeconds': 12},
                ],
            },
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)

        response = APIClient().get('/api/v1/commands/data/', {'command': 'junjie', 'tenant': 'test-tenant'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['commandType'], 'task')
        self.assertEqual(response.data['data']['command'], 'junjie')
        self.assertEqual(task_response.data['tasks'][0]['delaySeconds'], 12)
        self.assertEqual(response.data['data']['tasks'][0]['delaySeconds'], 12)
        self.assertEqual(response.data['data']['tasks'][0]['content']['text'], 'junjie task content')

    def test_navigation_task_step_returns_inner_tasks_at_runtime(self):
        self.grant_permissions(
            'commands.groups.create',
            'commands.tasks.create',
            'commands.tasks.view',
        )
        task_group_id = self.create_group('task', 'Nested Navigation Task Group', export_enabled=True)
        point_response = self.client.post(
            '/api/v1/commands/points/',
            {'name': 'Charging Pile', 'command': 'GO_CHARGING', 'isActive': True},
            format='json',
        )
        self.assertEqual(point_response.status_code, status.HTTP_201_CREATED)

        task_response = self.client.post(
            '/api/v1/commands/tasks/',
            {
                'groupId': task_group_id,
                'name': 'Nested Navigation Task',
                'command': 'NESTED_NAV',
                'isActive': True,
                'tasks': [
                    {
                        'order': 1,
                        'type': 'navigation',
                        'pointId': point_response.data['id'],
                        'waitForInnerTasks': True,
                        'innerTasks': [
                            {'order': 1, 'type': 'text', 'text': '已到达充电桩', 'delaySeconds': 2},
                        ],
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(task_response.data['tasks']), 1)
        self.assertTrue(task_response.data['tasks'][0]['waitForInnerTasks'])
        self.assertEqual(task_response.data['tasks'][0]['innerTasks'][0]['text'], '已到达充电桩')

        response = APIClient().get('/api/v1/commands/data/', {'command': 'NESTED_NAV', 'tenant': 'test-tenant'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['tasks']), 1)
        navigation_step = response.data['data']['tasks'][0]
        self.assertEqual(navigation_step['type'], 'navigation')
        self.assertEqual(navigation_step['content']['command'], 'GO_CHARGING')
        self.assertTrue(navigation_step['wait_for_inner_tasks'])
        self.assertEqual(navigation_step['inner_tasks'][0]['type'], 'text')
        self.assertEqual(navigation_step['inner_tasks'][0]['delaySeconds'], 2)
        self.assertEqual(navigation_step['inner_tasks'][0]['content']['text'], '已到达充电桩')

    def test_navigation_task_step_exposes_is_show_and_command_list(self):
        """导航子任务必须支持 is_show 开关，并在运行时返回 command_list 点位映射。"""
        self.grant_permissions(
            'commands.groups.create',
            'commands.tasks.create',
            'commands.tasks.view',
        )
        task_group_id = self.create_group('task', 'Skip Navigation Task Group', export_enabled=True)
        point_visible_response = self.client.post(
            '/api/v1/commands/points/',
            {'name': '前台', 'command': 'POINT_LOBBY', 'isActive': True},
            format='json',
        )
        self.assertEqual(point_visible_response.status_code, status.HTTP_201_CREATED)
        point_hidden_response = self.client.post(
            '/api/v1/commands/points/',
            {'name': '会议室', 'command': 'POINT_ROOM', 'isActive': True},
            format='json',
        )
        self.assertEqual(point_hidden_response.status_code, status.HTTP_201_CREATED)

        task_response = self.client.post(
            '/api/v1/commands/tasks/',
            {
                'groupId': task_group_id,
                'name': 'Skip Navigation Task',
                'command': 'SKIP_NAV',
                'isActive': True,
                'tasks': [
                    {
                        'order': 1,
                        'type': 'navigation',
                        'pointId': point_visible_response.data['id'],
                        'waitForInnerTasks': False,
                        # 默认 isShow=True，无需显式传，验证默认值。
                    },
                    {
                        'order': 2,
                        'type': 'navigation',
                        'pointId': point_hidden_response.data['id'],
                        'waitForInnerTasks': False,
                        'isShow': False,
                    },
                ],
            },
            format='json',
        )
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        # 管理 API 序列化器必须把 isShow 回显出来。
        self.assertEqual(task_response.data['tasks'][0]['isShow'], True)
        self.assertEqual(task_response.data['tasks'][1]['isShow'], False)

        response = APIClient().get('/api/v1/commands/data/', {'command': 'SKIP_NAV', 'tenant': 'test-tenant'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        # 现有 tasks 字段保持完全兼容：is_show=False 的导航子任务依然出现在 tasks 中。
        self.assertEqual(len(data['tasks']), 2)
        self.assertEqual(data['tasks'][0]['type'], 'navigation')
        self.assertTrue(data['tasks'][0]['is_show'])
        self.assertFalse(data['tasks'][1]['is_show'])
        # 每个导航子任务必须带 step_id（数据库自增主键），方便和 command_list 唯一匹配。
        self.assertIn('step_id', data['tasks'][0])
        self.assertIn('step_id', data['tasks'][1])
        self.assertIsInstance(data['tasks'][0]['step_id'], int)
        self.assertNotEqual(data['tasks'][0]['step_id'], data['tasks'][1]['step_id'])
        # command_list 只包含 is_show=True 的导航点位，且使用英文键 point_name（而不是中文键）。
        self.assertIn('command_list', data)
        self.assertEqual(len(data['command_list']), 1)
        self.assertEqual(
            data['command_list'],
            [
                {
                    'step_id': data['tasks'][0]['step_id'],
                    'point_name': '前台',
                    'command_key': 'POINT_LOBBY',
                    'is_show': True,
                },
            ],
        )
        # 旧的中文键不应再出现在 command_list 中。
        self.assertNotIn('点位名称', data['command_list'][0])

    def test_export_management_is_admin_only_even_with_export_permission(self):
        self.grant_permissions('commands.export.view', 'commands.export.download')

        response = self.client.get('/api/v1/commands/export/commands/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
