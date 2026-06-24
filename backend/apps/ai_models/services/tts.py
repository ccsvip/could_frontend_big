from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import wave
from dataclasses import dataclass
from urllib.parse import urlencode

import websockets
from django.conf import settings

from apps.ai_models.models import TTSProvider, TTSVoice, TenantTTSSettings


PCM_SOURCE_FORMAT = 'pcm_s16le'
DEFAULT_TEST_TEXT = '对吧~我就特别喜欢这种超市，尤其是过年的时候去逛超市就会觉得超级超级开心！想买好多好多的东西呢！'
DEFAULT_TTS_SEGMENT_BOUNDARIES = '。！？!?；;'


@dataclass(frozen=True)
class EffectiveTTSConfig:
    provider: TTSProvider
    api_key: str
    base_url: str
    model: str
    sample_rate: int
    default_test_text: str
    is_active: bool
    updated_at: object | None = None


def mask_api_key(value: str) -> str:
    if not value:
        return ''
    if len(value) <= 8:
        return '****'
    return f'{value[:3]}...{value[-4:]}'


def get_aliyun_tts_provider() -> TTSProvider:
    return TTSProvider.load_aliyun()


def get_effective_tts_config(provider: TTSProvider | None = None) -> EffectiveTTSConfig:
    cfg = provider or get_aliyun_tts_provider()
    return EffectiveTTSConfig(
        provider=cfg,
        api_key=(cfg.api_key or getattr(settings, 'ALIYUN_TTS_API_KEY', '')).strip(),
        base_url=(cfg.base_url or getattr(settings, 'ALIYUN_TTS_BASE_URL', '')).strip(),
        model=(cfg.model or getattr(settings, 'ALIYUN_TTS_MODEL', '')).strip(),
        sample_rate=int(cfg.sample_rate or getattr(settings, 'ALIYUN_TTS_SAMPLE_RATE', 24000)),
        default_test_text=(cfg.default_test_text or getattr(settings, 'ALIYUN_TTS_DEFAULT_TEST_TEXT', '') or DEFAULT_TEST_TEXT).strip(),
        is_active=bool(cfg.is_active),
        updated_at=cfg.updated_at,
    )


def is_tts_configured(config: EffectiveTTSConfig) -> bool:
    return bool(config.is_active and config.api_key and config.base_url and config.model)


def get_tenant_tts_settings(tenant):
    if tenant is None:
        return None
    settings_obj, _ = TenantTTSSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


def get_available_tts_voices(provider: TTSProvider | None = None):
    cfg = provider or get_aliyun_tts_provider()
    return cfg.voices.filter(is_active=True, is_visible=True).order_by('sort_order', 'id')


def is_voice_available(voice: TTSVoice | None) -> bool:
    if voice is None:
        return False
    return bool(voice.is_active and voice.is_visible and voice.provider.is_active)


def get_default_tts_voice(provider: TTSProvider | None = None) -> TTSVoice | None:
    cfg = provider or get_aliyun_tts_provider()
    if is_voice_available(cfg.default_voice):
        return cfg.default_voice
    return get_available_tts_voices(cfg).first()


def get_effective_tts_voice_for_tenant(tenant, provider: TTSProvider | None = None) -> TTSVoice | None:
    settings_obj = get_tenant_tts_settings(tenant)
    if settings_obj is not None and is_voice_available(settings_obj.default_voice):
        return settings_obj.default_voice
    return get_default_tts_voice(provider)


def normalize_tts_text(text: str | None, config: EffectiveTTSConfig) -> str:
    value = (text or '').strip()
    return value or config.default_test_text


def split_tts_text(
    text: str,
    *,
    chunk_size: int = 80,
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    flush: bool = True,
) -> list[str]:
    stripped = sanitize_tts_text(
        text,
        filter_punctuation=filter_punctuation,
        filter_emoji=filter_emoji,
        preserve_sentence_boundaries=True,
    )
    if not stripped:
        return []
    chunks = []
    current = ''
    separators = set(DEFAULT_TTS_SEGMENT_BOUNDARIES)
    for index, char in enumerate(stripped):
        current += char
        if len(current) >= chunk_size or (char in separators and _is_tts_boundary(stripped, index)):
            chunk = current.strip()
            if chunk:
                chunks.append(_finalize_tts_chunk(chunk, filter_punctuation=filter_punctuation))
            current = ''
    tail = current.strip()
    if tail and flush:
        chunks.append(_finalize_tts_chunk(tail, filter_punctuation=filter_punctuation))
    return chunks or [stripped]


def pop_tts_text_segments(
    buffer: str,
    *,
    chunk_size: int = 80,
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    flush: bool = False,
) -> tuple[list[str], str]:
    stripped = sanitize_tts_text(
        buffer,
        filter_punctuation=filter_punctuation,
        filter_emoji=filter_emoji,
        preserve_sentence_boundaries=True,
    )
    if not stripped:
        return [], ''
    chunks = []
    current = ''
    last_boundary = 0
    separators = set(DEFAULT_TTS_SEGMENT_BOUNDARIES)
    for index, char in enumerate(stripped):
        current += char
        if len(current) >= chunk_size or (char in separators and _is_tts_boundary(stripped, index)):
            chunk = _finalize_tts_chunk(current, filter_punctuation=filter_punctuation)
            if chunk:
                chunks.append(chunk)
            current = ''
            last_boundary = index + 1
    rest = stripped[last_boundary:]
    if flush and rest:
        chunk = _finalize_tts_chunk(rest.strip(), filter_punctuation=filter_punctuation)
        if chunk:
            chunks.append(chunk)
        rest = ''
    return chunks, rest


