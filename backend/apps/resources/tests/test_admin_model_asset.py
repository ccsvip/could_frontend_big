from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase


User = get_user_model()


class ResourceAdminEntryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='resource-admin',
            email='resource-admin@example.com',
            password='admin123456',
        )

    def test_resources_app_list_points_model_management_to_model_asset_admin(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user

        resources_app = next(app for app in admin.site.get_app_list(request) if app['app_label'] == 'resources')
        model_links = {item['name']: item['admin_url'] for item in resources_app['models']}

        self.assertEqual(model_links['模型管理'], '/admin/resources/modelasset/')
        self.assertEqual(model_links['资源（图片/视频）'], '/admin/resources/resource/')

    def test_model_management_admin_page_renders_model_fields(self):
        self.client.force_login(self.user)

        response = self.client.get('/admin/resources/modelasset/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '选择 模型管理 来修改')
        self.assertContains(response, '模型类型')
        self.assertContains(response, '模型方向')
        self.assertNotContains(response, '资源类型')
