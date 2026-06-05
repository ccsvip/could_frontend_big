from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.test import TestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


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

    def test_resolve_realtime_connection_requires_asr_permission(self):
        from apps.ai_models.realtime_asr import resolve_asr_realtime_connection

        token = str(RefreshToken.for_user(self.user).access_token)

        self.assertIsNone(resolve_asr_realtime_connection(token))

        self.grant_permissions('ai_models.asr.view')
        connection = resolve_asr_realtime_connection(token)

        self.assertEqual(connection, {'user_id': self.user.id})
