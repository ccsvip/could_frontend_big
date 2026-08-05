"""CosyVoice realtime streaming.

Bridges the Model Studio duplex task protocol (``run-task`` / ``continue-task`` /
``finish-task``) to this system's unified downstream WebSocket contract:
``tts.ready`` -> ``tts.segment_start`` -> binary audio chunks ->
``tts.segment_end`` -> ``tts.done``, with ``tts.error`` on failure.

Upstream audio frames are forwarded chunk by chunk as they arrive. They are
never accumulated into a complete buffer first — that would defeat the point of
a realtime channel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncIterable

import websockets
from websockets.exceptions import ConnectionClosed

from .tts import (
    COSYVOICE_TTS_MODEL,
    EffectiveTTSConfig,
    _extract_cosyvoice_task_error,
    _matching_cosyvoice_task_header,
    is_tts_configured,
    normalize_tts_text,
    split_tts_text,
)

logger = logging.getLogger(__name__)


def _run_task_message(task_id: str, *, voice_code: str, config: EffectiveTTSConfig, controls: dict[str, Any]) -> dict[str, Any]:
    return {
        'header': {'action': 'run-task', 'task_id': task_id, 'streaming': 'duplex'},
        'payload': {
            'task_group': 'audio',
            'task': 'tts',
            'function': 'SpeechSynthesizer',
            'model': COSYVOICE_TTS_MODEL,
            'input': {},
            'parameters': {
                'text_type': 'PlainText',
                'voice': voice_code,
                'format': 'pcm',
                'sample_rate': config.sample_rate,
                'volume': controls.get('volume', 50),
                'rate': controls.get('speech_rate', 1.0),
                'pitch': controls.get('pitch_rate', 1.0),
            },
        },
    }


def _continue_task_message(task_id: str, text: str) -> dict[str, Any]:
    return {
        'header': {'action': 'continue-task', 'task_id': task_id, 'streaming': 'duplex'},
        'payload': {'input': {'text': text}},
    }


def _finish_task_message(task_id: str) -> dict[str, Any]:
    return {
        'header': {'action': 'finish-task', 'task_id': task_id, 'streaming': 'duplex'},
        'payload': {'input': {}},
    }


def _connect_options() -> dict[str, Any]:
    return {
        'open_timeout': 10,
        'ping_interval': 20,
        'ping_timeout': 20,
        'close_timeout': 10,
        'max_size': 8 * 1024 * 1024,
    }


async def _send_json(send, payload: dict[str, Any]) -> None:
    await send({'type': 'websocket.send', 'text': json.dumps(payload, ensure_ascii=False)})


async def _send_ready(send, *, config: EffectiveTTSConfig, voice_code: str) -> None:
    await _send_json(send, {
        'type': 'tts.ready',
        'sampleRate': config.sample_rate,
        'responseFormat': 'pcm',
        'voice': voice_code,
    })


async def _send_segment_start(send, index: int, text: str) -> None:
    await _send_json(send, {'type': 'tts.segment_start', 'payload': {'index': index, 'text': text}})


async def _send_segment_end(send, index: int) -> None:
    await _send_json(send, {'type': 'tts.segment_end', 'payload': {'index': index}})


async def _await_task_started(upstream, task_id: str) -> None:
    async for raw_message in upstream:
        header = _matching_cosyvoice_task_header(raw_message, task_id)
        if header is None:
            continue
        event = header.get('event')
        if event == 'task-failed':
            raise RuntimeError(_extract_cosyvoice_task_error(header))
        if event == 'task-started':
            return
    raise RuntimeError('CosyVoice upstream closed before task started.')


def _open_upstream(config: EffectiveTTSConfig):
    if not is_tts_configured(config):
        raise RuntimeError('CosyVoice 服务未配置或未启用')
    return websockets.connect(
        config.base_url,
        additional_headers=[('Authorization', f'Bearer {config.api_key}')],
        user_agent_header='solin-admin/1.0',
        **_connect_options(),
    )


class CosyVoicePrewarmedTask:
    """An upstream connection whose ``run-task`` is already accepted.

    Holds the connection open and idle until text arrives, so the handshake and
    the ``task-started`` round trip stay off the first-audio critical path.
    """

    def __init__(self, *, context, upstream, task_id: str, voice_code: str):
        self._context = context
        self.upstream = upstream
        self.task_id = task_id
        self.voice_code = voice_code
        self._closed = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._context.__aexit__(None, None, None)
        except Exception:
            logger.exception('tts.cosyvoice.realtime.prewarm_close_failed task_id=%s', self.task_id)


async def prewarm_cosyvoice_realtime(
    *,
    voice,
    config: EffectiveTTSConfig,
    controls: dict[str, Any] | None = None,
) -> CosyVoicePrewarmedTask:
    """Open one upstream task and wait for ``task-started``, then hand it back idle."""
    controls = controls or {}
    task_id = str(uuid.uuid4())
    context = _open_upstream(config)
    upstream = await context.__aenter__()
    try:
        await upstream.send(json.dumps(_run_task_message(
            task_id,
            voice_code=voice.voice_code,
            config=config,
            controls=controls,
        )))
        await _await_task_started(upstream, task_id)
    except BaseException:
        await context.__aexit__(None, None, None)
        raise
    logger.info(
        'tts.cosyvoice.realtime.prewarmed task_id=%s voice=%s sample_rate=%s',
        task_id, voice.voice_code, config.sample_rate,
    )
    return CosyVoicePrewarmedTask(
        context=context,
        upstream=upstream,
        task_id=task_id,
        voice_code=voice.voice_code,
    )


async def stream_cosyvoice_realtime_text(
    *,
    text: str,
    voice,
    config: EffectiveTTSConfig,
    send,
    controls: dict[str, Any] | None = None,
    exclude_patterns=None,
) -> None:
    """Synthesize one text as a single downstream segment, streamed as it arrives."""
    controls = controls or {}
    task_id = str(uuid.uuid4())
    audio_chunks = 0
    audio_bytes = 0
    segment_started = False

    try:
        async with _open_upstream(config) as upstream:
            await upstream.send(json.dumps(_run_task_message(
                task_id,
                voice_code=voice.voice_code,
                config=config,
                controls=controls,
            )))
            await _await_task_started(upstream, task_id)
            await _send_ready(send, config=config, voice_code=voice.voice_code)

            chunks = split_tts_text(text, exclude_patterns=exclude_patterns)
            for chunk in chunks:
                await upstream.send(json.dumps(_continue_task_message(task_id, chunk)))
                await asyncio.sleep(0)
            await upstream.send(json.dumps(_finish_task_message(task_id)))
            logger.info(
                'tts.cosyvoice.realtime.text_sent task_id=%s chunks=%s text_chars=%s',
                task_id, len(chunks), len(text or ''),
            )

            async for raw_message in upstream:
                if isinstance(raw_message, bytes):
                    if not raw_message:
                        continue
                    if not segment_started and text:
                        await _send_segment_start(send, 1, text)
                        segment_started = True
                    audio_chunks += 1
                    audio_bytes += len(raw_message)
                    await send({'type': 'websocket.send', 'bytes': raw_message})
                    continue

                header = _matching_cosyvoice_task_header(raw_message, task_id)
                if header is None:
                    continue
                event = header.get('event')
                if event == 'task-failed':
                    raise RuntimeError(_extract_cosyvoice_task_error(header))
                if event == 'task-finished':
                    if segment_started:
                        await _send_segment_end(send, 1)
                    await _send_json(send, {'type': 'tts.done'})
                    logger.info(
                        'tts.cosyvoice.realtime.finished task_id=%s audio_chunks=%s audio_bytes=%s',
                        task_id, audio_chunks, audio_bytes,
                    )
                    return
            raise RuntimeError('CosyVoice upstream closed before task finished.')
    except ConnectionClosed as exc:
        logger.error(
            'tts.cosyvoice.realtime.connection_closed task_id=%s code=%s audio_chunks=%s',
            task_id, getattr(exc, 'code', None), audio_chunks,
        )
        raise
    except Exception:
        logger.exception('tts.cosyvoice.realtime.failed task_id=%s audio_chunks=%s', task_id, audio_chunks)
        raise


async def stream_cosyvoice_realtime_segments(
    *,
    segments: AsyncIterable[str],
    voice,
    config: EffectiveTTSConfig,
    send,
    controls: dict[str, Any] | None = None,
    exclude_patterns=None,
    prepared: CosyVoicePrewarmedTask | None = None,
) -> None:
    """Synthesize an async stream of segments over one upstream task.

    The whole answer rides a single ``run-task``: later segments are pushed as
    ``continue-task`` without waiting for the previous segment's audio, and a
    concurrent reader forwards frames as they arrive. That removes the
    ``run-task`` / ``task-started`` round trip between segments — at the cost of
    ``tts.segment_start`` / ``tts.segment_end`` becoming approximate markers,
    since the task protocol delimits audio per task and not per ``continue-task``.
    """
    controls = controls or {}
    if prepared is None:
        prepared = await prewarm_cosyvoice_realtime(voice=voice, config=config, controls=controls)
    upstream = prepared.upstream
    task_id = prepared.task_id
    stats: dict[str, Any] = {'audio_chunks': 0, 'audio_bytes': 0}

    try:
        await _send_ready(send, config=config, voice_code=voice.voice_code)

        segment_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        reader_task = asyncio.create_task(_forward_stream_audio(
            upstream,
            send,
            segment_queue=segment_queue,
            task_id=task_id,
            stats=stats,
        ))
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
                await segment_queue.put({'index': segment_index, 'text': text})
                for chunk in chunks:
                    await upstream.send(json.dumps(_continue_task_message(task_id, chunk)))
                    await asyncio.sleep(0)
                logger.info(
                    'tts.cosyvoice.realtime.segment_sent index=%s task_id=%s chunks=%s text_chars=%s',
                    segment_index, task_id, len(chunks), len(text),
                )

            await segment_queue.put(None)
            await upstream.send(json.dumps(_finish_task_message(task_id)))
            await reader_task
            logger.info(
                'tts.cosyvoice.realtime.segments_finished task_id=%s segments=%s audio_chunks=%s',
                task_id, segment_index, stats['audio_chunks'],
            )
        except BaseException:
            reader_task.cancel()
            await asyncio.gather(reader_task, return_exceptions=True)
            raise
    except ConnectionClosed as exc:
        logger.error(
            'tts.cosyvoice.realtime.segments_connection_closed task_id=%s code=%s audio_chunks=%s',
            task_id, getattr(exc, 'code', None), stats['audio_chunks'],
        )
        raise
    except Exception:
        logger.exception(
            'tts.cosyvoice.realtime.segments_failed task_id=%s audio_chunks=%s',
            task_id, stats['audio_chunks'],
        )
        raise
    finally:
        await prepared.aclose()


async def _forward_stream_audio(
    upstream,
    send,
    *,
    segment_queue: asyncio.Queue,
    task_id: str,
    stats: dict[str, Any],
) -> None:
    """Forward one task's whole audio stream, flipping segment markers as text arrives.

    The task protocol gives no per-``continue-task`` audio boundary, so markers
    are an approximation: each audio frame advances at most one queued segment,
    which means segment N opens once its text has been queued rather than when
    its own first frame arrives. Markers therefore run ahead of the audio they
    label. They stay well-formed (one ``segment_start`` / ``segment_end`` pair
    per segment, in order) and nothing downstream depends on their alignment.
    """
    active_segment: dict[str, Any] | None = None
    segments_finished = False

    async def finish_active_segment() -> None:
        nonlocal active_segment
        if active_segment is None:
            return
        await _send_segment_end(send, int(active_segment['index']))
        active_segment = None

    async def ensure_segment_started() -> None:
        nonlocal active_segment, segments_finished
        if segments_finished:
            return
        if active_segment is not None and segment_queue.empty():
            return
        segment = await segment_queue.get()
        if segment is None:
            segments_finished = True
            return
        await finish_active_segment()
        active_segment = segment
        await _send_segment_start(send, int(segment['index']), str(segment['text']))

    async for raw_message in upstream:
        if isinstance(raw_message, bytes):
            if not raw_message:
                continue
            await ensure_segment_started()
            stats['audio_chunks'] += 1
            stats['audio_bytes'] += len(raw_message)
            await send({'type': 'websocket.send', 'bytes': raw_message})
            continue

        header = _matching_cosyvoice_task_header(raw_message, task_id)
        if header is None:
            continue
        event = header.get('event')
        if event == 'task-failed':
            raise RuntimeError(_extract_cosyvoice_task_error(header))
        if event == 'task-finished':
            await finish_active_segment()
            await _send_json(send, {'type': 'tts.done'})
            logger.info(
                'tts.cosyvoice.realtime.stream_finished task_id=%s audio_chunks=%s audio_bytes=%s',
                task_id, stats['audio_chunks'], stats['audio_bytes'],
            )
            return
    raise RuntimeError('CosyVoice upstream closed before task finished.')
