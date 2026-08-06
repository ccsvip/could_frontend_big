"""TTS provider adapters.

The adapter is the seam where vendor differences live. Callers resolve an
authorized voice first, then dispatch on ``voice.provider.code`` — never on a
provider code supplied by the client. Everything vendor-specific (credentials,
upstream protocol, request payload shape) stays inside an adapter; callers only
ever see the generic control vocabulary declared by ``public_config_schema``.

Adding a card means adding an adapter here plus its super-admin settings page.
The tenant grant table, company options contract, device binding and runtime
resolution do not change shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterable

from apps.ai_models.models import TTSProvider, TTSVoice

from .tts import (
    DEFAULT_TEST_TEXT,
    EffectiveTTSConfig,
    _bounded_float,
    _bounded_int,
    _normalize_session_config,
    get_effective_tts_config,
    get_tts_model_profile_code_from_session,
    is_tts_configured,
    public_tts_model_profiles,
)


CHANNEL_HTTP_TEST = 'httpTest'
CHANNEL_HTTP_RUNTIME = 'httpRuntime'
CHANNEL_REALTIME = 'realtime'


class TTSAdapterError(RuntimeError):
    """Adapter cannot serve the request. Never falls back to another card."""


@dataclass(frozen=True)
class ConfigField:
    name: str
    label: str
    type: str
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[dict[str, Any], ...] = ()

    def as_public(self) -> dict[str, Any]:
        field: dict[str, Any] = {'name': self.name, 'label': self.label, 'type': self.type}
        if self.minimum is not None:
            field['min'] = self.minimum
        if self.maximum is not None:
            field['max'] = self.maximum
        if self.step is not None:
            field['step'] = self.step
        if self.options:
            field['options'] = [dict(option) for option in self.options]
        return field


class BaseTTSAdapter:
    provider_code = ''
    schema_key = ''
    supports_company_http_test = False
    supports_company_http_runtime = False
    supports_company_realtime = False
    config_fields: tuple[ConfigField, ...] = ()

    def supported_channels(self, provider: TTSProvider) -> list[str]:
        channels = []
        if self.supports_company_http_test:
            channels.append(CHANNEL_HTTP_TEST)
        if self.supports_company_http_runtime:
            channels.append(CHANNEL_HTTP_RUNTIME)
        if self.supports_company_realtime:
            channels.append(CHANNEL_REALTIME)
        return channels

    def company_runtime_capabilities(self, provider: TTSProvider) -> dict[str, bool]:
        return {
            'supportsCompanyHttpTest': self.supports_company_http_test,
            'supportsCompanyHttpRuntime': self.supports_company_http_runtime,
            'supportsCompanyRealtime': self.supports_company_realtime,
        }

    def public_config_schema(self, provider: TTSProvider) -> dict[str, Any]:
        return {
            'schemaKey': self.schema_key or self.provider_code,
            'fields': [field.as_public() for field in self.config_fields],
        }

    def public_provider_summary(self, provider: TTSProvider) -> dict[str, Any]:
        """Safe card summary. Never includes api keys, ws urls or private params."""
        return {
            'id': provider.id,
            'code': provider.code,
            'name': provider.name,
            'isActive': bool(provider.is_active),
            'defaultModelCode': self.default_model_code(provider),
            'modelOptions': self.public_model_options(provider),
            'supportedChannels': self.supported_channels(provider),
            'publicConfigSchema': self.public_config_schema(provider),
            'capabilities': self.company_runtime_capabilities(provider),
        }

    def public_voice_capabilities(self, voice: TTSVoice) -> dict[str, bool]:
        names = {field.name for field in self.config_fields}
        return {
            'speechRate': 'speech_rate' in names,
            'pitchRate': 'pitch_rate' in names,
            'volume': 'volume' in names,
        }

    def public_model_options(self, provider: TTSProvider) -> list[dict[str, Any]]:
        return []

    def default_model_code(self, provider: TTSProvider) -> str:
        return ''

    def normalize_public_controls(self, raw_controls: Any) -> dict[str, Any]:
        """Whitelist controls to this card's schema. Unknown keys are rejected."""
        raw = raw_controls if isinstance(raw_controls, dict) else {}
        allowed = {field.name for field in self.config_fields}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise TTSAdapterError(f'{self.provider_code} 不支持配置字段：{"、".join(unknown)}')
        return self._coerce_controls(raw)

    def _coerce_controls(self, raw: dict[str, Any]) -> dict[str, Any]:
        return dict(raw)

    def effective_config(self, provider: TTSProvider) -> EffectiveTTSConfig:
        raise NotImplementedError

    def supports_realtime(self, config: EffectiveTTSConfig) -> bool:
        return self.supports_company_realtime and is_tts_configured(config)

    def ensure_channel(self, provider: TTSProvider, channel: str) -> None:
        if channel not in self.supported_channels(provider):
            raise TTSAdapterError(f'{provider.name} 不支持该运行方式（{channel}）')

    def ensure_voice_supported(self, voice: TTSVoice, controls: dict | None = None) -> None:
        """Reject a voice this card cannot speak with under these controls.

        Distinct from authorization: the company may be allowed to use the voice,
        yet the selected playback profile cannot render it.
        """
        return None

    def synthesize_pcm(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, controls: dict | None = None) -> bytes:
        raise NotImplementedError

    async def stream_realtime_text(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, exclude_patterns=None) -> None:
        raise TTSAdapterError(f'{self.provider_code} 暂不支持实时语音合成')

    async def prepare_realtime_stream(self, *, voice: TTSVoice, config: EffectiveTTSConfig, controls=None):
        """Open the upstream ahead of the first segment, if this card can.

        Returns a handle with an idempotent ``aclose()``, or ``None`` when the
        card has nothing to prewarm. Callers must treat ``None`` as normal and
        keep working — every ``stream_realtime_segments`` still opens its own
        upstream when handed no handle.
        """
        return None

    async def stream_realtime_segments(self, *, segments: AsyncIterable[str], voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, prepared=None) -> None:
        raise TTSAdapterError(f'{self.provider_code} 暂不支持实时语音合成')


