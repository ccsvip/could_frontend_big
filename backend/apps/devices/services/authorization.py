from __future__ import annotations

from django.utils import timezone

from apps.devices.models import Device, DeviceAuthLog
from apps.devices.realtime import publish_device_event_sync


def bind_device_authorization(device: Device, serializer) -> Device:
    return serializer.save(device=device)


def ignore_device_authorization_request(device: Device) -> Device:
    device.authorization_ignored_at = timezone.now()
    device.save(update_fields=['authorization_ignored_at', 'updated_at'])
    return device


def rename_authorization_device(device: Device, name: str) -> Device:
    device.name = name
    device.save(update_fields=['name', 'updated_at'])
    return device


def revoke_device_authorization(device: Device) -> Device:
    device.is_enabled = False
    device.status = Device.STATUS_OFFLINE
    device.save(update_fields=['is_enabled', 'status', 'updated_at'])
    return device


def record_device_authorization_action(
    device: Device,
    action: str,
    message: str,
    *,
    ip_address: str | None = None,
) -> DeviceAuthLog:
    return DeviceAuthLog.objects.create(
        tenant=device.tenant,
        application=device.application,
        agent_application=device.agent_application,
        device=device,
        code=device.code,
        action=action,
        result=True,
        message=message,
        ip_address=ip_address,
        device_info=authorization_device_snapshot(device),
    )


def authorization_device_snapshot(device: Device) -> dict:
    return {
        'tenantId': device.tenant_id,
        'applicationId': device.application_id,
        'agentApplicationId': device.agent_application_id,
        'groupId': device.group_id,
        'authorizationType': device.authorization_type,
        'expiresAt': device.expires_at.isoformat() if device.expires_at else None,
        'isEnabled': device.is_enabled,
    }


def publish_device_authorization_event(device: Device, action: str) -> None:
    publish_device_event_sync(
        {
            'type': 'device.authorization',
            'action': action,
            'tenantId': device.tenant_id,
            'applicationId': device.application_id,
            'agentApplicationId': device.agent_application_id,
            'groupId': device.group_id,
            'deviceCode': device.code,
            'status': device.status,
            'isEnabled': device.is_enabled,
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': 'authorizationChanged',
            },
        }
    )