def sanitize_tts_text(
    text: str,
    *,
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    preserve_sentence_boundaries: bool = False,
) -> str:
    value = strip_markdown_for_tts(text)
    if filter_emoji:
        value = re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\ufe0f]', '', value)
    value = value.replace('\r\n', '\n')
    value = re.sub(r'[*_`>#~|\[\]{}]', ' ', value)
    value = re.sub(r'[ \t]+', ' ', value)
    if not preserve_sentence_boundaries:
        value = re.sub(r'\s*\n\s*', ' ', value)
    value = re.sub(r'\n{2,}', '\n', value)
    value = re.sub(r' {2,}', ' ', value)
    if preserve_sentence_boundaries:
        return value.strip(' \t')
    return value.strip()


def strip_markdown_for_tts(text: str) -> str:
    value = str(text or '').replace('\r\n', '\n')
    value = re.sub(r'```[\s\S]*?```', ' ', value)
    value = re.sub(r'`([^`]+)`', r'\1', value)
    lines = []
    for line in value.split('\n'):
        stripped = line.strip()
        if not stripped:
            lines.append('')
            continue
        if re.fullmatch(r'\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?', stripped):
            lines.append('')
            continue
        if re.fullmatch(r'\d+[.)、]?', stripped):
            lines.append(' ')
            continue
        if '|' in stripped:
            stripped = '，'.join(cell.strip() for cell in stripped.strip('|').split('|') if cell.strip())
        stripped = re.sub(r'^#{1,6}\s+', '', stripped)
        stripped = re.sub(r'^[-*+]\s+', '', stripped)
        stripped = re.sub(r'^\d+[.)]\s+', '', stripped)
        stripped = re.sub(r'^>\s?', '', stripped)
        lines.append(stripped)
    value = '\n'.join(lines)
    value = re.sub(r'!\[[^\]]*]\([^)]*\)', ' ', value)
    value = re.sub(r'\[([^\]]+)]\([^)]*\)', r'\1', value)
    value = re.sub(r'(\*\*|__)(.*?)\1', r'\2', value)
    value = re.sub(r'(\*|_)(.*?)\1', r'\2', value)
    return value


def _is_tts_boundary(text: str, index: int) -> bool:
    char = text[index]
    previous_char = text[index - 1] if index > 0 else ''
    next_char = text[index + 1] if index + 1 < len(text) else ''
    if char == '.' and previous_char.isdigit() and next_char.isdigit():
        return False
    if char in '.)' and re.search(r'(?:^|\s)\d+[.)]$', text[:index + 1]):
        return False
    return True


def _finalize_tts_chunk(chunk: str, *, filter_punctuation: str | None = None) -> str:
    value = chunk.strip()
    if filter_punctuation:
        value = value.translate(str.maketrans('', '', filter_punctuation))
    return re.sub(r'\s+', ' ', value).strip()


def pcm_to_wav(pcm: bytes, *, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


def build_tts_ws_url(config: EffectiveTTSConfig) -> str:
    base_url = config.base_url.rstrip()
    separator = '&' if '?' in base_url else '?'
    return f'{base_url}{separator}{urlencode({"model": config.model})}'


def response_format_for_sample_rate(sample_rate: int) -> str:
    return 'pcm'


def synthesize_tts_pcm(*, text: str, voice: TTSVoice, config: EffectiveTTSConfig | None = None) -> bytes:
    effective = config or get_effective_tts_config(voice.provider)
    return asyncio.run(_synthesize_tts_pcm_async(text=text, voice=voice, config=effective))


async def _synthesize_tts_pcm_async(*, text: str, voice: TTSVoice, config: EffectiveTTSConfig) -> bytes:
    if not is_tts_configured(config):
        raise RuntimeError('TTS 服务未配置或未启用')
    if voice is None:
        raise RuntimeError('TTS 音色未配置')

    audio_parts: list[bytes] = []
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
                    audio_parts.append(base64.b64decode(delta))
                continue
            if event_type in {'error', 'session.error'}:
                raise RuntimeError(_extract_upstream_error_message(event))
            if event_type == 'session.finished':
                break

    return b''.join(audio_parts)


def _extract_upstream_error_message(event: dict) -> str:
    error = event.get('error')
    if isinstance(error, dict):
        message = error.get('message') or error.get('code') or error.get('type')
        if message:
            return str(message)[:200]
    message = event.get('message') or error or 'TTS upstream error'
    return str(message)[:200]


def _session_update_event(config: EffectiveTTSConfig, voice: TTSVoice) -> dict:
    return {
        'event_id': 'event_tts_session_update',
        'type': 'session.update',
        'session': {
            'model': config.model,
            'voice': voice.voice_code,
            'response_format': response_format_for_sample_rate(config.sample_rate),
            'mode': 'server_commit',
        },
    }


def _text_append_event(text: str) -> dict:
    return {
        'event_id': 'event_tts_text_append',
        'type': 'input_text_buffer.append',
        'text': text,
    }


def _text_commit_event() -> dict:
    return {
        'event_id': 'event_tts_text_commit',
        'type': 'input_text_buffer.commit',
    }


def _session_finish_event() -> dict:
    return {
        'event_id': 'event_tts_session_finish',
        'type': 'session.finish',
    }
