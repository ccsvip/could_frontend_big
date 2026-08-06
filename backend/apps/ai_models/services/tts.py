from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import wave
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import websockets
from django.conf import settings

from apps.ai_models.models import TTSProvider, TTSVoice, TenantTTSSettings


PCM_SOURCE_FORMAT = 'pcm_s16le'
DEFAULT_TEST_TEXT = '对吧~我就特别喜欢这种超市，尤其是过年的时候去逛超市就会觉得超级超级开心！想买好多好多的东西呢！'
COSYVOICE_TTS_MODEL = 'cosyvoice-v3.5-plus'
DEFAULT_TTS_SEGMENT_BOUNDARIES = frozenset('。！？!?；;')
DEFAULT_TTS_SOFT_SEGMENT_BOUNDARIES = frozenset('，,：:、\r\n')
DEFAULT_TTS_SOFT_SEGMENT_TARGET_CHARACTERS = 32
TTS_EMOJI_PATTERN = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\ufe0f]')
COSYVOICE_MAX_MESSAGE_CHARACTERS = 20_000
COSYVOICE_MAX_TASK_CHARACTERS = 200_000


def validate_cosyvoice_task_text(text: str, sent_characters: int = 0) -> int:
    text_characters = len(text)
    if text_characters > COSYVOICE_MAX_MESSAGE_CHARACTERS:
        raise RuntimeError(
            f'CosyVoice 单条文本超过 {COSYVOICE_MAX_MESSAGE_CHARACTERS} 字符限制'
        )
    total_characters = sent_characters + text_characters
    if total_characters > COSYVOICE_MAX_TASK_CHARACTERS:
        raise RuntimeError(
            f'CosyVoice 单任务文本超过 {COSYVOICE_MAX_TASK_CHARACTERS} 字符限制'
        )
    return total_characters


TTS_MODEL_PROFILES = [
    {
        'code': 'instructional',
        'label': '情感增强',
        'model': 'qwen3-tts-instruct-flash-realtime',
        'supportsInstructionControl': True,
    },
    {
        'code': 'standard',
        'label': '标准播报',
        'model': 'qwen3-tts-flash-realtime',
        'supportsInstructionControl': False,
    },
]
DEFAULT_TTS_MODEL_PROFILE_CODE = 'instructional'
QWEN3_INSTRUCT_FLASH_VOICE_CODES = {
    'Cherry',
    'Serena',
    'Ethan',
    'Chelsie',
    'Momo',
    'Vivian',
    'Moon',
    'Maia',
    'Kai',
    'Nofish',
    'Bella',
    'Eldric Sage',
    'Mia',
    'Mochi',
    'Bellona',
    'Vincent',
    'Bunny',
    'Neil',
    'Arthur',
    'Nini',
    'Elias',
    'Seren',
    'Pip',
    'Stella',
}
QWEN3_FLASH_EXTRA_VOICE_CODES = {
    'Jennifer',
    'Ryan',
    'Katerina',
    'Aiden',
    'Dylan',
    'Jada',
    'Li',
    'Marcus',
    'Roy',
    'Peter',
    'Sunny',
    'Eric',
    'Rocky',
    'Kiki',
    'Bodega',
    'Sonrisa',
    'Alek',
    'Dolce',
    'Sohee',
    'Ono Anna',
    'Lenn',
    'Emilien',
    'Andre',
    'Radio Gol',
}
QWEN3_FLASH_VOICE_CODES = QWEN3_INSTRUCT_FLASH_VOICE_CODES | QWEN3_FLASH_EXTRA_VOICE_CODES


@dataclass(frozen=True)
class EffectiveTTSConfig:
    provider: TTSProvider
    provider_code: str
    api_key: str
    base_url: str
    model: str
    sample_rate: int
    tts_session_config: dict
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
        provider_code=cfg.code,
        api_key=(cfg.api_key or getattr(settings, 'ALIYUN_TTS_API_KEY', '')).strip(),
        base_url=(cfg.base_url or getattr(settings, 'ALIYUN_TTS_BASE_URL', '')).strip(),
        model=(cfg.model or getattr(settings, 'ALIYUN_TTS_MODEL', '')).strip(),
        sample_rate=int(cfg.sample_rate or getattr(settings, 'ALIYUN_TTS_SAMPLE_RATE', 24000)),
        tts_session_config=dict(getattr(cfg, 'tts_session_config', None) or {}),
        default_test_text=(cfg.default_test_text or getattr(settings, 'ALIYUN_TTS_DEFAULT_TEST_TEXT', '') or DEFAULT_TEST_TEXT).strip(),
        is_active=bool(cfg.is_active),
        updated_at=cfg.updated_at,
    )


