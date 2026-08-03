from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.ai_models.models import (
    TenantTTSProviderGrant,
    TenantTTSSettings,
    TenantTTSVoiceGrant,
    TTSProvider,
    TTSVoice,
)
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


class VoiceLevelGrantTests(TestCase):
    """Voice-level narrowing (``grant_mode``) and per-company voice ownership.

    Cards carry two voices each so a ``selected`` grant can be observed to keep
    one and drop the other instead of collapsing to "all or nothing".
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name='甲公司', code='voice-grant-a')
        self.other_tenant = Tenant.objects.create(name='乙公司', code='voice-grant-b')

        self.card_a = TTSProvider.objects.create(code='vg-card-a', name='卡片 A')
        self.a1 = TTSVoice.objects.create(provider=self.card_a, display_name='A1', voice_code='vg-a1', sort_order=1)
        self.a2 = TTSVoice.objects.create(provider=self.card_a, display_name='A2', voice_code='vg-a2', sort_order=2)

        self.card_b = TTSProvider.objects.create(code='vg-card-b', name='卡片 B')
        self.b1 = TTSVoice.objects.create(provider=self.card_b, display_name='B1', voice_code='vg-b1', sort_order=1)
        self.b2 = TTSVoice.objects.create(provider=self.card_b, display_name='B2', voice_code='vg-b2', sort_order=2)

    def grant(self, tenant, provider, *, grant_mode=TenantTTSProviderGrant.GRANT_MODE_ALL, is_active=True):
        return TenantTTSProviderGrant.objects.create(
            tenant=tenant,
            provider=provider,
            is_active=is_active,
            grant_mode=grant_mode,
        )

    def grant_voice(self, tenant, voice, *, is_active=True):
        return TenantTTSVoiceGrant.objects.create(tenant=tenant, voice=voice, is_active=is_active)

    def effective_ids(self, tenant, **kwargs):
        return set(tts_auth.get_effective_tts_voices_for_tenant(tenant, **kwargs).values_list('id', flat=True))

    def test_all_mode_matches_pre_change_card_level_behaviour(self):
        self.grant(self.tenant, self.card_a)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.a2.id})

    def test_all_mode_ignores_voice_grants(self):
        """A leftover checkbox must not narrow a card that is back on ``all``."""
        self.grant(self.tenant, self.card_a)
        self.grant_voice(self.tenant, self.a1)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.a2.id})

    def test_selected_mode_returns_only_granted_voices(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id})

    def test_selected_mode_without_any_voice_grant_is_empty(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)

        self.assertEqual(self.effective_ids(self.tenant), set())

    def test_inactive_voice_grant_is_not_effective(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1, is_active=False)

        self.assertEqual(self.effective_ids(self.tenant), set())

    def test_card_switch_beats_voice_grant(self):
        """Card-level ``is_active=False`` wins over any voice checkbox."""
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED, is_active=False)
        self.grant_voice(self.tenant, self.a1)

        self.assertEqual(self.effective_ids(self.tenant), set())

    def test_other_tenants_voice_grant_does_not_leak(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.other_tenant, self.a1)

        self.assertEqual(self.effective_ids(self.tenant), set())

    def test_another_tenants_all_grant_does_not_widen_our_selected_card(self):
        """The classic split-``.filter()`` leak.

        ``(tenant, provider)`` is unique, so our own rows can never supply both
        "active for us" and "mode is all" for the same card. Another company's
        ``all`` grant on the same card can — but only if ``grant_mode`` is matched
        on a second, tenant-unconstrained join. Keeping every card condition in
        one ``.filter()`` call is what makes this assertion hold.
        """
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)
        self.grant(self.other_tenant, self.card_a)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id})
        self.assertEqual(self.effective_ids(self.other_tenant), {self.a1.id, self.a2.id})

    def test_all_card_and_selected_card_do_not_interfere(self):
        """A card on ``all`` must stay whole while a sibling card is narrowed.

        Both ``grant_mode`` and the card-grant conditions have to sit in one
        ``.filter()`` call; splitting them degrades to "some grant row is active"
        plus "some grant row is all", which would wrongly widen card B here.
        """
        self.grant(self.tenant, self.card_a)
        self.grant(self.tenant, self.card_b, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.b1)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.a2.id, self.b1.id})

    def test_selected_card_and_all_card_do_not_interfere_when_order_is_swapped(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)
        self.grant(self.tenant, self.card_b)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.b1.id, self.b2.id})

    def test_result_has_no_duplicate_rows(self):
        """Reverse joins multiply rows; ``.distinct()`` must survive the change."""
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)
        self.grant_voice(self.tenant, self.a2)

        ids = list(tts_auth.get_effective_tts_voices_for_tenant(self.tenant).values_list('id', flat=True))

        self.assertEqual(len(ids), 2)
        self.assertEqual(len(ids), len(set(ids)))

    def test_new_platform_voice_is_not_auto_granted_in_selected_mode(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)
        added = TTSVoice.objects.create(provider=self.card_a, display_name='新增', voice_code='vg-a3')

        self.assertNotIn(added.id, self.effective_ids(self.tenant))

    def test_new_platform_voice_is_auto_granted_in_all_mode(self):
        self.grant(self.tenant, self.card_a)
        added = TTSVoice.objects.create(provider=self.card_a, display_name='新增', voice_code='vg-a4')

        self.assertIn(added.id, self.effective_ids(self.tenant))

    def test_owned_voice_is_visible_only_to_its_owner(self):
        self.grant(self.tenant, self.card_a)
        self.grant(self.other_tenant, self.card_a)
        self.a2.owner_tenant = self.tenant
        self.a2.save(update_fields=['owner_tenant'])

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.a2.id})
        self.assertEqual(self.effective_ids(self.other_tenant), {self.a1.id})

    def test_public_voice_stays_visible_to_every_granted_tenant(self):
        self.grant(self.tenant, self.card_a)
        self.grant(self.other_tenant, self.card_a)

        self.assertEqual(self.effective_ids(self.tenant), {self.a1.id, self.a2.id})
        self.assertEqual(self.effective_ids(self.other_tenant), {self.a1.id, self.a2.id})

    def test_owned_voice_needs_both_ownership_and_voice_grant_in_selected_mode(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.a2.owner_tenant = self.tenant
        self.a2.save(update_fields=['owner_tenant'])

        self.assertEqual(self.effective_ids(self.tenant), set())

        self.grant_voice(self.tenant, self.a2)
        self.assertEqual(self.effective_ids(self.tenant), {self.a2.id})

    def test_ensure_authorized_rejects_voice_excluded_by_selected_mode(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)

        with self.assertRaises(ValidationError):
            tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, self.a2.id)

    def test_ensure_authorized_rejects_another_companys_private_voice(self):
        self.grant(self.tenant, self.card_a)
        self.a2.owner_tenant = self.other_tenant
        self.a2.save(update_fields=['owner_tenant'])

        with self.assertRaises(ValidationError):
            tts_auth.ensure_tts_voice_authorized_for_tenant(self.tenant, self.a2.id)

    def test_default_voice_falls_back_inside_selected_scope(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a2)
        TenantTTSSettings.objects.create(tenant=self.tenant, default_voice=self.a1)

        self.assertEqual(tts_auth.get_effective_tts_voice_for_tenant(self.tenant), self.a2)

    def test_voice_grant_ids_reports_active_selection_per_card(self):
        self.grant(self.tenant, self.card_a, grant_mode=TenantTTSProviderGrant.GRANT_MODE_SELECTED)
        self.grant_voice(self.tenant, self.a1)
        self.grant_voice(self.tenant, self.a2, is_active=False)
        self.grant_voice(self.tenant, self.b1)
        self.grant_voice(self.other_tenant, self.a2)

        self.assertEqual(tts_auth.tts_voice_grant_ids_for_tenant(self.tenant, self.card_a), {self.a1.id})
        self.assertEqual(tts_auth.tts_voice_grant_ids_for_tenant(self.tenant, self.card_b), {self.b1.id})

    def test_voice_grant_ids_is_empty_for_missing_arguments(self):
        self.assertEqual(tts_auth.tts_voice_grant_ids_for_tenant(None, self.card_a), set())
        self.assertEqual(tts_auth.tts_voice_grant_ids_for_tenant(self.tenant, None), set())
