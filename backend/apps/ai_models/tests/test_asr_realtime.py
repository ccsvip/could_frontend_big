import asyncio
from types import SimpleNamespace
from unittest.mock import patch

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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
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

        self.assertEqual(payload, {'type': 'asr.transcript', 'text': '你好', 'final': False})

    def test_extract_transcript_payload_normalizes_final_text(self):
        from apps.ai_models.realtime_asr import extract_transcript_payload

        payload = extract_transcript_payload({
            'type': 'conversation.item.input_audio_transcription.completed',
            'transcript': '你好，欢迎使用',
        })

        self.assertEqual(payload, {'type': 'asr.transcript', 'text': '你好，欢迎使用', 'final': True})

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

        self.assertEqual(payload, {'type': 'asr.transcript', 'text': '请小张关闭展厅灯光', 'final': True})

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
            },
        )

    def test_asr_realtime_returns_without_closing_after_browser_disconnect(self):
        from apps.ai_models.realtime_asr import asr_realtime_websocket_application

        sent_messages = []
        state = {'disconnected': False}

        async def receive():
            state['disconnected'] = True
            return {'type': 'websocket.disconnect'}

        async def send(message):
            if state['disconnected'] and message.get('type') == 'websocket.close':
                raise RuntimeError(
                    "Unexpected ASGI message 'websocket.close', after sending "
                    "'websocket.close' or response already completed."
                )
            sent_messages.append(message)

        config = SimpleNamespace(is_active=True, api_key='test-api-key', workspace_id='test-workspace')
        upstream = HangingUpstream()
        scope = {'type': 'websocket', 'query_string': b'token=test-token', 'headers': []}

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
            asyncio.run(asr_realtime_websocket_application(scope, receive, send))

        self.assertNotIn('websocket.close', [message.get('type') for message in sent_messages])