def is_tts_configured(config: EffectiveTTSConfig) -> bool:
    return bool(config.is_active and config.api_key and config.base_url and config.model)


def public_tts_model_profiles() -> list[dict]:
    return [
        {
            'code': item['code'],
            'label': item['label'],
            'supportsInstructionControl': item['supportsInstructionControl'],
        }
        for item in TTS_MODEL_PROFILES
    ]


def resolve_tts_model_profile_code(value: str | None) -> str:
    raw = str(value or '').strip()
    available = {item['code'] for item in TTS_MODEL_PROFILES}
    return raw if raw in available else DEFAULT_TTS_MODEL_PROFILE_CODE


def resolve_tts_model_profile_model(value: str | None, fallback_model: str = '') -> str:
    code = resolve_tts_model_profile_code(value)
    for item in TTS_MODEL_PROFILES:
        if item['code'] == code:
            return str(item['model'])
    return fallback_model


def get_tts_model_profile_code_from_session(session_config: dict | None, fallback_model: str = '') -> str:
    if isinstance(session_config, dict):
        model_code = session_config.get('model_code') or session_config.get('modelCode')
        if model_code:
            return resolve_tts_model_profile_code(str(model_code))
    normalized_fallback = str(fallback_model or '').strip().lower()
    for item in TTS_MODEL_PROFILES:
        if normalized_fallback.startswith(str(item['model']).lower()):
            return str(item['code'])
    return DEFAULT_TTS_MODEL_PROFILE_CODE


def get_tts_model_profile_voice_codes(model_code: str | None) -> set[str]:
    resolved = resolve_tts_model_profile_code(model_code)
    if resolved == 'standard':
        return set(QWEN3_FLASH_VOICE_CODES)
    return set(QWEN3_INSTRUCT_FLASH_VOICE_CODES)


def is_tts_voice_supported_by_model_code(voice: TTSVoice | None, model_code: str | None) -> bool:
    if voice is None:
        return False
    return voice.voice_code in get_tts_model_profile_voice_codes(model_code)


def get_tenant_tts_settings(tenant):
    if tenant is None:
        return None
    settings_obj, _ = TenantTTSSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


def get_available_tts_voices(provider: TTSProvider | None = None, *, model_code: str | None = None):
    """Platform-wide listed voices on one card.

    Platform scope only: ``is_visible`` means "listed on the platform", never
    "this company may use it". Do NOT use this to decide company availability —
    it knows nothing about card grants, voice grants or ``owner_tenant``. Company
    availability lives in ``services.tts_authorization``.
    """
    cfg = provider or get_aliyun_tts_provider()
    queryset = cfg.voices.filter(is_active=True, is_visible=True)
    if model_code:
        queryset = queryset.filter(voice_code__in=get_tts_model_profile_voice_codes(model_code))
    return queryset.order_by('sort_order', 'id')


def is_voice_available(voice: TTSVoice | None) -> bool:
    """Whether the platform itself offers this voice.

    Platform scope only — see ``get_available_tts_voices``. For "may this company
    use this voice?" call ``tts_authorization.is_tts_voice_effective_for_tenant``.
    """
    if voice is None:
        return False
    return bool(voice.is_active and voice.is_visible and voice.provider.is_active)


def get_default_tts_voice(provider: TTSProvider | None = None, *, model_code: str | None = None) -> TTSVoice | None:
    cfg = provider or get_aliyun_tts_provider()
    if is_voice_available(cfg.default_voice) and (not model_code or is_tts_voice_supported_by_model_code(cfg.default_voice, model_code)):
        return cfg.default_voice
    return get_available_tts_voices(cfg, model_code=model_code).first()


def normalize_tts_text(text: str | None, config: EffectiveTTSConfig) -> str:
    value = '' if text is None else str(text)
    return value if value else config.default_test_text


@dataclass(frozen=True, slots=True)
class _TTSStreamToken:
    text: str = ''
    boundary: bool = False
    hard_boundary: bool = False



