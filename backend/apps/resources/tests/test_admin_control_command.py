from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase


User = get_user_model()


class ControlCommandAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='command-admin',
            email='command-admin@example.com',
            password='admin123456',
        )

    def test_resources_app_list_contains_backend_management_entries(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user

        resources_app = next(app for app in admin.site.get_app_list(request) if app['app_label'] == 'resources')
        model_links = {item['name']: item['admin_url'] for item in resources_app['models']}

        self.assertEqual(model_links['指令分组'], '/admin/resources/commandgroup/')
        self.assertEqual(model_links['控制指令'], '/admin/resources/controlcommand/')
        self.assertEqual(model_links['任务指令'], '/admin/resources/taskcommand/')
        self.assertEqual(model_links['点位管理'], '/admin/resources/point/')

    def test_control_command_admin_page_renders_command_fields(self):
        self.client.force_login(self.user)

        response = self.client.get('/admin/resources/controlcommand/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '控制指令')
        self.assertContains(response, '指令')
        self.assertContains(response, 'IP')
        self.assertContains(response, '端口')

    def test_task_command_admin_page_renders_task_fields(self):
        self.client.force_login(self.user)

        response = self.client.get('/admin/resources/taskcommand/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '任务指令')
        self.assertContains(response, '指令')
        self.assertContains(response, '子任务数量')
