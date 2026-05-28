from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from config.business_cache import get_business_response_cache, set_business_response_cache

User = get_user_model()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'cache-admin-tests',
        }
    }
)
class CacheAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='cache-admin', password='test123456')
        self.client.force_login(self.user)
        self.request = RequestFactory().get('/api/v1/resources/images/?category=horizontal', HTTP_HOST='testserver')

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_staff_can_open_cache_management_page(self):
        response = self.client.get('/admin/cache/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Redis 缓存管理')
        self.assertContains(response, '图片/视频资源')

    def test_cache_management_is_visible_in_simpleui_menu(self):
        system_tools_menu = next(
            menu for menu in settings.SIMPLEUI_CONFIG['menus'] if menu['name'] == '系统工具'
        )

        self.assertTrue(settings.SIMPLEUI_CONFIG['system_keep'])
        self.assertIn('系统工具', settings.SIMPLEUI_CONFIG['menu_display'])
        self.assertIn(
            {'name': 'Redis缓存管理', 'icon': 'fas fa-database', 'url': '/admin/cache/'},
            system_tools_menu['models'],
        )

    def test_staff_can_clear_business_cache_namespace(self):
        set_business_response_cache('resources', self.request, {'count': 1, 'results': []})

        response = self.client.post(
            '/admin/cache/',
            {'action': 'clear_namespace', 'namespace': 'resources'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '图片/视频资源')
        self.assertIsNone(get_business_response_cache('resources', self.request))
