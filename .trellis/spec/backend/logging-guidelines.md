# Logging Guidelines

> Structured logging conventions, configuration, and redaction rules for the backend.

---

## Overview

This project uses **Python standard library `logging`** with Django REST Framework. There is no third-party logging library (no structlog, no loguru). All logging follows a structured key-value convention using `%`-style formatting.

The logging configuration lives in `backend/config/settings/base.py` and applies across all environments (dev, prod).

---

## Logging Configuration

Defined in `backend/config/settings/base.py:36-73`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'console',
        },
    },
    'loggers': {
        'apps.devices': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'config.realtime': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.ai_models.services.third_party_chatbots': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'drf_spectacular': {
            'handlers': ['console'],
            'level': 'CRITICAL',
            'propagate': False,
        },
    },
}
```

Key points:
- **Formatter**: plain text `%(levelname)s %(name)s %(message)s` — no JSON output.
- **Handler**: single `StreamHandler` (stdout/stderr) at `INFO` level.
- **No root logger** defined. Unmatched loggers inherit Django's default (`WARNING`).
- **Only three application loggers** are explicitly configured: `apps.devices`, `config.realtime`, and `apps.ai_models.services.third_party_chatbots` — all at `INFO`.
- **`drf_spectacular`** is set to `CRITICAL` to suppress OpenAPI schema generation noise.
- **No environment variable** overrides the log level; to raise/lower a logger's level, edit `base.py` or set `DJANGO_LOG_LEVEL` through Django's default root logger handling (though no root logger is defined here).

---

## Logger Name Convention

Every module MUST use:

```python
import logging

logger = logging.getLogger(__name__)
```

This produces the **dotted module path** as the logger name, e.g.:

| Module | Logger name |
|--------|-------------|
| `backend/apps/devices/views.py` | `apps.devices.views` |
| `backend/config/realtime.py` | `config.realtime` |
| `backend/apps/resources/services/command_dispatch.py` | `apps.resources.services.command_dispatch` |
| `backend/apps/ai_models/realtime_tts.py` | `apps.ai_models.realtime_tts` |

**Rules**:
- Always use `__name__`. Never hardcode a string like `logging.getLogger('my_logger')`.
- The logger name MUST match the import path so that `LOGGING['loggers']` can filter by prefix (e.g., `apps.devices` catches all devices submodules).

---

## Structured Logging Convention

Although the formatter is plain text, the project follows a **de facto structured format** using space-separated key-value pairs.

### Format

```
<LEVEL> <dotted.module.path> <event_key> key=value key=value ... payload={...}
```

- **`<event_key>`**: A dotted event name as the first word of the message (e.g., `tts.realtime.connecting`, `chat.send.received`, `command_dispatch.completed`).
- **key=value pairs**: Space-separated, no quoting around values unless the value may contain spaces (use `%s` formatting).
- **Complex payloads**: Serialized with `json.dumps(...)` as `payload={...}`.

### Examples from the codebase

```python
# TTS lifecycle (apps/ai_models/realtime_tts.py)
logger.info(
    'tts.realtime.connecting mode=single model=%s voice=%s sample_rate=%s text_chars=%s options=%s',
    tts_session.get('model'),
    voice.voice_code,
    sample_rate,
    len(text),
    connect_options,
)
# Output: INFO apps.ai_models.realtime_tts tts.realtime.connecting mode=single model=qwen3-tts-flash-realtime voice=Cherry sample_rate=24000 text_chars=42 options={'max_size': 8388608}

# Chat send lifecycle (apps/ai_models/views.py)
logger.info(
    'chat.send.received conversation_id=%s user_id=%s content_length=%s use_stream=%s',
    conversation.id,
    request.user.id,
    len(content),
    use_stream,
)
# Output: INFO apps.ai_models.views chat.send.received conversation_id=42 user_id=7 content_length=156 use_stream=True

