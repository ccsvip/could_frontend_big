from __future__ import annotations

from typing import Any

from apps.ai_models.models import default_tts_session_config
from apps.ai_models.services import tts as tts_services


DEVICE_TTS_VOICE_CONFIG_KEYS = ('speech_rate', 'pitch_rate', 'volume')
_DEFAULT_CONFIG = default_tts_session_config()


def _first(raw: dict[str, Any], snake_key: str, camel_key: str):
    if snake_key in raw:
        return raw.get(snake_key)
    if camel_key in raw:
        return raw.get(camel_key)
    return None


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


def normalize_device_tts_voice_config(value: dict | None, base_config: dict | None = None) -> dict:
    raw = value if isinstance(value, dict) else {}
    base = base_config if isinstance(base_config, dict) else _DEFAULT_CONFIG
    return {
        'speech_rate': _bounded_float(
            _first(raw, 'speech_rate', 'speechRate'),
            _bounded_float(base.get('speech_rate') or base.get('speechRate'), 1.0, 0.5, 2.0),
            0.5,
            2.0,
        ),
        'pitch_rate': _bounded_float(
            _first(raw, 'pitch_rate', 'pitchRate'),
            _bounded_float(base.get('pitch_rate') or base.get('pitchRate'), 1.0, 0.5, 2.0),
            0.5,
            2.0,
        ),
        'volume': _bounded_int(
            _first(raw, 'volume', 'volume'),
            _bounded_int(base.get('volume'), 50, 0, 100),
            0,
            100,
        ),
    }


def has_device_tts_voice_config(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return any(key in value for key in ('speech_rate', 'speechRate', 'pitch_rate', 'pitchRate', 'volume'))


def company_tts_session_config_for_device(device, provider=None) -> dict:
    config = tts_services.get_effective_tts_config(provider)
    settings_obj = tts_services.get_tenant_tts_settings(getattr(device, 'tenant', None))
    if settings_obj is not None and isinstance(settings_obj.tts_session_config, dict):
        return {**config.tts_session_config, **settings_obj.tts_session_config}
    return dict(config.tts_session_config)


def device_tts_session_config(device, provider=None) -> dict:
    base = company_tts_session_config_for_device(device, provider)
    controls = normalize_device_tts_voice_config(getattr(device, 'tts_voice_config', None), base)
    return {**base, **controls}


def public_device_tts_voice_config(device, provider=None) -> dict:
    config = normalize_device_tts_voice_config(
        getattr(device, 'tts_voice_config', None),
        company_tts_session_config_for_device(device, provider),
    )
    return {
        'speechRate': config['speech_rate'],
        'pitchRate': config['pitch_rate'],
        'volume': config['volume'],
    }
