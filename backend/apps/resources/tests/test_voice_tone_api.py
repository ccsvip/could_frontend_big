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
from apps.resources.models import VoiceTone
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


def build_test_png(name: str = 'voice-icon.png') -> SimpleUploadedFile:
    image = Image.new('RGB', (1, 1), color=(0, 153, 255))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class VoiceToneApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()
        self.user = User.objects.create_user(username='voice-tone-tester', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='音色测试角色', code='voice_tone_tester')
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
                    'module': 'resources_voice_tones',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def test_list_voice_tones_requires_view_permission(self):
        self.tenant.permission_points.clear()

        response = self.client.get('/api/v1/resources/voice-tones/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_voice_tone_success(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.create')
        uploaded_icon = build_test_png()
        uploaded_audio = SimpleUploadedFile('voice.mp3', b'fake-audio-content', content_type='audio/mpeg')

        response = self.client.post(
            '/api/v1/resources/voice-tones/',
            {
                'name': '温柔女声',
                'voiceCode': 'voice_female_soft_v1',
                'asrText': '这是一段 ASR 结果',
                'icon': uploaded_icon,
                'audio': uploaded_audio,
                'isActive': True,
                'isVisible': True,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['voiceCode'], 'voice_female_soft_v1')
        self.assertEqual(response.data['asrText'], '这是一段 ASR 结果')
        self.assertEqual(response.data['iconName'], 'voice-icon.png')
        self.assertEqual(response.data['audioName'], 'voice.mp3')
        self.assertEqual(response.data['audioSize'], len(b'fake-audio-content'))
        self.assertTrue(response.data['iconUrl'])
        self.assertTrue(response.data['audioUrl'])
        self.assertTrue(response.data['hasIcon'])
        self.assertTrue(response.data['hasAudio'])
        self.assertTrue(response.data['isVisible'])
        self.assertTrue(VoiceTone.objects.filter(voice_code='voice_female_soft_v1', is_visible=True).exists())

    def test_create_voice_tone_rejects_duplicate_voice_code(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.create')
        VoiceTone.objects.create(
            name='沉稳男声',
            voice_code='voice_male_deep_v1',
            content='已有音色',
            is_active=True,
            tenant=self.tenant,
        )

        response = self.client.post(
            '/api/v1/resources/voice-tones/',
            {
                'name': '新音色',
                'voiceCode': 'voice_male_deep_v1',
                'asrText': '重复标识',
                'isActive': True,
                'isVisible': False,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], '该音色标识已存在')

    def test_create_voice_tone_rejects_invalid_icon(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.create')

        response = self.client.post(
            '/api/v1/resources/voice-tones/',
            {
                'name': '图标异常音色',
                'voiceCode': 'voice_invalid_icon',
                'asrText': '测试',
                'icon': SimpleUploadedFile('voice.txt', b'not-image', content_type='text/plain'),
                'isActive': True,
                'isVisible': True,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('图片', response.data['message'])

    def test_update_voice_tone_allows_changing_unique_voice_code_and_asr_text(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.update')
        voice_tone = VoiceTone.objects.create(
            name='活泼女声',
            voice_code='voice_female_bright_v1',
            content='旧内容',
            is_active=True,
            is_visible=True,
            tenant=self.tenant,
        )

        response = self.client.patch(
            f'/api/v1/resources/voice-tones/{voice_tone.id}/',
            {
                'voiceCode': 'voice_female_bright_v2',
                'asrText': '更新后的 ASR 结果',
                'isVisible': False,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice_tone.refresh_from_db()
        self.assertEqual(voice_tone.voice_code, 'voice_female_bright_v2')
        self.assertEqual(voice_tone.content, '更新后的 ASR 结果')
        self.assertFalse(voice_tone.is_visible)

    def test_list_voice_tones_supports_keyword_and_active_filters(self):
        self.grant_permissions('resources.voice_tones.view')
        VoiceTone.objects.create(
            name='温柔女声',
            voice_code='voice_soft_female_001',
            content='温柔内容',
            is_active=True,
            is_visible=True,
            tenant=self.tenant,
        )
        VoiceTone.objects.create(
            name='沉稳男声',
            voice_code='voice_deep_male_001',
            content='沉稳内容',
            is_active=False,
            is_visible=False,
            tenant=self.tenant,
        )

        response = self.client.get('/api/v1/resources/voice-tones/?keyword=温柔&is_active=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['voiceCode'], 'voice_soft_female_001')
        self.assertTrue(response.data['results'][0]['isVisible'])

    def test_update_voice_tone_can_clear_icon_and_audio(self):
        self.grant_permissions('resources.voice_tones.view', 'resources.voice_tones.update')
        voice_tone = VoiceTone.objects.create(
            name='音频音色',
            voice_code='voice_audio_001',
            content='带音频',
            is_active=True,
            is_visible=True,
            icon=build_test_png(),
            audio=SimpleUploadedFile('voice.wav', b'fake-wave-audio', content_type='audio/wav'),
            tenant=self.tenant,
        )

        response = self.client.patch(
            f'/api/v1/resources/voice-tones/{voice_tone.id}/',
            {'clearIcon': True, 'clearAudio': True},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['iconUrl'])
        self.assertEqual(response.data['iconName'], '')
        self.assertIsNone(response.data['iconSize'])
        self.assertFalse(response.data['hasIcon'])
        self.assertFalse(response.data['audioUrl'])
        self.assertEqual(response.data['audioName'], '')
        self.assertIsNone(response.data['audioSize'])
        self.assertFalse(response.data['hasAudio'])
        voice_tone.refresh_from_db()
        self.assertFalse(bool(voice_tone.icon))
        self.assertFalse(bool(voice_tone.audio))