# Command dispatch (apps/resources/services/command_dispatch.py)
logger.info(
    'command_dispatch.completed tenant=%s hits=%s reply_length=%s',
    tenant_id,
    len(executed_calls),
    len(reply_text),
)
# Output: INFO apps.resources.services.command_dispatch command_dispatch.completed tenant=t-abc123 hits=3 reply_length=892
```

### Event naming convention

Use **dotted hierarchical event names** as the first word of the log message:

| Component | Event key pattern | Examples |
|-----------|-------------------|----------|
| TTS realtime | `tts.realtime.<event>` | `tts.realtime.connecting`, `tts.realtime.connected`, `tts.realtime.text_prepared`, `tts.realtime.upstream_error`, `tts.realtime.failed` |
| Chat | `chat.<event>` | `chat.send.received`, `chat.send.dispatch`, `chat.send.completed_sse`, `chat.send.http_error`, `chat.title.generated`, `chat.conversation.config_updated` |
| Command dispatch | `command_dispatch.<event>` | `command_dispatch.completed`, `command_dispatch.selection_failed`, `command_dispatch.llm_first_round_failed`, `command_dispatch.local_completed` |
| Command executor | `command_executor.<event>` | `command_executor.dispatched`, `command_executor.timeout`, `command_executor.send_failed` |
| Realtime WebSocket | `realtime.<event>` | `realtime.agent.session_closed`, `realtime.agent.tts_started`, `realtime.websocket.closed`, `realtime.websocket.disconnect` |
| Device session | `device.session_store.<event>` | `device.session_store.corrupt` |

### Use `%s`-style formatting only

All log calls use `%`-style formatting (the first argument is the format string, followed by positional args). **Never use f-strings or `.format()` in log calls** — the logging framework defers string interpolation until the log level is confirmed.

```python
# ✅ Correct — deferred interpolation
logger.warning('command_executor.timeout command=%s host=%s latency_ms=%s', cmd.command_code, cmd.host, latency_ms)

# ❌ Wrong — eager interpolation, wastes work if the log line is filtered
logger.warning(f'command_executor.timeout command={cmd.command_code}')
```

### Exception logging

Use `logger.exception()` inside `except` blocks to include the traceback:

```python
# ✅ Correct — includes full traceback
except Exception:
    logger.exception('realtime.asr.close_upstream_failed')

# ✅ Also correct — with event key and context
except Exception:
    logger.exception(
        'realtime.agent.asr_finish_failed agent_session=%s request_id=%s trace_id=%s',
        connection.agent_session_id,
        connection.agent_request_id,
        connection.agent_trace_id,
    )
```

**Rule**: `logger.exception()` MUST only be used inside an `except` block. The traceback is automatically appended.

---

## Log Levels

| Level | When to use |
|-------|-------------|
| `DEBUG` | Development-only diagnostics. Not used in production paths (no `DEBUG` loggers are configured in `base.py`). |
| `INFO` | Normal lifecycle events: connection established, message sent/received, dispatch completed, TTS segment prepared. This is the default production level. |
| `WARNING` | Recoverable issues: timeout, non-critical failure, unexpected but non-fatal state, third-party service unavailable, corrupt cache data. |
| `ERROR` | Operation failures that prevent a single request from completing but don't crash the process: upstream connection closed, HTTP error from provider, incomplete MinIO settings. |
| `CRITICAL` | Catastrophic failures. Currently only used for `drf_spectacular` suppression. |

---

## Voice Pipeline Logging (ASR/TTS Lifecycle)

Voice pipeline events (ASR recognition, TTS synthesis, agent voice interactions) MUST use the shared `log_voice_pipeline` helper instead of raw `logger.info()`.

### Location

`backend/apps/devices/services/voice_pipeline_logging.py`

### Signature

```python
def log_voice_pipeline(
    logger,
    event_name: str,
    stage: str,
    *,
    command_id,
    request_id: str,
    trace_id: str,
    device_code: str,
    payload: dict[str, Any],
) -> None:
```

### Output format

```
INFO <module> <event_name> stage=<stage> agent_session=<command_id> request_id=<request_id> trace_id=<trace_id> device_code=<device_code> payload=<json>
```

### Usage

```python
from apps.devices.services.voice_pipeline_logging import log_voice_pipeline

