from __future__ import annotations

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder


_REDACTED_KEYS = frozenset({
    'api_key', 'apikey', 'authorization', 'token', 'secret', 'password',
    'audio', 'audio_data', 'input_audio', 'pcm', 'audiobase64', 'audio_base64',
})


def log_voice_pipeline(logger, event_name: str, stage: str, *, command_id, request_id: str, trace_id: str, device_code: str, payload: dict[str, Any]) -> None:
    logger.info(
        '%s stage=%s agent_session=%s request_id=%s trace_id=%s device_code=%s payload=%s',
        event_name,
        stage,
        command_id,
        request_id,
        trace_id,
        device_code,
        json.dumps(_redact_value(payload), cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True),
    )


def _redact_value(value):
    if isinstance(value, dict):
        return {
            key: '[REDACTED]' if str(key).lower() in _REDACTED_KEYS else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f'[REDACTED_BINARY:{len(value)}]'
    return value
