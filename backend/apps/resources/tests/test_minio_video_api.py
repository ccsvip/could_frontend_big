from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import MinioConfig, Resource
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class MinioVideoApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='minio-video-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='MinIO Video Tester', code='minio_video_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'resources', 'description': code, 'is_active': True},
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    @patch('apps.resources.views.get_video_upload_config')
    def test_upload_config_requires_video_create_permission(self, mock_config):
        self.grant_permissions('resources.videos.create')
        mock_config.return_value = {'enabled': True, 'maxSizeMB': 1024, 'bucketName': 'digital-human'}

        response = self.client.get('/api/v1/resources/videos/upload-config/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bucketName'], 'digital-human')

    @patch('apps.resources.views.presign_video_put_url')
    def test_presign_uses_request_tenant(self, mock_presign):
        self.grant_permissions('resources.videos.create')
        mock_presign.return_value = {
            'uploadUrl': 'http://localhost:9000/digital-human/upload',
            'objectKey': f'tenants/{self.tenant.id}/videos/2026/06/04/demo.mp4',
            'publicUrl': 'http://localhost:9000/digital-human/demo.mp4',
            'headers': {'Content-Type': 'video/mp4'},
        }

        response = self.client.post(
            '/api/v1/resources/videos/presign/',
            {'filename': 'demo.mp4', 'contentType': 'video/mp4', 'fileSize': 100},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_presign.assert_called_once()
        self.assertEqual(mock_presign.call_args.kwargs['tenant'], self.tenant)
        self.assertTrue(response.data['objectKey'].startswith(f'tenants/{self.tenant.id}/'))

    def test_create_video_resource_accepts_own_tenant_object_key(self):
        self.grant_permissions('resources.videos.view', 'resources.videos.create')
        object_key = f'tenants/{self.tenant.id}/videos/2026/06/04/demo.mp4'

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Tenant video',
                'category': Resource.CATEGORY_HORIZONTAL,
                'objectKey': object_key,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['objectKey'], object_key)
        self.assertTrue(response.data['hasFile'])
        self.assertEqual(Resource.objects.get(id=response.data['id']).tenant, self.tenant)

    def test_create_video_resource_rejects_object_key_and_cloud_url_together(self):
        self.grant_permissions('resources.videos.create')

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Mixed video',
                'category': Resource.CATEGORY_HORIZONTAL,
                'objectKey': f'tenants/{self.tenant.id}/videos/2026/06/04/demo.mp4',
                'cloudUrl': 'https://example.com/demo.mp4',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('二选一', response.data['message'])

    def test_create_video_resource_requires_source_when_cloud_url_enabled(self):
        self.grant_permissions('resources.videos.create')

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Empty video',
                'category': Resource.CATEGORY_HORIZONTAL,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('请上传视频或填写云端 URL', response.data['message'])

    def test_create_video_resource_rejects_cloud_url_when_disabled(self):
        self.grant_permissions('resources.videos.create')
        MinioConfig.objects.update_or_create(pk=1, defaults={'allow_video_cloud_url': False})

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Cloud video',
                'category': Resource.CATEGORY_HORIZONTAL,
                'cloudUrl': 'https://example.com/demo.mp4',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('不允许填写视频云端 URL', response.data['message'])

    def test_create_video_resource_requires_upload_when_cloud_url_disabled(self):
        self.grant_permissions('resources.videos.create')
        MinioConfig.objects.update_or_create(pk=1, defaults={'allow_video_cloud_url': False})

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Empty video',
                'category': Resource.CATEGORY_HORIZONTAL,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('请上传视频', response.data['message'])

    def test_create_video_resource_rejects_other_tenant_object_key(self):
        self.grant_permissions('resources.videos.create')
        other = Tenant.objects.create(name='Other Tenant', code='other-tenant')

        response = self.client.post(
            '/api/v1/resources/videos/',
            {
                'name': 'Cross tenant video',
                'category': Resource.CATEGORY_HORIZONTAL,
                'objectKey': f'tenants/{other.id}/videos/2026/06/04/demo.mp4',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('视频对象不属于当前公司', str(response.data))
