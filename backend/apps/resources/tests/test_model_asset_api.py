from io import BytesIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.resources.models import ModelAsset

User = get_user_model()


def build_test_png(name: str = 'model-thumbnail.png') -> SimpleUploadedFile:
    image = Image.new('RGB', (1, 1), color=(37, 99, 235))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def build_test_model_file(name: str = 'avatar-model.bin', content: bytes = b'model-binary-content') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type='application/octet-stream')


class ModelAssetApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()
        self.user = User.objects.create_user(username='model-tester', password='test123456')
        self.role = Role.objects.create(name='模型测试角色', code='model_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.override_media_root.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'resources_models',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)

    def test_list_model_assets_requires_view_permission(self):
        response = self.client.get('/api/v1/resources/models/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_model_asset_with_local_file_success(self):
        self.grant_permissions('resources.models.view', 'resources.models.create')
        uploaded_thumbnail = build_test_png()
        uploaded_model_file = build_test_model_file(content=b'avatar-model-content')

        response = self.client.post(
            '/api/v1/resources/models/',
            {
                'name': '数字人基础模型',
                'modelType': 'male',
                'orientation': 'horizontal',
                'thumbnail': uploaded_thumbnail,
                'model_file': uploaded_model_file,
                'cloudUrl': 'https://cdn.example.com/models/avatar-model.bin',
                'isVisible': True,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], '数字人基础模型')
        self.assertEqual(response.data['modelType'], 'male')
        self.assertEqual(response.data['orientation'], 'horizontal')
        self.assertEqual(response.data['thumbnailName'], 'model-thumbnail.png')
        self.assertEqual(response.data['modelFileName'], 'avatar-model.bin')
        self.assertEqual(response.data['modelSize'], len(b'avatar-model-content'))
        self.assertTrue(response.data['localUrl'].startswith('http://testserver/media/'))
        self.assertEqual(response.data['effectiveUrl'], response.data['localUrl'])
        self.assertTrue(response.data['hasThumbnail'])
        self.assertTrue(response.data['hasModelFile'])
        self.assertTrue(ModelAsset.objects.filter(name='数字人基础模型', is_visible=True).exists())

    def test_create_model_asset_allows_cloud_only(self):
        self.grant_permissions('resources.models.view', 'resources.models.create')

        response = self.client.post(
            '/api/v1/resources/models/',
            {
                'name': '云端兜底模型',
                'modelType': 'female',
                'orientation': 'vertical',
                'cloudUrl': 'https://cdn.example.com/models/cloud-only.bin',
                'isVisible': False,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['cloudUrl'], 'https://cdn.example.com/models/cloud-only.bin')
        self.assertEqual(response.data['effectiveUrl'], 'https://cdn.example.com/models/cloud-only.bin')
        self.assertFalse(response.data['hasModelFile'])
        self.assertEqual(response.data['localUrl'], '')
        self.assertIsNone(response.data['modelSize'])
        self.assertFalse(response.data['isVisible'])

    def test_create_model_asset_rejects_duplicate_name(self):
        self.grant_permissions('resources.models.view', 'resources.models.create')
        ModelAsset.objects.create(
            name='重复模型',
            model_type='male',
            orientation='horizontal',
            cloud_url='https://cdn.example.com/models/existing.bin',
            is_visible=True,
        )

        response = self.client.post(
            '/api/v1/resources/models/',
            {
                'name': '重复模型',
                'modelType': 'female',
                'orientation': 'vertical',
                'cloudUrl': 'https://cdn.example.com/models/new.bin',
                'isVisible': True,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '该模型名称已存在')

    def test_create_model_asset_requires_local_file_or_cloud_url(self):
        self.grant_permissions('resources.models.view', 'resources.models.create')

        response = self.client.post(
            '/api/v1/resources/models/',
            {
                'name': '无地址模型',
                'modelType': 'male',
                'orientation': 'vertical',
                'isVisible': True,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '请上传模型文件或填写云端地址')

    def test_list_model_assets_supports_keyword_type_and_orientation_filters(self):
        self.grant_permissions('resources.models.view')
        ModelAsset.objects.create(
            name='横屏男模型',
            model_type='male',
            orientation='horizontal',
            cloud_url='https://cdn.example.com/models/hm.bin',
            is_visible=True,
        )
        ModelAsset.objects.create(
            name='竖屏女模型',
            model_type='female',
            orientation='vertical',
            cloud_url='https://cdn.example.com/models/vf.bin',
            is_visible=True,
        )

        response = self.client.get('/api/v1/resources/models/?keyword=横屏&model_type=male&orientation=horizontal')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], '横屏男模型')

    def test_update_model_asset_can_clear_local_file_when_cloud_url_exists(self):
        self.grant_permissions('resources.models.view', 'resources.models.update')
        model_asset = ModelAsset.objects.create(
            name='本地模型',
            model_type='male',
            orientation='horizontal',
            model_file=build_test_model_file(name='local-model.bin', content=b'local-model-content'),
            cloud_url='https://cdn.example.com/models/fallback.bin',
            is_visible=True,
        )

        response = self.client.patch(
            f'/api/v1/resources/models/{model_asset.id}/',
            {'clearModelFile': True},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['hasModelFile'])
        self.assertEqual(response.data['localUrl'], '')
        self.assertEqual(response.data['effectiveUrl'], 'https://cdn.example.com/models/fallback.bin')
        self.assertIsNone(response.data['modelSize'])
        model_asset.refresh_from_db()
        self.assertFalse(bool(model_asset.model_file))
        self.assertIsNone(model_asset.model_size)
