from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import (
    AgentApplication,
    TenantTTSProviderGrant,
    TenantTTSSettings,
    TTSProvider,
    TTSVoice,
)
from apps.ai_models.services import cosyvoice as cosyvoice_services
from apps.devices.models import Device, DeviceApplication
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class DeviceTTSAuthorizationTests(TenantTestMixin, APITestCase):
    """Device binding, device applications and runtime config honour card grants."""

    def setUp(self):
        self.user = User.objects.create_user(username='device-tts-admin', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='Device TTS Admin', code='device_tts_admin')
        UserRole.objects.create(user=self.user, role=self.role)
        self.grant_permissions('devices.view', 'devices.create', 'devices.update')
        self.client.force_authenticate(user=self.user)

        self.other_tenant = Tenant.objects.create(name='别家公司', code='device-tts-other')
        self.agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='TTS Agent',
            system_prompt='你是数字人。',
        )
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='TTS App',
            code='device-tts-app',
            agent_application=self.agent_application,
        )

        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')
        self.cosy_settings = cosyvoice_services.get_cosyvoice_settings()
        self.cosyvoice = self.cosy_settings.provider
        self.cosy_voice = TTSVoice.objects.create(
            provider=self.cosyvoice,
            display_name='客服女声',
            voice_code='remote-voice-device-1',
        )

    def grant_permissions(self, *codes: str):
        points = []
        for code in codes:
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'devices', 'description': code, 'is_active': True},
            )
            points.append(point)
        self.role.permission_points.set(points)
        self.tenant.permission_points.set(points)

    def authorize(self, provider, *, tenant=None, is_active=True):
        return TenantTTSProviderGrant.objects.update_or_create(
            tenant=tenant or self.tenant,
            provider=provider,
            defaults={'is_active': is_active},
        )[0]

    def make_device(self, code='ANDROID-TTS-AUTH-001', **overrides):
        defaults = {
            'tenant': self.tenant,
            'application': self.application,
            'agent_application': self.agent_application,
            'name': 'TTS Device',
            'code': code,
            'authorization_type': Device.AUTHORIZATION_PERMANENT,
            'registered_at': timezone.now(),
        }
        defaults.update(overrides)
        return Device.objects.create(**defaults)

    def runtime_config(self, device_code):
        return self.client.get(
            '/api/v1/device-runtime/config/',
            format='json',
            HTTP_X_DEVICE_CODE=device_code,
        )

    def test_binding_unauthorized_voice_returns_400(self):
        self.authorize(self.aliyun)
        device = self.make_device()

        response = self.client.patch(
            f'/api/v1/devices/{device.code}/',
            {'voiceToneId': self.cosy_voice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        device.refresh_from_db()
        self.assertIsNone(device.tts_voice_id)

    def test_binding_authorized_qwen_voice_succeeds(self):
        self.authorize(self.aliyun)
        device = self.make_device()

        response = self.client.patch(
            f'/api/v1/devices/{device.code}/',
            {'voiceToneId': self.cherry.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.tts_voice_id, self.cherry.id)

    def test_binding_authorized_cosyvoice_voice_succeeds(self):
        self.authorize(self.cosyvoice)
        device = self.make_device()

        response = self.client.patch(
            f'/api/v1/devices/{device.code}/',
            {'voiceToneId': self.cosy_voice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.tts_voice_id, self.cosy_voice.id)

    def test_binding_still_publishes_full_runtime_config_event(self):
        self.authorize(self.cosyvoice)
        device = self.make_device()

        with patch('apps.devices.views.publish_device_event_sync') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    f'/api/v1/devices/{device.code}/',
                    {'voiceToneId': self.cosy_voice.id},
                    format='json',
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        publish.assert_called()
        event = publish.call_args[0][0]
        self.assertEqual(event['type'], 'device.voice_configuration.changed')

    def test_device_application_rejects_unauthorized_voice(self):
        self.authorize(self.aliyun)

        response = self.client.post(
            '/api/v1/device-applications/',
            {
                'name': 'Unauthorized Voice App',
                'code': 'unauthorized-voice-app',
                'voiceToneIds': [self.cosy_voice.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_device_application_accepts_authorized_voice(self):
        self.authorize(self.cosyvoice)

        response = self.client.post(
            '/api/v1/device-applications/',
            {
                'name': 'Authorized Voice App',
                'code': 'authorized-voice-app',
                'voiceToneIds': [self.cosy_voice.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('voiceToneIds'), [self.cosy_voice.id])

    def test_runtime_config_prefers_device_binding_over_company_default(self):
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        device = self.make_device(tts_voice=self.cosy_voice)

        response = self.runtime_config(device.code)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice_tones = response.data['resources']['voiceTones']
        self.assertEqual(len(voice_tones), 1)
        self.assertEqual(voice_tones[0]['id'], self.cosy_voice.id)

    def test_runtime_config_falls_back_inside_authorization_when_binding_revoked(self):
        grant = self.authorize(self.cosyvoice)
        self.authorize(self.aliyun)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        device = self.make_device(tts_voice=self.cosy_voice)

        grant.is_active = False
        grant.save(update_fields=['is_active'])
        response = self.runtime_config(device.code)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice_tones = response.data['resources']['voiceTones']
        self.assertEqual(len(voice_tones), 1)
        # Never returns the now-unauthorized binding.
        self.assertNotEqual(voice_tones[0]['id'], self.cosy_voice.id)
        self.assertEqual(voice_tones[0]['id'], self.cherry.id)

    def test_runtime_config_returns_no_voice_when_tenant_has_no_grant(self):
        device = self.make_device(tts_voice=self.cherry)

        response = self.runtime_config(device.code)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resources']['voiceTones'], [])

    def test_runtime_config_ignores_platform_disabled_voice(self):
        # A dedicated single-voice card, so disabling its only voice leaves the
        # tenant with nothing to fall back to.
        solo_card = TTSProvider.objects.create(code='solo-card', name='独立卡片')
        solo_voice = TTSVoice.objects.create(provider=solo_card, display_name='独立音色', voice_code='solo-1')
        self.authorize(solo_card)
        device = self.make_device(tts_voice=solo_voice)
        solo_voice.is_active = False
        solo_voice.save(update_fields=['is_active'])

        response = self.runtime_config(device.code)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resources']['voiceTones'], [])

    def test_android_runtime_config_voice_payload_keeps_existing_fields(self):
        """Frozen contract: Android must not need a release for CosyVoice."""
        self.authorize(self.cosyvoice)
        device = self.make_device(
            tts_voice=self.cosy_voice,
            tts_voice_config={'speech_rate': 1.35, 'pitch_rate': 0.9, 'volume': 72},
        )

        response = self.runtime_config(device.code)

        voice = response.data['resources']['voiceTones'][0]
        self.assertEqual(
            set(voice),
            {'id', 'name', 'voiceCode', 'audioUrl', 'iconUrl', 'speechRate', 'pitchRate', 'volume'},
        )
        self.assertEqual(voice['name'], '客服女声')
        self.assertEqual(voice['voiceCode'], 'remote-voice-device-1')
        self.assertEqual(voice['speechRate'], 1.35)
        self.assertEqual(voice['pitchRate'], 0.9)
        self.assertEqual(voice['volume'], 72)

    def test_runtime_config_does_not_leak_provider_credentials(self):
        self.cosy_settings.websocket_url = 'wss://leak-check.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
        self.cosy_settings.save()
        self.authorize(self.cosyvoice)
        device = self.make_device(tts_voice=self.cosy_voice)

        body = json.dumps(self.runtime_config(device.code).data, ensure_ascii=False, default=str)

        self.assertNotIn('leak-check', body)
        self.assertNotIn('apiKey', body)
        self.assertNotIn('providerCode', body)


class DeviceHTTPRuntimeTTSAuthorizationTests(TenantTestMixin, APITestCase):
    """POST /ai-models/tts/runtime/ stays Android-compatible and grant-scoped."""

    def setUp(self):
        self.user = User.objects.create_user(username='device-runtime-tts', password='test123456')
        self.setup_tenant(self.user)
        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')
        self.cosy_settings = cosyvoice_services.get_cosyvoice_settings()
        self.cosy_settings.api_key_encrypted = ''
        self.cosy_settings.websocket_url = 'wss://ws-runtime.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
        self.cosy_settings.save()
        self.cosyvoice = self.cosy_settings.provider
        self.cosy_voice = TTSVoice.objects.create(
            provider=self.cosyvoice,
            display_name='客服女声',
            voice_code='remote-voice-runtime-1',
        )
        self.device = Device.objects.create(
            tenant=self.tenant,
            name='Runtime TTS Device',
            code='ANDROID-RUNTIME-TTS-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )

    def authorize(self, provider):
        return TenantTTSProviderGrant.objects.update_or_create(
            tenant=self.tenant,
            provider=provider,
            defaults={'is_active': True},
        )[0]

    def post_runtime(self, payload):
        return self.client.post(
            '/api/v1/ai-models/tts/runtime/',
            payload,
            format='json',
            HTTP_X_DEVICE_CODE=self.device.code,
        )

    def test_unauthorized_voice_id_is_rejected(self):
        self.authorize(self.aliyun)

        response = self.post_runtime({'text': '越权', 'voiceId': self.cosy_voice.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_without_grant_is_rejected(self):
        response = self.post_runtime({'text': '无授权'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('联系超管分配', str(response.data))

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x03\x04')
    def test_android_needs_only_device_code_text_and_voice_id(self, synthesize):
        self.authorize(self.cosyvoice)
        self.device.tts_voice = self.cosy_voice
        self.device.save(update_fields=['tts_voice'])

        response = self.post_runtime({'text': '设备端测试'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/pcm')
        self.assertEqual(response['X-Audio-Source-Format'], 'pcm_s16le')
        self.assertEqual(response['X-TTS-Voice'], 'remote-voice-runtime-1')
        self.assertIn('X-Audio-Sample-Rate', response)
        self.assertIn('X-Audio-Channels', response)
        self.assertEqual(response.content, b'\x03\x04')
        # The card came from the resolved voice, not from any request field.
        self.assertEqual(synthesize.call_args.kwargs['config'].provider_code, 'cosyvoice')

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x03\x04')
    def test_wav_wrapping_still_supported(self, synthesize):
        self.authorize(self.aliyun)
        self.device.tts_voice = self.cherry
        self.device.save(update_fields=['tts_voice'])

        response = self.post_runtime({'text': '设备端测试', 'wrapWav': True})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertTrue(response.content.startswith(b'RIFF'))

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x03\x04')
    def test_device_binding_wins_over_company_default(self, synthesize):
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)
        self.device.tts_voice = self.cosy_voice
        self.device.save(update_fields=['tts_voice'])

        response = self.post_runtime({'text': '设备端测试'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(synthesize.call_args.kwargs['voice'].id, self.cosy_voice.id)


class TTSAuthorizationRuntimeConfigPushTests(TenantTestMixin, APITestCase):
    """Grant/config changes must reach online devices over the existing WS channel."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(username='tts-push-root', password='test123456')
        self.member = User.objects.create_user(username='tts-push-member', password='test123456')
        self.setup_tenant(self.member)
        self.agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Push Agent',
            system_prompt='你是数字人。',
        )
        self.agent_application.publish()
        self.application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Push App',
            code='tts-push-app',
            agent_application=self.agent_application,
        )
        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')
        self.device = Device.objects.create(
            tenant=self.tenant,
            application=self.application,
            agent_application=self.agent_application,
            name='Push Device',
            code='ANDROID-TTS-PUSH-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
            registered_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.superuser)

    def test_saving_card_authorization_pushes_full_runtime_config(self):
        from asgiref.sync import async_to_sync, sync_to_async
        from asgiref.testing import ApplicationCommunicator

        async def run_websocket():
            from config.asgi import application

            communicator = ApplicationCommunicator(
                application,
                {'type': 'websocket', 'path': '/ws/realtime/', 'query_string': b'', 'headers': []},
            )
            await communicator.send_input({'type': 'websocket.connect'})
            accepted = await communicator.receive_output(timeout=1)
            self.assertEqual(accepted['type'], 'websocket.accept')

            await communicator.send_input({
                'type': 'websocket.receive',
                'text': json.dumps({
                    'type': 'device.runtime_config.subscribe',
                    'id': 'tts-grant-runtime-config-sub',
                    'payload': {'deviceCode': self.device.code},
                }),
            })
            initial = await communicator.receive_output(timeout=1)
            self.assertEqual(json.loads(initial['text'])['type'], 'device.runtime_config.subscribed')

            def save_authorization():
                # The publish is queued with transaction.on_commit, which a TestCase's
                # wrapping atomic block would otherwise swallow.
                with self.captureOnCommitCallbacks(execute=True):
                    return self.client.put(
                        f'/api/v1/settings/tts/tenants/{self.tenant.id}/card-authorizations/',
                        {
                            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
                            'defaultVoiceId': self.cherry.id,
                        },
                        format='json',
                    )

            save_response = await sync_to_async(save_authorization, thread_sensitive=True)()
            self.assertEqual(save_response.status_code, status.HTTP_200_OK)

            changed = await communicator.receive_output(timeout=2)
            payload = json.loads(changed['text'])
            self.assertEqual(payload['type'], 'device.runtime_config.subscribed')
            self.assertEqual(payload['payload']['action'], 'voiceConfigurationChanged')
            config = payload['payload']['config']
            # Must be the full rebuilt config, not a voice-only delta.
            for key in ('device', 'application', 'agentApplication', 'wakeWords', 'scrollingTexts'):
                self.assertIn(key, config)
            voice_tones = config.get('voiceConfiguration', {}).get('voiceTones', [])
            self.assertEqual(len(voice_tones), 1)
            self.assertEqual(voice_tones[0]['id'], self.cherry.id)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
