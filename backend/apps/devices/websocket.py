from __future__ import annotations

from django.utils import timezone

from .models import Device, DeviceAuthLog
from .services.runtime import get_runtime_device_or_none


def mark_device_online_for_websocket(device_code: str) -> Device | None:
    device = get_runtime_device_or_none(device_code, require_tenant=False)
    if device is None:
        return None
    now = timezone.now()
    device.status = Device.STATUS_ONLINE
    device.last_heartbeat = now
    device.save(update_fields=['status', 'last_heartbeat', 'updated_at'])
    DeviceAuthLog.objects.create(
        tenant=device.tenant,
        application=device.application,
        agent_application=device.agent_application,
        device=device,
        code=device.code,
        action=DeviceAuthLog.ACTION_HEARTBEAT,
        result=True,
        message='WebSocket 在线连接成功',
    )
    return device


def touch_device_for_websocket(device_id: int) -> None:
    Device.objects.filter(id=device_id).update(last_heartbeat=timezone.now(), updated_at=timezone.now())


def mark_device_offline_for_websocket(device_id: int) -> dict | None:
    device = Device.objects.select_related('tenant', 'application__agent_application', 'agent_application').filter(id=device_id).first()
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
        'agentApplicationId': device.effective_agent_application.id if device.effective_agent_application else None,
        'deviceCode': device.code,
        'status': status,
        'isEnabled': device.is_enabled,
    }
