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
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant

from .models import TTSProvider, TTSVoice
from .services.tts import (
    build_tts_ws_url,
    get_aliyun_tts_provider,
    get_default_tts_voice,
    get_effective_tts_config,
    get_effective_tts_voice_for_tenant,
    is_tts_configured,
    normalize_tts_text,
    split_tts_text,
    _session_finish_event,
    _session_update_event,
    _text_append_event,
    _text_commit_event,
)


async def tts_realtime_websocket_application(scope, receive, send):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    token = (params.get('token') or [''])[0].strip()
    connection = await sync_to_async(resolve_tts_realtime_connection, thread_sensitive=True)(
        token,
        query_params=params,
    )
    if connection is None:
        await send({'type': 'websocket.close', 'code': 4401})
        return

    await send({'type': 'websocket.accept'})

    start_payload = await _receive_start_payload(receive)
    if start_payload is None:
        await send({'type': 'websocket.close', 'code': 1000})
        return

    try:
        provider = await sync_to_async(resolve_tts_provider, thread_sensitive=True)(start_payload.get('providerCode'))
        config = await sync_to_async(get_effective_tts_config, thread_sensitive=True)(provider)
        if not is_tts_configured(config):
            raise RuntimeError('TTS 服务未配置或未启用')

        voice = await sync_to_async(resolve_tts_voice, thread_sensitive=True)(connection, start_payload.get('voiceId'), provider)
        if voice is None:
            raise RuntimeError('TTS 音色未配置')

        text = normalize_tts_text(str(start_payload.get('text') or ''), config)
        await _stream_tts_audio(text=text, voice=voice, config=config, send=send)
    except Exception as exc:
        await send({
            'type': 'websocket.send',
            'text': json.dumps({'type': 'tts.error', 'message': str(exc)[:200]}),
        })
    finally:
        await send({'type': 'websocket.close', 'code': 1000})


def resolve_tts_realtime_connection(token: str, *, query_params: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
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
    if not user.is_superuser and 'ai_models.tts.view' not in get_active_permission_codes_for_user(user):
        return None

    connection = {'user_id': user.id, 'is_superuser': user.is_superuser}
    if user.is_superuser:
        tenant = _extract_superuser_tenant(query_params)
    else:
        tenant = get_user_tenant(user)
    if tenant is not None:
        connection['tenant_id'] = tenant.id
    return connection


def resolve_tts_voice(connection: dict[str, Any], raw_voice_id, provider: TTSProvider) -> TTSVoice | None:
    voice_id = _parse_positive_int(raw_voice_id)
    if voice_id is not None:
        voice = TTSVoice.objects.select_related('provider').filter(id=voice_id, provider=provider).first()
        if voice is not None and voice.is_active and (connection.get('is_superuser') or voice.is_visible):
            return voice

    if connection.get('tenant_id'):
        tenant = Tenant.objects.filter(id=connection['tenant_id'], is_active=True).first()
        return get_effective_tts_voice_for_tenant(tenant, provider)
    return get_default_tts_voice(provider)


def resolve_tts_provider(raw_provider_code) -> TTSProvider:
    provider_code = str(raw_provider_code or '').strip()
    if not provider_code:
        return get_aliyun_tts_provider()
    return TTSProvider.objects.filter(code=provider_code).first() or get_aliyun_tts_provider()


async def _receive_start_payload(receive) -> dict[str, Any] | None:
    while True:
        event = await receive()
        event_type = event.get('type')
        if event_type == 'websocket.disconnect':
            return None
        if event_type != 'websocket.receive':
            continue
        text = event.get('text') or ''
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if payload.get('type') == 'tts.start':
            return payload


async def _stream_tts_audio(*, text: str, voice: TTSVoice, config, send) -> None:
    await send({
        'type': 'websocket.send',
        'text': json.dumps({'type': 'tts.ready', 'sampleRate': config.sample_rate, 'voice': voice.voice_code}),
    })
    async with websockets.connect(
        build_tts_ws_url(config),
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
        await upstream.send(json.dumps(_session_update_event(config, voice)))
        for chunk in split_tts_text(text):
            await upstream.send(json.dumps(_text_append_event(chunk)))
            await asyncio.sleep(0.05)
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
                message = event.get('message') or event.get('error') or 'TTS upstream error'
                raise RuntimeError(str(message)[:200])
            if event_type == 'session.finished':
                await send({'type': 'websocket.send', 'text': json.dumps({'type': 'tts.done'})})
                return


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
