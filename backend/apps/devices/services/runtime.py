from __future__ import annotations

from dataclasses import dataclass

from rest_framework import status

from apps.devices.models import Device


@dataclass(slots=True)
class RuntimeDeviceError(Exception):
    message: str
    status_code: int


def get_runtime_device(device_code: str, *, require_tenant: bool = False) -> Device:
    """Resolve and validate an Android runtime device by deviceCode.

    This is the shared seam for public device runtime endpoints and realtime
    device identity. It intentionally returns domain errors rather than DRF
    responses so callers can choose their own transport shape.
    """
    device_code = str(device_code or '').strip()
    if not device_code:
        raise RuntimeDeviceError('设备码不能为空', status.HTTP_400_BAD_REQUEST)

    devices = list(
        Device.objects.select_related('tenant', 'application__agent_application', 'agent_application')
        .filter(code=device_code)
        .order_by('id')[:2]
    )
    if not devices:
        raise RuntimeDeviceError('设备未登记', status.HTTP_404_NOT_FOUND)
    if len(devices) > 1:
        raise RuntimeDeviceError('设备码存在重复绑定，请联系后台处理', status.HTTP_409_CONFLICT)

    device = devices[0]
    if require_tenant and device.tenant_id is None:
        raise RuntimeDeviceError('设备未绑定公司', status.HTTP_403_FORBIDDEN)
    if device.tenant is not None and not device.tenant.is_active:
        raise RuntimeDeviceError('公司已停用', status.HTTP_403_FORBIDDEN)
    if not device.is_enabled:
        raise RuntimeDeviceError('设备已停用', status.HTTP_403_FORBIDDEN)
    if device.is_expired:
        raise RuntimeDeviceError('设备授权已过期', status.HTTP_403_FORBIDDEN)
    return device


def get_runtime_device_or_none(device_code: str, *, require_tenant: bool = True) -> Device | None:
    try:
        return get_runtime_device(device_code, require_tenant=require_tenant)
    except RuntimeDeviceError:
        return None
