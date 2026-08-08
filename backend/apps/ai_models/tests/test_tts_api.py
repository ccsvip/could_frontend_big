import base64
import asyncio
import json
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.credential_crypto import decrypt_credential
from apps.ai_models.models import (
    CosyVoiceSettings,
    TenantTTSProviderGrant,
    TenantTTSSettings,
    TenantTTSVoiceTestText,
    TTSProvider,
    TTSVoice,
)
from apps.ai_models.services import cosyvoice as cosyvoice_services, tts as tts_services
from apps.devices.models import Device
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class TTSServiceTests(TestCase):
    def test_split_tts_text_is_identity_without_page_rules(self):
        source = '**球形LED显示屏** \n- 内球幕LED显示屏'

        segments = tts_services.split_tts_text(source)

        self.assertEqual(segments, ['**球形LED显示屏** \n- 内球幕LED显示屏'])
        self.assertEqual(''.join(segments), source)

    def test_split_tts_text_keeps_boundaries_after_configured_characters_are_removed(self):
        segments = tts_services.split_tts_text(
            '球形LED显示屏。\r\n内球幕LED显示屏。',
            filter_punctuation='。\r\n',
        )

        self.assertEqual(segments, ['球形LED显示屏', '内球幕LED显示屏'])
    def test_split_tts_text_keeps_product_lists_in_one_sentence(self):
        source = '公司产品涵盖LED幕墙屏、LED异形屏、\nLED户外显示屏。'

        segments = tts_services.split_tts_text(source)

        self.assertEqual(segments, [source])
    def test_streaming_processor_emits_sized_soft_boundaries(self):
        source = '公司产品涵盖LED幕墙屏、LED异形屏、LED户外显示屏、LED室内显示屏。'
        processor = tts_services.TTSStreamingTextProcessor(soft_boundary_target=20)

        segments = [*processor.feed(source), *processor.finish()]

        self.assertEqual(segments, [
            '公司产品涵盖LED幕墙屏、LED异形屏、',
            'LED户外显示屏、LED室内显示屏。',
        ])
        self.assertEqual(''.join(segments), source)

    def test_apply_agent_tts_rules_uses_page_rule_order(self):
        filtered = tts_services.apply_agent_tts_rules(
            '甲a-b乙',
            filter_punctuation='-',
            exclude_patterns=['a-b'],
        )

        self.assertEqual(filtered, '甲乙')

    def test_streaming_filter_matches_exclusion_across_deltas(self):
        processor = tts_services.TTSStreamingTextProcessor(
            exclude_patterns=['内心独白'],
        )

        first = processor.feed('第一句。内心')
        second = processor.feed('独白第二句。')
        final = processor.finish()

        self.assertEqual(first, ['第一句。'])
        self.assertEqual(second, ['第二句。'])
        self.assertEqual(final, [])

    def test_streaming_filter_is_lossless_at_every_delta_cut(self):
        source = '甲[动作]乙🙂，丙\r\n尾部'
        rules = {
            'exclude_patterns': ['[动作]'],
            'filter_emoji': True,
            'filter_punctuation': '，\r\n',
        }
        expected = tts_services.apply_agent_tts_rules(source, **rules)

        for cut in range(len(source) + 1):
            with self.subTest(cut=cut):
                processor = tts_services.TTSStreamingTextProcessor(**rules)
                segments = [
                    *processor.feed(source[:cut]),
                    *processor.feed(source[cut:]),
                    *processor.finish(),
                ]
                self.assertEqual(''.join(segments), expected)

    def test_streaming_filter_does_not_hard_split_unpunctuated_text(self):
        for length in (80, 81, 200):
            with self.subTest(length=length):
                source = '甲' * length
                processor = tts_services.TTSStreamingTextProcessor()

                self.assertEqual(processor.feed(source), [])
                self.assertEqual(processor.finish(), [source])

    def test_streaming_filter_preserves_whitespace_only_content(self):
        source = ' \r\n\t'
        processor = tts_services.TTSStreamingTextProcessor()

        segments = [*processor.feed(source), *processor.finish()]

        self.assertEqual(''.join(segments), source)

    def test_streaming_filter_applies_exclusion_emoji_and_character_rules_once(self):
        source = '前缀[动作]-🙂正文。'
        processor = tts_services.TTSStreamingTextProcessor(
            exclude_patterns=['[动作]'],
            filter_emoji=True,
            filter_punctuation='-。',
        )

        segments = [*processor.feed('前缀[动'), *processor.feed('作]-🙂正文。'), *processor.finish()]

        self.assertEqual(segments, ['前缀正文'])
        self.assertEqual(''.join(segments), tts_services.apply_agent_tts_rules(
            source,
            exclude_patterns=['[动作]'],
            filter_emoji=True,
            filter_punctuation='-。',
        ))

    def test_new_streaming_filter_does_not_reuse_previous_session_state(self):
        interrupted = tts_services.TTSStreamingTextProcessor(exclude_patterns=['内心独白'])
        self.assertEqual(interrupted.feed('内心'), [])

        replacement = tts_services.TTSStreamingTextProcessor(exclude_patterns=['内心独白'])
        self.assertEqual(replacement.feed('正常回答。'), ['正常回答。'])
        self.assertEqual(replacement.finish(), [])

    def test_cosyvoice_task_text_limit_counts_all_messages(self):
        sent_characters = tts_services.validate_cosyvoice_task_text(
            '甲' * tts_services.COSYVOICE_MAX_MESSAGE_CHARACTERS,
            tts_services.COSYVOICE_MAX_TASK_CHARACTERS - tts_services.COSYVOICE_MAX_MESSAGE_CHARACTERS,
        )

        self.assertEqual(sent_characters, tts_services.COSYVOICE_MAX_TASK_CHARACTERS)
        with self.assertRaises(RuntimeError) as ctx:
            tts_services.validate_cosyvoice_task_text('乙', sent_characters)
        self.assertIn('200000', str(ctx.exception))



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