class _LiteralExclusionStage:
    """Incrementally remove one literal pattern without consuming a partial suffix."""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self._pending: list[_TTSStreamToken] = []

    def feed(self, tokens: list[_TTSStreamToken]) -> list[_TTSStreamToken]:
        emitted: list[_TTSStreamToken] = []
        for token in tokens:
            self._pending.append(token)
            emitted.extend(self._drain_safe_prefix())
        return emitted

    def finish(self) -> list[_TTSStreamToken]:
        pending = self._pending
        self._pending = []
        return pending

    def _drain_safe_prefix(self) -> list[_TTSStreamToken]:
        char_positions = [index for index, token in enumerate(self._pending) if token.text]
        visible = ''.join(self._pending[index].text for index in char_positions)
        if visible.endswith(self.pattern):
            hard_boundary = any(token.hard_boundary for token in self._pending)
            boundary = any(token.boundary for token in self._pending)
            self._pending = []
            return [_TTSStreamToken(boundary=boundary, hard_boundary=hard_boundary)] if boundary else []

        max_prefix_length = min(len(visible), len(self.pattern) - 1)
        held_characters = 0
        for length in range(max_prefix_length, 0, -1):
            if self.pattern.startswith(visible[-length:]):
                held_characters = length
                break

        if held_characters:
            held_from = char_positions[-held_characters]
            emitted = self._pending[:held_from]
            self._pending = self._pending[held_from:]
            return emitted

        emitted = self._pending
        self._pending = []
        return emitted


class TTSStreamingTextProcessor:
    """Apply page-owned TTS rules once, then split at hard or sized soft boundaries."""

    def __init__(
        self,
        *,
        filter_punctuation: str | None = None,
        filter_emoji: bool = False,
        exclude_patterns: list[str] | tuple[str, ...] | None = None,
        soft_boundary_target: int | None = None,
    ):
        self._exclusion_stages = [
            _LiteralExclusionStage(pattern)
            for pattern in _normalize_tts_exclude_patterns(exclude_patterns)
        ]
        self._filtered_characters = frozenset(filter_punctuation or '')
        self._filter_emoji = filter_emoji
        self._soft_boundary_target = soft_boundary_target
        self._segment_characters: list[str] = []
        self._finished = False

    def feed(self, text: str) -> list[str]:
        if self._finished:
            raise RuntimeError('TTS text processor is already finished.')
        tokens = [
            _TTSStreamToken(
                char,
                char in DEFAULT_TTS_SEGMENT_BOUNDARIES or char in DEFAULT_TTS_SOFT_SEGMENT_BOUNDARIES,
                char in DEFAULT_TTS_SEGMENT_BOUNDARIES,
            )
            for char in str(text or '')
        ]
        return self._consume(self._apply_rules(tokens))

    def finish(self) -> list[str]:
        if self._finished:
            return []
        self._finished = True
        tokens: list[_TTSStreamToken] = []
        for index, stage in enumerate(self._exclusion_stages):
            stage_output = stage.finish()
            for downstream in self._exclusion_stages[index + 1:]:
                stage_output = downstream.feed(stage_output)
            tokens.extend(stage_output)
        segments = self._consume(self._apply_character_rules(tokens))
        if self._segment_characters:
            segments.append(''.join(self._segment_characters))
            self._segment_characters = []
        return segments

    def _apply_rules(self, tokens: list[_TTSStreamToken]) -> list[_TTSStreamToken]:
        for stage in self._exclusion_stages:
            tokens = stage.feed(tokens)
        return self._apply_character_rules(tokens)

    def _apply_character_rules(self, tokens: list[_TTSStreamToken]) -> list[_TTSStreamToken]:
        filtered: list[_TTSStreamToken] = []
        for token in tokens:
            remove_character = bool(
                token.text
                and (
                    (self._filter_emoji and TTS_EMOJI_PATTERN.fullmatch(token.text))
                    or token.text in self._filtered_characters
                )
            )
            if remove_character:
                if token.boundary:
                    filtered.append(_TTSStreamToken(boundary=True, hard_boundary=token.hard_boundary))
                continue
            filtered.append(token)
        return filtered

    def _consume(self, tokens: list[_TTSStreamToken]) -> list[str]:
        segments: list[str] = []
        for token in tokens:
            if token.text:
                self._segment_characters.append(token.text)
            soft_boundary_ready = (
                token.boundary
                and not token.hard_boundary
                and self._soft_boundary_target is not None
                and len(self._segment_characters) >= self._soft_boundary_target
            )
            if token.boundary and (token.hard_boundary or soft_boundary_ready) and self._segment_characters:
                segments.append(''.join(self._segment_characters))
                self._segment_characters = []
        return segments


