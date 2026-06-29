from __future__ import annotations

import asyncio
import base64
import json
from typing import Any, AsyncIterable

import websockets
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant

from .models import TTSProvider, TTSVoice
from .services.tts import (
    build_tts_ws_url,
    get_aliyun_tts_provider,
    get_default_tts_voice,
    get_effective_tts_config,
    get_effective_tts_voice_for_tenant,
    is_tts_voice_supported_by_model_code,
    is_tts_configured,
    normalize_tts_text,
    split_tts_text,
    _session_finish_event,
    _session_update_event,
    _text_append_event,
    _text_commit_event,
)


def resolve_tts_realtime_connection(token: str, *, query_params: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
    device_connection = _resolve_device_connection(query_params)
    if device_connection is not None:
        return device_connection

    if not token:
        return None

    try:
        authentication = JWTAuthentication()
        validated_token = authentication.get_validated_token(token)
        user = authentication.get_user(validated_token)
    except Exception:
        return None

    if not user or not user.is_authenticated:
        return None

    connection = {'user_id': user.id, 'is_superuser': user.is_superuser}
    if user.is_superuser:
        tenant = _extract_superuser_tenant(query_params)
    else:
        if 'ai_models.tts.view' not in get_active_permission_codes_for_user(user):
            return None
        tenant = get_user_tenant(user)
    if tenant is not None:
        connection['tenant_id'] = tenant.id
    return connection


def _resolve_device_connection(query_params: dict[str, list[str]] | None) -> dict[str, Any] | None:
    params = query_params or {}
    device_code = (params.get('deviceCode') or params.get('device_code') or [''])[0].strip()
    if not device_code:
        return None
    try:
        device = get_runtime_device(device_code)
    except RuntimeDeviceError:
        return None
    return {
        'device_id': device.id,
        'device_code': device.code,
        'tenant_id': device.tenant_id,
        'is_superuser': False,
    }


def resolve_tts_voice(
    connection: dict[str, Any],
    raw_voice_id,
    provider: TTSProvider,
    *,
    model_code: str | None = None,
) -> TTSVoice | None:
    voice_id = _parse_positive_int(raw_voice_id)
    if voice_id is not None:
        voice = TTSVoice.objects.select_related('provider').filter(id=voice_id, provider=provider).first()
        if (
            voice is not None
            and voice.is_active
            and (connection.get('is_superuser') or voice.is_visible)
            and (model_code is None or is_tts_voice_supported_by_model_code(voice, model_code))
        ):
            return voice
        return None

    if connection.get('tenant_id'):
        tenant = Tenant.objects.filter(id=connection['tenant_id'], is_active=True).first()
        return get_effective_tts_voice_for_tenant(tenant, provider, model_code=model_code)
    return get_default_tts_voice(provider, model_code=model_code)


def resolve_tts_provider(raw_provider_code) -> TTSProvider:
    provider_code = str(raw_provider_code or '').strip()
    if not provider_code:
        return get_aliyun_tts_provider()
    return TTSProvider.objects.filter(code=provider_code).first() or get_aliyun_tts_provider()


async def _stream_tts_audio(*, text: str, voice: TTSVoice, config, send, session_config: dict | None = None) -> None:
    session_event = _session_update_event(config, voice, session_config)
    tts_session = session_event['session']
    async with websockets.connect(
        build_tts_ws_url(config, tts_session.get('model')),
        additional_headers=[
            ('Authorization', f'Bearer {config.api_key}'),
            ('OpenAI-Beta', 'realtime=v1'),
        ],
        user_agent_header='solin-admin/1.0',
        open_timeout=10,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ) as upstream:
        await upstream.send(json.dumps({
            'event_id': 'event_tts_session_update',
            'type': 'session.update',
            'session': tts_session,
        }))
        await send({
            'type': 'websocket.send',
            'text': json.dumps({
                'type': 'tts.ready',
                'sampleRate': tts_session.get('sample_rate') or config.sample_rate,
                'responseFormat': tts_session.get('response_format') or 'pcm',
                'voice': voice.voice_code,
            }),
        })
        for chunk in split_tts_text(text):
            await upstream.send(json.dumps(_text_append_event(chunk)))
            await asyncio.sleep(0)
        await upstream.send(json.dumps(_text_commit_event()))
        await upstream.send(json.dumps(_session_finish_event()))

        async for raw_message in upstream:
            try:
                event = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(event, dict):
                continue

            event_type = str(event.get('type') or '')
            if event_type == 'response.audio.delta':
                delta = event.get('delta')
                if isinstance(delta, str) and delta:
                    await send({'type': 'websocket.send', 'bytes': base64.b64decode(delta)})
                continue
            if event_type in {'error', 'session.error'}:
                raise RuntimeError(_extract_upstream_error_message(event))
            if event_type == 'session.finished':
                await send({'type': 'websocket.send', 'text': json.dumps({'type': 'tts.done'})})
                return


async def _stream_tts_segments_audio(*, segments: AsyncIterable[str], voice: TTSVoice, config, send, session_config: dict | None = None) -> None:
    session_event = _session_update_event(config, voice, session_config)
    tts_session = session_event['session']
    async with websockets.connect(
        build_tts_ws_url(config, tts_session.get('model')),
        additional_headers=[
            ('Authorization', f'Bearer {config.api_key}'),
            ('OpenAI-Beta', 'realtime=v1'),
        ],
        user_agent_header='solin-admin/1.0',
        open_timeout=10,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ) as upstream:
        await upstream.send(json.dumps({
            'event_id': 'event_tts_session_update',
            'type': 'session.update',
            'session': tts_session,
        }))
        await send({
            'type': 'websocket.send',
            'text': json.dumps({
                'type': 'tts.ready',
                'sampleRate': tts_session.get('sample_rate') or config.sample_rate,
                'responseFormat': tts_session.get('response_format') or 'pcm',
                'voice': voice.voice_code,
            }),
        })

        reader_task = asyncio.create_task(_forward_tts_upstream_audio(upstream, send))
        try:
            async for segment in segments:
                text = normalize_tts_text(segment, config)
                if not text:
                    continue
                for chunk in split_tts_text(text):
                    await upstream.send(json.dumps(_text_append_event(chunk)))
                    await asyncio.sleep(0)
                await upstream.send(json.dumps(_text_commit_event()))
                await asyncio.sleep(0)

            await upstream.send(json.dumps(_session_finish_event()))
            await reader_task
        except asyncio.CancelledError:
            reader_task.cancel()
            await asyncio.gather(reader_task, return_exceptions=True)
            raise
        except Exception:
            reader_task.cancel()
            await asyncio.gather(reader_task, return_exceptions=True)
            raise


async def _forward_tts_upstream_audio(upstream, send) -> None:
    async for raw_message in upstream:
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue

        event_type = str(event.get('type') or '')
        if event_type == 'response.audio.delta':
            delta = event.get('delta')
            if isinstance(delta, str) and delta:
                await send({'type': 'websocket.send', 'bytes': base64.b64decode(delta)})
            continue
        if event_type in {'error', 'session.error'}:
            raise RuntimeError(_extract_upstream_error_message(event))
        if event_type == 'session.finished':
            await send({'type': 'websocket.send', 'text': json.dumps({'type': 'tts.done'})})
            return


def _extract_upstream_error_message(event: dict[str, Any]) -> str:
    error = event.get('error')
    if isinstance(error, dict):
        message = error.get('message') or error.get('code') or error.get('type')
        if message:
            return str(message)[:200]
    message = event.get('message') or error or 'TTS upstream error'
    return str(message)[:200]


def _extract_superuser_tenant(query_params: dict[str, list[str]] | None) -> Tenant | None:
    params = query_params or {}
    raw = (params.get('tenantId') or params.get('tenant') or [''])[0].strip()
    tenant_id = _parse_positive_int(raw)
    if tenant_id is None:
        return None
    return Tenant.objects.filter(id=tenant_id, is_active=True).first()


def _parse_positive_int(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw.isdigit():
        return None
    parsed = int(raw)
    return parsed if parsed > 0 else None
