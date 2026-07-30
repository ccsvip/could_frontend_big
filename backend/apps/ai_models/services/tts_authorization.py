"""Tenant-scoped TTS authorization.

This module is the only sanctioned entry point for answering "which TTS voices may
this company use?". Company options, default-voice saves, previews, device
binding, device applications, HTTP runtime TTS and the unified realtime WebSocket
must all resolve voices through here instead of querying ``TTSVoice.objects``
with a client-supplied ``voiceId``.

Effective voices are derived, never stored: a voice is effective for a tenant
when the tenant holds an active grant on the voice's card (``TTSProvider``), the
card is active, and the voice itself is active and visible.
"""
from __future__ import annotations

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.ai_models.models import TenantTTSProviderGrant, TTSProvider, TTSVoice

from .tts import get_tts_model_profile_voice_codes


ALIYUN_PROVIDER_CODE = 'aliyun'


def get_effective_tts_voices_for_tenant(tenant, *, provider_code: str | None = None, model_code: str | None = None):
    """Return the tenant's authorized voices, ordered by card then voice order."""
    if tenant is None:
        return TTSVoice.objects.none()
    queryset = (
        TTSVoice.objects
        .select_related('provider')
        .filter(
            is_active=True,
            is_visible=True,
            provider__is_active=True,
            provider__tenant_grants__tenant=tenant,
            provider__tenant_grants__is_active=True,
        )
    )
    if provider_code:
        queryset = queryset.filter(provider__code=provider_code)
    queryset = _apply_model_code_filter(queryset, model_code)
    return queryset.order_by('provider__id', 'sort_order', 'id').distinct()


def _apply_model_code_filter(queryset, model_code: str | None):
    """Restrict Qwen/Aliyun voices to the profile's voice codes.

    ``model_code`` is an Aliyun/Qwen playback-profile concept. Other cards do not
    share Qwen's voice-code vocabulary, so filtering them by it would wrongly
    drop every one of their voices.
    """
    if not model_code:
        return queryset
    return queryset.filter(
        ~Q(provider__code=ALIYUN_PROVIDER_CODE)
        | Q(voice_code__in=get_tts_model_profile_voice_codes(model_code)),
    )


def get_effective_tts_voice_for_tenant(tenant, *, provider_code: str | None = None, model_code: str | None = None) -> TTSVoice | None:
    """Resolve the tenant's default voice, falling back inside its authorization.

    Priority: the tenant's configured default when it is still authorized, then
    the first authorized voice. Never falls back to an unauthorized platform
    default.
    """
    if tenant is None:
        return None
    authorized = get_effective_tts_voices_for_tenant(tenant, provider_code=provider_code, model_code=model_code)
    settings_obj = _tenant_tts_settings(tenant)
    default_voice_id = getattr(settings_obj, 'default_voice_id', None)
    if default_voice_id:
        default_voice = authorized.filter(id=default_voice_id).first()
        if default_voice is not None:
            return default_voice
    return authorized.first()


def is_tts_voice_effective_for_tenant(tenant, voice, *, model_code: str | None = None) -> bool:
    if tenant is None or voice is None:
        return False
    return get_effective_tts_voices_for_tenant(tenant, model_code=model_code).filter(id=voice.id).exists()


def ensure_tts_voice_authorized_for_tenant(
    tenant,
    raw_voice_id,
    *,
    provider_code: str | None = None,
    model_code: str | None = None,
    field: str = 'voiceId',
) -> TTSVoice:
    """Return the voice for ``raw_voice_id`` or raise 400.

    Unauthorized, unknown, hidden, disabled and cross-tenant ids are reported
    with the same message so a company cannot probe another company's voice ids.
    """
    voice_id = _parse_positive_int(raw_voice_id)
    if voice_id is None:
        raise ValidationError({field: '音色不能为空'})
    voice = get_effective_tts_voices_for_tenant(
        tenant,
        provider_code=provider_code,
        model_code=model_code,
    ).filter(id=voice_id).first()
    if voice is None:
        raise ValidationError({field: '所选音色未授权或已停用'})
    return voice


def resolve_tenant_tts_voice(
    tenant,
    raw_voice_id=None,
    *,
    provider_code: str | None = None,
    model_code: str | None = None,
    allow_fallback: bool = True,
) -> TTSVoice | None:
    """Resolve an explicit voice id, else the tenant's effective default.

    An explicit id is always authorization-checked and never silently swapped for
    a different voice.
    """
    if raw_voice_id not in (None, ''):
        return ensure_tts_voice_authorized_for_tenant(
            tenant,
            raw_voice_id,
            provider_code=provider_code,
            model_code=model_code,
        )
    if not allow_fallback:
        return None
    return get_effective_tts_voice_for_tenant(tenant, provider_code=provider_code, model_code=model_code)


