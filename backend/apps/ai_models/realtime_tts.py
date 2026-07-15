from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, AsyncIterable

import websockets
from django.conf import settings
from websockets.exceptions import ConnectionClosed
from apps.accounts.authentication import TenantAwareJWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.devices.models import Device
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

logger = logging.getLogger(__name__)


def resolve_tts_realtime_connection(token: str, *, query_params: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
    device_connection = _resolve_device_connection(query_params)
    if device_connection is not None:
        return device_connection

    if not token:
        return None

    try:
        authentication = TenantAwareJWTAuthentication()
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

    device_id = connection.get('device_id')
    if device_id:
        device = Device.objects.select_related('tts_voice__provider').filter(id=device_id).first()
        device_voice = getattr(device, 'tts_voice', None)
        if device_voice is not None:
            if (
                device_voice.provider_id == provider.id
                and device_voice.is_active
                and device_voice.is_visible
                and device_voice.provider.is_active
                and (model_code is None or is_tts_voice_supported_by_model_code(device_voice, model_code))
            ):
                return device_voice
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


def _optional_positive_seconds(value) -> float | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def _tts_ws_connect_options() -> dict[str, Any]:
    return {
        'open_timeout': _optional_positive_seconds(getattr(settings, 'TTS_REALTIME_WS_OPEN_TIMEOUT_SECONDS', 10)) or 10,
        'ping_interval': _optional_positive_seconds(getattr(settings, 'TTS_REALTIME_WS_PING_INTERVAL_SECONDS', 20)),
        'ping_timeout': _optional_positive_seconds(getattr(settings, 'TTS_REALTIME_WS_PING_TIMEOUT_SECONDS', 60)),
        'close_timeout': _optional_positive_seconds(getattr(settings, 'TTS_REALTIME_WS_CLOSE_TIMEOUT_SECONDS', 10)) or 10,
        'max_size': int(getattr(settings, 'TTS_REALTIME_WS_MAX_SIZE_BYTES', 8 * 1024 * 1024)),
    }


async def _stream_tts_audio(
    *,
    text: str,
    voice: TTSVoice,
    config,
    send,
    session_config: dict | None = None,
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> None:
    stats = _new_tts_stream_stats('single')
    session_event = _session_update_event(config, voice, session_config)
    tts_session = session_event['session']
    ws_url = build_tts_ws_url(config, tts_session.get('model'))
    connect_options = _tts_ws_connect_options()
    logger.info(
        'tts.realtime.connecting mode=single model=%s voice=%s sample_rate=%s text_chars=%s options=%s',
        tts_session.get('model'),
        voice.voice_code,
        tts_session.get('sample_rate') or config.sample_rate,
        len(text or ''),
        connect_options,
    )
    try:
        async with websockets.connect(
            ws_url,
            additional_headers=[
                ('Authorization', f'Bearer {config.api_key}'),
                ('OpenAI-Beta', 'realtime=v1'),
            ],
            user_agent_header='solin-admin/1.0',
            **connect_options,
        ) as upstream:
            logger.info('tts.realtime.connected %s', _tts_stats_summary(stats))
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
            chunks = split_tts_text(text, exclude_patterns=exclude_patterns)
            stats['segments'] = 1 if text else 0
            stats['chunks'] = len(chunks)
            stats['text_chars'] = len(text or '')
            logger.info('tts.realtime.text_prepared mode=single chunks=%s text_chars=%s %s', len(chunks), len(text or ''), _tts_stats_summary(stats))
            for chunk in chunks:
                await upstream.send(json.dumps(_text_append_event(chunk)))
                await asyncio.sleep(0)
            await upstream.send(json.dumps(_text_commit_event()))
            await upstream.send(json.dumps(_session_finish_event()))

            active_segment_index = 1 if text else None
            active_segment_started = False

            async for raw_message in upstream:
                try:
                    event = json.loads(raw_message)
                except (TypeError, json.JSONDecodeError):
                    logger.warning('tts.realtime.invalid_event raw_type=%s %s', type(raw_message).__name__, _tts_stats_summary(stats))
                    continue
                if not isinstance(event, dict):
                    continue

                event_type = str(event.get('type') or '')
                _record_tts_event(stats, event_type)
                if event_type == 'response.audio.delta':
                    delta = event.get('delta')
                    if isinstance(delta, str) and delta:
                        if active_segment_index is not None and not active_segment_started:
                            await _send_tts_segment_start(send, active_segment_index, text)
                            active_segment_started = True
                        audio = base64.b64decode(delta)
                        _record_tts_audio(stats, len(audio))
                        await send({'type': 'websocket.send', 'bytes': audio})
                    continue
                if event_type in {'error', 'session.error'}:
                    logger.error('tts.realtime.upstream_error error=%s event=%s %s', _extract_upstream_error_message(event), _safe_tts_event(event), _tts_stats_summary(stats))
                    raise RuntimeError(_extract_upstream_error_message(event))
                if event_type in {'response.audio.done', 'response.output_audio.done', 'response.done'}:
                    if active_segment_index is not None and active_segment_started:
                        await _send_tts_segment_end(send, active_segment_index)
                        active_segment_index = None
                    logger.info('tts.realtime.upstream_event type=%s %s', event_type, _tts_stats_summary(stats))
                    continue
                if event_type == 'session.finished':
                    if active_segment_index is not None and active_segment_started:
                        await _send_tts_segment_end(send, active_segment_index)
                    await send({'type': 'websocket.send', 'text': json.dumps({'type': 'tts.done'})})
                    logger.info('tts.realtime.finished %s', _tts_stats_summary(stats))
                    return
            logger.warning('tts.realtime.upstream_ended_without_session_finished %s', _tts_stats_summary(stats))
    except ConnectionClosed as exc:
        logger.error('tts.realtime.connection_closed code=%s reason=%s %s', getattr(exc, 'code', None), getattr(exc, 'reason', None), _tts_stats_summary(stats))
        raise
    except Exception:
        logger.exception('tts.realtime.failed %s', _tts_stats_summary(stats))
        raise


async def _stream_tts_segments_audio(
    *,
    segments: AsyncIterable[str],
    voice: TTSVoice,
    config,
    send,
    session_config: dict | None = None,
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> None:
    stats = _new_tts_stream_stats('segments')
    session_event = _session_update_event(config, voice, session_config)
    tts_session = session_event['session']
    ws_url = build_tts_ws_url(config, tts_session.get('model'))
    connect_options = _tts_ws_connect_options()
    logger.info(
        'tts.realtime.connecting mode=segments model=%s voice=%s sample_rate=%s options=%s',
        tts_session.get('model'),
        voice.voice_code,
        tts_session.get('sample_rate') or config.sample_rate,
        connect_options,
    )
    try:
        async with websockets.connect(
            ws_url,
            additional_headers=[
                ('Authorization', f'Bearer {config.api_key}'),
                ('OpenAI-Beta', 'realtime=v1'),
            ],
            user_agent_header='solin-admin/1.0',
            **connect_options,
        ) as upstream:
            logger.info('tts.realtime.connected %s', _tts_stats_summary(stats))
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

            segment_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
            reader_task = asyncio.create_task(_forward_tts_upstream_audio(upstream, send, segment_queue=segment_queue, stats=stats))
            try:
                segment_index = 0
                async for segment in segments:
                    text = normalize_tts_text(segment, config)
                    if not text:
                        continue
                    chunks = split_tts_text(text, exclude_patterns=exclude_patterns)
                    if not chunks:
                        continue
                    segment_index += 1
                    stats['segments'] = segment_index
                    stats['chunks'] += len(chunks)
                    stats['text_chars'] += len(text)
                    logger.info('tts.realtime.segment_prepared index=%s text_chars=%s chunks=%s %s', segment_index, len(text), len(chunks), _tts_stats_summary(stats))
                    await segment_queue.put({'index': segment_index, 'text': text})
                    for chunk_index, chunk in enumerate(chunks, start=1):
                        await upstream.send(json.dumps(_text_append_event(chunk)))
                        if chunk_index == 1 or chunk_index == len(chunks):
                            logger.info('tts.realtime.text_chunk_sent segment=%s chunk=%s/%s chars=%s %s', segment_index, chunk_index, len(chunks), len(chunk), _tts_stats_summary(stats))
                        await asyncio.sleep(0)
                    await upstream.send(json.dumps(_text_commit_event()))
                    await asyncio.sleep(0)

                await segment_queue.put(None)
                await upstream.send(json.dumps(_session_finish_event()))
                logger.info('tts.realtime.session_finish_sent %s', _tts_stats_summary(stats))
                await reader_task
            except asyncio.CancelledError:
                logger.warning('tts.realtime.cancelled %s', _tts_stats_summary(stats))
                reader_task.cancel()
                await asyncio.gather(reader_task, return_exceptions=True)
                raise
            except Exception:
                logger.exception('tts.realtime.stream_loop_failed %s', _tts_stats_summary(stats))
                reader_task.cancel()
                await asyncio.gather(reader_task, return_exceptions=True)
                raise
    except ConnectionClosed as exc:
        logger.error('tts.realtime.connection_closed code=%s reason=%s %s', getattr(exc, 'code', None), getattr(exc, 'reason', None), _tts_stats_summary(stats))
        raise
    except Exception:
        logger.exception('tts.realtime.failed %s', _tts_stats_summary(stats))
        raise


async def _forward_tts_upstream_audio(upstream, send, *, segment_queue: asyncio.Queue | None = None, stats: dict[str, Any] | None = None) -> None:
    stats = stats if stats is not None else _new_tts_stream_stats('forward')
    active_segment: dict[str, Any] | None = None
    segments_finished = False

    async def ensure_segment_started() -> None:
        nonlocal active_segment, segments_finished
        if active_segment is not None or segments_finished or segment_queue is None:
            return
        segment = await segment_queue.get()
        if segment is None:
            segments_finished = True
            return
        active_segment = segment
        await _send_tts_segment_start(send, int(segment['index']), str(segment['text']))

    async def finish_active_segment() -> None:
        nonlocal active_segment
        if active_segment is None:
            return
        await _send_tts_segment_end(send, int(active_segment['index']))
        active_segment = None

    try:
        async for raw_message in upstream:
            try:
                event = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                logger.warning('tts.realtime.invalid_event raw_type=%s %s', type(raw_message).__name__, _tts_stats_summary(stats))
                continue
            if not isinstance(event, dict):
                continue

            event_type = str(event.get('type') or '')
            _record_tts_event(stats, event_type)
            if event_type == 'response.audio.delta':
                delta = event.get('delta')
                if isinstance(delta, str) and delta:
                    await ensure_segment_started()
                    audio = base64.b64decode(delta)
                    _record_tts_audio(stats, len(audio))
                    await send({'type': 'websocket.send', 'bytes': audio})
                continue
            if event_type in {'error', 'session.error'}:
                logger.error('tts.realtime.upstream_error error=%s event=%s %s', _extract_upstream_error_message(event), _safe_tts_event(event), _tts_stats_summary(stats))
                raise RuntimeError(_extract_upstream_error_message(event))
            if event_type in {'response.audio.done', 'response.output_audio.done', 'response.done'}:
                await finish_active_segment()
                logger.info('tts.realtime.upstream_event type=%s %s', event_type, _tts_stats_summary(stats))
                continue
            if event_type == 'session.finished':
                await finish_active_segment()
                await send({'type': 'websocket.send', 'text': json.dumps({'type': 'tts.done'})})
                logger.info('tts.realtime.finished %s', _tts_stats_summary(stats))
                return
            if event_type and event_type != 'response.audio.delta':
                logger.debug('tts.realtime.upstream_event type=%s %s', event_type, _tts_stats_summary(stats))
        logger.warning('tts.realtime.upstream_ended_without_session_finished %s', _tts_stats_summary(stats))
    except ConnectionClosed as exc:
        logger.error('tts.realtime.reader_connection_closed code=%s reason=%s %s', getattr(exc, 'code', None), getattr(exc, 'reason', None), _tts_stats_summary(stats))
        raise


def _new_tts_stream_stats(mode: str) -> dict[str, Any]:
    return {
        'mode': mode,
        'started_at': time.monotonic(),
        'segments': 0,
        'chunks': 0,
        'text_chars': 0,
        'audio_chunks': 0,
        'audio_bytes': 0,
        'last_event_type': None,
        'response_done': False,
        'session_finished': False,
    }


def _record_tts_event(stats: dict[str, Any], event_type: str) -> None:
    stats['last_event_type'] = event_type
    if event_type == 'response.done':
        stats['response_done'] = True
    elif event_type == 'session.finished':
        stats['session_finished'] = True


def _record_tts_audio(stats: dict[str, Any], byte_count: int) -> None:
    stats['audio_chunks'] += 1
    stats['audio_bytes'] += byte_count
    if stats['audio_chunks'] in {1, 10} or stats['audio_chunks'] % 50 == 0:
        logger.info('tts.realtime.audio_chunk chunk=%s bytes=%s %s', stats['audio_chunks'], byte_count, _tts_stats_summary(stats))


def _tts_stats_summary(stats: dict[str, Any]) -> str:
    elapsed = time.monotonic() - float(stats.get('started_at') or time.monotonic())
    return (
        f'mode={stats.get("mode")} '
        f'elapsed={elapsed:.3f} '
        f'segments={stats.get("segments")} '
        f'chunks={stats.get("chunks")} '
        f'text_chars={stats.get("text_chars")} '
        f'audio_chunks={stats.get("audio_chunks")} '
        f'audio_bytes={stats.get("audio_bytes")} '
        f'last_event_type={stats.get("last_event_type")} '
        f'response_done={stats.get("response_done")} '
        f'session_finished={stats.get("session_finished")}'
    )


def _safe_tts_event(event: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in event.items() if key != 'delta'}
    if 'error' in safe:
        return safe
    return {key: safe.get(key) for key in ('event_id', 'type', 'response_id', 'item_id') if key in safe}


async def _send_tts_segment_start(send, index: int, text: str) -> None:
    await send({
        'type': 'websocket.send',
        'text': json.dumps({
            'type': 'tts.segment_start',
            'payload': {'index': index, 'text': text},
        }, ensure_ascii=False),
    })


async def _send_tts_segment_end(send, index: int) -> None:
    await send({
        'type': 'websocket.send',
        'text': json.dumps({
            'type': 'tts.segment_end',
            'payload': {'index': index},
        }, ensure_ascii=False),
    })


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
