import asyncio
import json
from unittest.mock import patch

from django.test import TestCase

from apps.ai_models.models import TTSProvider, TTSVoice
from apps.ai_models.services import cosyvoice as cosyvoice_services
from apps.ai_models.services import tts as tts_services
from apps.ai_models.services import tts_adapters


class FakeCosyVoiceUpstream:
    """Minimal duplex stand-in for the Model Studio task protocol."""

    def __init__(self, *, audio_frames=(b'\x01\x02', b'\x03\x04'), fail=False, tasks=1):
        self.sent: list[dict] = []
        self._audio_frames = list(audio_frames)
        self._fail = fail
        self._tasks = tasks
        self._queue: list = []
        self._task_ids: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def send(self, raw: str):
        message = json.loads(raw)
        self.sent.append(message)
        header = message.get('header') or {}
        action = header.get('action')
        task_id = header.get('task_id')
        if action == 'run-task':
            self._task_ids.append(task_id)
            self._queue.append(json.dumps({'header': {'task_id': task_id, 'event': 'task-started'}}))
        elif action == 'finish-task':
            if self._fail:
                self._queue.append(json.dumps({
                    'header': {'task_id': task_id, 'event': 'task-failed', 'error_code': 'E1', 'error_message': 'boom'},
                }))
                return
            self._queue.extend(self._audio_frames)
            self._queue.append(json.dumps({'header': {'task_id': task_id, 'event': 'task-finished'}}))

    def actions(self) -> list[str]:
        return [(message.get('header') or {}).get('action') for message in self.sent]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._queue:
            raise StopAsyncIteration
        return self._queue.pop(0)


class Collector:
    def __init__(self):
        self.events: list[dict] = []

    async def __call__(self, message):
        self.events.append(message)

    def types(self) -> list[str]:
        types = []
        for event in self.events:
            if 'bytes' in event:
                types.append('binary')
            else:
                types.append(json.loads(event['text'])['type'])
        return types

    def audio(self) -> list[bytes]:
        return [event['bytes'] for event in self.events if 'bytes' in event]

    def payload(self, event_type: str) -> dict:
        for event in self.events:
            if 'text' not in event:
                continue
            body = json.loads(event['text'])
            if body['type'] == event_type:
                return body
        raise AssertionError(f'{event_type} not emitted: {self.types()}')


class TTSAdapterRegistryTests(TestCase):
    def test_known_cards_resolve_to_their_adapter(self):
        self.assertIsInstance(
            tts_adapters.get_tts_provider_adapter('aliyun'),
            tts_adapters.AliyunQwenTTSAdapter,
        )
        self.assertIsInstance(
            tts_adapters.get_tts_provider_adapter('cosyvoice'),
            tts_adapters.CosyVoiceTTSAdapter,
        )

    def test_unknown_card_raises_instead_of_falling_back(self):
        with self.assertRaises(tts_adapters.TTSAdapterError):
            tts_adapters.get_tts_provider_adapter('not-a-card')
        with self.assertRaises(tts_adapters.TTSAdapterError):
            tts_adapters.get_tts_provider_adapter('')
        self.assertFalse(tts_adapters.has_tts_provider_adapter('not-a-card'))

    def test_adapter_is_selected_from_the_voices_own_card(self):
        cosyvoice = cosyvoice_services.get_cosyvoice_settings().provider
        voice = TTSVoice.objects.create(provider=cosyvoice, display_name='声音', voice_code='rv-1')

        adapter = tts_adapters.get_adapter_for_voice(voice)

        self.assertEqual(adapter.provider_code, 'cosyvoice')

    def test_voice_without_card_is_rejected(self):
        with self.assertRaises(tts_adapters.TTSAdapterError):
            tts_adapters.get_adapter_for_voice(None)

    def test_cosyvoice_declares_company_realtime_support(self):
        adapter = tts_adapters.get_tts_provider_adapter('cosyvoice')
        provider = cosyvoice_services.get_cosyvoice_settings().provider

        capabilities = adapter.company_runtime_capabilities(provider)

        self.assertTrue(capabilities['supportsCompanyRealtime'])
        self.assertIn(tts_adapters.CHANNEL_REALTIME, adapter.supported_channels(provider))

    def test_unsupported_channel_raises(self):
        adapter = tts_adapters.get_tts_provider_adapter('cosyvoice')
        provider = cosyvoice_services.get_cosyvoice_settings().provider

        with self.assertRaises(tts_adapters.TTSAdapterError):
            adapter.ensure_channel(provider, 'notAChannel')


