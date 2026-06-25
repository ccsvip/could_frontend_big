import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.test import TestCase

from apps.ai_models.models import ASRReplacementRule
from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.devices.models import Device, DeviceApplication
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class HangingUpstream:
    def __init__(self):
        self.messages = []
        self._event = asyncio.Event()
        self.exited = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    async def send(self, message):
        self.messages.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._event.wait()
        raise StopAsyncIteration


class ASRRealtimeTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='asr-ws-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='ASR WS Role', code='asr_ws_tester')
        UserRole.objects.create(user=self.user, role=self.role)
        self.tenant.permission_points.clear()

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            permission_point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={
                    'name': code,
                    'module': 'ai_models_asr',
                    'description': code,
                    'is_active': True,
                },
            )
            permission_points.append(permission_point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def test_extract_transcript_payload_ignores_technical_events(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({'type': 'session.created'})

        self.assertIsNone(payload)

    def test_extract_transcript_payload_normalizes_realtime_text(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.text',
            'text': '你好',
        })

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '你好',
                'originalText': '你好',
                'replacementApplied': False,
                'delta': False,
                'final': False,
                'sourceEventType': 'conversation.item.input_audio_transcription.text',
            },
        )

    def test_extract_transcript_payload_combines_realtime_text_and_stash(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.text',
            'text': '今天',
            'stash': '天气不错',
        })

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '今天天气不错',
                'originalText': '今天天气不错',
                'replacementApplied': False,
                'delta': False,
                'final': False,
                'sourceEventType': 'conversation.item.input_audio_transcription.text',
            },
        )

    def test_extract_transcript_payload_keeps_stash_only_preview(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.text',
            'text': '',
            'stash': '北京的',
        })

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '北京的',
                'originalText': '北京的',
                'replacementApplied': False,
                'delta': False,
                'final': False,
                'sourceEventType': 'conversation.item.input_audio_transcription.text',
            },
        )

    def test_sync_transcript_text_combines_text_and_stash(self):
        from apps.ai_models.services.asr import _extract_transcript_text

        text = _extract_transcript_text({
            'type': 'conversation.item.input_audio_transcription.text',
            'text': '今天',
            'stash': '天气不错',
        })

        self.assertEqual(text, '今天天气不错')

    def test_extract_transcript_payload_filters_filler_words_when_enabled(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        self.assertIsNone(
            extract_transcript_payload(
                {
                    'type': 'conversation.item.input_audio_transcription.completed',
                    'transcript': '嗯。',
                },
                filter_filler_words=True,
            )
        )

    def test_filtered_filler_final_event_is_detected(self):
        from apps.ai_models.realtime_asr import is_filtered_filler_final_event

        self.assertTrue(
            is_filtered_filler_final_event(
                {
                    'type': 'conversation.item.input_audio_transcription.completed',
                    'transcript': '嗯。',
                },
                filter_filler_words=True,
            )
        )

    def test_meaningful_final_event_is_not_treated_as_filtered_filler(self):
        from apps.ai_models.realtime_asr import is_filtered_filler_final_event

        self.assertFalse(
            is_filtered_filler_final_event(
                {
                    'type': 'conversation.item.input_audio_transcription.completed',
                    'transcript': '嗯好的',
                },
                filter_filler_words=True,
            )
        )

    def test_extract_transcript_payload_keeps_meaningful_text_when_filter_enabled(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload(
            {
                'type': 'conversation.item.input_audio_transcription.completed',
                'transcript': '嗯好的',
            },
            filter_filler_words=True,
        )

        self.assertEqual(payload['text'], '嗯好的')

    def test_extract_transcript_payload_marks_delta_event(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.delta',
            'delta': '你',
        })

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '你',
                'originalText': '你',
                'replacementApplied': False,
                'delta': True,
                'final': False,
                'sourceEventType': 'conversation.item.input_audio_transcription.delta',
            },
        )

    def test_extract_transcript_payload_normalizes_final_text(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.completed',
            'transcript': '你好，欢迎使用',
        })

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '你好，欢迎使用',
                'originalText': '你好，欢迎使用',
                'replacementApplied': False,
                'delta': False,
                'final': True,
                'sourceEventType': 'conversation.item.input_audio_transcription.completed',
            },
        )

    def test_extract_transcript_payload_applies_tenant_replacement_rules(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        ASRReplacementRule.objects.create(
            tenant=self.tenant,
            source_text='小明',
            replacement_text='小张',
        )
        ASRReplacementRule.objects.create(
            tenant=self.tenant,
            source_text='关闭',
            replacement_text='打开',
            is_active=False,
        )

        payload = extract_transcript_payload(
            {
                'type': 'conversation.item.input_audio_transcription.completed',
                'transcript': '请小明关闭展厅灯光',
            },
            tenant_id=self.tenant.id,
        )

        self.assertEqual(
            payload,
            {
                'type': 'asr.transcript',
                'text': '请小张关闭展厅灯光',
                'originalText': '请小明关闭展厅灯光',
                'replacementApplied': True,
                'delta': False,
                'final': True,
                'sourceEventType': 'conversation.item.input_audio_transcription.completed',
            },
        )

    def test_resolve_realtime_connection_requires_asr_permission(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        token = str(RefreshToken.for_user(self.user).access_token)

        self.assertIsNone(resolve_asr_realtime_connection(token))

        self.grant_permissions('ai_models.asr.view')
        connection = resolve_asr_realtime_connection(token)

        self.assertEqual(connection, {'user_id': self.user.id, 'tenant_id': self.tenant.id})

    def test_resolve_realtime_connection_accepts_superuser_tenant_scope(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        superuser = User.objects.create_superuser(username='asr-superuser', password='test123456')
        token = str(RefreshToken.for_user(superuser).access_token)

        connection = resolve_asr_realtime_connection(
            token,
            query_params={'tenantId': [str(self.tenant.id)]},
        )

        self.assertEqual(connection, {'user_id': superuser.id, 'tenant_id': self.tenant.id})

    def test_resolve_realtime_connection_accepts_android_device_code_header(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='ASR Android App',
            code='asr-android-app',
        )
        device = Device.objects.create(
            tenant=self.tenant,
            application=application,
            name='ASR Android Device',
            code='ANDROID-ASR-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        connection = resolve_asr_realtime_connection(
            '',
            headers=[(b'x-device-code', b'ANDROID-ASR-001')],
        )

        self.assertEqual(
            connection,
            {
                'device_id': device.id,
                'device_code': 'ANDROID-ASR-001',
                'tenant_id': self.tenant.id,
                'application_id': application.id,
                'agent_application_id': None,
            },
        )

    def test_resolve_realtime_connection_rejects_unbound_android_device(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        Device.objects.create(
            name='Unbound ASR Android Device',
            code='ANDROID-ASR-PENDING',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        connection = resolve_asr_realtime_connection(
            '',
            headers=[(b'x-device-code', b'ANDROID-ASR-PENDING')],
        )

        self.assertIsNone(connection)

    def test_resolve_realtime_connection_accepts_device_code_query_for_browser_test_page(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='ASR Browser Test App',
            code='asr-browser-test-app',
        )
        device = Device.objects.create(
            tenant=self.tenant,
            application=application,
            name='ASR Browser Test Device',
            code='ANDROID-ASR-BROWSER',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )

        connection = resolve_asr_realtime_connection(
            '',
            query_params={'deviceCode': ['ANDROID-ASR-BROWSER']},
        )

        self.assertEqual(
            connection,
            {
                'device_id': device.id,
                'device_code': 'ANDROID-ASR-BROWSER',
                'tenant_id': self.tenant.id,
                'application_id': application.id,
                'agent_application_id': None,
            },
        )

    def test_unified_asr_session_cleanup_on_browser_disconnect(self):
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
            upstream = HangingUpstream()
            with (
                patch(
                    'apps.ai_models.realtime_asr.resolve_asr_realtime_connection',
                    return_value={'user_id': self.user.id, 'tenant_id': self.tenant.id},
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
                        'id': 'asr-cleanup-1',
                        'payload': {'token': 'test-token', 'tenantId': self.tenant.id},
                    }),
                })
                ready = await communicator.receive_output(timeout=1)
                ready_payload = json.loads(ready['text'])
                self.assertEqual(ready_payload['type'], 'asr.ready')
                self.assertEqual(ready_payload['id'], 'asr-cleanup-1')
                self.assertTrue(ready_payload['requestId'])
                self.assertEqual(ready_payload['traceId'], ready_payload['requestId'])

                await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
                await communicator.wait(timeout=1)

            self.assertTrue(upstream.exited)

        async_to_sync(run_websocket)()