log_voice_pipeline(
    logger,
    'realtime.agent.tts_started',      # event_name
    'tts_start',                         # stage
    command_id=command_id,
    request_id=request_id,
    trace_id=trace_id,
    device_code=device_code,
    payload={'first_segment_length': len(first_segment), 'model': model_name},
)
```

### Callers in the codebase

The helper is called from:
- `backend/config/realtime.py` — `_log_agent_voice_pipeline()` wraps it for agent voice lifecycle events.
- `backend/apps/devices/views.py` — `_log_http_voice_pipeline()` wraps it for HTTP-triggered voice pipeline events.

---

## Sensitive Data Redaction

### Redacted fields

Defined in `voice_pipeline_logging.py` as `_REDACTED_KEYS`:

```python
_REDACTED_KEYS = frozenset({
    'api_key', 'apikey', 'authorization', 'token', 'secret', 'password',
    'audio', 'audio_data', 'input_audio', 'pcm', 'audiobase64', 'audio_base64',
})
```

### How redaction works

The `_redact_value()` function recursively walks dicts, lists, and tuples:
- **Dict keys** matching any redacted field (case-insensitive comparison after lowercasing) are replaced with the literal string `[REDACTED]`.
- **`bytes`/`bytearray`/`memoryview`** values at any depth are replaced with `[REDACTED_BINARY:<length>]`.
- All other values pass through unchanged.

### When to redact

- **Always** use `log_voice_pipeline()` for ASR/TTS lifecycle events — it applies redaction automatically via `json.dumps(_redact_value(payload), ...)`.
- For **all other log calls**, redact manually: never log `api_key`, `token`, `secret`, `password`, raw audio bytes (`pcm`, `audio`, `audio_data`, `audiobase64`, `audio_base64`), or `authorization` headers.
- If you are logging a dict that may contain sensitive keys, use the same `_redact_value()` pattern — or better, extract only the non-sensitive fields explicitly.

---

## Forbidden Patterns

1. **❌ Hardcoded logger names**
   ```python
   logger = logging.getLogger('my_app')  # Wrong — use __name__
   ```

2. **❌ F-strings or `.format()` in log calls**
   ```python
   logger.info(f'event key={key}')  # Wrong — eager evaluation
   ```

3. **❌ Logging raw audio data or binary payloads**
   ```python
   logger.info('audio length=%s', len(audio_data))  # Wrong — even length may leak; use [REDACTED_BINARY:N]
   ```

4. **❌ Logging API keys, tokens, secrets, or passwords**
   ```python
   logger.info('api_key=%s', api_key)  # Wrong — never log credentials
   ```

5. **❌ Using `logger.exception()` outside an `except` block**
   ```python
   logger.exception('something happened')  # Wrong — no active exception, no traceback to log
   ```

6. **❌ Sending sensitive data in `payload=` without redaction**
   ```python
   logger.info('event payload=%s', json.dumps(raw_dict))  # Wrong — may contain audio or tokens
   ```

---

## Common Mistakes

- **Forgetting to use `log_voice_pipeline()` for voice events**: Raw `logger.info()` calls in voice pipeline code may leak audio data or API tokens. Always route ASR/TTS lifecycle events through the shared helper.
- **Using `logger.exception()` without an active exception**: The logging framework will record "No exception" as the traceback. Only use it in `except` blocks.
- **Assuming JSON output**: The formatter is plain text (`%(message)s`). Do not rely on JSON parsing of log output. The structured convention is for human readability and grep-based analysis.
- **Missing event key**: Every log line should start with a dotted event key. A bare message like "connecting to upstream" without `tts.realtime.connecting` makes filtering impossible.
