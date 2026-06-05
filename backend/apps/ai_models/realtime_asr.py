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

    connection = await sync_to_async(resolve_asr_realtime_connection, thread_sensitive=True)(token)
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
            upstream_task = asyncio.create_task(_upstream_to_browser(upstream, send))
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


def resolve_asr_realtime_connection(token: str) -> dict[str, int] | None:
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
    if not user.is_superuser and 'ai_models.asr.view' not in get_active_permission_codes_for_user(user):
        return None
    return {'user_id': user.id}


def extract_transcript_payload(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(event.get('type') or '')
    if event_type not in TEXT_EVENT_TYPES and event_type not in FINAL_EVENT_TYPES:
        return None

    text = _extract_text(event)
    if not text:
        return None

    return {
        'type': 'asr.transcript',
        'text': text,
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


async def _upstream_to_browser(upstream, send) -> None:
    async for raw_message in upstream:
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue

        transcript_payload = extract_transcript_payload(event)
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
