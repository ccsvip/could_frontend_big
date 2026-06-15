from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import TTSProvider, TTSVoice, TenantTTSSettings
from apps.ai_models.services import tts as tts_services
from apps.devices.models import Device
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class TTSApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.tenant_user = User.objects.create_user(username='tts-user', password='test123456')
        self.setup_tenant(self.tenant_user)
        self.role = Role.objects.create(name='TTS Test Role', code='tts_tester')
        UserRole.objects.create(user=self.tenant_user, role=self.role)
        self.provider = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.provider, voice_code='Cherry')

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'ai_models_tts',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def test_seed_creates_aliyun_provider_voices_and_update_permission(self):
        self.assertEqual(self.provider.name, '阿里云 TTS')
        self.assertEqual(self.provider.default_voice_id, self.cherry.id)
        self.assertTrue(self.cherry.avatar_path.endswith('voice_female_one.png'))
        self.assertTrue(PermissionPoint.objects.filter(code='ai_models.tts.update').exists())

    def test_tts_protocol_uses_pcm_response_format(self):
        self.assertEqual(tts_services.response_format_for_sample_rate(24000), 'pcm')
        self.assertEqual(tts_services.response_format_for_sample_rate(16000), 'pcm')

    def test_superuser_can_read_and_update_tts_settings_without_raw_key(self):
        superuser = User.objects.create_superuser(username='tts-root', password='test123456')
        self.provider.api_key = 'dashscope-secret'
        self.provider.save(update_fields=['api_key'])
        self.client.force_authenticate(user=superuser)

        read_response = self.client.get('/api/v1/settings/tts/')

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['apiKeyMasked'], 'das...cret')
        self.assertTrue(read_response.data['voices'][0]['avatarPath'].startswith('http://testserver/static/tts/voices/'))
        self.assertNotIn('dashscope-secret', str(read_response.data))

        update_response = self.client.patch(
            '/api/v1/settings/tts/',
            {
                'apiKey': 'new-dashscope-secret',
                'baseUrl': 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
                'model': 'qwen3-tts-flash-realtime',
                'sampleRate': 16000,
                'defaultVoiceId': self.cherry.id,
                'defaultTestText': '测试一句中文语音。',
                'isActive': False,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data['isActive'])
        self.assertEqual(update_response.data['sampleRate'], 16000)
        self.assertEqual(update_response.data['defaultVoiceId'], self.cherry.id)
        self.assertEqual(update_response.data['defaultTestText'], '测试一句中文语音。')
        self.assertNotIn('new-dashscope-secret', str(update_response.data))

    def test_company_user_can_select_default_voice_without_provider_secrets(self):
        self.grant_permissions('ai_models.tts.view', 'ai_models.tts.update')
        self.client.force_authenticate(user=self.tenant_user)

        options_response = self.client.get('/api/v1/ai-models/tts/options/')

        self.assertEqual(options_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('apiKey', str(options_response.data))
        self.assertNotIn('baseUrl', str(options_response.data))
        self.assertGreaterEqual(len(options_response.data['voices']), 1)

        update_response = self.client.patch(
            '/api/v1/ai-models/tts/default-voice/',
            {'voiceId': self.cherry.id},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        settings = TenantTTSSettings.objects.get(tenant=self.tenant)
        self.assertEqual(settings.default_voice_id, self.cherry.id)
        self.assertEqual(update_response.data['defaultVoiceId'], self.cherry.id)

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x01\x02')
    def test_company_test_returns_wav_wrapped_pcm(self, synthesize_tts_pcm):
        self.grant_permissions('ai_models.tts.view')
        self.provider.default_test_text = '默认测试文本'
        self.provider.save(update_fields=['default_test_text'])
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.post('/api/v1/ai-models/tts/test/', {'text': ''}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertEqual(response['X-Audio-Source-Format'], 'pcm_s16le')
        self.assertEqual(response['X-Audio-Sample-Rate'], str(self.provider.sample_rate))
        self.assertTrue(response.content.startswith(b'RIFF'))
        call_kwargs = synthesize_tts_pcm.call_args.kwargs
        self.assertEqual(call_kwargs['text'], '默认测试文本')
        self.assertEqual(call_kwargs['voice'].voice_code, 'Cherry')

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x03\x04')
    def test_device_runtime_uses_device_code_and_returns_raw_pcm(self, synthesize_tts_pcm):
        Device.objects.create(
            tenant=self.tenant,
            name='TTS Runtime Device',
            code='ANDROID-TTS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            '/api/v1/ai-models/tts/runtime/',
            {'text': '设备端测试'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-TTS-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/pcm')
        self.assertEqual(response['X-Audio-Source-Format'], 'pcm_s16le')
        self.assertEqual(response['X-Audio-Sample-Rate'], str(self.provider.sample_rate))
        self.assertEqual(response['X-TTS-Voice'], 'Cherry')
        self.assertEqual(response.content, b'\x03\x04')
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['text'], '设备端测试')