_QWEN_LANGUAGE_TYPES = (
    'Auto', 'Chinese', 'English', 'German', 'Italian', 'Portuguese',
    'Spanish', 'Japanese', 'Korean', 'French', 'Russian',
)


class AliyunQwenTTSAdapter(BaseTTSAdapter):
    """Aliyun / Qwen realtime card — the pre-existing behaviour, unchanged."""

    provider_code = 'aliyun'
    schema_key = 'aliyun-qwen'
    supports_company_http_test = True
    supports_company_http_runtime = True
    supports_company_realtime = True
    config_fields = (
        ConfigField('model_code', '播报模型', 'select'),
        ConfigField('language_type', '语种', 'select', options=tuple({'value': item, 'label': item} for item in _QWEN_LANGUAGE_TYPES)),
        ConfigField('speech_rate', '语速', 'slider', minimum=0.5, maximum=2.0, step=0.05),
        ConfigField('pitch_rate', '音调', 'slider', minimum=0.5, maximum=2.0, step=0.05),
        ConfigField('volume', '音量', 'slider', minimum=0, maximum=100, step=1),
        ConfigField('bit_rate', '码率', 'slider', minimum=6, maximum=510, step=1),
        ConfigField('sample_rate', '采样率', 'select', options=({'value': 8000, 'label': '8000'}, {'value': 16000, 'label': '16000'}, {'value': 24000, 'label': '24000'}, {'value': 48000, 'label': '48000'})),
        ConfigField('instructions', '指令控制', 'textarea'),
        ConfigField('optimize_instructions', '优化指令', 'switch'),
        ConfigField('mode', '提交模式', 'select', options=({'value': 'server_commit', 'label': 'server_commit'}, {'value': 'commit', 'label': 'commit'})),
        ConfigField('response_format', '音频格式', 'select', options=({'value': 'pcm', 'label': 'pcm'}, {'value': 'wav', 'label': 'wav'}, {'value': 'mp3', 'label': 'mp3'}, {'value': 'opus', 'label': 'opus'})),
    )

    def public_model_options(self, provider: TTSProvider) -> list[dict[str, Any]]:
        return public_tts_model_profiles()

    def default_model_code(self, provider: TTSProvider) -> str:
        return get_tts_model_profile_code_from_session(
            getattr(provider, 'tts_session_config', None),
            provider.model,
        )

    def public_voice_capabilities(self, voice: TTSVoice) -> dict[str, bool]:
        return {'speechRate': True, 'pitchRate': True, 'volume': True}

    def ensure_voice_supported(self, voice: TTSVoice, controls: dict | None = None) -> None:
        from .tts import is_tts_voice_supported_by_model_code

        model_code = (controls or {}).get('model_code')
        if not model_code:
            return
        if not is_tts_voice_supported_by_model_code(voice, model_code):
            raise TTSAdapterError('所选音色不支持当前播报模型')

    def effective_config(self, provider: TTSProvider) -> EffectiveTTSConfig:
        return get_effective_tts_config(provider)

    def _coerce_controls(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Reuse the historical Qwen session normalizer so bounds stay identical."""
        provider_config = get_effective_tts_config(_qwen_provider())
        return _normalize_session_config(provider_config, raw)

    def synthesize_pcm(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, controls: dict | None = None) -> bytes:
        from .tts import synthesize_tts_pcm

        return synthesize_tts_pcm(text=text, voice=voice, config=config, session_config=controls)

    async def stream_realtime_text(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, exclude_patterns=None) -> None:
        from ..realtime_tts import _stream_tts_audio

        await _stream_tts_audio(
            text=text,
            voice=voice,
            config=config,
            send=send,
            session_config=controls,
            exclude_patterns=exclude_patterns,
        )

    async def stream_realtime_segments(self, *, segments: AsyncIterable[str], voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, prepared=None) -> None:
        from ..realtime_tts import _stream_tts_segments_audio

        # No prewarm on this card: ``prepared`` is always None here, and
        # ``_stream_tts_segments_audio`` keeps opening its own session.
        await _stream_tts_segments_audio(
            segments=segments,
            voice=voice,
            config=config,
            send=send,
            session_config=controls,
        )


class CosyVoiceTTSAdapter(BaseTTSAdapter):
    """CosyVoice v3.5-plus card.

    Upstream speaks the Model Studio task protocol (``run-task`` /
    ``continue-task`` / ``finish-task``); this adapter normalizes it to the same
    downstream contract every other card produces.
    """

    provider_code = 'cosyvoice'
    schema_key = 'cosyvoice'
    supports_company_http_test = True
    supports_company_http_runtime = True
    supports_company_realtime = True
    config_fields = (
        ConfigField('speech_rate', '语速', 'slider', minimum=0.5, maximum=2.0, step=0.05),
        ConfigField('pitch_rate', '音调', 'slider', minimum=0.5, maximum=2.0, step=0.05),
        ConfigField('volume', '音量', 'slider', minimum=0, maximum=100, step=1),
    )

    def default_model_code(self, provider: TTSProvider) -> str:
        from .cosyvoice import COSYVOICE_MODEL

        return COSYVOICE_MODEL

    def effective_config(self, provider: TTSProvider) -> EffectiveTTSConfig:
        from .cosyvoice import get_cosyvoice_settings, get_effective_cosyvoice_tts_config

        settings_obj = getattr(provider, 'cosyvoice_settings', None) or get_cosyvoice_settings()
        return get_effective_cosyvoice_tts_config(settings_obj)

    def _coerce_controls(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            'speech_rate': _bounded_float(raw.get('speech_rate'), 1.0, 0.5, 2.0),
            'pitch_rate': _bounded_float(raw.get('pitch_rate'), 1.0, 0.5, 2.0),
            'volume': _bounded_int(raw.get('volume'), 50, 0, 100),
        }

    def synthesize_pcm(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, controls: dict | None = None) -> bytes:
        from .tts import synthesize_tts_pcm

        return synthesize_tts_pcm(text=text, voice=voice, config=config, session_config=controls)

    async def stream_realtime_text(self, *, text: str, voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, exclude_patterns=None) -> None:
        from .cosyvoice_realtime import stream_cosyvoice_realtime_text

        await stream_cosyvoice_realtime_text(
            text=text,
            voice=voice,
            config=config,
            send=send,
            controls=self._coerce_controls(controls if isinstance(controls, dict) else {}),
            exclude_patterns=exclude_patterns,
        )

    async def prepare_realtime_stream(self, *, voice: TTSVoice, config: EffectiveTTSConfig, controls=None):
        from .cosyvoice_realtime import prewarm_cosyvoice_realtime

        return await prewarm_cosyvoice_realtime(
            voice=voice,
            config=config,
            controls=self._coerce_controls(controls if isinstance(controls, dict) else {}),
        )

    async def stream_realtime_segments(self, *, segments: AsyncIterable[str], voice: TTSVoice, config: EffectiveTTSConfig, send, controls=None, prepared=None) -> None:
        from .cosyvoice_realtime import stream_cosyvoice_realtime_segments

        await stream_cosyvoice_realtime_segments(
            segments=segments,
            voice=voice,
            config=config,
            send=send,
            controls=self._coerce_controls(controls if isinstance(controls, dict) else {}),
            prepared=prepared,
        )



_ADAPTERS: dict[str, BaseTTSAdapter] = {
    AliyunQwenTTSAdapter.provider_code: AliyunQwenTTSAdapter(),
    CosyVoiceTTSAdapter.provider_code: CosyVoiceTTSAdapter(),
}


def get_tts_provider_adapter(provider_code: str | None) -> BaseTTSAdapter:
    """Return the adapter for a card code, or raise — never silently fall back."""
    code = str(provider_code or '').strip()
    adapter = _ADAPTERS.get(code)
    if adapter is None:
        raise TTSAdapterError(f'TTS 卡片 {code or "(空)"} 暂未接入')
    return adapter


def get_adapter_for_voice(voice: TTSVoice) -> BaseTTSAdapter:
    """Route by the resolved voice's own card, not by any client-sent code."""
    if voice is None or getattr(voice, 'provider', None) is None:
        raise TTSAdapterError('音色未绑定 TTS 卡片')
    return get_tts_provider_adapter(voice.provider.code)


def has_tts_provider_adapter(provider_code: str | None) -> bool:
    return str(provider_code or '').strip() in _ADAPTERS


def _qwen_provider() -> TTSProvider:
    from .tts import get_aliyun_tts_provider

    return get_aliyun_tts_provider()
