from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync, sync_to_async
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.services.permissions import get_active_permission_codes_for_user
from apps.tenants.services import get_user_tenant


@dataclass(frozen=True)
class DeviceEventSubscriber:
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop
    tenant_id: int | None


_subscribers: set[DeviceEventSubscriber] = set()
_subscribers_lock = threading.Lock()


async def device_events_websocket_application(scope, receive, send):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    token = (params.get('token') or [''])[0].strip()
    tenant_id_param = (params.get('tenantId') or params.get('tenant') or [''])[0].strip()

    connection = await sync_to_async(_resolve_connection, thread_sensitive=True)(token, tenant_id_param)
    if connection is None:
        await send({'type': 'websocket.close', 'code': 4401})
        return

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    subscriber = DeviceEventSubscriber(
        queue=queue,
        loop=asyncio.get_running_loop(),
        tenant_id=connection['tenant_id'],
    )
    with _subscribers_lock:
        _subscribers.add(subscriber)

    await send({'type': 'websocket.accept'})
    receive_task = asyncio.create_task(receive())
    try:
        while True:
            queue_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {receive_task, queue_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if queue_task not in done:
                queue_task.cancel()

            if receive_task in done:
                event = receive_task.result()
                if event['type'] == 'websocket.disconnect':
                    break
                if event.get('text') == 'ping':
                    await send({'type': 'websocket.send', 'text': json.dumps({'type': 'pong'})})
                receive_task = asyncio.create_task(receive())

            if queue_task in done:
                payload = queue_task.result()
                await send({'type': 'websocket.send', 'text': json.dumps(payload)})
    finally:
        if not receive_task.done():
            receive_task.cancel()
        with _subscribers_lock:
            _subscribers.discard(subscriber)


async def publish_device_event(event: dict) -> None:
    tenant_id = event.get('tenantId')
    if tenant_id is not None:
        _invalidate_device_stats(tenant_id)

    with _subscribers_lock:
        subscribers = list(_subscribers)

    for subscriber in subscribers:
        if subscriber.tenant_id is not None and subscriber.tenant_id != tenant_id:
            continue
        subscriber.loop.call_soon_threadsafe(_put_event, subscriber.queue, event)


def publish_device_event_sync(event: dict) -> None:
    async_to_sync(publish_device_event)(event)


def _put_event(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(event)


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
