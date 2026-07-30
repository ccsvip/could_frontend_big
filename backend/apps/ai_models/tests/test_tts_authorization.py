from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.ai_models.models import TenantTTSProviderGrant, TTSProvider, TTSVoice, TenantTTSSettings
from apps.ai_models.services import tts_authorization as tts_auth
from apps.devices.models import Device, DeviceApplication
from apps.tenants.models import Tenant


class TenantTTSAuthorizationTests(TestCase):
    """Tenant-scoped authorization behaviour.

    Cards are created inline rather than reusing seeded providers so the
    assertions do not depend on how many voices a seed migration happens to
    install.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name='授权公司', code='grant-tenant')
        self.other_tenant = Tenant.objects.create(name='未授权公司', code='no-grant-tenant')

        self.card_a = TTSProvider.objects.create(code='card-a', name='卡片 A')
        self.voice_a = TTSVoice.objects.create(provider=self.card_a, display_name='A 音色', voice_code='a-voice-1')

        self.card_b = TTSProvider.objects.create(code='card-b', name='卡片 B')
        self.voice_b = TTSVoice.objects.create(provider=self.card_b, display_name='B 音色', voice_code='b-voice-1')

    def grant(self, tenant, provider, *, is_active=True, public_config=None):
        return TenantTTSProviderGrant.objects.create(
            tenant=tenant,
            provider=provider,
            is_active=is_active,
            public_config=public_config or {},
        )

    def effective_ids(self, tenant, **kwargs):
        return set(tts_auth.get_effective_tts_voices_for_tenant(tenant, **kwargs).values_list('id', flat=True))

    def test_new_tenant_without_grant_has_no_effective_voices(self):
        self.assertFalse(tts_auth.get_effective_tts_voices_for_tenant(self.tenant).exists())
        self.assertIsNone(tts_auth.get_effective_tts_voice_for_tenant(self.tenant))

    def test_active_grant_exposes_only_that_cards_voices(self):
        self.grant(self.tenant, self.card_b)

        effective = self.effective_ids(self.tenant)

        self.assertIn(self.voice_b.id, effective)
        self.assertNotIn(self.voice_a.id, effective)

    def test_inactive_grant_is_not_effective(self):
        self.grant(self.tenant, self.card_b, is_active=False)

        self.assertNotIn(self.voice_b.id, self.effective_ids(self.tenant))

    def test_multiple_cards_are_unioned_and_ordered_by_card(self):
        self.grant(self.tenant, self.card_a)
        self.grant(self.tenant, self.card_b)

        voices = list(tts_auth.get_effective_tts_voices_for_tenant(self.tenant))
        ids = {voice.id for voice in voices}
        provider_ids = [voice.provider_id for voice in voices]

        self.assertIn(self.voice_a.id, ids)
        self.assertIn(self.voice_b.id, ids)
        self.assertEqual(provider_ids, sorted(provider_ids))

    def test_provider_code_filter_narrows_to_one_card(self):
        self.grant(self.tenant, self.card_a)
        self.grant(self.tenant, self.card_b)

        effective = self.effective_ids(self.tenant, provider_code='card-b')

        self.assertEqual(effective, {self.voice_b.id})

    def test_disabled_provider_hides_authorized_voices(self):
        self.grant(self.tenant, self.card_b)
        self.card_b.is_active = False
        self.card_b.save(update_fields=['is_active'])

        self.assertNotIn(self.voice_b.id, self.effective_ids(self.tenant))

    def test_hidden_or_disabled_voice_is_excluded(self):
        self.grant(self.tenant, self.card_b)
        self.voice_b.is_visible = False
        self.voice_b.save(update_fields=['is_visible'])
        self.assertNotIn(self.voice_b.id, self.effective_ids(self.tenant))

        self.voice_b.is_visible = True
        self.voice_b.is_active = False
        self.voice_b.save(update_fields=['is_visible', 'is_active'])
        self.assertNotIn(self.voice_b.id, self.effective_ids(self.tenant))

    def test_new_voice_on_granted_card_is_automatically_effective(self):
        self.grant(self.tenant, self.card_b)
        added = TTSVoice.objects.create(provider=self.card_b, display_name='后加音色', voice_code='b-voice-2')

        self.assertIn(added.id, self.effective_ids(self.tenant))

    def test_model_code_filter_only_narrows_qwen_voices(self):
        aliyun = TTSProvider.objects.get(code='aliyun')
        cherry = TTSVoice.objects.get(provider=aliyun, voice_code='Cherry')
        dylan = TTSVoice.objects.get(provider=aliyun, voice_code='Dylan')
        self.grant(self.tenant, aliyun)
        self.grant(self.tenant, self.card_b)

        instructional = self.effective_ids(self.tenant, model_code='instructional')

        self.assertNotIn(dylan.id, instructional)
        self.assertIn(cherry.id, instructional)
        self.assertIn(self.voice_b.id, instructional)

    def test_default_voice_is_used_when_still_authorized(self):
        self.grant(self.tenant, self.card_b)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.voice_b)

        self.assertEqual(tts_auth.get_effective_tts_voice_for_tenant(self.tenant), self.voice_b)

    def test_unauthorized_default_falls_back_inside_authorization(self):
        self.grant(self.tenant, self.card_b)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.voice_a)

        resolved = tts_auth.get_effective_tts_voice_for_tenant(self.tenant)

        self.assertEqual(resolved.provider_id, self.card_b.id)
        self.assertNotEqual(resolved, self.voice_a)

    def test_ensure_authorized_rejects_unauthorized_voice_id(self):
        self.grant(self.tenant, self.card_b)

        with self.assertRaises(ValidationError) as ctx:
            tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, self.voice_a.id)

        self.assertIn('voiceId', ctx.exception.detail)

    def test_ensure_authorized_rejects_cross_tenant_voice_id(self):
        self.grant(self.other_tenant, self.card_b)

        with self.assertRaises(ValidationError):
            tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, self.voice_b.id)

    def test_ensure_authorized_rejects_blank_and_non_numeric_ids(self):
        self.grant(self.tenant, self.card_b)

        for raw in (None, '', 'abc', 0, -1):
            with self.assertRaises(ValidationError):
                tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, raw)

    def test_ensure_authorized_returns_voice_when_granted(self):
        self.grant(self.tenant, self.card_b)

        self.assertEqual(
            tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, self.voice_b.id),
            self.voice_b,
        )

    def test_resolve_prefers_explicit_voice_over_default(self):
        self.grant(self.tenant, self.card_a)
        self.grant(self.tenant, self.card_b)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.voice_a)

        self.assertEqual(tts_auth.resolve_tenant_tts_voice(self.tenant, self.voice_b.id), self.voice_b)
        self.assertEqual(tts_auth.resolve_tenant_tts_voice(self.tenant), self.voice_a)

    def test_resolve_without_fallback_returns_none(self):
        self.grant(self.tenant, self.card_b)

        self.assertIsNone(tts_auth.resolve_tenant_tts_voice(self.tenant, allow_fallback=False))

    def test_card_public_config_is_isolated_per_card(self):
        self.grant(self.tenant, self.card_a, public_config={'model_code': 'standard'})
        self.grant(self.tenant, self.card_b, public_config={'speech_rate': 1.2})

        self.assertEqual(
            tts_auth.get_tenant_tts_card_public_config(self.tenant, self.card_a),
            {'model_code': 'standard'},
        )
        self.assertEqual(
            tts_auth.get_tenant_tts_card_public_config(self.tenant, self.card_b),
            {'speech_rate': 1.2},
        )

    def test_card_public_config_is_empty_without_grant(self):
        self.assertEqual(tts_auth.get_tenant_tts_card_public_config(self.tenant, self.card_b), {})

    def test_usage_reports_tenant_default_device_and_application(self):
        self.grant(self.tenant, self.card_b)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.voice_b)
        Device.objects.create(code='DEV-USAGE-1', name='设备一', tenant=self.tenant, tts_voice=self.voice_b)
        application = DeviceApplication.objects.create(name='应用一', tenant=self.tenant)
        application.tts_voices.add(self.voice_b)

        usage = tts_auth.tts_provider_usage_for_tenant(self.tenant, self.card_b)

        self.assertTrue(usage['tenantDefault'])
        self.assertEqual(usage['deviceCount'], 1)
        self.assertEqual(usage['deviceApplicationCount'], 1)
        self.assertTrue(tts_auth.tts_provider_grant_is_in_use(self.tenant, self.card_b))

    def test_usage_excludes_other_tenants_references(self):
        self.grant(self.tenant, self.card_b)
        self.grant(self.other_tenant, self.card_b)
        Device.objects.create(code='DEV-OTHER-1', name='别家设备', tenant=self.other_tenant, tts_voice=self.voice_b)

        usage = tts_auth.tts_provider_usage_for_tenant(self.tenant, self.card_b)

        self.assertEqual(usage['deviceCount'], 0)
        self.assertFalse(tts_auth.tts_provider_grant_is_in_use(self.tenant, self.card_b))

    def test_voice_usage_reports_single_voice_references(self):
        self.grant(self.tenant, self.card_b)
        other_voice = TTSVoice.objects.create(provider=self.card_b, display_name='另一个', voice_code='b-voice-3')
        Device.objects.create(code='DEV-VOICE-1', name='设备二', tenant=self.tenant, tts_voice=self.voice_b)

        self.assertEqual(tts_auth.tts_voice_usage_for_tenant(self.tenant, self.voice_b)['deviceCount'], 1)
        self.assertEqual(tts_auth.tts_voice_usage_for_tenant(self.tenant, other_voice)['deviceCount'], 0)

    def test_provider_active_company_authorization_tracks_grants(self):
        self.assertFalse(tts_auth.tts_provider_has_active_company_authorization(self.card_b))

        grant = self.grant(self.tenant, self.card_b)
        self.assertTrue(tts_auth.tts_provider_has_active_company_authorization(self.card_b))
        self.assertTrue(tts_auth.tts_voice_has_active_company_authorization(self.voice_b))

        grant.is_active = False
        grant.save(update_fields=['is_active'])
        self.assertFalse(tts_auth.tts_provider_has_active_company_authorization(self.card_b))

    def test_none_tenant_is_never_authorized(self):
        self.assertFalse(tts_auth.get_effective_tts_voices_for_tenant(None).exists())
        self.assertIsNone(tts_auth.get_effective_tts_voice_for_tenant(None))
        self.assertFalse(tts_auth.is_tts_voice_effective_for_tenant(None, self.voice_b))
