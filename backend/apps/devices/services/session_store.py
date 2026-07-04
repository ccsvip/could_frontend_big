"""
Device voice-chat session store.

Stores recent conversation turns in Redis (via Django cache) so that
``_generate_answer`` can load multi-turn history for the LLM.

Key format:  device:voice_session:{device_code}:{session_id}
Value:       JSON list of ``{"role": ..., "content": ...}`` dicts
TTL:         30 minutes (auto-evicted by Redis / Django cache)
Max turns:   10 (oldest dropped when exceeded)
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_PREFIX = 'device:voice_session:'
_TTL_SECONDS = 30 * 60  # 30 minutes
_MAX_TURNS = 10


def _cache_key(device_code: str, session_id: str) -> str:
    return f'{_CACHE_PREFIX}{device_code}:{session_id}'


def get_history(device_code: str, session_id: str) -> list[dict[str, str]]:
    """Return the conversation history for this session, or an empty list."""
    raw = cache.get(_cache_key(device_code, session_id))
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        logger.warning('device.session_store.corrupt key=%s', _cache_key(device_code, session_id))
    return []


def append_turn(
    device_code: str,
    session_id: str,
    role: Literal['user', 'assistant', 'system'],
    content: str,
) -> None:
    """Append a single turn and persist, enforcing ``_MAX_TURNS``."""
    key = _cache_key(device_code, session_id)
    raw = cache.get(key)
    turns: list[dict[str, str]] = []
    if raw:
        try:
            turns = json.loads(raw)
            if not isinstance(turns, list):
                turns = []
        except (json.JSONDecodeError, TypeError):
            turns = []

    turns.append({'role': role, 'content': str(content)})

    # Keep only the most recent turns (drop oldest when exceeding limit).
    if len(turns) > _MAX_TURNS:
        turns = turns[-_MAX_TURNS:]

    cache.set(key, json.dumps(turns, ensure_ascii=False), timeout=_TTL_SECONDS)


def clear_session(device_code: str, session_id: str) -> None:
    """Delete a session's history (used by explicit reset)."""
    cache.delete(_cache_key(device_code, session_id))
