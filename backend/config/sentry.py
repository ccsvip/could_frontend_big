from __future__ import annotations

from collections.abc import Mapping
from typing import Any


Event = dict[str, Any]


def _coerce_text(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _event_message(event: Mapping[str, Any]) -> str:
    messages = [_coerce_text(event.get('message'))]
    logentry = event.get('logentry')
    if isinstance(logentry, Mapping):
        messages.append(_coerce_text(logentry.get('message')))
        messages.append(_coerce_text(logentry.get('formatted')))
    return '\n'.join(message for message in messages if message)


def _event_exception_text(event: Mapping[str, Any]) -> str:
    exception = event.get('exception')
    if not isinstance(exception, Mapping):
        return ''

    values = exception.get('values')
    if not isinstance(values, list):
        return ''

    parts: list[str] = []
    for item in values:
        if not isinstance(item, Mapping):
            continue
        parts.append(_coerce_text(item.get('type')))
        parts.append(_coerce_text(item.get('value')))
    return '\n'.join(part for part in parts if part)


def _argv(event: Mapping[str, Any]) -> list[str]:
    extra = event.get('extra')
    if not isinstance(extra, Mapping):
        return []

    argv = extra.get('sys.argv')
    if isinstance(argv, list):
        return [_coerce_text(item) for item in argv]
    if isinstance(argv, tuple):
        return [_coerce_text(item) for item in argv]
    if argv:
        return [_coerce_text(argv)]
    return []


def _is_celery_role(event: Mapping[str, Any], role: str) -> bool:
    argv = _argv(event)
    return any(part.endswith('/celery') or part == 'celery' for part in argv) and role in argv


def _is_expected_celery_worker_broker_retry(event: Mapping[str, Any]) -> bool:
    if not _is_celery_role(event, 'worker'):
        return False

    message = _event_message(event)
    return (
        'Cannot connect to redis://' in message
        and 'Connection refused' in message
        and 'Trying again in' in message
    )


def _is_expected_celery_beat_database_shutdown(event: Mapping[str, Any]) -> bool:
    if not _is_celery_role(event, 'beat'):
        return False

    text = '\n'.join([_event_message(event), _event_exception_text(event)])
    return 'terminating connection due to administrator command' in text


def before_send(event: Event, hint: Mapping[str, Any]) -> Event | None:
    if _is_expected_celery_worker_broker_retry(event):
        return None
    if _is_expected_celery_beat_database_shutdown(event):
        return None
    return event
