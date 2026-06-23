from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import AgentApplication, LLMModel, LLMProvider, TenantLLMModelGrant
from apps.devices.models import Device, DeviceApplication
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class UnifiedASRUpstream:
    def __init__(self):
        self.messages = []
        self._audio_seen = asyncio.Event()
        self._finish_seen = asyncio.Event()
        self._stage = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        payload = json.loads(message)
        self.messages.append(payload)
        if payload.get('type') == 'input_audio_buffer.append':
            self._audio_seen.set()
        if payload.get('type') == 'session.finish':
            self._finish_seen.set()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._stage == 0:
            await self._audio_seen.wait()
            self._stage += 1
            return json.dumps({
                'type': 'conversation.item.input_audio_transcription.text',
                'text': '统一 ASR',
            })
        if self._stage == 1:
            await self._finish_seen.wait()
            self._stage += 1
            return json.dumps({'type': 'session.finished'})
        raise StopAsyncIteration


class UnifiedTTSUpstream:
    def __init__(self):
        self.messages = []
        self._events = iter([
            json.dumps({'type': 'response.audio.delta', 'delta': base64.b64encode(b'\x03\x04').decode('ascii')}),
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


class HangingUnifiedTTSUpstream:
    def __init__(self):
        self.messages = []
        self.exited = False
        self._event = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    async def send(self, message):
        self.messages.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._event.wait()
        raise StopAsyncIteration


class FailingUnifiedASRUpstream:
    async def __aenter__(self):
        raise RuntimeError('upstream unavailable')

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RealtimeWebSocketTests(SimpleTestCase):
    def test_unified_realtime_websocket_responds_to_ping_command(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'type': 'ping', 'id': 'ping-1'}),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            self.assertEqual(
                json.loads(message['text']),
                {'type': 'pong', 'id': 'ping-1', 'payload': {}},
            )

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_reports_unknown_command(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'type': 'realtime.not_supported', 'id': 'unknown-1'}),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            self.assertEqual(
                json.loads(message['text']),
                {
                    'type': 'error',
                    'id': 'unknown-1',
                    'error': {
                        'code': 'unknown_command',
                        'message': 'Unsupported realtime command: realtime.not_supported',
                    },
                },
            )

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_runs_asr_session_commands_and_binary_audio(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            config = SimpleNamespace(
                is_active=True,
                api_key='test-api-key',
                workspace_id='test-workspace',
                vad_threshold=-0.4,
                vad_silence_duration_ms=700,
            )
            upstream = UnifiedASRUpstream()
            with (
                patch(
                    'apps.ai_models.realtime_asr.resolve_asr_realtime_connection',
                    return_value={'user_id': 1, 'tenant_id': 2},
                ),
                patch('apps.ai_models.realtime_asr.get_effective_asr_config', return_value=config),
                patch('apps.ai_models.realtime_asr.is_asr_configured', return_value=True),
                patch('apps.ai_models.realtime_asr.build_asr_ws_url', return_value='ws://asr.example/realtime'),
                patch('apps.ai_models.realtime_asr.load_asr_replacement_pairs', return_value=[]),
                patch('apps.ai_models.realtime_asr.websockets.connect', return_value=upstream),
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'asr.session.start',
                        'id': 'asr-session-1',
                        'payload': {
                            'token': 'test-token',
                            'tenantId': 2,
                            'requestId': 'req-asr-ready-1',
                            'traceId': 'trace-asr-ready-1',
                        },
                    }),
                })
                ready = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(ready['text']),
                    {
                        'type': 'asr.ready',
                        'id': 'asr-session-1',
                        'requestId': 'req-asr-ready-1',
                        'traceId': 'trace-asr-ready-1',
                    },
                )

                await communicator.send_input({'type': 'websocket.receive', 'bytes': b'\x01\x02'})
                transcript = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(transcript['text']),
                    {
                        'type': 'asr.transcript',
                        'id': 'asr-session-1',
                        'text': '统一 ASR',
                        'originalText': '统一 ASR',
                        'replacementApplied': False,
                        'final': False,
                    },
                )

                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({'type': 'asr.session.finish', 'id': 'asr-finish-1'}),
                })
                done = await communicator.receive_output(timeout=1)
                self.assertEqual(json.loads(done['text']), {'type': 'asr.done', 'id': 'asr-session-1'})

            sent_types = [message.get('type') for message in upstream.messages]
            self.assertIn('session.update', sent_types)
            self.assertIn('input_audio_buffer.append', sent_types)
            self.assertIn('session.finish', sent_types)
            session_update = next(message for message in upstream.messages if message.get('type') == 'session.update')
            self.assertEqual(session_update['session']['turn_detection']['threshold'], -0.4)
            self.assertEqual(session_update['session']['turn_detection']['silence_duration_ms'], 700)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_asr_error_paths_echo_trace_context(self):
        async def run_start(command_id):
            from config.realtime import RealtimeConnection, _handle_asr_session_start

            sent = []

            async def send(event):
                sent.append(event)

            await _handle_asr_session_start(
                send,
                RealtimeConnection(),
                {
                    'type': 'asr.session.start',
                    'id': command_id,
                    'payload': {
                        'token': 'test-token',
                        'tenantId': 2,
                        'requestId': 'req-asr-error-1',
                        'traceId': 'trace-asr-error-1',
                    },
                },
            )
            self.assertEqual(sent[-1]['type'], 'websocket.send')
            return json.loads(sent[-1]['text'])

        async def run_cases():
            with patch('apps.ai_models.realtime_asr.resolve_asr_realtime_connection', return_value=None):
                unauthorized = await run_start('asr-unauthorized')
            self.assertEqual(
                unauthorized,
                {
                    'type': 'asr.error',
                    'id': 'asr-unauthorized',
                    'requestId': 'req-asr-error-1',
                    'traceId': 'trace-asr-error-1',
                    'message': 'ASR session is not authorized',
                },
            )

            inactive_config = SimpleNamespace(is_active=False)
            with (
                patch('apps.ai_models.realtime_asr.resolve_asr_realtime_connection', return_value={'tenant_id': 2}),
                patch('apps.ai_models.realtime_asr.get_effective_asr_config', return_value=inactive_config),
            ):
                config_error = await run_start('asr-config-error')
            self.assertEqual(
                config_error,
                {
                    'type': 'asr.error',
                    'id': 'asr-config-error',
                    'requestId': 'req-asr-error-1',
                    'traceId': 'trace-asr-error-1',
                    'message': 'ASR 服务未就绪',
                },
            )

            active_config = SimpleNamespace(is_active=True, api_key='test-api-key', workspace_id='test-workspace')
            with (
                patch('apps.ai_models.realtime_asr.resolve_asr_realtime_connection', return_value={'tenant_id': 2}),
                patch('apps.ai_models.realtime_asr.get_effective_asr_config', return_value=active_config),
                patch('apps.ai_models.realtime_asr.is_asr_configured', return_value=True),
                patch('apps.ai_models.realtime_asr.load_asr_replacement_pairs', return_value=[]),
                patch('apps.ai_models.realtime_asr.build_asr_ws_url', return_value='ws://asr.example/realtime'),
                patch('apps.ai_models.realtime_asr.websockets.connect', return_value=FailingUnifiedASRUpstream()),
            ):
                upstream_error = await run_start('asr-upstream-error')
            self.assertEqual(
                upstream_error,
                {
                    'type': 'asr.error',
                    'id': 'asr-upstream-error',
                    'requestId': 'req-asr-error-1',
                    'traceId': 'trace-asr-error-1',
                    'message': 'upstream unavailable',
                },
            )

        async_to_sync(run_cases)()

    def test_unified_realtime_websocket_runs_tts_session_command_and_binary_audio(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            provider = SimpleNamespace(code='aliyun')
            voice = SimpleNamespace(id=7, voice_code='Cherry')
            config = SimpleNamespace(
                is_active=True,
                api_key='test-api-key',
                base_url='wss://tts.example/realtime',
                model='qwen3-tts-flash-realtime',
                sample_rate=24000,
                default_test_text='默认测试文本',
            )
            upstream = UnifiedTTSUpstream()
            with (
                patch(
                    'apps.ai_models.realtime_tts.resolve_tts_realtime_connection',
                    return_value={'user_id': 1, 'tenant_id': 2, 'is_superuser': False},
                ),
                patch('apps.ai_models.realtime_tts.resolve_tts_provider', return_value=provider),
                patch('apps.ai_models.realtime_tts.get_effective_tts_config', return_value=config),
                patch('apps.ai_models.realtime_tts.is_tts_configured', return_value=True),
                patch('apps.ai_models.realtime_tts.resolve_tts_voice', return_value=voice),
                patch('apps.ai_models.realtime_tts.build_tts_ws_url', return_value='wss://tts.example/realtime?model=test'),
                patch('apps.ai_models.realtime_tts.websockets.connect', return_value=upstream),
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'tts.session.start',
                        'id': 'tts-session-1',
                        'payload': {
                            'token': 'test-token',
                            'tenantId': 2,
                            'text': '你好',
                            'voiceId': 7,
                            'providerCode': 'aliyun',
                        },
                    }),
                })

                ready = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(ready['text']),
                    {'type': 'tts.ready', 'sampleRate': 24000, 'voice': 'Cherry', 'id': 'tts-session-1'},
                )
                audio = await communicator.receive_output(timeout=1)
                self.assertEqual(audio, {'type': 'websocket.send', 'bytes': b'\x03\x04'})
                done = await communicator.receive_output(timeout=1)
                self.assertEqual(json.loads(done['text']), {'type': 'tts.done', 'id': 'tts-session-1'})

            sent_types = [message.get('type') for message in upstream.messages]
            self.assertIn('session.update', sent_types)
            self.assertIn('input_text_buffer.append', sent_types)
            self.assertIn('session.finish', sent_types)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_cancels_asr_session(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            config = SimpleNamespace(is_active=True, api_key='test-api-key', workspace_id='test-workspace')
            upstream = HangingUnifiedTTSUpstream()
            with (
                patch(
                    'apps.ai_models.realtime_asr.resolve_asr_realtime_connection',
                    return_value={'user_id': 1, 'tenant_id': 2},
                ),
                patch('apps.ai_models.realtime_asr.get_effective_asr_config', return_value=config),
                patch('apps.ai_models.realtime_asr.is_asr_configured', return_value=True),
                patch('apps.ai_models.realtime_asr.build_asr_ws_url', return_value='ws://asr.example/realtime'),
                patch('apps.ai_models.realtime_asr.load_asr_replacement_pairs', return_value=[]),
                patch('apps.ai_models.realtime_asr.websockets.connect', return_value=upstream),
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'asr.session.start',
                        'id': 'asr-cancel-session',
                        'payload': {
                            'token': 'test-token',
                            'tenantId': 2,
                            'requestId': 'req-asr-cancel-1',
                            'traceId': 'trace-asr-cancel-1',
                        },
                    }),
                })
                ready = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(ready['text']),
                    {
                        'type': 'asr.ready',
                        'id': 'asr-cancel-session',
                        'requestId': 'req-asr-cancel-1',
                        'traceId': 'trace-asr-cancel-1',
                    },
                )

                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({'type': 'asr.session.cancel', 'id': 'asr-cancel-1'}),
                })
                cancelled = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(cancelled['text']),
                    {
                        'type': 'asr.cancelled',
                        'id': 'asr-cancel-1',
                        'payload': {'sessionId': 'asr-cancel-session'},
                    },
                )

            self.assertTrue(upstream.exited)
            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_cancels_tts_session(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            provider = SimpleNamespace(code='aliyun')
            voice = SimpleNamespace(id=7, voice_code='Cherry')
            config = SimpleNamespace(
                is_active=True,
                api_key='test-api-key',
                base_url='wss://tts.example/realtime',
                model='qwen3-tts-flash-realtime',
                sample_rate=24000,
                default_test_text='默认测试文本',
            )
            upstream = HangingUnifiedTTSUpstream()
            with (
                patch(
                    'apps.ai_models.realtime_tts.resolve_tts_realtime_connection',
                    return_value={'user_id': 1, 'tenant_id': 2, 'is_superuser': False},
                ),
                patch('apps.ai_models.realtime_tts.resolve_tts_provider', return_value=provider),
                patch('apps.ai_models.realtime_tts.get_effective_tts_config', return_value=config),
                patch('apps.ai_models.realtime_tts.is_tts_configured', return_value=True),
                patch('apps.ai_models.realtime_tts.resolve_tts_voice', return_value=voice),
                patch('apps.ai_models.realtime_tts.build_tts_ws_url', return_value='wss://tts.example/realtime?model=test'),
                patch('apps.ai_models.realtime_tts.websockets.connect', return_value=upstream),
            ):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'tts.session.start',
                        'id': 'tts-cancel-session',
                        'payload': {
                            'token': 'test-token',
                            'tenantId': 2,
                            'text': '你好',
                            'voiceId': 7,
                            'providerCode': 'aliyun',
                        },
                    }),
                })
                ready = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(ready['text']),
                    {'type': 'tts.ready', 'sampleRate': 24000, 'voice': 'Cherry', 'id': 'tts-cancel-session'},
                )

                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({'type': 'tts.session.cancel', 'id': 'tts-cancel-1'}),
                })
                cancelled = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(cancelled['text']),
                    {
                        'type': 'tts.cancelled',
                        'id': 'tts-cancel-1',
                        'payload': {'sessionId': 'tts-cancel-session'},
                    },
                )

            self.assertTrue(upstream.exited)
            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()


class RealtimeDeviceEventsTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='realtime-device-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='Realtime Device Role', code='realtime_device_role')
        UserRole.objects.create(user=self.user, role=self.role)
        self.grant_permissions('devices.view')
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Realtime Events App',
            code='realtime-events-app',
        )

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'devices',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def test_unified_realtime_websocket_subscribes_to_device_events(self):
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-1',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(subscribed['type'], 'websocket.send')
            self.assertEqual(
                json.loads(subscribed['text']),
                {
                    'type': 'devices.events.subscribed',
                    'id': 'devices-sub-1',
                    'payload': {'tenantId': self.tenant.id},
                },
            )

            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-UNIFIED-001',
                    'status': 'online',
                }
            )
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            self.assertEqual(
                json.loads(message['text']),
                {
                    'type': 'devices.event',
                    'id': 'devices-sub-1',
                    'payload': {
                        'type': 'device.status',
                        'tenantId': self.tenant.id,
                        'deviceCode': 'ANDROID-UNIFIED-001',
                        'status': 'online',
                    },
                },
            )

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_runs_device_llm_session_command(self):
        provider = LLMProvider.objects.create(
            name='Runtime LLM Provider',
            provider_type='openai',
            api_base_url='https://llm.example/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='runtime-model', is_active=True)
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Runtime Agent',
            llm_model=model,
            system_prompt='你是设备助手。',
            temperature=0.2,
            max_tokens=256,
        )
        device_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Runtime LLM App',
            code='runtime-llm-app',
            agent_application=agent_application,
        )
        Device.objects.create(
            tenant=self.tenant,
            application=device_application,
            name='Runtime LLM Device',
            code='ANDROID-LLM-WS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

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
            self.assertEqual(response['type'], 'websocket.accept')

            async def stream_answer(**kwargs):
                yield '这是'
                yield '实时回答。'

            with patch('apps.ai_models.llm_services.stream_llm_chat_completion', side_effect=stream_answer) as stream_llm:
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'llm.session.start',
                        'id': 'llm-session-1',
                        'payload': {
                            'deviceCode': 'ANDROID-LLM-WS-001',
                            'text': '介绍一下展厅',
                            'requestId': 'req-llm-1',
                            'traceId': 'trace-llm-1',
                        },
                    }),
                })

                message = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(message['text']),
                    {
                        'type': 'llm.started',
                        'id': 'llm-session-1',
                        'requestId': 'req-llm-1',
                        'traceId': 'trace-llm-1',
                        'payload': {
                            'deviceCode': 'ANDROID-LLM-WS-001',
                            'questionText': '介绍一下展厅',
                            'agentApplicationId': agent_application.id,
                            'agentApplicationName': 'Runtime Agent',
                            'applicationId': device_application.id,
                            'applicationName': 'Runtime LLM App',
                        },
                    },
                )
                first_delta = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(first_delta['text']),
                    {
                        'type': 'llm.delta',
                        'id': 'llm-session-1',
                        'requestId': 'req-llm-1',
                        'traceId': 'trace-llm-1',
                        'payload': {'text': '这是'},
                    },
                )
                second_delta = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(second_delta['text']),
                    {
                        'type': 'llm.delta',
                        'id': 'llm-session-1',
                        'requestId': 'req-llm-1',
                        'traceId': 'trace-llm-1',
                        'payload': {'text': '实时回答。'},
                    },
                )
                done = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(done['text']),
                    {
                        'type': 'llm.done',
                        'id': 'llm-session-1',
                        'requestId': 'req-llm-1',
                        'traceId': 'trace-llm-1',
                        'payload': {
                            'deviceCode': 'ANDROID-LLM-WS-001',
                            'questionText': '介绍一下展厅',
                            'answerText': '这是实时回答。',
                            'agentApplicationId': agent_application.id,
                            'agentApplicationName': 'Runtime Agent',
                            'applicationId': device_application.id,
                            'applicationName': 'Runtime LLM App',
                        },
                    },
                )
                call_kwargs = stream_llm.call_args.kwargs
                self.assertEqual(call_kwargs['model_config']['name'], model.name)
                self.assertEqual(call_kwargs['temperature'], 0.2)
                self.assertEqual(call_kwargs['max_tokens'], 256)
                self.assertEqual(call_kwargs['messages'][0]['role'], 'system')
                self.assertIn('Runtime Agent', call_kwargs['messages'][0]['content'])
                self.assertEqual(call_kwargs['messages'][1], {'role': 'user', 'content': '介绍一下展厅'})

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_cancels_llm_session(self):
        provider = LLMProvider.objects.create(
            name='Cancelable LLM Provider',
            provider_type='openai',
            api_base_url='https://llm.example/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='cancelable-model', is_active=True)
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Cancelable Agent',
            llm_model=model,
            system_prompt='你是设备助手。',
            temperature=0.2,
            max_tokens=256,
        )
        device_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Cancelable LLM App',
            code='cancelable-llm-app',
            agent_application=agent_application,
        )
        Device.objects.create(
            tenant=self.tenant,
            application=device_application,
            name='Cancelable LLM Device',
            code='ANDROID-LLM-CANCEL-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        async def run_websocket():
            from config.asgi import application

            stream_started = asyncio.Event()
            stream_cancelled = asyncio.Event()

            async def hanging_stream(**kwargs):
                stream_started.set()
                try:
                    await asyncio.Event().wait()
                    yield ''
                finally:
                    stream_cancelled.set()

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
            self.assertEqual(response['type'], 'websocket.accept')

            with patch('apps.ai_models.llm_services.stream_llm_chat_completion', side_effect=hanging_stream):
                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({
                        'type': 'llm.session.start',
                        'id': 'llm-cancel-session',
                        'payload': {
                            'deviceCode': 'ANDROID-LLM-CANCEL-001',
                            'text': '请开始长回答',
                            'requestId': 'req-llm-cancel-1',
                            'traceId': 'trace-llm-cancel-1',
                        },
                    }),
                })

                started = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(started['text']),
                    {
                        'type': 'llm.started',
                        'id': 'llm-cancel-session',
                        'requestId': 'req-llm-cancel-1',
                        'traceId': 'trace-llm-cancel-1',
                        'payload': {
                            'deviceCode': 'ANDROID-LLM-CANCEL-001',
                            'questionText': '请开始长回答',
                            'agentApplicationId': agent_application.id,
                            'agentApplicationName': 'Cancelable Agent',
                            'applicationId': device_application.id,
                            'applicationName': 'Cancelable LLM App',
                        },
                    },
                )
                await asyncio.wait_for(stream_started.wait(), timeout=1)

                await communicator.send_input({
                    'type': 'websocket.receive',
                    'text': json.dumps({'type': 'llm.session.cancel', 'id': 'llm-cancel-1'}),
                })
                cancelled = await communicator.receive_output(timeout=1)
                self.assertEqual(
                    json.loads(cancelled['text']),
                    {
                        'type': 'llm.cancelled',
                        'id': 'llm-cancel-1',
                        'payload': {'sessionId': 'llm-cancel-session'},
                    },
                )
                await asyncio.wait_for(stream_cancelled.wait(), timeout=1)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_unsubscribes_from_device_events(self):
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-unsub',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'type': 'devices.events.unsubscribe', 'id': 'devices-unsub-1'}),
            })
            unsubscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(
                json.loads(unsubscribed['text']),
                {'type': 'devices.events.unsubscribed', 'id': 'devices-unsub-1', 'payload': {}},
            )

            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-UNSUB-001',
                    'status': 'online',
                }
            )

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'type': 'ping', 'id': 'after-unsub-ping'}),
            })
            pong = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(pong['text']), {'type': 'pong', 'id': 'after-unsub-ping', 'payload': {}})

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_device_events_subscription_does_not_stop_device_status_session(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            name='Unified Combined Device',
            code='ANDROID-COMBINED-001',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from asgiref.sync import sync_to_async
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.status.start',
                    'id': 'device-status-combined',
                    'payload': {'deviceCode': 'ANDROID-COMBINED-001'},
                }),
            })
            started = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(started['text'])['type'], 'device.status.started')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-combined',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            status_after_subscribe = await sync_to_async(
                lambda: Device.objects.get(id=device.id).status,
                thread_sensitive=True,
            )()
            self.assertEqual(status_after_subscribe, Device.STATUS_ONLINE)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertEqual(device.status, Device.STATUS_OFFLINE)


class RealtimeDeviceStatusTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='realtime-device-status', password='test123456')
        self.setup_tenant(self.user)
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Realtime Device App',
            code='realtime-device-app',
        )

    def test_unified_realtime_websocket_marks_device_online_until_disconnect(self):
        device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            name='Unified Runtime Device',
            code='ANDROID-UNIFIED-STATUS',
            status=Device.STATUS_OFFLINE,
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        async def run_websocket():
            from asgiref.sync import sync_to_async
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.status.start',
                    'id': 'device-status-1',
                    'payload': {'deviceCode': 'ANDROID-UNIFIED-STATUS'},
                }),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            self.assertEqual(
                json.loads(message['text']),
                {
                    'type': 'device.status.started',
                    'id': 'device-status-1',
                    'payload': {
                        'deviceCode': 'ANDROID-UNIFIED-STATUS',
                        'status': Device.STATUS_ONLINE,
                    },
                },
            )

            online_status = await sync_to_async(
                lambda: Device.objects.get(id=device.id).status,
                thread_sensitive=True,
            )()
            self.assertEqual(online_status, Device.STATUS_ONLINE)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        device.refresh_from_db()
        self.assertEqual(device.status, Device.STATUS_OFFLINE)

    def test_unified_realtime_websocket_device_status_ping_requires_started_session(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'type': 'device.status.ping', 'id': 'device-ping-1'}),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(
                json.loads(message['text']),
                {
                    'type': 'error',
                    'id': 'device-ping-1',
                    'error': {
                        'code': 'device_status_not_started',
                        'message': 'Device status session is not started',
                    },
                },
            )

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_filters_other_tenant_device_events(self):
        other_tenant = Tenant.objects.create(name='Realtime Other Tenant', code='realtime-other-tenant')
        token = str(AccessToken.for_user(self.user))

        async def run_websocket():
            from apps.devices.realtime import publish_device_event
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'devices.events.subscribe',
                    'id': 'devices-sub-filter',
                    'payload': {'token': token},
                }),
            })
            subscribed = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(subscribed['text'])['type'], 'devices.events.subscribed')

            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': other_tenant.id,
                    'deviceCode': 'ANDROID-OTHER-UNIFIED',
                    'status': 'online',
                }
            )
            await publish_device_event(
                {
                    'type': 'device.status',
                    'tenantId': self.tenant.id,
                    'deviceCode': 'ANDROID-SAME-UNIFIED',
                    'status': 'online',
                }
            )

            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            payload = json.loads(message['text'])
            self.assertEqual(payload['payload']['deviceCode'], 'ANDROID-SAME-UNIFIED')
            self.assertNotEqual(payload['payload']['deviceCode'], 'ANDROID-OTHER-UNIFIED')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_unified_realtime_websocket_requires_command_type(self):
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
            self.assertEqual(response['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({'id': 'missing-type-1', 'payload': {}}),
            })
            message = await communicator.receive_output(timeout=1)
            self.assertEqual(message['type'], 'websocket.send')
            self.assertEqual(
                json.loads(message['text']),
                {
                    'type': 'error',
                    'id': 'missing-type-1',
                    'error': {
                        'code': 'invalid_command',
                        'message': 'Realtime command type is required',
                    },
                },
            )

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