def get_tenant_tts_provider_grant(tenant, provider) -> TenantTTSProviderGrant | None:
    if tenant is None or provider is None:
        return None
    return TenantTTSProviderGrant.objects.filter(tenant=tenant, provider=provider).first()


def resolve_device_tts_voice(device, raw_voice_id=None, *, model_code: str | None = None) -> TTSVoice | None:
    """Resolve the voice a device should actually speak with.

    Priority (unchanged from before, but now authorization-bounded):
    an explicit request id, then the device's own binding while it is still
    authorized, then the company default, then the first authorized voice.
    A binding whose card lost its grant is treated as invalid rather than
    silently honoured.
    """
    if device is None:
        return None
    tenant = getattr(device, 'tenant', None)
    if raw_voice_id not in (None, ''):
        return ensure_tts_voice_authorized_for_tenant(tenant, raw_voice_id, model_code=model_code)

    device_voice = getattr(device, 'tts_voice', None)
    if device_voice is not None and is_tts_voice_effective_for_tenant(tenant, device_voice, model_code=model_code):
        return device_voice

    return get_effective_tts_voice_for_tenant(tenant, model_code=model_code)


def get_tenant_tts_card_public_config(tenant, provider) -> dict:
    """Return the tenant's public config for one card.

    Each card keeps its own config so saving CosyVoice controls cannot overwrite
    Qwen's ``model_code`` / ``instructions`` and vice versa.
    """
    grant = get_tenant_tts_provider_grant(tenant, provider)
    config = getattr(grant, 'public_config', None)
    return dict(config) if isinstance(config, dict) else {}


def tts_provider_usage_for_tenant(tenant, provider) -> dict:
    """Count references that would break if this card's grant were disabled."""
    from apps.devices.models import Device, DeviceApplication

    if tenant is None or provider is None:
        return {'tenantDefault': False, 'deviceCount': 0, 'deviceApplicationCount': 0}

    settings_obj = _tenant_tts_settings(tenant)
    default_voice = getattr(settings_obj, 'default_voice', None)
    return {
        'tenantDefault': bool(default_voice is not None and default_voice.provider_id == provider.id),
        'deviceCount': Device.objects.filter(tenant=tenant, tts_voice__provider=provider).count(),
        'deviceApplicationCount': (
            DeviceApplication.objects
            .filter(tenant=tenant, tts_voices__provider=provider)
            .distinct()
            .count()
        ),
    }


def tts_voice_usage_for_tenant(tenant, voice) -> dict:
    from apps.devices.models import Device, DeviceApplication

    if tenant is None or voice is None:
        return {'tenantDefault': False, 'deviceCount': 0, 'deviceApplicationCount': 0}

    settings_obj = _tenant_tts_settings(tenant)
    return {
        'tenantDefault': bool(getattr(settings_obj, 'default_voice_id', None) == voice.id),
        'deviceCount': Device.objects.filter(tenant=tenant, tts_voice=voice).count(),
        'deviceApplicationCount': (
            DeviceApplication.objects
            .filter(tenant=tenant, tts_voices=voice)
            .distinct()
            .count()
        ),
    }


def tts_provider_grant_is_in_use(tenant, provider) -> bool:
    usage = tts_provider_usage_for_tenant(tenant, provider)
    return bool(usage['tenantDefault'] or usage['deviceCount'] or usage['deviceApplicationCount'])


def tts_provider_has_active_company_authorization(provider) -> bool:
    """True when any company still holds an active grant on this card."""
    if provider is None:
        return False
    return TenantTTSProviderGrant.objects.filter(provider=provider, is_active=True).exists()


def tts_voice_has_active_company_authorization(voice) -> bool:
    if voice is None:
        return False
    return TenantTTSProviderGrant.objects.filter(provider_id=voice.provider_id, is_active=True).exists()


def grantable_tts_providers():
    return TTSProvider.objects.prefetch_related('voices').order_by('id')


def _tenant_tts_settings(tenant):
    from .tts import get_tenant_tts_settings

    return get_tenant_tts_settings(tenant)


def _parse_positive_int(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw.isdigit():
        return None
    parsed = int(raw)
    return parsed if parsed > 0 else None