class CosyVoiceTTSUpstream:
    def __init__(self):
        self.messages = []
        self._events = asyncio.Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        payload = json.loads(message)
        self.messages.append(payload)
        header = payload['header']
        if header['action'] == 'run-task':
            await self._events.put(json.dumps({'type': 'session.finished'}))
            await self._events.put(json.dumps({
                'header': {'task_id': header['task_id'], 'event': 'task-started', 'attributes': {}},
                'payload': {},
            }))
        elif header['action'] == 'finish-task':
            await self._events.put(json.dumps({'type': 'session.finished'}))
            await self._events.put(b'\x01\x02')
            await self._events.put(b'\x03\x04')
            await self._events.put(json.dumps({
                'header': {'task_id': header['task_id'], 'event': 'task-finished', 'attributes': {}},
                'payload': {'usage': {'characters': 6}},
            }))

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._events.get()


class FailedCosyVoiceTTSUpstream(CosyVoiceTTSUpstream):
    async def send(self, message):
        payload = json.loads(message)
        self.messages.append(payload)
        header = payload['header']
        if header['action'] == 'run-task':
            await self._events.put(json.dumps({
                'header': {
                    'task_id': header['task_id'],
                    'event': 'task-failed',
                    'error_code': 'InvalidParameter',
                    'error_message': 'TTS input is invalid.',
                    'attributes': {},
                },
                'payload': {},
            }))