class TTSAdapterConfigSchemaTests(TestCase):
    def setUp(self):
        self.qwen = tts_adapters.get_tts_provider_adapter('aliyun')
        self.cosy = tts_adapters.get_tts_provider_adapter('cosyvoice')
        self.qwen_provider = TTSProvider.objects.get(code='aliyun')
        self.cosy_provider = cosyvoice_services.get_cosyvoice_settings().provider

    def test_each_card_publishes_its_own_schema_key(self):
        self.assertEqual(self.qwen.public_config_schema(self.qwen_provider)['schemaKey'], 'aliyun-qwen')
        self.assertEqual(self.cosy.public_config_schema(self.cosy_provider)['schemaKey'], 'cosyvoice')

    def test_qwen_schema_exposes_model_and_instruction_fields(self):
        names = {field['name'] for field in self.qwen.public_config_schema(self.qwen_provider)['fields']}

        self.assertIn('model_code', names)
        self.assertIn('instructions', names)

    def test_cosyvoice_schema_excludes_qwen_only_fields(self):
        names = {field['name'] for field in self.cosy.public_config_schema(self.cosy_provider)['fields']}

        self.assertEqual(names, {'speech_rate', 'pitch_rate', 'volume'})
        self.assertNotIn('model_code', names)
        self.assertNotIn('instructions', names)

    def test_cosyvoice_rejects_qwen_fields(self):
        with self.assertRaises(tts_adapters.TTSAdapterError) as ctx:
            self.cosy.normalize_public_controls({'speech_rate': 1.1, 'instructions': '开心一点'})

        self.assertIn('instructions', str(ctx.exception))

    def test_cosyvoice_controls_are_bounded(self):
        controls = self.cosy.normalize_public_controls({'speech_rate': 99, 'pitch_rate': 1.5, 'volume': 80})

        self.assertEqual(controls['speech_rate'], 1.0)
        self.assertEqual(controls['pitch_rate'], 1.5)
        self.assertEqual(controls['volume'], 80)

    def test_qwen_controls_keep_historical_normalization(self):
        controls = self.qwen.normalize_public_controls({'model_code': 'standard', 'volume': 70})

        self.assertEqual(controls['model_code'], 'standard')
        self.assertEqual(controls['volume'], 70)
        self.assertEqual(controls['response_format'], 'pcm')

    def test_public_provider_summary_hides_credentials(self):
        self.qwen_provider.api_key = 'dashscope-secret'
        self.qwen_provider.base_url = 'wss://secret.example.com/realtime'
        self.qwen_provider.save(update_fields=['api_key', 'base_url'])

        summary = self.qwen.public_provider_summary(self.qwen_provider)

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn('dashscope-secret', serialized)
        self.assertNotIn('secret.example.com', serialized)
        self.assertEqual(summary['code'], 'aliyun')


