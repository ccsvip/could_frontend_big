from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

from asgiref.sync import async_to_sync
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.tenants.services import get_user_tenant
from .services.runtime import get_runtime_device_or_none


@dataclass(frozen=True)
class DeviceEventSubscriber:
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop
    tenant_id: int | None
    device_code: str | None = None


_subscribers: set[DeviceEventSubscriber] = set()
_subscribers_lock = threading.Lock()


async def publish_device_event(event: dict) -> None:
    tenant_id = event.get('tenantId')
    if tenant_id is not None:
        _invalidate_device_stats(tenant_id)

    with _subscribers_lock:
        subscribers = list(_subscribers)

    for subscriber in subscribers:
        if subscriber.tenant_id is not None and subscriber.tenant_id != tenant_id:
            continue
        if subscriber.device_code is not None and not _event_targets_device(event, subscriber.device_code):
            continue
        subscriber.loop.call_soon_threadsafe(_put_event, subscriber.queue, event)


def publish_device_event_sync(event: dict) -> None:
    async_to_sync(publish_device_event)(event)


def resolve_device_event_subscription(token: str, tenant_id_param: str) -> dict | None:
    return _resolve_connection(token, tenant_id_param)


def resolve_runtime_config_event_subscription(device_code: str) -> dict | None:
    device = get_runtime_device_or_none(device_code, require_tenant=True)
    if device is None:
        return None
    return {'tenant_id': device.tenant_id, 'device_code': device.code}


def add_device_event_subscriber(tenant_id: int | None, device_code: str | None = None) -> DeviceEventSubscriber:
    subscriber = DeviceEventSubscriber(
        queue=asyncio.Queue(maxsize=100),
        loop=asyncio.get_running_loop(),
        tenant_id=tenant_id,
        device_code=device_code,
    )
    with _subscribers_lock:
        _subscribers.add(subscriber)
    return subscriber


def remove_device_event_subscriber(subscriber: DeviceEventSubscriber) -> None:
    with _subscribers_lock:
        _subscribers.discard(subscriber)


def _put_event(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(event)


def _event_targets_device(event: dict, device_code: str) -> bool:
    device_code = str(device_code or '').strip()
    if not device_code:
        return False

    # Device-code subscribers are runtime devices. They should receive only
    # runtime-config invalidation events, not the management/status firehose.
    if not event.get('refresh') and str(event.get('type') or '') != 'device.wake_words.changed':
        return False

    event_device_code = str(event.get('deviceCode') or event.get('device_code') or '').strip()
    if event_device_code == device_code:
        return True

    raw_codes = event.get('deviceCodes') or event.get('device_codes') or []
    if not isinstance(raw_codes, (list, tuple, set)):
        return False
    return device_code in {str(code).strip() for code in raw_codes}


def _resolve_connection(token: str, tenant_id_param: str) -> dict | None:
    if not token:
        return None

    try:
        authentication = JWTAuthentication()
        validated_token = authentication.get_validated_token(token)
        user = authentication.get_user(validated_token)
    except Exception:
        return None

    if not user or not user.is_authenticated:
        return None

    if not user.is_superuser and 'devices.view' not in get_active_permission_codes_for_user(user):
        return None

    if user.is_superuser:
        tenant_id = _parse_positive_int(tenant_id_param)
    else:
        tenant = get_user_tenant(user)
        if tenant is None:
            return None
        tenant_id = tenant.id

    return {'user_id': user.id, 'tenant_id': tenant_id}


def _parse_positive_int(value: str) -> int | None:
    if not value or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _invalidate_device_stats(tenant_id: int) -> None:
    cache.delete_many(
        [
            f'device_stats:{tenant_id}',
            f'device_stats:scoped:{tenant_id}',
            'device_stats:all',
        ]
    )
