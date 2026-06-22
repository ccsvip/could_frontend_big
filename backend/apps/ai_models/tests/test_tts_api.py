import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import TTSProvider, TTSVoice, TenantTTSSettings
from apps.ai_models.services import tts as tts_services
from apps.devices.models import Device
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class OneShotTTSUpstream:
    def __init__(self):
        self.messages = []
        self._events = iter([
            json.dumps({'type': 'response.audio.delta', 'delta': base64.b64encode(b'\x01\x02').decode('ascii')}),
            json.dumps({'type': 'session.finished'}),
        ])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        self.messages.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration


class TTSRealtimeTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tts-ws-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS WS Role', code='tts_ws_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.provider = TTSProvider.objects.get(code='aliyun')
        self.voice = TTSVoice.objects.get(provider=self.provider, voice_code='Cherry')
        self.tenant.permission_points.clear()

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

    def test_tts_realtime_streams_upstream_audio_delta_to_browser(self):
        self.grant_permissions('ai_models.tts.view')
        token = str(RefreshToken.for_user(self.user).access_token)

        config = SimpleNamespace(
            is_active=True,
            api_key='test-api-key',
            base_url='wss://tts.example/realtime',
            model='qwen3-tts-flash-realtime',
            sample_rate=24000,
            default_test_text='默认测试文本',
        )
        upstream = OneShotTTSUpstream()

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {
                    'type': 'websocket',
                    'path': '/ws/realtime/',
                    'query_string': b'',
                    'headers': [],
                },
            )
            await communicator.send_input({'type': 'websocket.connect'})
            response = await communicator.receive_output(timeout=1)
            self.assertEqual(response, {'type': 'websocket.accept'})

            with (
                patch(
                    'apps.ai_models.realtime_tts.resolve_tts_realtime_connection',
                    return_value={'user_id': self.user.id, 'tenant_id': self.tenant.id, 'is_superuser': False},
                ),
                patch('apps.ai_models.realtime_tts.get_effective_tts_config', return_value=config),
                patch('apps.ai_models.realtime_tts.is_tts_configured', return_value=True),
                patch('apps.ai_models.realtime_tts.build_tts_ws_url', return_value='wss://tts.example/realtime?model=test'),
                patch('apps.ai_models.realtime_tts.websockets.connect', return_value=upstream),
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'tts.session.start',
                        'id': 'tts-suite-1',
                        'payload': {'token': token, 'text': '你好', 'voiceId': self.voice.id},
                    }),
                })

                ready = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(ready['text']),
                    {'type': 'tts.ready', 'sampleRate': 24000, 'voice': 'Cherry', 'id': 'tts-suite-1'},
                )
                audio = await communicator.receive_output(timeout=1)
                self.assertEqual(audio, {'type': 'websocket.send', 'bytes': b'\x01\x02'})
                done = await communicator.receive_output(timeout=1)
                self.assertEqual(json.loads(done['text']), {'type': 'tts.done', 'id': 'tts-suite-1'})

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

        sent_types = [message.get('type') for message in upstream.messages]
        self.assertIn('input_text_buffer.append', sent_types)
        self.assertIn('session.finish', sent_types)

    def test_tts_realtime_allows_superuser_without_tenant_permission(self):
        from apps.ai_models.realtime_tts import resolve_tts_realtime_connection

        superuser = User.objects.create_superuser(username='tts-ws-root', password='test123456')
        token = str(RefreshToken.for_user(superuser).access_token)

        connection = resolve_tts_realtime_connection(token)

        self.assertIsNotNone(connection)
        self.assertTrue(connection['is_superuser'])

    def test_tts_realtime_resolver_accepts_device_code_without_jwt(self):
        from apps.ai_models.realtime_tts import resolve_tts_realtime_connection

        device = Device.objects.create(
            tenant=self.tenant,
            name='TTS WS Device',
            code='ANDROID-TTS-WS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        connection = resolve_tts_realtime_connection(
            '',
            query_params={'deviceCode': ['ANDROID-TTS-WS-001']},
        )

        self.assertEqual(connection['device_id'], device.id)
        self.assertEqual(connection['device_code'], 'ANDROID-TTS-WS-001')
        self.assertEqual(connection['tenant_id'], self.tenant.id)


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

    def test_superuser_can_list_tts_providers_for_card_entry(self):
        superuser = User.objects.create_superuser(username='tts-provider-root', password='test123456')
        self.provider.api_key = 'dashscope-secret'
        self.provider.save(update_fields=['api_key'])
        self.client.force_authenticate(user=superuser)

        response = self.client.get('/api/v1/settings/tts/providers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['code'], 'aliyun')
        self.assertEqual(response.data[0]['name'], '阿里云 TTS')
        self.assertIn('voiceCount', response.data[0])
        self.assertNotIn('dashscope-secret', str(response.data))

    def test_superuser_can_read_and_update_tts_settings_without_raw_key(self):
        superuser = User.objects.create_superuser(username='tts-root', password='test123456')
        self.provider.api_key = 'dashscope-secret'
        self.provider.save(update_fields=['api_key'])
        self.client.force_authenticate(user=superuser)

        read_response = self.client.get('/api/v1/settings/tts/providers/aliyun/')

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data['code'], 'aliyun')
        self.assertEqual(read_response.data['apiKeyMasked'], 'das...cret')
        self.assertTrue(read_response.data['voices'][0]['avatarPath'].startswith('http://testserver/static/tts/voices/'))
        self.assertNotIn('dashscope-secret', str(read_response.data))

        update_response = self.client.patch(
            '/api/v1/settings/tts/providers/aliyun/',
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

    def test_device_code_can_read_company_tts_options_without_jwt(self):
        Device.objects.create(
            tenant=self.tenant,
            name='TTS Options Device',
            code='ANDROID-TTS-OPTIONS-001',
            is_enabled=True,
        )

        response = self.client.get(
            '/api/v1/ai-models/tts/options/',
            HTTP_X_DEVICE_CODE='ANDROID-TTS-OPTIONS-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['provider']['code'], 'aliyun')
        self.assertGreaterEqual(len(response.data['voices']), 1)
        self.assertEqual(response.data['voices'][0]['voiceCode'], 'Cherry')
        self.assertNotIn('apiKey', str(response.data))

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

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x01\x02')
    def test_company_test_can_use_selected_voice(self, synthesize_tts_pcm):
        self.grant_permissions('ai_models.tts.view')
        other_voice = TTSVoice.objects.create(
            provider=self.provider,
            display_name='Test Voice',
            voice_code='TestVoice',
            is_active=True,
            is_visible=True,
        )
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.post(
            '/api/v1/ai-models/tts/test/',
            {'text': '测试指定音色', 'voiceId': other_voice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call_kwargs = synthesize_tts_pcm.call_args.kwargs
        self.assertEqual(call_kwargs['voice'].id, other_voice.id)

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

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x03\x04')
    def test_device_runtime_can_wrap_pcm_as_wav_for_browser_playback(self, synthesize_tts_pcm):
        Device.objects.create(
            tenant=self.tenant,
            name='TTS Runtime Browser Device',
            code='ANDROID-TTS-WAV-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            '/api/v1/ai-models/tts/runtime/',
            {'text': '浏览器播放测试', 'wrapWav': True},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-TTS-WAV-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertEqual(response['X-Audio-Source-Format'], 'pcm_s16le')
        self.assertTrue(response.content.startswith(b'RIFF'))
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['text'], '浏览器播放测试')

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x05\x06')
    def test_device_runtime_can_use_selected_voice_by_device_code(self, synthesize_tts_pcm):
        other_voice = TTSVoice.objects.create(
            provider=self.provider,
            display_name='Device Voice',
            voice_code='DeviceVoice',
            is_active=True,
            is_visible=True,
        )
        Device.objects.create(
            tenant=self.tenant,
            name='TTS Runtime Voice Device',
            code='ANDROID-TTS-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            '/api/v1/ai-models/tts/runtime/',
            {'text': '设备端指定音色', 'voiceId': other_voice.id},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-TTS-VOICE-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['X-TTS-Voice'], 'DeviceVoice')
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['voice'].id, other_voice.id)