def split_tts_text(
    text: str,
    *,
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    processor = TTSStreamingTextProcessor(
        filter_punctuation=filter_punctuation,
        filter_emoji=filter_emoji,
        exclude_patterns=exclude_patterns,
    )
    return [*processor.feed(text), *processor.finish()]


def apply_agent_tts_rules(
    text: str,
    *,
    filter_punctuation: str | None = None,
    filter_emoji: bool = False,
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> str:
    return ''.join(split_tts_text(
        text,
        filter_punctuation=filter_punctuation,
        filter_emoji=filter_emoji,
        exclude_patterns=exclude_patterns,
    ))


def _normalize_tts_exclude_patterns(patterns: list[str] | tuple[str, ...] | None) -> list[str]:
    if not patterns:
        return []
    normalized = []
    seen = set()
    for pattern in patterns:
        text = str(pattern)
        if text and text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def pcm_to_wav(pcm: bytes, *, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


def build_tts_ws_url(config: EffectiveTTSConfig, model: str | None = None) -> str:
    base_url = config.base_url.rstrip()
    separator = '&' if '?' in base_url else '?'
    return f'{base_url}{separator}{urlencode({"model": model or config.model})}'


def response_format_for_sample_rate(sample_rate: int) -> str:
    return 'pcm'


def synthesize_tts_pcm(
    *,
    text: str,
    voice: TTSVoice,
    config: EffectiveTTSConfig | None = None,
    session_config: dict | None = None,
) -> bytes:
    effective = config or get_effective_tts_config(voice.provider)
    if effective.provider_code == 'cosyvoice':
        return asyncio.run(_synthesize_cosyvoice_tts_pcm_async(
            text=text,
            voice=voice,
            config=effective,
            controls=session_config,
        ))
    return asyncio.run(_synthesize_tts_pcm_async(text=text, voice=voice, config=effective, session_config=session_config))


async def _synthesize_cosyvoice_tts_pcm_async(
    *,
    text: str,
    voice: TTSVoice,
    config: EffectiveTTSConfig,
    controls: dict | None = None,
) -> bytes:
    if not is_tts_configured(config):
        raise RuntimeError('TTS 服务未配置或未启用')
    if voice is None:
        raise RuntimeError('TTS 音色未配置')

    options = controls if isinstance(controls, dict) else {}
    chunks = split_tts_text(text)
    sent_characters = 0
    for chunk in chunks:
        sent_characters = validate_cosyvoice_task_text(chunk, sent_characters)
    task_id = str(uuid.uuid4())
    run_task = {
        'header': {
            'action': 'run-task',
            'task_id': task_id,
            'streaming': 'duplex',
        },
        'payload': {
            'task_group': 'audio',
            'task': 'tts',
            'function': 'SpeechSynthesizer',
            'model': COSYVOICE_TTS_MODEL,
            'input': {},
            'parameters': {
                'text_type': 'PlainText',
                'voice': voice.voice_code,
                'format': 'pcm',
                'sample_rate': config.sample_rate,
                'volume': _bounded_int(options.get('volume'), 50, 0, 100),
                'rate': _bounded_float(options.get('speech_rate'), 1.0, 0.5, 2.0),
                'pitch': _bounded_float(options.get('pitch_rate'), 1.0, 0.5, 2.0),
            },
        },
    }
    audio_parts: list[bytes] = []
    async with websockets.connect(
        config.base_url,
        additional_headers=[('Authorization', f'Bearer {config.api_key}')],
        user_agent_header='solin-admin/1.0',
        open_timeout=10,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ) as upstream:
        await upstream.send(json.dumps(run_task))
        async for raw_message in upstream:
            header = _matching_cosyvoice_task_header(raw_message, task_id)
            if header is None:
                continue
            if header.get('event') == 'task-failed':
                raise RuntimeError(_extract_cosyvoice_task_error(header))
            if header.get('event') == 'task-started':
                break
        else:
            raise RuntimeError('CosyVoice upstream closed before task started.')

        for chunk in chunks:
            await upstream.send(json.dumps({
                'header': {
                    'action': 'continue-task',
                    'task_id': task_id,
                    'streaming': 'duplex',
                },
                'payload': {'input': {'text': chunk}},
            }))
        await upstream.send(json.dumps({
            'header': {
                'action': 'finish-task',
                'task_id': task_id,
                'streaming': 'duplex',
            },
            'payload': {'input': {}},
        }))

        async for raw_message in upstream:
            if isinstance(raw_message, bytes):
                audio_parts.append(raw_message)
                continue
            header = _matching_cosyvoice_task_header(raw_message, task_id)
            if header is None:
                continue
            if header.get('event') == 'task-failed':
                raise RuntimeError(_extract_cosyvoice_task_error(header))
            if header.get('event') == 'task-finished':
                break
        else:
            raise RuntimeError('CosyVoice upstream closed before task finished.')

    return b''.join(audio_parts)


def _matching_cosyvoice_task_header(raw_message, task_id: str) -> dict | None:
    try:
        event = json.loads(raw_message)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(event, dict):
        return None
    header = event.get('header')
    if not isinstance(header, dict) or header.get('task_id') != task_id:
        return None
    return header


def _extract_cosyvoice_task_error(header: dict) -> str:
    error_code = str(header.get('error_code') or '').strip()
    error_message = str(header.get('error_message') or '').strip()
    if error_code and error_message:
        return f'{error_code}: {error_message}'[:200]
    return (error_message or error_code or 'CosyVoice task failed.')[:200]


async def _synthesize_tts_pcm_async(
    *,
    text: str,
    voice: TTSVoice,
    config: EffectiveTTSConfig,
    session_config: dict | None = None,
) -> bytes:
    if not is_tts_configured(config):
        raise RuntimeError('TTS 服务未配置或未启用')
    if voice is None:
        raise RuntimeError('TTS 音色未配置')

    audio_parts: list[bytes] = []
    session_event = _session_update_event(config, voice, session_config)
    session_model = session_event['session']['model']
    async with websockets.connect(
        build_tts_ws_url(config, session_model),
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
        await upstream.send(json.dumps(session_event))
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


def _session_update_event(config: EffectiveTTSConfig, voice: TTSVoice, session_config: dict | None = None) -> dict:
    options = _normalize_session_config(config, session_config)
    model_code = get_tts_model_profile_code_from_session(options, config.model)
    model = resolve_tts_model_profile_model(model_code, config.model)
    return {
        'event_id': 'event_tts_session_update',
        'type': 'session.update',
        'session': {
            'model': model,
            'voice': voice.voice_code,
            **options,
        },
    }


def _normalize_session_config(config: EffectiveTTSConfig, session_config: dict | None = None) -> dict:
    raw = session_config if isinstance(session_config, dict) else (getattr(config, 'tts_session_config', None) or {})
    response_format = raw.get('response_format') or raw.get('responseFormat')
    if response_format not in {'pcm', 'wav', 'mp3', 'opus'}:
        response_format = response_format_for_sample_rate(config.sample_rate)
    language_type = raw.get('language_type') or raw.get('languageType') or 'Auto'
    if language_type not in {
        'Auto', 'Chinese', 'English', 'German', 'Italian', 'Portuguese',
        'Spanish', 'Japanese', 'Korean', 'French', 'Russian',
    }:
        language_type = 'Auto'
    sample_rate = _bounded_int(raw.get('sample_rate') or raw.get('sampleRate'), config.sample_rate, 8000, 48000)
    if sample_rate not in {8000, 16000, 24000, 48000}:
        sample_rate = config.sample_rate
    instructions = str(raw.get('instructions') or '').strip()
    model_code = get_tts_model_profile_code_from_session(raw, config.model)
    return {
        'model_code': model_code,
        'mode': raw.get('mode') if raw.get('mode') in {'server_commit', 'commit'} else 'server_commit',
        'language_type': language_type,
        'response_format': response_format,
        'sample_rate': sample_rate,
        'speech_rate': _bounded_float(raw.get('speech_rate') or raw.get('speechRate'), 1.0, 0.5, 2.0),
        'volume': _bounded_int(raw.get('volume'), 50, 0, 100),
        'pitch_rate': _bounded_float(raw.get('pitch_rate') or raw.get('pitchRate'), 1.0, 0.5, 2.0),
        'bit_rate': _bounded_int(raw.get('bit_rate') or raw.get('bitRate'), 128, 6, 510),
        'instructions': instructions,
        'optimize_instructions': bool(instructions and raw.get('optimize_instructions', raw.get('optimizeInstructions', False))),
    }


def _bounded_float(value, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < minimum or number > maximum:
        return default
    return round(number, 2)


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < minimum or number > maximum:
        return default
    return number


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
