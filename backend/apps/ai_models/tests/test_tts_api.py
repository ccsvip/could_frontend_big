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
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class TTSServiceTests(TestCase):
    def test_split_tts_text_removes_configured_text_from_segments(self):
        segments = tts_services.split_tts_text(
            '第一句正常播报。第二句包含（动作提示）也要播报。第三句继续播报。',
            exclude_patterns=['（动作提示）'],
        )

        self.assertEqual(segments, ['第一句正常播报。', '第二句包含也要播报。', '第三句继续播报。'])

    def test_pop_tts_text_segments_removes_configured_text_and_keeps_remainder(self):
        segments, rest = tts_services.pop_tts_text_segments(
            '第一句正常播报。第二句包含内心独白也要播报。第三句还没结束',
            exclude_patterns=['内心独白'],
        )

        self.assertEqual(segments, ['第一句正常播报。', '第二句包含也要播报。'])
        self.assertEqual(rest, '第三句还没结束')

    def test_split_tts_text_skips_segment_when_exclusions_remove_everything(self):
        segments = tts_services.split_tts_text('（动作提示）', exclude_patterns=['（动作提示）'])

        self.assertEqual(segments, [])


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


class ErrorTTSUpstream:
    def __init__(self):
        self.messages = []
        self._events = iter([
            json.dumps({
                'event_id': 'event_error_1',
                'type': 'error',
                'error': {
                    'code': 'rate_limit_exceeded',
                    'message': 'Too many characters in realtime TTS request.',
                },
            }),
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
                    {'type': 'tts.ready', 'sampleRate': 24000, 'responseFormat': 'pcm', 'voice': 'Cherry', 'id': 'tts-suite-1'},
                )
                segment_start = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(segment_start['text']),
                    {'type': 'tts.segment_start', 'payload': {'index': 1, 'text': '你好'}, 'id': 'tts-suite-1'},
                )
                audio = await communicator.receive_output(timeout=1)
                self.assertEqual(audio, {'type': 'websocket.send', 'bytes': b'\x01\x02'})
                segment_end = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(segment_end['text']),
                    {'type': 'tts.segment_end', 'payload': {'index': 1}, 'id': 'tts-suite-1'},
                )
                done = await communicator.receive_output(timeout=1)
                self.assertEqual(json.loads(done['text']), {'type': 'tts.done', 'id': 'tts-suite-1'})

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

        sent_types = [message.get('type') for message in upstream.messages]
        self.assertIn('input_text_buffer.append', sent_types)
        self.assertIn('session.finish', sent_types)

    def test_tts_realtime_logs_upstream_error_details(self):
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
        upstream = ErrorTTSUpstream()

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
                with self.assertLogs('apps.ai_models.realtime_tts', level='ERROR') as logs:
                    await communicator.send_input({
                        'type': 'websocket.receive',
                        'text': json.dumps({
                            'type': 'tts.session.start',
                            'id': 'tts-error-1',
                            'payload': {'token': token, 'text': '很长的测试文本', 'voiceId': self.voice.id},
                        }),
                    })
                    ready = await communicator.receive_output(timeout=1)
                    self.assertEqual(json.loads(ready['text'])['type'], 'tts.ready')
                    error = await communicator.receive_output(timeout=1)
                    payload = json.loads(error['text'])
                    self.assertEqual(payload['type'], 'tts.error')
                    self.assertIn('Too many characters', payload['message'])

                combined_logs = '\n'.join(logs.output)
                self.assertIn('tts.realtime.upstream_error', combined_logs)
                self.assertIn('rate_limit_exceeded', combined_logs)
                self.assertIn('Too many characters', combined_logs)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

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

    def test_tts_realtime_resolver_ignores_foreign_tenant_for_company_user(self):
        from apps.ai_models.realtime_tts import resolve_tts_realtime_connection

        self.grant_permissions('ai_models.tts.view')
        other_tenant = Tenant.objects.create(name='Foreign TTS Tenant', code='foreign-tts-tenant')
        token = str(RefreshToken.for_user(self.user).access_token)

        connection = resolve_tts_realtime_connection(
            token,
            query_params={'tenantId': [str(other_tenant.id)]},
        )

        self.assertIsNotNone(connection)
        self.assertFalse(connection['is_superuser'])
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

    def test_tts_session_model_alias_maps_to_real_upstream_model(self):
        config = tts_services.get_effective_tts_config(self.provider)

        standard_session = tts_services._session_update_event(
            config,
            self.cherry,
            {'model_code': 'standard'},
        )['session']
        instructional_session = tts_services._session_update_event(
            config,
            self.cherry,
            {'modelCode': 'instructional'},
        )['session']

        self.assertEqual(standard_session['model'], 'qwen3-tts-flash-realtime')
        self.assertEqual(instructional_session['model'], 'qwen3-tts-instruct-flash-realtime')

    def test_tts_model_alias_filters_unsupported_voices(self):
        dylan = TTSVoice.objects.get(provider=self.provider, voice_code='Dylan')
        jennifer = TTSVoice.objects.get(provider=self.provider, voice_code='Jennifer')
        elias = TTSVoice.objects.get(provider=self.provider, voice_code='Elias')

        instructional_voices = tts_services.get_available_tts_voices(
            self.provider,
            model_code='instructional',
        )
        standard_voices = tts_services.get_available_tts_voices(
            self.provider,
            model_code='standard',
        )

        self.assertFalse(instructional_voices.filter(id=dylan.id).exists())
        self.assertFalse(instructional_voices.filter(id=jennifer.id).exists())
        self.assertTrue(instructional_voices.filter(id=elias.id).exists())
        self.assertTrue(standard_voices.filter(id=dylan.id).exists())
        self.assertTrue(standard_voices.filter(id=jennifer.id).exists())

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
        self.assertEqual(read_response.data['ttsSessionConfig']['mode'], 'server_commit')
        self.assertTrue(read_response.data['voices'][0]['avatarPath'].startswith('http://testserver/static/tts/voices/'))
        self.assertNotIn('dashscope-secret', str(read_response.data))

        update_response = self.client.patch(
            '/api/v1/settings/tts/providers/aliyun/',
            {
                'apiKey': 'new-dashscope-secret',
                'baseUrl': 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
                'model': 'qwen3-tts-flash-realtime',
                'sampleRate': 16000,
                'ttsSessionConfig': {
                    'mode': 'commit',
                    'languageType': 'Chinese',
                    'responseFormat': 'opus',
                    'sampleRate': 48000,
                    'speechRate': 1.25,
                    'volume': 80,
                    'pitchRate': 0.85,
                    'bitRate': 192,
                    'instructions': '用温柔自然的语气播报。',
                    'optimizeInstructions': True,
                },
                'defaultVoiceId': self.cherry.id,
                'defaultTestText': '测试一句中文语音。',
                'isActive': False,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data['isActive'])
        self.assertEqual(update_response.data['sampleRate'], 16000)
        self.assertEqual(update_response.data['ttsSessionConfig']['language_type'], 'Chinese')
        self.assertEqual(update_response.data['ttsSessionConfig']['response_format'], 'opus')
        self.assertEqual(update_response.data['ttsSessionConfig']['sample_rate'], 48000)
        self.assertEqual(update_response.data['defaultVoiceId'], self.cherry.id)
        self.assertEqual(update_response.data['defaultTestText'], '测试一句中文语音。')
        self.assertNotIn('new-dashscope-secret', str(update_response.data))

    def test_company_user_can_select_default_voice_and_model_alias_without_provider_secrets(self):
        self.grant_permissions('ai_models.tts.view', 'ai_models.tts.update')
        self.provider.model = 'qwen3-tts-instruct-flash-realtime'
        self.provider.save(update_fields=['model'])
        self.client.force_authenticate(user=self.tenant_user)

        options_response = self.client.get('/api/v1/ai-models/tts/options/')

        self.assertEqual(options_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('apiKey', str(options_response.data))
        self.assertNotIn('baseUrl', str(options_response.data))
        self.assertNotIn('qwen3-tts-instruct-flash-realtime', str(options_response.data))
        self.assertNotIn('qwen3-tts-flash-realtime', str(options_response.data))
        self.assertEqual(options_response.data['provider']['defaultModelCode'], 'instructional')
        self.assertEqual(
            options_response.data['provider']['modelOptions'],
            [
                {
                    'code': 'instructional',
                    'label': '情感增强',
                    'supportsInstructionControl': True,
                },
                {
                    'code': 'standard',
                    'label': '标准播报',
                    'supportsInstructionControl': False,
                },
            ],
        )
        self.assertEqual(options_response.data['ttsSessionConfig']['mode'], 'server_commit')
        self.assertGreaterEqual(len(options_response.data['voices']), 1)

        update_response = self.client.patch(
            '/api/v1/ai-models/tts/default-voice/',
            {
                'modelCode': 'standard',
                'voiceId': self.cherry.id,
                'ttsSessionConfig': {
                    'languageType': 'Chinese',
                    'responseFormat': 'mp3',
                    'sampleRate': 24000,
                    'speechRate': 1.1,
                    'volume': 70,
                    'pitchRate': 0.9,
                    'bitRate': 128,
                },
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        settings = TenantTTSSettings.objects.get(tenant=self.tenant)
        self.assertEqual(settings.default_voice_id, self.cherry.id)
        self.assertEqual(settings.tts_session_config['model_code'], 'standard')
        self.assertEqual(settings.tts_session_config['language_type'], 'Chinese')
        self.assertEqual(settings.tts_session_config['response_format'], 'mp3')
        self.assertEqual(update_response.data['defaultVoiceId'], self.cherry.id)
        self.assertEqual(update_response.data['provider']['defaultModelCode'], 'standard')
        self.assertEqual(update_response.data['ttsSessionConfig']['language_type'], 'Chinese')

    def test_company_user_cannot_save_voice_unsupported_by_selected_model_alias(self):
        self.grant_permissions('ai_models.tts.view', 'ai_models.tts.update')
        dylan = TTSVoice.objects.get(provider=self.provider, voice_code='Dylan')
        self.client.force_authenticate(user=self.tenant_user)

        update_response = self.client.patch(
            '/api/v1/ai-models/tts/default-voice/',
            {
                'modelCode': 'instructional',
                'voiceId': dylan.id,
            },
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(update_response.data['voiceId'], '所选音色不支持当前播报模型')

    def test_realtime_voice_resolver_rejects_voice_unsupported_by_model_alias(self):
        from apps.ai_models.realtime_tts import resolve_tts_voice

        jennifer = TTSVoice.objects.get(provider=self.provider, voice_code='Jennifer')

        voice = resolve_tts_voice(
            {'user_id': self.tenant_user.id, 'tenant_id': self.tenant.id, 'is_superuser': False},
            jennifer.id,
            self.provider,
            model_code='instructional',
        )

        self.assertIsNone(voice)

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
        other_voice = TTSVoice.objects.get(provider=self.provider, voice_code='Elias')
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
        other_voice = TTSVoice.objects.get(provider=self.provider, voice_code='Elias')
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
        self.assertEqual(response['X-TTS-Voice'], 'Elias')
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['voice'].id, other_voice.id)
