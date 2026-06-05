from __future__ import annotations

from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.utils import timezone

from .models import Device, DeviceAuthLog
from .realtime import publish_device_event


async def device_status_websocket_application(scope, receive, send):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    device_code = (params.get('deviceCode') or params.get('device_code') or [''])[0].strip()
    if not device_code:
        await send({'type': 'websocket.close', 'code': 4400})
        return

    device = await sync_to_async(_mark_device_online, thread_sensitive=True)(device_code)
    if device is None:
        await send({'type': 'websocket.close', 'code': 4404})
        return
    await publish_device_event(_device_status_event(device, Device.STATUS_ONLINE))

    await send({'type': 'websocket.accept'})
    try:
        while True:
            event = await receive()
            if event['type'] == 'websocket.disconnect':
                break
            if event['type'] == 'websocket.receive':
                await sync_to_async(_touch_device, thread_sensitive=True)(device.id)
                if event.get('text') == 'ping':
                    await send({'type': 'websocket.send', 'text': 'pong'})
    finally:
        offline_event = await sync_to_async(_mark_device_offline, thread_sensitive=True)(device.id)
        if offline_event is not None:
            await publish_device_event(offline_event)


def _mark_device_online(device_code: str) -> Device | None:
    device = (
        Device.objects.select_related('tenant', 'application')
        .filter(code=device_code)
        .order_by('id')
        .first()
    )
    if device is None or not device.is_enabled or device.is_expired:
        return None
    now = timezone.now()
    device.status = Device.STATUS_ONLINE
    device.last_heartbeat = now
    device.save(update_fields=['status', 'last_heartbeat', 'updated_at'])
    DeviceAuthLog.objects.create(
        tenant=device.tenant,
        application=device.application,
        device=device,
        code=device.code,
        action=DeviceAuthLog.ACTION_HEARTBEAT,
        result=True,
        message='WebSocket 在线连接成功',
    )
    return device


def _touch_device(device_id: int) -> None:
    Device.objects.filter(id=device_id).update(last_heartbeat=timezone.now(), updated_at=timezone.now())


def _mark_device_offline(device_id: int) -> dict | None:
    device = Device.objects.select_related('tenant', 'application').filter(id=device_id).first()
    if device is None:
        return None
    device.status = Device.STATUS_OFFLINE
    device.save(update_fields=['status', 'updated_at'])
    return _device_status_event(device, Device.STATUS_OFFLINE)


def _device_status_event(device: Device, status: str) -> dict:
    return {
        'type': 'device.status',
        'tenantId': device.tenant_id,
        'applicationId': device.application_id,
        'deviceCode': device.code,
        'status': status,
        'isEnabled': device.is_enabled,
    }
