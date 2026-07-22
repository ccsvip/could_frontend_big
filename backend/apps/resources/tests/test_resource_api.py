import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import AgentAnnotation, AgentApplication
from apps.resources.models import Resource
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()

LONG_OSS_VIDEO_URL = (
    'https://cancerwake.oss-cn-beijing.aliyuncs.com/solin/'
    '2-%E7%A7%91%E6%8A%80%E9%A6%86%E7%94%A8AI%E6%95%B0%E5%AD%97%E4%BA%BA'
    '%E9%80%8F%E6%98%8E%E6%9F%9C%E5%A4%9A%E8%BD%AE%E5%AF%B9%E8%AF%9D'
    '%E8%A7%A3%E7%AD%94%E5%AD%A9%E5%AD%90%E5%8D%81%E4%B8%87%E4%B8%AA'
    '%E4%B8%BA%E4%BB%80%E4%B9%88.mp4'
)


class ResourceApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='resource-tester', password='test123456')
        self.setup_tenant(self.user)
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
        self.tenant.permission_points.set(permission_points)

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

    def test_create_video_resource_rejects_empty_cloud_url_and_empty_file(self):
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('请上传视频或填写云端 URL', response.data['message'])

    def test_video_resource_list_accepts_page_size_query_param(self):
        self.grant_permissions('resources.videos.view')
        for index in range(3):
            Resource.objects.create(
                name=f'分页视频资源 {index}',
                resource_type=Resource.TYPE_VIDEO,
                category=Resource.CATEGORY_HORIZONTAL,
                tenant=self.tenant,
            )

        response = self.client.get('/api/v1/resources/videos/?page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNotNone(response.data['next'])

    def test_create_image_resource_accepts_digital_human_background_flag(self):
        self.grant_permissions('resources.images.view', 'resources.images.create')

        response = self.client.post(
            '/api/v1/resources/images/',
            {
                'name': '数字人背景',
                'category': Resource.CATEGORY_HORIZONTAL,
                'isDigitalHumanBackground': 'true',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['isDigitalHumanBackground'])
        resource = Resource.objects.get(id=response.data['id'])
        self.assertTrue(resource.is_digital_human_background)

    def test_create_image_resource_records_hash_and_rejects_duplicate_content(self):
        self.grant_permissions('resources.images.view', 'resources.images.create')
        content = b'same-image-content'

        first_response = self.client.post(
            '/api/v1/resources/images/',
            {
                'name': 'first image',
                'category': Resource.CATEGORY_HORIZONTAL,
                'file': SimpleUploadedFile('first.png', content, content_type='image/png'),
            },
            format='multipart',
        )
        duplicate_response = self.client.post(
            '/api/v1/resources/images/',
            {
                'name': 'renamed image',
                'category': Resource.CATEGORY_VERTICAL,
                'file': SimpleUploadedFile('renamed.png', content, content_type='image/png'),
            },
            format='multipart',
        )

        expected_hash = hashlib.sha256(content).hexdigest()
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first_response.data['contentHash'], expected_hash)
        self.assertEqual(Resource.objects.get(id=first_response.data['id']).content_hash, expected_hash)
        self.assertEqual(duplicate_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(duplicate_response.data['message'], '该图片已存在')
        self.assertEqual(
            duplicate_response.data['data']['existingResource'],
            {
                'id': first_response.data['id'],
                'category': Resource.CATEGORY_HORIZONTAL,
                'isDigitalHumanBackground': False,
            },
        )
        self.assertEqual(Resource.objects.filter(tenant=self.tenant, resource_type=Resource.TYPE_IMAGE).count(), 1)

    @patch('apps.resources.views.presign_resource_put_url')
    def test_image_presign_requires_valid_hash_and_rejects_current_tenant_duplicate(self, mock_presign):
        self.grant_permissions('resources.images.create')
        content_hash = hashlib.sha256(b'existing image').hexdigest()
        existing_resource = Resource.objects.create(
            name='existing',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=content_hash,
            tenant=self.tenant,
        )
        payload = {
            'resourceType': Resource.TYPE_IMAGE,
            'filename': 'image.png',
            'contentType': 'image/png',
            'fileSize': 100,
        }

        missing_response = self.client.post('/api/v1/resources/presign/', payload, format='json')
        invalid_response = self.client.post(
            '/api/v1/resources/presign/',
            {**payload, 'contentHash': 'invalid'},
            format='json',
        )
        duplicate_response = self.client.post(
            '/api/v1/resources/presign/',
            {**payload, 'contentHash': content_hash},
            format='json',
        )

        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(duplicate_response.data['message'], '该图片已存在')
        self.assertEqual(
            duplicate_response.data['data']['existingResource'],
            {
                'id': existing_resource.id,
                'category': Resource.CATEGORY_HORIZONTAL,
                'isDigitalHumanBackground': False,
            },
        )
        mock_presign.assert_not_called()

    @patch('apps.resources.views.presign_resource_put_url')
    def test_presign_does_not_leak_hashes_from_other_tenants_and_keeps_video_compatible(self, mock_presign):
        self.grant_permissions('resources.images.create', 'resources.videos.create')
        content_hash = hashlib.sha256(b'shared image').hexdigest()
        other_tenant = Tenant.objects.create(name='Hash Other Tenant', code='hash-other-tenant')
        Resource.objects.create(
            name='other image',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=content_hash,
            tenant=other_tenant,
        )
        mock_presign.return_value = {
            'uploadUrl': 'https://upload.example.com/object',
            'objectKey': f'tenants/{self.tenant.id}/images/object.png',
            'headers': {'Content-Type': 'image/png'},
        }

        image_response = self.client.post(
            '/api/v1/resources/presign/',
            {
                'resourceType': Resource.TYPE_IMAGE,
                'filename': 'image.png',
                'contentType': 'image/png',
                'fileSize': 100,
                'contentHash': content_hash,
            },
            format='json',
        )
        video_response = self.client.post(
            '/api/v1/resources/presign/',
            {
                'resourceType': Resource.TYPE_VIDEO,
                'filename': 'video.mp4',
                'contentType': 'video/mp4',
                'fileSize': 100,
            },
            format='json',
        )

        self.assertEqual(image_response.status_code, status.HTTP_200_OK)
        self.assertEqual(video_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_presign.call_count, 2)
        self.assertTrue(all(call.kwargs['tenant'] == self.tenant for call in mock_presign.call_args_list))

    @patch('apps.resources.serializers.delete_object')
    def test_r2_duplicate_create_cleans_unreferenced_object(self, mock_delete_object):
        self.grant_permissions('resources.images.create')
        content_hash = hashlib.sha256(b'existing r2 image').hexdigest()
        Resource.objects.create(
            name='existing',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=content_hash,
            tenant=self.tenant,
        )
        object_key = f'tenants/{self.tenant.id}/images/new-object.png'

        response = self.client.post(
            '/api/v1/resources/images/',
            {
                'name': 'duplicate object',
                'category': Resource.CATEGORY_HORIZONTAL,
                'objectKey': object_key,
                'storageBackend': 'r2',
                'objectSize': 100,
                'contentHash': content_hash,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_delete_object.assert_called_once_with(object_key, backend='r2')

    def test_image_resource_list_filters_by_digital_human_background_flag(self):
        self.grant_permissions('resources.images.view')
        background = Resource.objects.create(
            name='数字人背景',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            is_digital_human_background=True,
            tenant=self.tenant,
        )
        material = Resource.objects.create(
            name='普通图片素材',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )

        background_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=true')
        material_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=false')

        self.assertEqual(background_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in background_response.data['results']], [background.id])
        self.assertEqual(material_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in material_response.data['results']], [material.id])

    def test_bulk_create_image_resources_defaults_to_material(self):
        self.grant_permissions('resources.images.view', 'resources.images.create')
        cache.clear()

        cached_empty_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=false')
        self.assertEqual(cached_empty_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cached_empty_response.data['count'], 0)

        response = self.client.post(
            '/api/v1/resources/images/bulk/',
            {
                'category': Resource.CATEGORY_VERTICAL,
                'files': [
                    SimpleUploadedFile('first.png', b'first-image', content_type='image/png'),
                    SimpleUploadedFile('second.jpg', b'second-image', content_type='image/jpeg'),
                ],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['created']), 2)
        self.assertEqual(response.data['duplicates'], [])
        self.assertEqual({item['name'] for item in response.data['created']}, {'first', 'second'})
        self.assertTrue(all(item['category'] == Resource.CATEGORY_VERTICAL for item in response.data['created']))
        self.assertTrue(all(item['isDigitalHumanBackground'] is False for item in response.data['created']))
        self.assertEqual(Resource.objects.filter(resource_type=Resource.TYPE_IMAGE, tenant=self.tenant).count(), 2)

        refreshed_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=false')
        self.assertEqual(refreshed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refreshed_response.data['count'], 2)

    def test_bulk_create_image_resources_skips_duplicate_content(self):
        self.grant_permissions('resources.images.view', 'resources.images.create')
        existing_content = b'existing-image-content'
        Resource.objects.create(
            name='existing',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            content_hash=hashlib.sha256(existing_content).hexdigest(),
            tenant=self.tenant,
        )

        response = self.client.post(
            '/api/v1/resources/images/bulk/',
            {
                'category': Resource.CATEGORY_VERTICAL,
                'files': [
                    SimpleUploadedFile('duplicate.png', existing_content, content_type='image/png'),
                    SimpleUploadedFile('new.png', b'new-image-content', content_type='image/png'),
                    SimpleUploadedFile('new-copy.png', b'new-image-content', content_type='image/png'),
                ],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual([item['name'] for item in response.data['created']], ['new'])
        self.assertEqual(
            [item['fileName'] for item in response.data['duplicates']],
            ['duplicate.png', 'new-copy.png'],
        )
        self.assertEqual(Resource.objects.filter(tenant=self.tenant, resource_type=Resource.TYPE_IMAGE).count(), 2)

    def test_bulk_delete_image_resources_removes_uploaded_file(self):
        self.grant_permissions('resources.images.delete')

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            resource = Resource.objects.create(
                name='uploaded image',
                resource_type=Resource.TYPE_IMAGE,
                category=Resource.CATEGORY_HORIZONTAL,
                file=SimpleUploadedFile('uploaded.png', b'uploaded-image-content', content_type='image/png'),
                tenant=self.tenant,
            )
            uploaded_file_path = Path(resource.file.path)
            self.assertTrue(uploaded_file_path.exists())

            response = self.client.delete(
                '/api/v1/resources/images/bulk/',
                {'ids': [resource.id]},
                format='json',
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, {'deletedIds': [resource.id], 'failures': []})
            self.assertFalse(Resource.objects.filter(id=resource.id).exists())
            self.assertFalse(uploaded_file_path.exists())

    def test_bulk_delete_image_resources_supports_partial_success_and_tenant_isolation(self):
        self.grant_permissions('resources.images.view', 'resources.images.delete')
        cache.clear()
        deletable = Resource.objects.create(
            name='可批量删除图片',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )
        protected = Resource.objects.create(
            name='被引用图片',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )
        video = Resource.objects.create(
            name='不可通过图片接口删除的视频',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )
        other_tenant = Tenant.objects.create(name='其他公司', code='other-resource-tenant')
        other_image = Resource.objects.create(
            name='其他公司图片',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=other_tenant,
        )
        application = AgentApplication.objects.create(
            name='资源引用测试应用',
            tenant=self.tenant,
            created_by=self.user,
        )
        AgentAnnotation.objects.create(
            application=application,
            tenant=self.tenant,
            question='展示被引用图片',
            answer='图片回复',
            answer_blocks=[{'type': 'image', 'resourceId': protected.id}],
            created_by=self.user,
        )

        cached_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=false')
        self.assertEqual(cached_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cached_response.data['count'], 2)

        response = self.client.delete(
            '/api/v1/resources/images/bulk/',
            {'ids': [deletable.id, protected.id, other_image.id, video.id, 999999]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deletedIds'], [deletable.id])
        failures = {item['id']: item for item in response.data['failures']}
        self.assertIn('被 1 个标注回复引用', failures[protected.id]['reason'])
        for hidden_id in (other_image.id, video.id, 999999):
            self.assertEqual(failures[hidden_id]['name'], '')
            self.assertEqual(failures[hidden_id]['reason'], '图片不存在或无权访问')
        self.assertFalse(Resource.objects.filter(id=deletable.id).exists())
        self.assertTrue(Resource.objects.filter(id=protected.id).exists())
        self.assertTrue(Resource.objects.filter(id=other_image.id).exists())
        self.assertTrue(Resource.objects.filter(id=video.id).exists())

        refreshed_response = self.client.get('/api/v1/resources/images/?isDigitalHumanBackground=false')
        self.assertEqual(refreshed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refreshed_response.data['count'], 1)

    def test_bulk_delete_image_resources_requires_delete_permission(self):
        self.grant_permissions('resources.images.view')
        resource = Resource.objects.create(
            name='无权限不可删除图片',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )

        response = self.client.delete('/api/v1/resources/images/bulk/', {'ids': [resource.id]}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Resource.objects.filter(id=resource.id).exists())

    def test_bulk_delete_image_resources_rejects_duplicate_ids(self):
        self.grant_permissions('resources.images.delete')
        resource = Resource.objects.create(
            name='重复选择图片',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
            tenant=self.tenant,
        )

        response = self.client.delete(
            '/api/v1/resources/images/bulk/',
            {'ids': [resource.id, resource.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Resource.objects.filter(id=resource.id).exists())

    def test_update_video_resource_allows_long_oss_cloud_url(self):
        self.grant_permissions('resources.videos.view', 'resources.videos.update')
        resource = Resource.objects.create(
            name='长链接视频资源',
            resource_type=Resource.TYPE_VIDEO,
            category=Resource.CATEGORY_VERTICAL,
            tenant=self.tenant,
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
