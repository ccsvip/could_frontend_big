from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import ScrollingText, ScrollingTextItem
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()

LOC_MEM_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'scrolling-text-tests',
    }
}


@override_settings(CACHES=LOC_MEM_CACHES)
class ScrollingTextApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='scrolling-text-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='滚动文本测试角色', code='scrolling_text_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'resources_scrolling_texts',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)

    def test_list_scrolling_texts_is_public(self):
        # scrolling-texts 是多租户改造里明确定为公开的运行时端点：
        # ScrollingTextViewSet 硬编码 permission_classes=[AllowAny] 且 get_permissions()
        # 恒返回 [AllowAny()]，靠 ?tenant=<code> 行级隔离服务匿名数字人设备，不靠登录鉴权。
        # 因此未授予 view 权限的请求应当 200（公开可读），而非 403。
        response = self.client.get('/api/v1/resources/scrolling-texts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_scrolling_text_success(self):
        self.grant_permissions('resources.scrolling_texts.view', 'resources.scrolling_texts.create')

        response = self.client.post(
            '/api/v1/resources/scrolling-texts/',
            {
                'title': '首页滚动公告',
                'i18nScheme': 'zh_en',
                'isActive': True,
                'items': [
                    {'order': 1, 'zh': '欢迎参观', 'en': 'Welcome'},
                    {'order': 2, 'zh': '请保持安静', 'en': 'Please keep quiet'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], '首页滚动公告')
        self.assertEqual(response.data['i18nScheme'], 'zh_en')
        self.assertTrue(response.data['isActive'])
        self.assertEqual(len(response.data['items']), 2)
        self.assertEqual(response.data['localizedItems'][0]['text'], '欢迎参观')
        self.assertTrue(ScrollingText.objects.filter(title='首页滚动公告', items__en_text='Welcome').exists())

    def test_create_scrolling_text_rejects_empty_items(self):
        self.grant_permissions('resources.scrolling_texts.view', 'resources.scrolling_texts.create')

        response = self.client.post(
            '/api/v1/resources/scrolling-texts/',
            {
                'title': '空公告',
                'i18nScheme': 'zh_en',
                'isActive': True,
                'items': [],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('至少配置一条', response.data['message'])

    def test_create_scrolling_text_can_omit_title_and_active_state(self):
        self.grant_permissions('resources.scrolling_texts.view', 'resources.scrolling_texts.create')

        response = self.client.post(
            '/api/v1/resources/scrolling-texts/?page=1',
            {
                'i18nScheme': 'zh_en',
                'items': [
                    {'order': 1, 'zh': '自动标题中文', 'en': 'Auto title English'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], '自动标题中文')
        self.assertTrue(response.data['isActive'])

    def test_list_scrolling_texts_returns_language_specific_texts(self):
        self.grant_permissions('resources.scrolling_texts.view')
        scrolling_text = ScrollingText.objects.create(title='多语言公告', is_active=True, tenant=self.tenant)
        ScrollingTextItem.objects.create(
            scrolling_text=scrolling_text,
            order=1,
            zh_text='中文内容',
            en_text='English content',
        )

        zh_response = self.client.get('/api/v1/resources/scrolling-texts/?lang=zh')
        en_response = self.client.get('/api/v1/resources/scrolling-texts/?lang=en')
        fallback_response = self.client.get('/api/v1/resources/scrolling-texts/?lang=fr')

        self.assertEqual(zh_response.status_code, status.HTTP_200_OK)
        self.assertEqual(en_response.status_code, status.HTTP_200_OK)
        self.assertEqual(fallback_response.status_code, status.HTTP_200_OK)
        self.assertEqual(zh_response.data['results'][0]['localizedItems'][0]['text'], '中文内容')
        self.assertEqual(en_response.data['results'][0]['localizedItems'][0]['text'], 'English content')
        self.assertEqual(fallback_response.data['results'][0]['localizedItems'][0]['text'], '中文内容')

    def test_list_scrolling_texts_without_params_returns_pair_content_list(self):
        self.grant_permissions('resources.scrolling_texts.view')
        active = ScrollingText.objects.create(title='启用公告', is_active=True, tenant=self.tenant)
        inactive = ScrollingText.objects.create(title='停用公告', is_active=False, tenant=self.tenant)
        ScrollingTextItem.objects.create(scrolling_text=active, order=1, zh_text='启用中文', en_text='Active English')
        ScrollingTextItem.objects.create(scrolling_text=inactive, order=1, zh_text='停用中文', en_text='Inactive English')

        response = self.client.get('/api/v1/resources/scrolling-texts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{'zh': '启用中文', 'en': 'Active English'}])

    def test_scrolling_text_content_action_supports_language_body(self):
        self.grant_permissions('resources.scrolling_texts.view')
        scrolling_text = ScrollingText.objects.create(title='消费公告', is_active=True, tenant=self.tenant)
        ScrollingTextItem.objects.create(scrolling_text=scrolling_text, order=1, zh_text='第一条中文', en_text='First English')
        ScrollingTextItem.objects.create(scrolling_text=scrolling_text, order=2, zh_text='第二条中文', en_text='Second English')

        cn_response = self.client.post('/api/v1/resources/scrolling-texts/content/', {'language': 'cn'}, format='json')
        en_response = self.client.post('/api/v1/resources/scrolling-texts/content/', {'language': 'en'}, format='json')
        pair_response = self.client.post('/api/v1/resources/scrolling-texts/content/', {}, format='json')

        self.assertEqual(cn_response.status_code, status.HTTP_200_OK)
        self.assertEqual(en_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pair_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cn_response.data, ['第一条中文', '第二条中文'])
        self.assertEqual(en_response.data, ['First English', 'Second English'])
        self.assertEqual(
            pair_response.data,
            [
                {'zh': '第一条中文', 'en': 'First English'},
                {'zh': '第二条中文', 'en': 'Second English'},
            ],
        )

    def test_list_scrolling_texts_supports_exact_title_query(self):
        self.grant_permissions('resources.scrolling_texts.view')
        first = ScrollingText.objects.create(title='首页滚动公告', is_active=True, tenant=self.tenant)
        second = ScrollingText.objects.create(title='首页滚动公告副本', is_active=True, tenant=self.tenant)
        ScrollingTextItem.objects.create(
            scrolling_text=first,
            order=1,
            zh_text='标题匹配中文',
            en_text='Title matched English',
        )
        ScrollingTextItem.objects.create(
            scrolling_text=second,
            order=1,
            zh_text='不应返回',
            en_text='Should not return',
        )

        response = self.client.get('/api/v1/resources/scrolling-texts/?title=首页滚动公告&lang=en')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], '首页滚动公告')
        self.assertEqual(response.data['results'][0]['localizedItems'][0]['text'], 'Title matched English')

    def test_update_scrolling_text_replaces_items_in_order(self):
        self.grant_permissions('resources.scrolling_texts.view', 'resources.scrolling_texts.update')
        scrolling_text = ScrollingText.objects.create(title='旧公告', is_active=True, tenant=self.tenant)
        ScrollingTextItem.objects.create(scrolling_text=scrolling_text, order=1, zh_text='旧中文', en_text='Old')

        response = self.client.patch(
            f'/api/v1/resources/scrolling-texts/{scrolling_text.id}/',
            {
                'title': '新公告',
                'items': [
                    {'order': 20, 'zh': '第二条', 'en': 'Second'},
                    {'order': 10, 'zh': '第一条', 'en': 'First'},
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        scrolling_text.refresh_from_db()
        self.assertEqual(scrolling_text.title, '新公告')
        self.assertEqual(list(scrolling_text.items.values_list('order', 'zh_text', 'en_text')), [(1, '第一条', 'First'), (2, '第二条', 'Second')])
