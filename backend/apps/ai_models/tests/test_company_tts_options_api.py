import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import (
    TenantTTSProviderGrant,
    TenantTTSSettings,
    TTSProvider,
    TTSVoice,
)
from apps.ai_models.services import cosyvoice as cosyvoice_services
from apps.devices.models import Device
from apps.tenants.models import Tenant
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class CompanyTTSProviderNeutralOptionsTests(TenantTestMixin, APITestCase):
    """Company options must be card-neutral and authorization-scoped."""

    def setUp(self):
        self.user = User.objects.create_user(username='tts-neutral-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS Neutral Role', code='tts_neutral')
        UserRole.objects.create(user=self.user, role=self.role)

        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')

        self.cosy_settings = cosyvoice_services.get_cosyvoice_settings()
        self.cosyvoice = self.cosy_settings.provider
        self.cosy_voice = TTSVoice.objects.create(
            provider=self.cosyvoice,
            display_name='客服女声',
            voice_code='remote-voice-neutral-1',
        )

        self.grant_permissions('ai_models.tts.view', 'ai_models.tts.update')
        self.client.force_authenticate(user=self.user)

    def grant_permissions(self, *codes: str):
        permission_points = []
        for code in codes:
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'ai_models_tts', 'description': code, 'is_active': True},
            )
            permission_points.append(point)
        self.role.permission_points.set(permission_points)
        self.tenant.permission_points.set(permission_points)

    def authorize(self, provider, *, is_active=True, public_config=None):
        return TenantTTSProviderGrant.objects.update_or_create(
            tenant=self.tenant,
            provider=provider,
            defaults={'is_active': is_active, 'public_config': public_config or {}},
        )[0]

    def options(self):
        response = self.client.get('/api/v1/ai-models/tts/options/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_tenant_without_grant_sees_empty_state(self):
        data = self.options()

        self.assertEqual(data['voices'], [])
        self.assertEqual(data['providers'], [])
        self.assertIsNone(data['defaultVoiceId'])
        self.assertEqual(data['provider']['code'], '')
        self.assertFalse(data['provider']['isActive'])

    def test_only_authorized_cards_voices_are_returned(self):
        self.authorize(self.cosyvoice)

        data = self.options()

        voice_ids = {voice['id'] for voice in data['voices']}
        self.assertIn(self.cosy_voice.id, voice_ids)
        self.assertNotIn(self.cherry.id, voice_ids)
        self.assertEqual({voice['providerCode'] for voice in data['voices']}, {'cosyvoice'})

    def test_flat_voices_union_all_authorized_cards(self):
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)

        data = self.options()

        voice_ids = {voice['id'] for voice in data['voices']}
        self.assertIn(self.cherry.id, voice_ids)
        self.assertIn(self.cosy_voice.id, voice_ids)

    def test_voices_are_also_grouped_by_card_with_schema(self):
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)

        data = self.options()

        by_code = {provider['code']: provider for provider in data['providers']}
        self.assertEqual(set(by_code), {'aliyun', 'cosyvoice'})
        self.assertEqual(by_code['aliyun']['publicConfigSchema']['schemaKey'], 'aliyun-qwen')
        self.assertEqual(by_code['cosyvoice']['publicConfigSchema']['schemaKey'], 'cosyvoice')
        cosy_fields = {field['name'] for field in by_code['cosyvoice']['publicConfigSchema']['fields']}
        self.assertEqual(cosy_fields, {'speech_rate', 'pitch_rate', 'volume'})
        self.assertIn(self.cosy_voice.id, {voice['id'] for voice in by_code['cosyvoice']['voices']})

    def test_each_voice_carries_its_card_identity_for_schema_selection(self):
        self.authorize(self.cosyvoice)

        voice = self.options()['voices'][0]

        self.assertEqual(voice['providerId'], self.cosyvoice.id)
        self.assertEqual(voice['providerCode'], 'cosyvoice')
        self.assertEqual(voice['configSchemaKey'], 'cosyvoice')
        self.assertIn('realtime', voice['supportedChannels'])
        self.assertIn('speechRate', voice['capabilities'])

    def test_legacy_provider_field_reflects_default_voices_card(self):
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)
        TenantTTSSettings.objects.update_or_create(
            tenant=self.tenant,
            defaults={'default_voice': self.cosy_voice},
        )

        data = self.options()

        self.assertEqual(data['provider']['code'], 'cosyvoice')
        self.assertEqual(data['defaultVoiceId'], self.cosy_voice.id)

    def test_options_never_expose_credentials_or_private_endpoints(self):
        self.aliyun.api_key = 'dashscope-secret'
        self.aliyun.base_url = 'wss://qwen-secret.example.com/realtime'
        self.aliyun.save(update_fields=['api_key', 'base_url'])
        self.cosy_settings.websocket_url = 'wss://cosy-secret.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
        self.cosy_settings.customization_url = 'https://cosy-secret.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization'
        self.cosy_settings.save()
        self.authorize(self.aliyun)
        self.authorize(self.cosyvoice)

        body = json.dumps(self.options(), ensure_ascii=False, default=str)

        self.assertNotIn('dashscope-secret', body)
        self.assertNotIn('qwen-secret.example.com', body)
        self.assertNotIn('cosy-secret', body)
        self.assertNotIn('apiKey', body)

    def test_revoked_grant_removes_voices_from_options(self):
        grant = self.authorize(self.cosyvoice)
        self.assertNotEqual(self.options()['voices'], [])

        grant.is_active = False
        grant.save(update_fields=['is_active'])

        self.assertEqual(self.options()['voices'], [])

    def test_device_code_reads_options_scoped_to_its_own_tenant(self):
        self.authorize(self.cosyvoice)
        Device.objects.create(
            tenant=self.tenant,
            name='Neutral Options Device',
            code='ANDROID-NEUTRAL-001',
            is_enabled=True,
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(
            '/api/v1/ai-models/tts/options/',
            HTTP_X_DEVICE_CODE='ANDROID-NEUTRAL-001',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice_ids = {voice['id'] for voice in response.data['voices']}
        self.assertIn(self.cosy_voice.id, voice_ids)
        self.assertNotIn(self.cherry.id, voice_ids)
        self.assertEqual({voice['providerCode'] for voice in response.data['voices']}, {'cosyvoice'})


class CompanyTTSDefaultVoiceAuthorizationTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tts-default-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS Default Role', code='tts_default')
        UserRole.objects.create(user=self.user, role=self.role)

        self.other_tenant = Tenant.objects.create(name='别家公司', code='other-default-tenant')
        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')
        self.cosy_settings = cosyvoice_services.get_cosyvoice_settings()
        self.cosyvoice = self.cosy_settings.provider
        self.cosy_voice = TTSVoice.objects.create(
            provider=self.cosyvoice,
            display_name='客服女声',
            voice_code='remote-voice-default-1',
        )

        for code in ('ai_models.tts.view', 'ai_models.tts.update'):
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'ai_models_tts', 'description': code, 'is_active': True},
            )
            self.role.permission_points.add(point)
            self.tenant.permission_points.add(point)
        self.client.force_authenticate(user=self.user)

    def authorize(self, tenant, provider, *, public_config=None):
        return TenantTTSProviderGrant.objects.update_or_create(
            tenant=tenant,
            provider=provider,
            defaults={'is_active': True, 'public_config': public_config or {}},
        )[0]

    def patch_default(self, payload):
        return self.client.patch('/api/v1/ai-models/tts/default-voice/', payload, format='json')

    def test_unauthorized_voice_is_rejected(self):
        self.authorize(self.tenant, self.cosyvoice)

        response = self.patch_default({'voiceId': self.cherry.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('未授权', str(response.data))
        self.assertFalse(TenantTTSSettings.objects.filter(tenant=self.tenant, default_voice=self.cherry).exists())

    def test_cross_tenant_voice_is_rejected(self):
        self.authorize(self.other_tenant, self.cosyvoice)

        response = self.patch_default({'voiceId': self.cosy_voice.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authorized_voice_is_saved(self):
        self.authorize(self.tenant, self.cosyvoice)

        response = self.patch_default({'voiceId': self.cosy_voice.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['defaultVoiceId'], self.cosy_voice.id)
        self.assertEqual(
            TenantTTSSettings.objects.get(tenant=self.tenant).default_voice_id,
            self.cosy_voice.id,
        )

    def test_tenant_without_any_grant_gets_clear_error(self):
        response = self.patch_default({})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('联系超管分配', str(response.data))

    def test_saving_cosyvoice_config_does_not_touch_qwen_config(self):
        self.authorize(self.tenant, self.aliyun, public_config={'model_code': 'standard', 'instructions': '保持原样'})
        self.authorize(self.tenant, self.cosyvoice)

        response = self.patch_default({
            'voiceId': self.cosy_voice.id,
            'ttsSessionConfig': {'speechRate': 1.4, 'volume': 80},
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cosy_config = TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=self.cosyvoice).public_config
        qwen_config = TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=self.aliyun).public_config
        self.assertEqual(cosy_config['speech_rate'], 1.4)
        self.assertEqual(cosy_config['volume'], 80)
        self.assertNotIn('instructions', cosy_config)
        self.assertEqual(qwen_config['model_code'], 'standard')
        self.assertEqual(qwen_config['instructions'], '保持原样')

    def test_qwen_field_on_cosyvoice_voice_is_rejected(self):
        self.authorize(self.tenant, self.cosyvoice)

        response = self.patch_default({
            'voiceId': self.cosy_voice.id,
            'ttsSessionConfig': {'instructions': '开心一点'},
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('instructions', str(response.data))

    def test_saving_default_voice_publishes_runtime_config_refresh(self):
        self.authorize(self.tenant, self.cosyvoice)

        with patch('apps.ai_models.services.tts_runtime_events.publish_device_event_sync') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.patch_default({'voiceId': self.cosy_voice.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        publish.assert_called()
        event = publish.call_args[0][0]
        self.assertEqual(event['type'], 'device.voice_configuration.changed')
        self.assertEqual(event['tenantId'], self.tenant.id)
        self.assertEqual(event['refresh']['endpoint'], '/api/v1/device-runtime/config/')


class CompanyTTSTestAuthorizationTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tts-preview-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS Preview Role', code='tts_preview')
        UserRole.objects.create(user=self.user, role=self.role)

        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')
        self.cosy_settings = cosyvoice_services.get_cosyvoice_settings()
        self.cosyvoice = self.cosy_settings.provider
        self.cosy_voice = TTSVoice.objects.create(
            provider=self.cosyvoice,
            display_name='客服女声',
            voice_code='remote-voice-preview-1',
        )

        point, _ = PermissionPoint.objects.update_or_create(
            code='ai_models.tts.view',
            defaults={'name': 'view', 'module': 'ai_models_tts', 'description': 'view', 'is_active': True},
        )
        self.role.permission_points.add(point)
        self.tenant.permission_points.add(point)
        self.client.force_authenticate(user=self.user)

    def authorize(self, provider):
        return TenantTTSProviderGrant.objects.update_or_create(
            tenant=self.tenant,
            provider=provider,
            defaults={'is_active': True},
        )[0]

    def test_preview_rejects_unauthorized_voice(self):
        self.authorize(self.cosyvoice)

        response = self.client.post(
            '/api/v1/ai-models/tts/test/',
            {'text': '试听', 'voiceId': self.cherry.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_without_any_grant_returns_clear_error(self):
        response = self.client.post('/api/v1/ai-models/tts/test/', {'text': '试听'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('联系超管分配', str(response.data))

    @patch('apps.ai_models.services.tts.synthesize_tts_pcm', return_value=b'\x01\x02')
    def test_preview_routes_to_the_resolved_voices_adapter(self, synthesize):
        self.cosy_settings.api_key_encrypted = ''
        self.cosy_settings.websocket_url = 'wss://ws-preview.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'
        self.cosy_settings.save()
        self.authorize(self.cosyvoice)

        response = self.client.post(
            '/api/v1/ai-models/tts/test/',
            {'text': '试听 CosyVoice', 'voiceId': self.cosy_voice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call_kwargs = synthesize.call_args.kwargs
        self.assertEqual(call_kwargs['voice'].id, self.cosy_voice.id)
        self.assertEqual(call_kwargs['config'].provider_code, 'cosyvoice')
        # Qwen-only controls must not leak into a CosyVoice request.
        self.assertNotIn('instructions', call_kwargs['session_config'] or {})
