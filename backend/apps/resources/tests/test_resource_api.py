from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import Resource

User = get_user_model()

LONG_OSS_VIDEO_URL = (
    'https://cancerwake.oss-cn-beijing.aliyuncs.com/solin/'
    '2-%E7%A7%91%E6%8A%80%E9%A6%86%E7%94%A8AI%E6%95%B0%E5%AD%97%E4%BA%BA'
    '%E9%80%8F%E6%98%8E%E6%9F%9C%E5%A4%9A%E8%BD%AE%E5%AF%B9%E8%AF%9D'
    '%E8%A7%A3%E7%AD%94%E5%AD%A9%E5%AD%90%E5%8D%81%E4%B8%87%E4%B8%AA'
    '%E4%B8%BA%E4%BB%80%E4%B9%88.mp4'
)


class ResourceApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='resource-tester', password='test123456')
        self.role = Role.objects.create(name='资源测试角色', code='resource_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'resources',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)

    def test_create_video_resource_allows_cloud_url_without_file(self):
        self.grant_permissions('resources.videos.view', 'resources.videos.create')

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': '云端视频资源',
                'category': 'horizontal',
                'description': '只填 URL',
                'cloudUrl': 'https://cdn.example.com/videos/demo.mp4',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['cloudUrl'], 'https://cdn.example.com/videos/demo.mp4')
        self.assertFalse(response.data['hasFile'])

    def test_create_video_resource_allows_empty_cloud_url_and_empty_file(self):
        self.grant_permissions('resources.videos.view', 'resources.videos.create')

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': '空视频资源',
                'category': 'vertical',
                'description': '无文件无 URL',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['cloudUrl'], '')
        self.assertFalse(response.data['hasFile'])

    def test_video_resource_list_accepts_page_size_query_param(self):
        self.grant_permissions('resources.videos.view')
        for index in range(3):
            Resource.objects.create(
                name=f'分页视频资源 {index}',
                resource_type=Resource.TYPE_VIDEO,
                category=Resource.CATEGORY_HORIZONTAL,
            )

        response = self.client.get('/api/v1/resources/videos/?page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNotNone(response.data['next'])

    def test_update_video_resource_allows_long_oss_cloud_url(self):
        self.grant_permissions('resources.videos.view', 'resources.videos.update')
        resource = Resource.objects.create(
            name='长链接视频资源',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_VERTICAL,
        )

        response = self.client.patch(
            f'/api/v1/resources/videos/{resource.id}/',
            {
                'name': '长链接视频资源',
                'category': Resource.CATEGORY_VERTICAL,
                'cloudUrl': LONG_OSS_VIDEO_URL,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cloudUrl'], LONG_OSS_VIDEO_URL)
        resource.refresh_from_db()
        self.assertEqual(resource.cloud_url, LONG_OSS_VIDEO_URL)
