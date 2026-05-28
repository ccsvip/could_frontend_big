# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportIndexIssue=false, reportOptionalSubscript=false, reportMissingTypeStubs=false, reportUninitializedInstanceVariable=false
import json

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.admin_examples.api_catalog import find_endpoint, list_api_endpoints  # pyright: ignore[reportImplicitRelativeImport]
from apps.resources.models import CommandGroup, TaskCommand, TaskCommandStep  # pyright: ignore[reportImplicitRelativeImport]
from apps.resources.point_models import Point  # pyright: ignore[reportImplicitRelativeImport]


User = get_user_model()


class PointApiTestAdminTests(TestCase):
    admin_url = '/admin/admin_examples/pointapitest/'

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='api-example-admin',
            email='api-example-admin@example.com',
            password='admin123456',
        )
        self.staff_user = User.objects.create_user(
            username='api-example-staff',
            email='api-example-staff@example.com',
            password='staff123456',
            is_staff=True,
        )

    def test_admin_app_list_contains_command_task_test_entry(self):
        request = RequestFactory().get('/admin/')
        request.user = self.superuser

        api_examples_app = next(app for app in admin.site.get_app_list(request) if app['app_label'] == 'admin_examples')
        model_links = {item['name']: item['admin_url'] for item in api_examples_app['models']}

        self.assertEqual(api_examples_app['name'], '接口示例')
        self.assertEqual(model_links['指令任务接口测试'], self.admin_url)

    def test_admin_app_list_contains_general_api_tester_entry(self):
        request = RequestFactory().get('/admin/')
        request.user = self.superuser

        api_examples_app = next(app for app in admin.site.get_app_list(request) if app['app_label'] == 'admin_examples')
        model_links = {item['name']: item['admin_url'] for item in api_examples_app['models']}

        self.assertIn('全部接口测试', model_links)
        self.assertEqual(model_links['全部接口测试'], '/admin/admin_examples/apitester/')

    def test_staff_user_without_model_permissions_can_open_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '指令任务接口测试')
        self.assertContains(response, '点位命令')
        self.assertContains(response, '测试接口')

    def test_anonymous_user_is_redirected_to_admin_login(self):
        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_valid_command_displays_raw_success_json(self):
        self.client.force_login(self.superuser)
        Point.objects.create(name='欢迎点位', command='WELCOME_SCENE', is_active=True)
        group = CommandGroup.objects.create(name='场景任务编排', group_type=CommandGroup.TYPE_TASK, is_active=True)
        task_command = TaskCommand.objects.create(
            group=group,
            name='欢迎场景任务',
            command_code='WELCOME_SCENE',
            is_active=True,
        )
        TaskCommandStep.objects.create(
            task_command=task_command,
            order=1,
            task_type=TaskCommandStep.TYPE_TEXT,
            text_content='欢迎光临',
        )

        response = self.client.post(self.admin_url, {'command': 'WELCOME_SCENE'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['endpoint'], '/api/v1/commands/data/?command=WELCOME_SCENE')
        self.assertEqual(response.context['http_status'], 200)
        self.assertEqual(
            json.loads(response.context['result_json']),
            {
                'status': 'success',
                'message': 'success',
                'code': 200,
                'data': {
                    'commandType': 'task',
                    'name': '欢迎场景任务',
                    'command': 'WELCOME_SCENE',
                    'tasks': [
                        {
                            'order': 1,
                            'type': 'text',
                            'delaySeconds': 0,
                            'content': {'text': '欢迎光临'},
                        },
                    ],
                    'command_list': [],
                },
            },
        )

    def test_missing_command_displays_raw_error_json(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {'command': 'missing-room'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['endpoint'], '/api/v1/commands/data/?command=missing-room')
        self.assertEqual(response.context['http_status'], 404)
        self.assertEqual(
            json.loads(response.context['result_json']),
            {
                'status': 'error',
                'message': '指令不存在',
                'code': 40401,
                'data': None,
            },
        )

    def test_non_slug_command_displays_error_without_crashing(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {'command': 'bad room'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['endpoint'], '/api/v1/commands/data/?command=bad%20room')
        self.assertEqual(
            json.loads(response.context['result_json']),
            {
                'status': 'error',
                'message': '指令不存在',
                'code': 40401,
                'data': None,
            },
        )

    def test_response_renders_markdown_code_block(self):
        """指令任务接口测试页响应区改成 markdown code-block 风格。"""
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {'command': 'missing-room'})

        self.assertEqual(response.status_code, 200)
        # 关键 DOM 节点必须存在
        self.assertContains(response, 'class="md-codeblock"')
        self.assertContains(response, 'class="md-codeblock-header"')
        self.assertContains(response, 'language-json')
        # 不再使用 textarea 渲染
        self.assertNotContains(response, '<textarea class="api-test-result"')
        # highlight.js 应被引入
        self.assertContains(response, 'highlight.js')
        # cURL 预览
        self.assertContains(response, 'language-bash')


class ApiCatalogTests(TestCase):
    def test_list_api_endpoints_returns_known_endpoints(self):
        endpoints = list_api_endpoints()
        self.assertGreater(len(endpoints), 20, '应当枚举到 20 个以上 /api/v1/* 接口')

        paths_methods = {(e['method'], e['path']) for e in endpoints}

        # 各个 app 至少有一条命中
        self.assertIn(('POST', '/api/v1/auth/login/'), paths_methods)
        self.assertIn(('GET', '/api/v1/auth/me/'), paths_methods)
        self.assertIn(('GET', '/api/v1/devices/'), paths_methods)
        self.assertIn(('GET', '/api/v1/resources/images/'), paths_methods)
        self.assertIn(('GET', '/api/v1/commands/data/'), paths_methods)
        self.assertIn(('GET', '/api/v1/knowledge-base/'), paths_methods)

    def test_list_api_endpoints_excludes_admin_and_schema(self):
        endpoints = list_api_endpoints()
        for ep in endpoints:
            self.assertTrue(
                ep['path'].startswith('/api/v1/'),
                f'非 /api/v1/* 路径泄漏：{ep["path"]}',
            )
            self.assertFalse(ep['path'].startswith('/admin'))
            self.assertFalse(ep['path'].startswith('/api/schema'))

    def test_list_api_endpoints_have_required_keys(self):
        endpoints = list_api_endpoints()
        self.assertGreater(len(endpoints), 0)
        for ep in endpoints:
            self.assertIn('method', ep)
            self.assertIn('path', ep)
            self.assertIn('view', ep)
            self.assertIn('doc', ep)
            self.assertIn('app', ep)
            self.assertIn(ep['method'], {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'})

    def test_find_endpoint_round_trip(self):
        ep = find_endpoint('GET', '/api/v1/devices/')
        self.assertIsNotNone(ep)
        self.assertEqual(ep['method'], 'GET')
        self.assertEqual(ep['path'], '/api/v1/devices/')

        self.assertIsNone(find_endpoint('GET', '/api/v1/this-does-not-exist/'))


class ApiTesterAdminTests(TestCase):
    admin_url = '/admin/admin_examples/apitester/'

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='api-tester-admin',
            email='api-tester-admin@example.com',
            password='admin123456',
        )
        self.staff_user = User.objects.create_user(
            username='api-tester-staff',
            email='api-tester-staff@example.com',
            password='staff123456',
            is_staff=True,
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_get_renders_form_and_endpoint_table(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.admin_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '全部接口测试')
        self.assertContains(response, 'name="method"')
        self.assertContains(response, 'name="path"')
        self.assertContains(response, 'name="headers"')
        self.assertContains(response, 'name="body"')
        # endpoints 列表渲染
        self.assertContains(response, '/api/v1/devices/')
        self.assertContains(response, '/api/v1/auth/login/')
        # highlight.js + 代码块组件
        self.assertContains(response, 'highlight.js')
        self.assertContains(response, 'class="md-codeblock"', count=0, status_code=200)
        # GET 时还没有响应区，所以 codeblock 数=0；body 字段 textarea 仍然存在但不算 codeblock。

    def test_post_get_request_returns_real_api_response(self):
        """POST 表单 method=GET path=/api/v1/devices/ 应当真去调 DeviceViewSet.list 拿到响应。"""
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'GET',
            'path': '/api/v1/devices/',
            'query': '',
            'headers': '',
            'body': '',
            'body_format': 'none',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['endpoint'], '/api/v1/devices/')
        self.assertEqual(response.context['http_status'], 200)
        self.assertEqual(response.context['result_kind'], 'json')
        # 响应是合法 JSON
        parsed = json.loads(response.context['result_text'])
        # devices 列表分页响应至少应该有 results / count / status / data 之一
        self.assertIsInstance(parsed, dict)
        # 渲染出的 HTML 应该含有 markdown code-block 节点
        self.assertContains(response, 'class="md-codeblock"')
        self.assertContains(response, 'language-json')
        self.assertContains(response, 'language-bash')  # cURL 命令预览

    def test_post_with_invalid_path_shows_form_error(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'GET',
            'path': 'devices/',  # 缺少 leading slash
            'query': '',
            'headers': '',
            'body': '',
            'body_format': 'none',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('必须以 / 开头', response.context['form_error'])
        # 不应当发起请求，所以 http_status 仍是 None
        self.assertIsNone(response.context['http_status'])

    def test_post_with_invalid_json_body_shows_form_error(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'POST',
            'path': '/api/v1/auth/login/',
            'query': '',
            'headers': '',
            'body': '{invalid json',
            'body_format': 'json',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('合法 JSON', response.context['form_error'])
        self.assertIsNone(response.context['http_status'])

    def test_post_with_query_string(self):
        """query 字段应当被合并到 endpoint URL。"""
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'GET',
            'path': '/api/v1/commands/data/',
            'query': 'command=does-not-exist',
            'headers': '',
            'body': '',
            'body_format': 'none',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['endpoint'], '/api/v1/commands/data/?command=does-not-exist')
        self.assertEqual(response.context['http_status'], 404)
        self.assertEqual(response.context['result_kind'], 'json')

    def test_post_with_unauthorized_endpoint_returns_401_or_403(self):
        """staff_user 是普通 staff，不一定有所有 API 权限；但访问 /auth/me/ 这种需要登录的接口应当成功。"""
        self.client.force_login(self.staff_user)

        response = self.client.post(self.admin_url, {
            'method': 'GET',
            'path': '/api/v1/auth/me/',
            'query': '',
            'headers': '',
            'body': '',
            'body_format': 'none',
        })

        self.assertEqual(response.status_code, 200)
        # 因为 ApiTesterAdmin 用 force_login，所以 /auth/me/ 应该 200
        self.assertEqual(response.context['http_status'], 200)

    def test_curl_command_includes_method_and_path(self):
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'POST',
            'path': '/api/v1/auth/login/',
            'query': '',
            'headers': 'X-Foo: bar',
            'body': '{"username":"u","password":"p"}',
            'body_format': 'json',
        })

        curl = response.context['curl_command']
        self.assertIn("curl -X POST '/api/v1/auth/login/'", curl)
        self.assertIn("'X-Foo: bar'", curl)
        self.assertIn("'Content-Type: application/json'", curl)
        self.assertIn('"username":"u"', curl)

    def test_form_persists_user_input_after_error(self):
        """提交错误的表单后，用户填写的字段应保留。"""
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'PATCH',
            'path': 'broken',
            'query': 'k=v',
            'headers': 'A: b',
            'body': 'hi',
            'body_format': 'text',
        })

        self.assertEqual(response.context['selected_method'], 'PATCH')
        self.assertEqual(response.context['selected_path'], 'broken')
        self.assertEqual(response.context['query_string'], 'k=v')
        self.assertEqual(response.context['headers_text'], 'A: b')
        self.assertEqual(response.context['body_text'], 'hi')
        self.assertEqual(response.context['body_format'], 'text')

    def test_response_html_uses_markdown_codeblock(self):
        """响应渲染 HTML 必须采用 markdown code-block 视觉。"""
        self.client.force_login(self.superuser)

        response = self.client.post(self.admin_url, {
            'method': 'GET',
            'path': '/api/v1/devices/',
            'query': '',
            'headers': '',
            'body': '',
            'body_format': 'none',
        })

        self.assertContains(response, 'class="md-codeblock"')
        self.assertContains(response, 'class="md-codeblock-header"')
        self.assertContains(response, 'class="md-copy-btn"')
        # 状态码 tag
        self.assertContains(response, 'is-status-2xx')