class CosyVoiceTTSServiceTests(TestCase):
    def _config(self):
        return SimpleNamespace(
            provider_code='cosyvoice',
            is_active=True,
            api_key='test-api-key',
            base_url='wss://configured.example/api-ws/v1/inference',
            model='cosyvoice-v3.5-plus',
            sample_rate=24000,
        )

    @patch('apps.ai_models.services.tts.websockets.connect')
    def test_cosyvoice_uses_task_protocol_and_aggregates_binary_pcm(self, connect):
        upstream = CosyVoiceTTSUpstream()
        connect.return_value = upstream
        config = self._config()

        pcm = tts_services.synthesize_tts_pcm(
            text='第一句。第二句。',
            voice=SimpleNamespace(voice_code='custom-voice'),
            config=config,
        )

        self.assertEqual(pcm, b'\x01\x02\x03\x04')
        connect.assert_called_once_with(
            config.base_url,
            additional_headers=[('Authorization', 'Bearer test-api-key')],
            user_agent_header='solin-admin/1.0',
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            max_size=8 * 1024 * 1024,
        )
        actions = [message['header']['action'] for message in upstream.messages]
        self.assertEqual(actions, ['run-task', 'continue-task', 'continue-task', 'finish-task'])
        task_id = upstream.messages[0]['header']['task_id']
        self.assertRegex(task_id, r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
        self.assertTrue(all(message['header']['task_id'] == task_id for message in upstream.messages))
        self.assertEqual(
            upstream.messages[0],
            {
                'header': {'action': 'run-task', 'task_id': task_id, 'streaming': 'duplex'},
                'payload': {
                    'task_group': 'audio',
                    'task': 'tts',
                    'function': 'SpeechSynthesizer',
                    'model': 'cosyvoice-v3.5-plus',
                    'input': {},
                    'parameters': {
                        'text_type': 'PlainText',
                        'voice': 'custom-voice',
                        'format': 'pcm',
                        'sample_rate': 24000,
                        'volume': 50,
                        'rate': 1.0,
                        'pitch': 1.0,
                    },
                },
            },
        )
        self.assertEqual(
            [message['payload'] for message in upstream.messages[1:3]],
            [{'input': {'text': '第一句。'}}, {'input': {'text': '第二句。'}}],
        )
        self.assertEqual(upstream.messages[3]['payload'], {'input': {}})

    @patch('apps.ai_models.services.tts.websockets.connect')
    def test_cosyvoice_task_failed_raises_official_error(self, connect):
        upstream = FailedCosyVoiceTTSUpstream()
        connect.return_value = upstream

        with self.assertRaisesRegex(RuntimeError, r'^InvalidParameter: TTS input is invalid\.$'):
            tts_services.synthesize_tts_pcm(
                text='失败文本。',
                voice=SimpleNamespace(voice_code='custom-voice'),
                config=self._config(),
            )

        self.assertEqual([message['header']['action'] for message in upstream.messages], ['run-task'])

class TTSRealtimeTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tts-ws-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS WS Role', code='tts_ws_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.provider = TTSProvider.objects.get(code='aliyun')
        self.voice = TTSVoice.objects.get(provider=self.provider, voice_code='Cherry')
        # Realtime voice resolution now goes through card authorization.
        TenantTTSProviderGrant.objects.update_or_create(
            tenant=self.tenant,
            provider=self.provider,
            defaults={'is_active': True},
        )
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
                    self.assertEqual(payload['error'], {'code': '1027', 'message': 'TTS 上游服务暂不可用'})
                    self.assertNotIn('message', payload)

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
        # Company TTS is now card-authorization gated: a tenant created directly in
        # a test has no grant until a superuser allocates one.
        TenantTTSProviderGrant.objects.update_or_create(
            tenant=self.tenant,
            provider=self.provider,
            defaults={'is_active': True},
        )

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
        # Card controls are now authoritative on the per-card grant, so saving one
        # card's config cannot overwrite another card's.
        card_config = TenantTTSProviderGrant.objects.get(
            tenant=self.tenant,
            provider=self.provider,
        ).public_config
        self.assertEqual(card_config['model_code'], 'standard')
        self.assertEqual(card_config['language_type'], 'Chinese')
        self.assertEqual(card_config['response_format'], 'mp3')
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
        from apps.ai_models.realtime_tts import resolve_realtime_tts_voice

        jennifer = TTSVoice.objects.get(provider=self.provider, voice_code='Jennifer')

        resolution = resolve_realtime_tts_voice(
            {'user_id': self.tenant_user.id, 'tenant_id': self.tenant.id, 'is_superuser': False},
            jennifer.id,
            model_code='instructional',
        )

        self.assertIsNone(resolution.voice)
        self.assertEqual(resolution.error_key, 'TTS_VOICE_NOT_AVAILABLE')

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
    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x05\x06')
    def test_company_test_uses_voice_override_when_text_is_empty(self, synthesize_tts_pcm):
        self.grant_permissions('ai_models.tts.view')
        other_voice = TTSVoice.objects.get(provider=self.provider, voice_code='Elias')
        TenantTTSVoiceTestText.objects.create(
            tenant=self.tenant,
            voice=other_voice,
            test_text='该音色专属试听',
        )
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.post(
            '/api/v1/ai-models/tts/test/',
            {'text': '', 'voiceId': other_voice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['text'], '该音色专属试听')

        synthesize_tts_pcm.reset_mock()
        explicit = self.client.post(
            '/api/v1/ai-models/tts/test/',
            {'text': '临时试听内容', 'voiceId': other_voice.id},
            format='json',
        )

        self.assertEqual(explicit.status_code, status.HTTP_200_OK)
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['text'], '临时试听内容')

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

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x07\x08')
    def test_device_runtime_uses_bound_device_voice_before_company_default(self, synthesize_tts_pcm):
        other_voice = TTSVoice.objects.get(provider=self.provider, voice_code='Elias')
        Device.objects.create(
            tenant=self.tenant,
            name='TTS Runtime Bound Voice Device',
            code='ANDROID-TTS-BOUND-VOICE-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            tts_voice=other_voice,
        )
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            '/api/v1/ai-models/tts/runtime/',
            {'text': '设备绑定音色测试'},
            format='json',
            HTTP_X_DEVICE_CODE='ANDROID-TTS-BOUND-VOICE-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['X-TTS-Voice'], 'Elias')
        self.assertEqual(synthesize_tts_pcm.call_args.kwargs['voice'].id, other_voice.id)

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


class CosyVoiceApiTests(APITestCase):
    settings_path = '/api/v1/settings/tts/cosyvoice/'
    websocket_url = 'wss://workspace-123.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
    customization_url = 'https://workspace-123.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization'

    def setUp(self):
        self.superuser = User.objects.create_superuser(username='cosyvoice-root', password='test123456')

    def authenticate_superuser(self):
        self.client.force_authenticate(user=self.superuser)

    def test_dedicated_settings_are_superuser_only_and_generic_route_rejects_cosyvoice(self):
        self.assertEqual(self.client.get(self.settings_path).status_code, status.HTTP_401_UNAUTHORIZED)
        self.authenticate_superuser()

        response = self.client.get(self.settings_path)
        generic_response = self.client.get('/api/v1/settings/tts/providers/cosyvoice/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['model'], 'cosyvoice-v3.5-plus')
        self.assertEqual(generic_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_settings_mask_key_and_accept_only_cosyvoice_default_voice(self):
        self.authenticate_superuser()
        qwen_voice = TTSVoice.objects.get(provider__code='aliyun', voice_code='Cherry')

        rejected = self.client.patch(self.settings_path, {'defaultVoiceId': qwen_voice.id}, format='json')
        updated = self.client.patch(
            self.settings_path,
            {
                'apiKey': 'cosyvoice-secret',
                'websocketUrl': self.websocket_url,
                'customizationUrl': self.customization_url,
                'defaultTestText': 'CosyVoice 试听文本。',
            },
            format='json',
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['apiKeyMasked'], '****')
        self.assertTrue(updated.data['apiKeyConfigured'])
        self.assertTrue(updated.data['configured'])
        self.assertNotIn('cosyvoice-secret', str(updated.data))

        settings_obj = CosyVoiceSettings.objects.get(provider__code='cosyvoice')
        self.assertNotEqual(settings_obj.api_key_encrypted, 'cosyvoice-secret')
        self.assertEqual(decrypt_credential(settings_obj.api_key_encrypted), 'cosyvoice-secret')

    def test_settings_require_official_beijing_service_urls(self):
        self.authenticate_superuser()

        insecure_websocket = self.client.patch(
            self.settings_path,
            {'websocketUrl': 'ws://workspace-123.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'},
            format='json',
        )
        insecure_customization = self.client.patch(
            self.settings_path,
            {'customizationUrl': 'http://workspace-123.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization'},
            format='json',
        )

        self.assertEqual(insecure_websocket.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('北京地域端点', insecure_websocket.data['message'])
        self.assertEqual(insecure_customization.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('北京地域端点', insecure_customization.data['message'])
        invalid_endpoints = {
            'websocketUrl': [
                f'{self.websocket_url}/',
                f'{self.websocket_url}?debug=true',
                f'{self.websocket_url}#fragment',
                f'{self.websocket_url} ',
                'wss://workspace-123.cn-beijing.maas.aliyuncs.com:443/api-ws/v1/inference',
                'wss://workspace-123@evil.example/api-ws/v1/inference',
                'wss://workspace-123.cn-beijing.maas.aliyuncs.com.evil.example/api-ws/v1/inference',
            ],
            'customizationUrl': [
                f'{self.customization_url}/',
                f'{self.customization_url}?debug=true',
                f'{self.customization_url}#fragment',
                f'{self.customization_url} ',
                'https://workspace-123.cn-beijing.maas.aliyuncs.com:443/api/v1/services/audio/tts/customization',
                'https://workspace-123@evil.example/api/v1/services/audio/tts/customization',
                'https://workspace-123.cn-beijing.maas.aliyuncs.com.evil.example/api/v1/services/audio/tts/customization',
            ],
        }
        for field, urls in invalid_endpoints.items():
            for url in urls:
                with self.subTest(field=field, url=url):
                    response = self.client.patch(self.settings_path, {field: url}, format='json')

                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_runtime_rejects_whitespace_padded_websocket_endpoint(self):
        settings_obj = cosyvoice_services.get_cosyvoice_settings()
        settings_obj.websocket_url = f'{self.websocket_url} '

        with self.assertRaises(cosyvoice_services.CosyVoiceCustomizationError) as error:
            cosyvoice_services.get_effective_cosyvoice_tts_config(settings_obj)

        self.assertEqual(error.exception.status_code, status.HTTP_400_BAD_REQUEST)


    def test_settings_reject_singapore_customization_url_without_replacing_beijing_configuration(self):
        self.authenticate_superuser()
        configured = self.client.patch(
            self.settings_path,
            {
                'apiKey': 'cosyvoice-secret',
                'websocketUrl': self.websocket_url,
                'customizationUrl': self.customization_url,
            },
            format='json',
        )
        rejected = self.client.patch(
            self.settings_path,
            {
                'customizationUrl': (
                    'https://workspace-123.ap-southeast-1.maas.aliyuncs.com/'
                    'api/v1/services/audio/tts/customization'
                ),
            },
            format='json',
        )
        current = self.client.get(self.settings_path)

        self.assertEqual(configured.status_code, status.HTTP_200_OK)
        self.assertTrue(configured.data['configured'])
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('北京地域端点', rejected.data['message'])
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        self.assertEqual(current.data['customizationUrl'], self.customization_url)
        self.assertTrue(current.data['configured'])

    def test_unprofiled_cosyvoice_voice_cannot_be_exposed_or_selected(self):
        self.authenticate_superuser()
        self.client.get(self.settings_path)
        provider = TTSProvider.objects.get(code='cosyvoice')
        unprofiled_voice = TTSVoice.objects.create(
            provider=provider,
            display_name='无效音色',
            voice_code='unprofiled-cosyvoice',
        )

        set_default = self.client.patch(self.settings_path, {'defaultVoiceId': unprofiled_voice.id}, format='json')
        settings_response = self.client.get(self.settings_path)
        detail_response = self.client.patch(f'{self.settings_path}voices/{unprofiled_voice.id}/', {'isActive': False}, format='json')

        self.assertEqual(set_default.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(settings_response.status_code, status.HTTP_200_OK)
        self.assertEqual(settings_response.data['voices'], [])
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_enroll_https_voice_persists_only_custom_profile(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-enrolled-1'}}

        insecure = self.client.post(f'{self.settings_path}voices/enroll/', {'displayName': '测试音色', 'sourceAudioUrl': 'http://example.com/source.wav'}, format='json')
        response = self.client.post(f'{self.settings_path}voices/enroll/', {'displayName': '测试音色', 'sourceAudioUrl': 'https://example.com/source.wav'}, format='json')

        self.assertEqual(insecure.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        voice = TTSVoice.objects.get(voice_code='cv-enrolled-1')
        self.assertEqual(voice.provider.code, 'cosyvoice')
        self.assertEqual(voice.cosyvoice_profile.source_type, 'enroll')
        self.assertEqual(voice.cosyvoice_profile.source_audio_url, 'https://example.com/source.wav')
        self.assertEqual(post_customization.call_args.args[1]['input']['target_model'], 'cosyvoice-v3.5-plus')

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_design_and_delete_use_cosyvoice_remote_voice(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-designed-1'}}

        created = self.client.post(f'{self.settings_path}voices/design/', {'displayName': 'WarmVoice', 'description': '温暖、自然的女声', 'language': 'zh'}, format='json')
        voice = TTSVoice.objects.get(voice_code='cv-designed-1')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(voice.cosyvoice_profile.source_type, 'design')
        self.assertEqual(
            post_customization.call_args.args[1]['input']['language_hints'],
            ['zh'],
        )
        deleted = self.client.delete(f'{self.settings_path}voices/{voice.id}/')
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TTSVoice.objects.filter(id=voice.id).exists())
        self.assertEqual(
            post_customization.call_args.args[1]['input'],
            {'action': 'delete_voice', 'voice_id': 'cv-designed-1'},
        )

    def _build_test_png(self, name: str = 'voice-avatar.png') -> SimpleUploadedFile:
        image = Image.new('RGB', (8, 8), color=(15, 118, 110))
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_voice_json_edit_updates_fields_and_default(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-edit-1'}}
        created = self.client.post(
            f'{self.settings_path}voices/design/',
            {'displayName': '编辑前', 'description': '用于编辑测试', 'language': 'zh'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        voice_id = created.data['id']

        updated = self.client.patch(
            f'{self.settings_path}voices/{voice_id}/',
            {'displayName': '编辑后', 'isActive': False, 'isDefault': True},
            format='json',
        )

        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['displayName'], '编辑后')
        self.assertFalse(updated.data['isActive'])
        self.assertTrue(updated.data['isDefault'])
        voice = TTSVoice.objects.get(id=voice_id)
        self.assertEqual(voice.display_name, '编辑后')
        self.assertFalse(voice.is_active)
        settings_obj = CosyVoiceSettings.objects.get(provider__code='cosyvoice')
        self.assertEqual(settings_obj.default_voice_id, voice_id)

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_voice_avatar_multipart_upload_persists_media_path(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-avatar-1'}}
        created = self.client.post(
            f'{self.settings_path}voices/design/',
            {'displayName': '带头像音色', 'description': '上传头像', 'language': 'zh'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        voice_id = created.data['id']

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                response = self.client.patch(
                    f'{self.settings_path}voices/{voice_id}/',
                    {'avatar': self._build_test_png()},
                    format='multipart',
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn('/media/tts/voice-avatars/', response.data['avatarPath'])
                voice = TTSVoice.objects.get(id=voice_id)
                self.assertTrue(voice.avatar_path.startswith('/media/tts/voice-avatars/'))
                self.assertIn(str(voice_id), voice.avatar_path)


    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_enroll_with_avatar_multipart_persists_media_path(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-enroll-avatar-1'}}

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                response = self.client.post(
                    f'{self.settings_path}voices/enroll/',
                    {
                        'displayName': '复刻带头像',
                        'sourceAudioUrl': 'https://example.com/source.wav',
                        'avatar': self._build_test_png('enroll-avatar.png'),
                    },
                    format='multipart',
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertIn('/media/tts/voice-avatars/', response.data['avatarPath'])
                voice = TTSVoice.objects.get(voice_code='cv-enroll-avatar-1')
                self.assertTrue(voice.avatar_path.startswith('/media/tts/voice-avatars/'))
                self.assertIn(str(voice.id), voice.avatar_path)

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_enroll_with_invalid_avatar_rejects_before_create(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-enroll-avatar-bad'}}

        response = self.client.post(
            f'{self.settings_path}voices/enroll/',
            {
                'displayName': '复刻非法头像',
                'sourceAudioUrl': 'https://example.com/source.wav',
                'avatar': SimpleUploadedFile(
                    'not-image.txt',
                    b'not-an-image',
                    content_type='text/plain',
                ),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TTSVoice.objects.filter(voice_code='cv-enroll-avatar-bad').exists())
        post_customization.assert_not_called()

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_voice_avatar_rejects_invalid_file_type(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-avatar-bad'}}
        created = self.client.post(
            f'{self.settings_path}voices/design/',
            {'displayName': '非法头像', 'description': '拒绝非图片', 'language': 'zh'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        voice_id = created.data['id']

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                response = self.client.patch(
                    f'{self.settings_path}voices/{voice_id}/',
                    {
                        'avatar': SimpleUploadedFile(
                            'not-image.txt',
                            b'not-an-image',
                            content_type='text/plain',
                        ),
                    },
                    format='multipart',
                )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        voice = TTSVoice.objects.get(id=voice_id)
        self.assertFalse(voice.avatar_path.startswith('/media/tts/voice-avatars/'))



    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_clone_without_owner_tenant_stays_platform_public(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-public-1'}}

        response = self.client.post(
            f'{self.settings_path}voices/enroll/',
            {'displayName': '公有音色', 'sourceAudioUrl': 'https://example.com/source.wav'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(TTSVoice.objects.get(voice_code='cv-public-1').owner_tenant_id)

    @patch('apps.ai_models.services.cosyvoice._post_customization')
    def test_clone_with_owner_tenant_is_private_to_that_company(self, post_customization):
        self.authenticate_superuser()
        post_customization.return_value = {'output': {'voice_id': 'cv-owned-1'}}
        owner = Tenant.objects.create(name='复刻甲公司', code='clone-owner-a')
        other = Tenant.objects.create(name='复刻乙公司', code='clone-owner-b')
        cosyvoice = TTSProvider.objects.get(code='cosyvoice')
        for tenant in (owner, other):
            TenantTTSProviderGrant.objects.create(tenant=tenant, provider=cosyvoice, is_active=True)

        response = self.client.post(
            f'{self.settings_path}voices/enroll/',
            {
                'displayName': '甲公司专属音色',
                'sourceAudioUrl': 'https://example.com/source.wav',
                'ownerTenantId': owner.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        voice = TTSVoice.objects.get(voice_code='cv-owned-1')
        self.assertEqual(voice.owner_tenant_id, owner.id)
        self.assertIn(voice.id, self._effective_voice_ids(owner))
        self.assertNotIn(voice.id, self._effective_voice_ids(other))

    def test_clone_owner_tenant_must_be_an_active_company(self):
        self.authenticate_superuser()
        disabled = Tenant.objects.create(name='停用公司', code='clone-owner-off', is_active=False)

        unknown = self.client.post(
            f'{self.settings_path}voices/design/',
            {'displayName': 'X', 'description': '温暖女声', 'language': 'zh', 'ownerTenantId': 999999},
            format='json',
        )
        inactive = self.client.post(
            f'{self.settings_path}voices/design/',
            {'displayName': 'X', 'description': '温暖女声', 'language': 'zh', 'ownerTenantId': disabled.id},
            format='json',
        )

        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)

    def _effective_voice_ids(self, tenant):
        from apps.ai_models.services import tts_authorization as tts_auth

        return set(tts_auth.get_effective_tts_voices_for_tenant(tenant).values_list('id', flat=True))

