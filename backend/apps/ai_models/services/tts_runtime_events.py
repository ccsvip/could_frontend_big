"""Publish full runtime-config refresh events after TTS authorization changes.

Card grants, per-card public config and company default voice all change a
device's effective TTS voice or parameters *without* touching the ``Device`` row,
so nothing else would notify an online device. These helpers publish the existing
tenant-level ``device.voice_configuration.changed`` event so subscribers of
``device.runtime_config.subscribe`` rebuild their complete config.

Deliberately reuses the established event shape and the single ``/ws/realtime/``
entry point — no new WebSocket URL, and no incremental voice-only payload.
"""
from __future__ import annotations

from django.db import transaction

from apps.devices.realtime import publish_device_event_sync


VOICE_CONFIGURATION_CHANGED = 'device.voice_configuration.changed'
VOICE_CONFIGURATION_REASON = 'voiceConfigurationChanged'


def publish_tenant_tts_config_changed(tenant_id) -> None:
    """Queue a tenant-wide runtime config refresh for after the current commit."""
    if tenant_id is None:
        return
    payload = {
        'type': VOICE_CONFIGURATION_CHANGED,
        'tenantId': tenant_id,
        'refresh': {
            'endpoint': '/api/v1/device-runtime/config/',
            'reason': VOICE_CONFIGURATION_REASON,
        },
    }
    transaction.on_commit(lambda: publish_device_event_sync(payload))


def publish_tts_provider_authorization_changed(provider) -> None:
    """Refresh every tenant that currently holds an active grant on this card.

    Used when the platform toggles or hides a provider/voice: the tenants that can
    see it are exactly the ones whose runtime config may now resolve differently.
    """
    from apps.ai_models.models import TenantTTSProviderGrant

    if provider is None:
        return
    tenant_ids = (
        TenantTTSProviderGrant.objects
        .filter(provider=provider, is_active=True)
        .values_list('tenant_id', flat=True)
        .distinct()
    )
    for tenant_id in list(tenant_ids):
        publish_tenant_tts_config_changed(tenant_id)


def publish_tts_voice_authorization_changed(voice) -> None:
    if voice is None:
        return
    publish_tts_provider_authorization_changed(getattr(voice, 'provider', None))
