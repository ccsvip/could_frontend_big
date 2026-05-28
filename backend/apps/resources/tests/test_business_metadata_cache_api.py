from pathlib import Path
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.knowledge_base.models import KnowledgeDocument
from apps.resources.models import Resource, VoiceTone
from config.business_cache import get_business_cache_summaries

User = get_user_model()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'business-metadata-cache-api-tests',
        }
    }
)
class BusinessMetadataCacheApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()
        self.user = User.objects.create_user(username='metadata-cache-user', password='test123456')
        self.role = Role.objects.create(name='缓存测试角色', code='metadata_cache_role')
        UserRole.objects.create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        cache.clear()
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
                    'module': 'metadata_cache',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)

    def get_cache_key_count(self, namespace: str) -> int:
        for summary in get_business_cache_summaries():
            if summary.namespace == namespace:
                return summary.cache_key_count
        raise AssertionError(f'缓存命名空间不存在: {namespace}')

    def test_resource_list_metadata_is_cached_and_invalidated_after_create(self):
        self.grant_permissions('resources.images.view', 'resources.images.create')
        Resource.objects.create(
            name='横屏背景图',
            resource_type=Resource.TYPE_IMAGE,
            category=Resource.CATEGORY_HORIZONTAL,
        )

        response = self.client.get('/api/v1/resources/images/?category=horizontal')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.get_cache_key_count('resources'), 1)

        create_response = self.client.post(
            '/api/v1/resources/images/',
            {
                'name': '新增背景图',
                'category': Resource.CATEGORY_VERTICAL,
                'description': '触发资源缓存失效',
            },
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.get_cache_key_count('resources'), 0)

    def test_voice_tone_list_metadata_is_cached_and_invalidated_after_update(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.update')
        voice_tone = VoiceTone.objects.create(
            name='缓存音色',
            voice_code='voice_cache_001',
            content='用于缓存测试',
            is_active=True,
            is_visible=True,
        )

        response = self.client.get('/api/v1/resources/voice-tones/?is_active=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.get_cache_key_count('voice_tones'), 1)

        update_response = self.client.patch(
            f'/api/v1/resources/voice-tones/{voice_tone.id}/',
            {'isActive': False},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_cache_key_count('voice_tones'), 0)

    def test_knowledge_document_metadata_cache_is_invalidated_after_download_count_changes(self):
        self.grant_permissions('knowledge_base.view', 'knowledge_base.download')
        document = KnowledgeDocument.objects.create(
            title='缓存文档',
            file=SimpleUploadedFile('cache-doc.pdf', b'cache-doc-content', content_type='application/pdf'),
            uploaded_by=self.user,
        )

        response = self.client.get('/api/v1/knowledge-base/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.get_cache_key_count('knowledge_base'), 1)

        download_response = self.client.get(f'/api/v1/knowledge-base/{document.id}/download/')
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertEqual(b''.join(download_response.streaming_content), b'cache-doc-content')
        self.assertEqual(self.get_cache_key_count('knowledge_base'), 0)
        self.assertTrue(Path(document.file.path).exists())
