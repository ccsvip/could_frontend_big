from __future__ import annotations

import json
import time
import base64
from dataclasses import dataclass
from urllib.parse import urlencode

from django.conf import settings

from apps.ai_models.models import ASRConfig

try:
    import websocket
except ImportError:  # pragma: no cover - exercised only when dependency is missing in runtime image
    class _MissingWebSocketModule:
        WebSocketException = Exception

        @staticmethod
        def create_connection(*args, **kwargs):
            raise RuntimeError('websocket-client is not installed')

    websocket = _MissingWebSocketModule()


@dataclass(frozen=True)
class EffectiveASRConfig:
    workspace_id: str
    api_key: str
    base_url: str
    model: str
    is_active: bool
    vad_threshold: float = 0.0
    vad_silence_duration_ms: int = 400
    updated_at: object | None = None


def mask_secret(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 4:
        return '*' * len(value)
    return f'********{value[-4:]}'


def get_effective_asr_config() -> EffectiveASRConfig:
    cfg = ASRConfig.load()
    return EffectiveASRConfig(
        workspace_id=(cfg.workspace_id or getattr(settings, 'MULTIMODAL_WORKSPACE_ID', '')).strip(),
        api_key=(cfg.api_key or getattr(settings, 'MULTIMODAL_API_KEY', '')).strip(),
        base_url=(cfg.base_url or getattr(settings, 'ASR_BASE_URL', '')).strip(),
        model=(cfg.model or getattr(settings, 'ASR_MODEL', '')).strip(),
        vad_threshold=float(getattr(cfg, 'vad_threshold', 0.0)),
        vad_silence_duration_ms=int(getattr(cfg, 'vad_silence_duration_ms', 400)),
        is_active=bool(cfg.is_active),
        updated_at=cfg.updated_at,
    )


def build_asr_ws_url(config: EffectiveASRConfig) -> str:
    base_url = config.base_url.rstrip()
    separator = '&' if '?' in base_url else '?'
    return f'{base_url}{separator}{urlencode({"model": config.model})}'


def serialize_asr_settings(config: EffectiveASRConfig) -> dict:
    return {
        'workspaceId': config.workspace_id,
        'apiKey': mask_secret(config.api_key),
        'baseUrl': config.base_url,
        'model': config.model,
        'vadThreshold': config.vad_threshold,
        'vadSilenceDurationMs': config.vad_silence_duration_ms,
        'isActive': config.is_active,
        'configured': is_asr_configured(config),
        'updated_at': config.updated_at,
    }


def serialize_asr_status(config: EffectiveASRConfig | None = None) -> dict:
    effective = config or get_effective_asr_config()
    return {
        'configured': is_asr_configured(effective),
        'isActive': effective.is_active,
        'workspaceId': effective.workspace_id,
        'baseUrl': effective.base_url,
        'model': effective.model,
        'vadThreshold': effective.vad_threshold,
        'vadSilenceDurationMs': effective.vad_silence_duration_ms,
        'updated_at': effective.updated_at,
    }


def is_asr_configured(config: EffectiveASRConfig) -> bool:
    return bool(config.workspace_id and config.api_key and config.base_url and config.model)


def transcribe_pcm_audio(
    *,
    pcm: bytes,
    sample_rate: int = 16000,
    config: EffectiveASRConfig | None = None,
    tenant_id: int | None = None,
) -> str:
    effective = config or get_effective_asr_config()
    if not effective.is_active:
        raise RuntimeError('ASR 服务未启用')
    if not is_asr_configured(effective):
        raise RuntimeError(_missing_config_message(effective))
    if not pcm:
        raise RuntimeError('音频内容为空')

    from apps.ai_models.realtime_asr import is_filler_transcript_text, load_asr_filler_words

    filler_words = load_asr_filler_words(tenant_id)
    ws = None
    transcript = ''
    try:
        ws = websocket.create_connection(
            build_asr_ws_url(effective),
            timeout=30,
            header=[
                f'Authorization: Bearer {effective.api_key}',
                'OpenAI-Beta: realtime=v1',
                f'X-DashScope-WorkSpace: {effective.workspace_id}',
                'User-Agent: solin-device-runtime/1.0',
            ],
        )
        ws.send(json.dumps(_transcription_session_update_event(sample_rate, effective)))
        for offset in range(0, len(pcm), 32 * 1024):
            chunk = pcm[offset:offset + 32 * 1024]
            ws.send(json.dumps(_audio_append_event(chunk)))
        ws.send(json.dumps(_session_finish_event()))

        started_at = time.monotonic()
        while time.monotonic() - started_at < 30:
            raw_event = ws.recv()
            event = json.loads(raw_event) if isinstance(raw_event, str) else {}
            if not isinstance(event, dict):
                continue
            event_type = str(event.get('type') or '')
            if event_type in {'error', 'session.error'}:
                message = event.get('message') or event.get('error') or 'ASR upstream error'
                raise RuntimeError(str(message)[:200])
            text = _extract_transcript_text(event)
            if is_filler_transcript_text(text, filler_words=filler_words):
                text = ''
            if text:
                if event_type.endswith('.delta'):
                    transcript += text
                else:
                    transcript = text
            if event_type in {
                'conversation.item.input_audio_transcription.completed',
                'conversation.item.input_audio_transcription.finished',
                'session.finished',
            } and transcript.strip():
                break
        return transcript.strip()
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def _missing_config_message(config: EffectiveASRConfig) -> str:
    missing = []
    if not config.workspace_id:
        missing.append('MULTIMODAL_WORKSPACE_ID')
    if not config.api_key:
        missing.append('MULTIMODAL_API_KEY')
    if not config.base_url:
        missing.append('ASR_BASE_URL')
    if not config.model:
        missing.append('ASR_MODEL')
    return f'Missing ASR config: {", ".join(missing)}'


def _transcription_session_update_event(sample_rate: int, config: EffectiveASRConfig) -> dict:
    return {
        'event_id': 'event_device_voice_asr_session_update',
        'type': 'session.update',
        'session': {
            'input_audio_format': 'pcm',
            'sample_rate': sample_rate,
            'input_audio_transcription': {'language': 'zh'},
            'turn_detection': {
                'type': 'server_vad',
                'threshold': config.vad_threshold,
                'silence_duration_ms': config.vad_silence_duration_ms,
            },
        },
    }


def _audio_append_event(audio: bytes) -> dict:
    return {
        'event_id': 'event_device_voice_asr_audio_append',
        'type': 'input_audio_buffer.append',
        'audio': base64.b64encode(audio).decode('ascii'),
    }


def _session_finish_event() -> dict:
    return {
        'event_id': 'event_device_voice_asr_session_finish',
        'type': 'session.finish',
    }


def _extract_transcript_text(event: dict) -> str:
    text = event.get('text')
    stash = event.get('stash')
    if isinstance(text, str) or isinstance(stash, str):
        preview = f'{text if isinstance(text, str) else ""}{stash if isinstance(stash, str) else ""}'.strip()
        if preview:
            return preview

    for key in ('text', 'delta', 'transcript', 'content'):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def test_asr_connection() -> dict:
    config = get_effective_asr_config()
    start = time.time()

    if not config.is_active:
        return {'success': False, 'message': 'ASR is disabled', 'latencyMs': 0}
    if not is_asr_configured(config):
        return {'success': False, 'message': _missing_config_message(config), 'latencyMs': 0}

    ws = None
    try:
        ws = websocket.create_connection(
            build_asr_ws_url(config),
            timeout=10,
            header=[
                f'Authorization: Bearer {config.api_key}',
                'OpenAI-Beta: realtime=v1',
                f'X-DashScope-WorkSpace: {config.workspace_id}',
                'User-Agent: solin-admin/1.0',
            ],
        )
        ws.send(json.dumps({
            'event_id': 'event_asr_test_001',
            'type': 'session.update',
            'session': {
                'input_audio_format': 'pcm',
                'sample_rate': 16000,
                'input_audio_transcription': {'language': 'zh'},
                'turn_detection': {
                    'type': 'server_vad',
                    'threshold': config.vad_threshold,
                    'silence_duration_ms': config.vad_silence_duration_ms,
                },
            },
        }))
        ws.send(json.dumps({
            'event_id': 'event_asr_test_002',
            'type': 'session.finish',
        }))
        raw_event = ws.recv()
        event = json.loads(raw_event) if isinstance(raw_event, str) else {}
        latency = int((time.time() - start) * 1000)
        event_type = event.get('type') if isinstance(event, dict) else ''
        return {
            'success': True,
            'message': event_type or 'ASR connection succeeded',
            'latencyMs': latency,
        }
    except Exception as exc:
        latency = int((time.time() - start) * 1000)
        return {
            'success': False,
            'message': str(exc)[:200],
            'latencyMs': latency,
        }
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
