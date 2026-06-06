from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from urllib.parse import parse_qs

import websockets
from asgiref.sync import sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.devices.models import Device
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


async def asr_realtime_websocket_application(scope, receive, send):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    token = (params.get('token') or [''])[0].strip()

    connection = await sync_to_async(resolve_asr_realtime_connection, thread_sensitive=True)(
        token,
        headers=scope.get('headers') or [],
        query_params=params,
    )
    if connection is None:
        await send({'type': 'websocket.close', 'code': 4401})
        return

    await send({'type': 'websocket.accept'})

    config = await sync_to_async(get_effective_asr_config, thread_sensitive=True)()
    if not config.is_active or not is_asr_configured(config):
        await send({
            'type': 'websocket.send',
            'text': json.dumps({'type': 'asr.error', 'message': 'ASR 服务未就绪'}),
        })
        await send({'type': 'websocket.close', 'code': 4400})
        return

    replacement_pairs = await sync_to_async(load_asr_replacement_pairs, thread_sensitive=True)(
        connection.get('tenant_id'),
    )

    try:
        async with websockets.connect(
            build_asr_ws_url(config),
            additional_headers=[
                ('Authorization', f'Bearer {config.api_key}'),
                ('OpenAI-Beta', 'realtime=v1'),
                ('X-DashScope-WorkSpace', config.workspace_id),
            ],
            user_agent_header='solin-admin/1.0',
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 * 1024 * 1024,
        ) as upstream:
            await upstream.send(json.dumps(_session_update_event()))
            await send({'type': 'websocket.send', 'text': json.dumps({'type': 'asr.ready'})})

            browser_task = asyncio.create_task(_browser_to_upstream(receive, upstream))
            upstream_task = asyncio.create_task(_upstream_to_browser(upstream, send, replacement_pairs))
            done, pending = await asyncio.wait(
                {browser_task, upstream_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except Exception as exc:
        await send({
            'type': 'websocket.send',
            'text': json.dumps({'type': 'asr.error', 'message': str(exc)[:200]}),
        })
    finally:
        await send({'type': 'websocket.close', 'code': 1000})


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

    devices = list(
        Device.objects.select_related('tenant', 'application')
        .filter(code=device_code)
        .order_by('id')[:2]
    )
    if len(devices) != 1:
        return None

    device = devices[0]
    if device.tenant_id is None:
        return None
    if device.tenant is not None and not device.tenant.is_active:
        return None
    if not device.is_enabled or device.is_expired:
        return None

    return {
        'device_id': device.id,
        'device_code': device.code,
        'tenant_id': device.tenant_id,
        'application_id': device.application_id,
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

    return {
        'type': 'asr.transcript',
        'text': apply_asr_replacement_rules(text, pairs),
        'final': event_type in FINAL_EVENT_TYPES,
    }


async def _browser_to_upstream(receive, upstream) -> None:
    while True:
        event = await receive()
        event_type = event.get('type')
        if event_type == 'websocket.disconnect':
            try:
                await upstream.send(json.dumps(_session_finish_event()))
            except Exception:
                pass
            return

        if event_type != 'websocket.receive':
            continue

        if 'bytes' in event and event['bytes']:
            await upstream.send(json.dumps(_audio_append_event(event['bytes'])))
            continue

        text = event.get('text') or ''
        if text == 'ping':
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if payload.get('type') in {'asr.finish', 'session.finish'}:
            await upstream.send(json.dumps(_session_finish_event()))


async def _upstream_to_browser(upstream, send, replacement_pairs: list[tuple[str, str]]) -> None:
    async for raw_message in upstream:
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue

        transcript_payload = extract_transcript_payload(event, replacement_pairs=replacement_pairs)
        if transcript_payload is not None:
            await send({'type': 'websocket.send', 'text': json.dumps(transcript_payload)})
            continue

        if event.get('type') == 'session.finished':
            await send({'type': 'websocket.send', 'text': json.dumps({'type': 'asr.done'})})
            return


def _session_update_event() -> dict[str, Any]:
    return {
        'event_id': 'event_asr_test_session_update',
        'type': 'session.update',
        'session': {
            'input_audio_format': 'pcm',
            'sample_rate': 16000,
            'input_audio_transcription': {'language': 'zh'},
            'turn_detection': {
                'type': 'server_vad',
                'threshold': 0.0,
                'silence_duration_ms': 400,
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
    for key in ('text', 'delta', 'transcript', 'content'):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ''
