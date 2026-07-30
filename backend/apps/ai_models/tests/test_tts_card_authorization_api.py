import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_models.models import TenantTTSProviderGrant, TTSProvider, TTSVoice, TenantTTSSettings
from apps.devices.models import Device, DeviceApplication
from apps.tenants.models import Tenant

User = get_user_model()


class TenantTTSCardAuthorizationApiTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='tts-grant-root', password='test123456')
        self.tenant = Tenant.objects.create(name='授权公司', code='grant-api-tenant')
        self.disabled_tenant = Tenant.objects.create(name='停用公司', code='disabled-tenant', is_active=False)

        self.card_a = TTSProvider.objects.create(code='aliyun-clone-a', name='卡片 A')
        self.voice_a = TTSVoice.objects.create(provider=self.card_a, display_name='A 音色', voice_code='a-1')
        self.card_b = TTSProvider.objects.create(code='aliyun-clone-b', name='卡片 B')
        self.voice_b = TTSVoice.objects.create(provider=self.card_b, display_name='B 音色', voice_code='b-1')

        self.aliyun = TTSProvider.objects.get(code='aliyun')
        self.cherry = TTSVoice.objects.get(provider=self.aliyun, voice_code='Cherry')

        self.client.force_authenticate(user=self.superuser)

    def url(self, tenant_id=None):
        return f'/api/v1/settings/tts/tenants/{tenant_id or self.tenant.id}/card-authorizations/'

    def test_requires_superuser(self):
        member = User.objects.create_user(username='plain-user', password='test123456')
        self.client.force_authenticate(user=member)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_or_disabled_tenant_is_rejected(self):
        self.assertEqual(self.client.get(self.url(999999)).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(self.url(self.disabled_tenant.id)).status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_lists_adapter_backed_cards_with_grant_state(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {provider['code'] for provider in response.data['providers']}
        self.assertIn('aliyun', codes)
        self.assertIn('cosyvoice', codes)
        # Cards without an implemented adapter must not be offered for allocation.
        self.assertNotIn('aliyun-clone-a', codes)
        aliyun = next(item for item in response.data['providers'] if item['code'] == 'aliyun')
        self.assertTrue(aliyun['grantIsActive'])
        self.assertIn('publicConfigSchema', aliyun)
        self.assertIn('supportedChannels', aliyun)

    def test_get_does_not_expose_credentials(self):
        self.aliyun.api_key = 'dashscope-secret'
        self.aliyun.base_url = 'wss://secret.example.com/realtime'
        self.aliyun.save(update_fields=['api_key', 'base_url'])

        response = self.client.get(self.url())

        body = json.dumps(response.data, ensure_ascii=False, default=str)
        self.assertNotIn('dashscope-secret', body)
        self.assertNotIn('secret.example.com', body)

    def test_put_enables_grant_and_sets_default_voice(self):
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
            'defaultVoiceId': self.cherry.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['defaultVoiceId'], self.cherry.id)
        grant = TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=self.aliyun)
        self.assertTrue(grant.is_active)
        self.assertEqual(TenantTTSSettings.objects.get(tenant=self.tenant).default_voice_id, self.cherry.id)

    def test_put_rejects_unknown_provider_id(self):
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': 999999, 'isActive': True}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_rejects_default_voice_outside_enabled_grants(self):
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': False}],
            'defaultVoiceId': self.cherry.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('默认音色必须属于本次启用授权', str(response.data))

    def test_put_rejects_hidden_or_disabled_default_voice(self):
        self.cherry.is_visible = False
        self.cherry.save(update_fields=['is_visible'])

        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
            'defaultVoiceId': self.cherry.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.cherry.is_visible = True
        self.cherry.is_active = False
        self.cherry.save(update_fields=['is_visible', 'is_active'])
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
            'defaultVoiceId': self.cherry.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_rejects_nonexistent_default_voice(self):
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
            'defaultVoiceId': 999999,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_stores_per_card_public_config_without_cross_contamination(self):
        cosyvoice = TTSProvider.objects.get(code='cosyvoice')

        response = self.client.put(self.url(), {
            'cardGrants': [
                {'providerId': self.aliyun.id, 'isActive': True, 'publicConfig': {'model_code': 'standard', 'volume': 70}},
                {'providerId': cosyvoice.id, 'isActive': True, 'publicConfig': {'speech_rate': 1.5}},
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        qwen_config = TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=self.aliyun).public_config
        cosy_config = TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=cosyvoice).public_config
        self.assertEqual(qwen_config['model_code'], 'standard')
        self.assertEqual(qwen_config['volume'], 70)
        self.assertEqual(cosy_config['speech_rate'], 1.5)
        self.assertNotIn('model_code', cosy_config)
        self.assertNotIn('instructions', cosy_config)

    def test_put_rejects_config_field_not_in_that_cards_schema(self):
        cosyvoice = TTSProvider.objects.get(code='cosyvoice')

        response = self.client.put(self.url(), {
            'cardGrants': [
                {'providerId': cosyvoice.id, 'isActive': True, 'publicConfig': {'instructions': '开心一点'}},
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('instructions', str(response.data))

    def test_put_rejects_non_object_public_config(self):
        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True, 'publicConfig': 'nope'}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disabling_grant_used_by_company_default_is_blocked(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)

        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': False}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('仍在使用中', str(response.data))
        self.assertTrue(TenantTTSProviderGrant.objects.get(tenant=self.tenant, provider=self.aliyun).is_active)

    def test_disabling_grant_used_by_device_is_blocked_with_counts(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)
        Device.objects.create(code='DEV-GRANT-1', name='设备一', tenant=self.tenant, tts_voice=self.cherry)

        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': False}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('设备 1 台', str(response.data))

    def test_disabling_grant_used_by_device_application_is_blocked(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)
        application = DeviceApplication.objects.create(name='应用一', tenant=self.tenant)
        application.tts_voices.add(self.cherry)

        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': False}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('设备应用 1 个', str(response.data))

    def test_unused_grant_can_be_disabled_and_history_is_kept(self):
        grant = TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)

        response = self.client.put(self.url(), {
            'cardGrants': [{'providerId': self.aliyun.id, 'isActive': False}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        grant.refresh_from_db()
        self.assertFalse(grant.is_active)
        self.assertTrue(TenantTTSProviderGrant.objects.filter(id=grant.id).exists())

    def test_can_disable_grant_flag_reflects_usage(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)
        response = self.client.get(self.url())
        aliyun = next(item for item in response.data['providers'] if item['code'] == 'aliyun')
        self.assertTrue(aliyun['canDisableGrant'])

        Device.objects.create(code='DEV-GRANT-2', name='设备二', tenant=self.tenant, tts_voice=self.cherry)
        response = self.client.get(self.url())
        aliyun = next(item for item in response.data['providers'] if item['code'] == 'aliyun')
        self.assertFalse(aliyun['canDisableGrant'])
        self.assertEqual(aliyun['usage']['deviceCount'], 1)

    def test_voice_payload_reports_effective_authorization_and_default(self):
        TenantTTSProviderGrant.objects.create(tenant=self.tenant, provider=self.aliyun, is_active=True)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.cherry)

        response = self.client.get(self.url())

        aliyun = next(item for item in response.data['providers'] if item['code'] == 'aliyun')
        cherry = next(voice for voice in aliyun['voices'] if voice['id'] == self.cherry.id)
        self.assertTrue(cherry['effectiveAuthorized'])
        self.assertTrue(cherry['isDefault'])
        self.assertEqual(cherry['providerCode'], 'aliyun')

    def test_saving_authorization_publishes_full_runtime_config_refresh(self):
        # The event is queued via transaction.on_commit, which does not fire inside
        # a TestCase's wrapping atomic block unless the callbacks are captured.
        with patch('apps.ai_models.services.tts_runtime_events.publish_device_event_sync') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.put(self.url(), {
                    'cardGrants': [{'providerId': self.aliyun.id, 'isActive': True}],
                    'defaultVoiceId': self.cherry.id,
                }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        publish.assert_called()
        event = publish.call_args[0][0]
        self.assertEqual(event['type'], 'device.voice_configuration.changed')
        self.assertEqual(event['tenantId'], self.tenant.id)
        self.assertEqual(event['refresh']['reason'], 'voiceConfigurationChanged')
        self.assertEqual(event['refresh']['endpoint'], '/api/v1/device-runtime/config/')
