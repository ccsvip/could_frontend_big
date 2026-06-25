from __future__ import annotations

import base64
from typing import Any

import websockets
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.devices.services.runtime import get_runtime_device_or_none
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant

from .models import ASRReplacementRule
from .services.asr import build_asr_ws_url, get_effective_asr_config, is_asr_configured


TEXT_EVENT_TYPES = {
    'conversation.item.input_audio_transcription.text',
    'conversation.item.input_audio_transcription.delta',
}
FINAL_EVENT_TYPES = {
    'conversation.item.input_audio_transcription.completed',
    'conversation.item.input_audio_transcription.finished',
}


def resolve_asr_realtime_connection(
    token: str,
    *,
    headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...] = (),
    query_params: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    if not token:
        return resolve_asr_device_connection(_extract_device_code(headers, query_params))

    try:
        authentication = JWTAuthentication()
        validated_token = authentication.get_validated_token(token)
        user = authentication.get_user(validated_token)
    except Exception:
        return None

    if not user or not user.is_authenticated:
        return None
    if not user.is_superuser and 'ai_models.asr.view' not in get_active_permission_codes_for_user(user):
        return None

    connection = {'user_id': user.id}

    if user.is_superuser:
        tenant = _extract_superuser_tenant(query_params)
    else:
        tenant = get_user_tenant(user)
    if tenant is not None:
        connection['tenant_id'] = tenant.id
    return connection


def resolve_asr_device_connection(device_code: str) -> dict[str, Any] | None:
    if not device_code:
        return None

    device = get_runtime_device_or_none(device_code, require_tenant=True)
    if device is None:
        return None

    return {
        'device_id': device.id,
        'device_code': device.code,
        'tenant_id': device.tenant_id,
        'application_id': device.application_id,
        'agent_application_id': device.effective_agent_application.id if device.effective_agent_application else None,
    }


def _extract_device_code(
    headers: list[tuple[bytes, bytes]] | tuple[tuple[bytes, bytes], ...],
    query_params: dict[str, list[str]] | None,
) -> str:
    for key, value in headers:
        if key.decode('latin1').lower() == 'x-device-code':
            return value.decode('utf-8', errors='ignore').strip()

    params = query_params or {}
    for name in ('deviceCode', 'device_code'):
        value = (params.get(name) or [''])[0].strip()
        if value:
            return value
    return ''


def _extract_superuser_tenant(query_params: dict[str, list[str]] | None) -> Tenant | None:
    params = query_params or {}
    raw = (params.get('tenantId') or params.get('tenant') or [''])[0].strip()
    if not raw.isdigit():
        return None
    tenant_id = int(raw)
    if tenant_id <= 0:
        return None
    return Tenant.objects.filter(id=tenant_id, is_active=True).first()


def load_asr_replacement_pairs(tenant_id: int | None) -> list[tuple[str, str]]:
    if not tenant_id:
        return []
    return list(
        ASRReplacementRule.objects.filter(tenant_id=tenant_id, is_active=True)
        .order_by('id')
        .values_list('source_text', 'replacement_text')
    )


def apply_asr_replacement_rules(text: str, replacement_pairs: list[tuple[str, str]]) -> str:
    result = text
    for source_text, replacement_text in replacement_pairs:
        if source_text:
            result = result.replace(source_text, replacement_text)
    return result


def extract_transcript_payload(
    event: dict[str, Any],
    *,
    tenant_id: int | None = None,
    replacement_pairs: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    event_type = str(event.get('type') or '')
    if event_type not in TEXT_EVENT_TYPES and event_type not in FINAL_EVENT_TYPES:
        return None

    text = _extract_text(event)
    if not text:
        return None
    pairs = replacement_pairs if replacement_pairs is not None else load_asr_replacement_pairs(tenant_id)

    replaced_text = apply_asr_replacement_rules(text, pairs)
    return {
        'type': 'asr.transcript',
        'text': replaced_text,
        'originalText': text,
        'replacementApplied': replaced_text != text,
        'delta': event_type == 'conversation.item.input_audio_transcription.delta',
        'final': event_type in FINAL_EVENT_TYPES,
        'sourceEventType': event_type,
    }


def _session_update_event(*, vad_threshold: float = 0.0, vad_silence_duration_ms: int = 400) -> dict[str, Any]:
    return {
        'event_id': 'event_asr_test_session_update',
        'type': 'session.update',
        'session': {
            'input_audio_format': 'pcm',
            'sample_rate': 16000,
            'input_audio_transcription': {'language': 'zh'},
            'turn_detection': {
                'type': 'server_vad',
                'threshold': vad_threshold,
                'silence_duration_ms': vad_silence_duration_ms,
            },
        },
    }


def _session_finish_event() -> dict[str, str]:
    return {
        'event_id': 'event_asr_test_session_finish',
        'type': 'session.finish',
    }


def _audio_append_event(audio_bytes: bytes) -> dict[str, str]:
    return {
        'event_id': 'event_asr_test_audio_append',
        'type': 'input_audio_buffer.append',
        'audio': base64.b64encode(audio_bytes).decode('ascii'),
    }


def _extract_text(event: dict[str, Any]) -> str:
    text = event.get('text')
    stash = event.get('stash')
    if isinstance(text, str) or isinstance(stash, str):
        preview = f'{text if isinstance(text, str) else ""}{stash if isinstance(stash, str) else ""}'.strip()
        if preview:
            return preview

    for key in ('text', 'delta', 'transcript', 'content'):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ''