class CosyVoiceRealtimeAdapterTests(TestCase):
    def setUp(self):
        self.settings_obj = cosyvoice_services.get_cosyvoice_settings()
        self.settings_obj.api_key_encrypted = ''
        self.settings_obj.websocket_url = 'wss://ws-abc.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
        self.settings_obj.is_active = True
        self.settings_obj.save()
        self.voice = TTSVoice.objects.create(
            provider=self.settings_obj.provider,
            display_name='客服女声',
            voice_code='remote-voice-1',
        )
        self.adapter = tts_adapters.get_tts_provider_adapter('cosyvoice')
        self.config = tts_services.EffectiveTTSConfig(
            provider=self.settings_obj.provider,
            provider_code='cosyvoice',
            api_key='test-key',
            base_url=self.settings_obj.websocket_url,
            model='cosyvoice-v3.5-plus',
            sample_rate=24000,
            tts_session_config={},
            default_test_text='测试文本',
            is_active=True,
        )

    def run_text_stream(self, upstream, *, text='你好世界。'):
        collector = Collector()
        with patch('apps.ai_models.services.cosyvoice_realtime.websockets.connect', return_value=upstream):
            asyncio.run(self.adapter.stream_realtime_text(
                text=text,
                voice=self.voice,
                config=self.config,
                send=collector,
                controls={'speech_rate': 1.0, 'volume': 50},
            ))
        return collector

    def test_text_stream_uses_task_protocol_and_forwards_audio(self):
        upstream = FakeCosyVoiceUpstream(audio_frames=(b'\x01\x02', b'\x03\x04'))

        collector = self.run_text_stream(upstream)

        self.assertEqual(upstream.actions(), ['run-task', 'continue-task', 'finish-task'])
        self.assertEqual(collector.types(), [
            'tts.ready', 'tts.segment_start', 'binary', 'binary', 'tts.segment_end', 'tts.done',
        ])
        self.assertEqual(collector.audio(), [b'\x01\x02', b'\x03\x04'])

    def test_ready_event_reports_voice_and_sample_rate(self):
        collector = self.run_text_stream(FakeCosyVoiceUpstream())

        ready = collector.payload('tts.ready')

        self.assertEqual(ready['voice'], 'remote-voice-1')
        self.assertEqual(ready['sampleRate'], 24000)
        self.assertEqual(ready['responseFormat'], 'pcm')

    def test_run_task_carries_normalized_controls_not_qwen_params(self):
        upstream = FakeCosyVoiceUpstream()
        collector = Collector()
        with patch('apps.ai_models.services.cosyvoice_realtime.websockets.connect', return_value=upstream):
            asyncio.run(self.adapter.stream_realtime_text(
                text='你好。',
                voice=self.voice,
                config=self.config,
                send=collector,
                controls={'speech_rate': 1.5, 'pitch_rate': 0.8, 'volume': 70},
            ))

        parameters = upstream.sent[0]['payload']['parameters']

        self.assertEqual(parameters['voice'], 'remote-voice-1')
        self.assertEqual(parameters['rate'], 1.5)
        self.assertEqual(parameters['pitch'], 0.8)
        self.assertEqual(parameters['volume'], 70)
        self.assertNotIn('instructions', parameters)
        self.assertNotIn('model_code', parameters)

    def test_upstream_task_failure_propagates(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.run_text_stream(FakeCosyVoiceUpstream(fail=True))

        self.assertIn('boom', str(ctx.exception))

    def test_unconfigured_card_raises_before_connecting(self):
        broken = tts_services.EffectiveTTSConfig(
            provider=self.settings_obj.provider,
            provider_code='cosyvoice',
            api_key='',
            base_url='',
            model='cosyvoice-v3.5-plus',
            sample_rate=24000,
            tts_session_config={},
            default_test_text='',
            is_active=True,
        )
        collector = Collector()

        with self.assertRaises(RuntimeError):
            asyncio.run(self.adapter.stream_realtime_text(
                text='你好。',
                voice=self.voice,
                config=broken,
                send=collector,
            ))
        self.assertEqual(collector.events, [])

    def test_segment_stream_opens_one_task_per_segment(self):
        upstream = FakeCosyVoiceUpstream(audio_frames=(b'\x05',))
        collector = Collector()

        async def segments():
            yield '第一段。'
            yield '第二段。'

        with patch('apps.ai_models.services.cosyvoice_realtime.websockets.connect', return_value=upstream):
            asyncio.run(self.adapter.stream_realtime_segments(
                segments=segments(),
                voice=self.voice,
                config=self.config,
                send=collector,
                controls={},
            ))

        self.assertEqual(upstream.actions().count('run-task'), 2)
        self.assertEqual(upstream.actions().count('finish-task'), 2)
        self.assertEqual(collector.types(), [
            'tts.ready',
            'tts.segment_start', 'binary', 'tts.segment_end',
            'tts.segment_start', 'binary', 'tts.segment_end',
            'tts.done',
        ])

    def test_segment_stream_still_completes_when_no_segments_arrive(self):
        upstream = FakeCosyVoiceUpstream()
        collector = Collector()

        async def segments():
            if False:
                yield ''

        with patch('apps.ai_models.services.cosyvoice_realtime.websockets.connect', return_value=upstream):
            asyncio.run(self.adapter.stream_realtime_segments(
                segments=segments(),
                voice=self.voice,
                config=self.config,
                send=collector,
                controls={},
            ))

        self.assertEqual(collector.types(), ['tts.ready', 'tts.done'])
