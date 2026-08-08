import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import PermissionPoint, Role, UserRole
from apps.ai_models.models import (
    TenantTTSProviderGrant,
    TenantTTSSettings,
    TenantTTSVoiceTestText,
    TTSProvider,
    TTSVoice,
)
from apps.ai_models.services import cosyvoice as cosyvoice_services
from apps.devices.models import Device
from apps.tenants.models import Membership, Tenant
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


class CompanyTTSVoiceTestTextTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tts-test-text-user', password='test123456')
        self.setup_tenant(self.user)
        self.role = Role.objects.create(name='TTS Test Text Role', code='tts_test_text')
        UserRole.objects.create(user=self.user, role=self.role)
        self.other_user = User.objects.create_user(username='tts-test-text-other', password='test123456')
        self.other_tenant = Tenant.objects.create(name='另一家公司', code='other-test-text-tenant')
        Membership.objects.create(user=self.other_user, tenant=self.other_tenant)

        permission_points = []
        for code in ('ai_models.tts.view', 'ai_models.tts.update'):
            point, _ = PermissionPoint.objects.update_or_create(
                code=code,
                defaults={'name': code, 'module': 'ai_models_tts', 'description': code, 'is_active': True},
            )
            permission_points.append(point)
            self.role.permission_points.add(point)
        self.tenant.permission_points.set(permission_points)
        self.other_tenant.permission_points.set(permission_points)

        self.provider = TTSProvider.objects.get(code='aliyun')
        self.provider.default_test_text = '平台默认试听文本'
        self.provider.save(update_fields=['default_test_text'])
        self.voice = TTSVoice.objects.get(provider=self.provider, voice_code='Cherry')
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.provider)
        TenantTTSProviderGrant.objects.create(tenant=self.other_tenant, provider=self.provider)
        self.client.force_authenticate(user=self.user)

    def text_url(self, voice_id=None):
        return f'/api/v1/ai-models/tts/voice-test-texts/{voice_id or self.voice.id}/'

    def options(self):
        response = self.client.get('/api/v1/ai-models/tts/options/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def voice_from_options(self, data=None):
        data = data or self.options()
        return next(voice for voice in data['voices'] if voice['id'] == self.voice.id)

    def test_options_fall_back_to_platform_text(self):
        voice = self.voice_from_options()
        self.assertEqual(voice['testText'], '平台默认试听文本')
        self.assertEqual(voice['customTestText'], '')
        self.assertEqual(voice['platformTestText'], '平台默认试听文本')
        self.assertFalse(voice['hasTestTextOverride'])

    def test_two_tenants_receive_isolated_texts(self):
        TenantTTSVoiceTestText.objects.create(tenant=self.tenant, voice=self.voice, test_text='甲公司试听')
        TenantTTSVoiceTestText.objects.create(tenant=self.other_tenant, voice=self.voice, test_text='乙公司试听')
        self.assertEqual(self.voice_from_options()['testText'], '甲公司试听')
        self.assertEqual(self.voice_from_options()['customTestText'], '甲公司试听')
        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.voice_from_options()['testText'], '乙公司试听')
        self.assertEqual(self.voice_from_options()['customTestText'], '乙公司试听')

    def test_put_trims_text_and_delete_restores_platform_text(self):
        response = self.client.put(self.text_url(), {'testText': '  公司专属试听  '}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['testText'], '公司专属试听')
        self.assertEqual(response.data['customTestText'], '公司专属试听')
        self.assertTrue(response.data['hasTestTextOverride'])
        self.assertEqual(
            TenantTTSVoiceTestText.objects.get(tenant=self.tenant, voice=self.voice).test_text,
            '公司专属试听',
        )

        delete_response = self.client.delete(self.text_url())

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.voice_from_options()['testText'], '平台默认试听文本')
        self.assertEqual(self.voice_from_options()['customTestText'], '')
        self.assertFalse(TenantTTSVoiceTestText.objects.filter(tenant=self.tenant, voice=self.voice).exists())

    def test_text_length_and_blank_validation(self):
        for test_text in ('', '   ', 'x' * 2001):
            response = self.client.put(self.text_url(), {'testText': test_text}, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(TenantTTSVoiceTestText.objects.filter(tenant=self.tenant, voice=self.voice).exists())

    def test_override_requires_tts_update_permission(self):
        self.tenant.permission_points.remove(PermissionPoint.objects.get(code='ai_models.tts.update'))

        response = self.client.put(self.text_url(), {'testText': '不应写入'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TenantTTSVoiceTestText.objects.filter(tenant=self.tenant, voice=self.voice).exists())

    def test_platform_superuser_cannot_write_company_override(self):
        superuser = User.objects.create_superuser(username='tts-test-text-root', password='test123456')
        self.client.force_authenticate(user=superuser)

        response = self.client.put(self.text_url(), {'testText': '平台账号不应写入'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TenantTTSVoiceTestText.objects.filter(voice=self.voice).exists())

    def test_unauthorized_voice_is_rejected_without_record(self):
        ungranted_provider = TTSProvider.objects.create(code='ungranted-test-text-provider', name='未授权卡片')
        ungranted_voice = TTSVoice.objects.create(
            provider=ungranted_provider,
            display_name='未授权音色',
            voice_code='ungranted-test-text-voice',
        )

        response = self.client.put(self.text_url(ungranted_voice.id), {'testText': '不应写入'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TenantTTSVoiceTestText.objects.filter(tenant=self.tenant, voice=ungranted_voice).exists())

    def test_device_options_expose_only_custom_test_text(self):
        TenantTTSVoiceTestText.objects.create(tenant=self.tenant, voice=self.voice, test_text='仅设备可见的公司试听')
        Device.objects.create(tenant=self.tenant, name='Test Text Device', code='ANDROID-TEST-TEXT-001', is_enabled=True)
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/v1/ai-models/tts/options/', HTTP_X_DEVICE_CODE='ANDROID-TEST-TEXT-001')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice = next(item for item in response.data['voices'] if item['id'] == self.voice.id)
        self.assertEqual(voice['customTestText'], '仅设备可见的公司试听')
        self.assertNotIn('testText', voice)
        self.assertNotIn('platformTestText', voice)
        self.assertNotIn('hasTestTextOverride', voice)
        # customTestText 位于 voiceCode 与 gender 之间
        keys = list(voice.keys())
        self.assertLess(keys.index('voiceCode'), keys.index('customTestText'))
        self.assertLess(keys.index('customTestText'), keys.index('gender'))

    def test_device_options_custom_test_text_empty_without_override(self):
        Device.objects.create(tenant=self.tenant, name='Test Text Empty', code='ANDROID-TEST-TEXT-EMPTY', is_enabled=True)
        self.client.force_authenticate(user=None)

        response = self.client.get('/api/v1/ai-models/tts/options/', HTTP_X_DEVICE_CODE='ANDROID-TEST-TEXT-EMPTY')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        voice = next(item for item in response.data['voices'] if item['id'] == self.voice.id)
        self.assertEqual(voice['customTestText'], '')
        self.assertNotIn('testText', voice)


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
