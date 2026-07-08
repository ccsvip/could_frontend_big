from __future__ import annotations

from dataclasses import dataclass

from rest_framework import status

from apps.devices.models import Device


@dataclass(slots=True)
class RuntimeDeviceError(Exception):
    message: str
    status_code: int
    code: str = 'DEVICE_RUNTIME_ERROR'
    business_status_code: int = 44000

    def as_payload(self) -> dict[str, object]:
        return {
            'code': self.code,
            'statusCode': self.business_status_code,
            'message': self.message,
        }


RUNTIME_ERROR_EMPTY_DEVICE_CODE = ('DEVICE_CODE_REQUIRED', 44001)
RUNTIME_ERROR_DEVICE_NOT_REGISTERED = ('DEVICE_NOT_REGISTERED', 44004)
RUNTIME_ERROR_DUPLICATE_DEVICE_CODE = ('DEVICE_CODE_DUPLICATED', 44009)
RUNTIME_ERROR_DEVICE_UNBOUND_TENANT = ('DEVICE_TENANT_UNBOUND', 44011)
RUNTIME_ERROR_TENANT_DISABLED = ('DEVICE_TENANT_DISABLED', 44012)
RUNTIME_ERROR_DEVICE_DISABLED = ('DEVICE_DISABLED', 44013)
RUNTIME_ERROR_DEVICE_EXPIRED = ('DEVICE_EXPIRED', 44014)
RUNTIME_ERROR_AGENT_UNBOUND = ('DEVICE_AGENT_UNBOUND', 44021)
RUNTIME_ERROR_APPLICATION_INACTIVE = ('DEVICE_APPLICATION_INACTIVE', 44022)


def runtime_device_error(message: str, status_code: int, error: tuple[str, int]) -> RuntimeDeviceError:
    code, business_status_code = error
    return RuntimeDeviceError(message, status_code, code, business_status_code)


def get_runtime_device(device_code: str, *, require_tenant: bool = False) -> Device:
    """Resolve and validate an Android runtime device by deviceCode.

    This is the shared seam for public device runtime endpoints and realtime
    device identity. It intentionally returns domain errors rather than DRF
    responses so callers can choose their own transport shape.
    """
    device_code = str(device_code or '').strip()
    if not device_code:
        raise runtime_device_error('设备码不能为空', status.HTTP_400_BAD_REQUEST, RUNTIME_ERROR_EMPTY_DEVICE_CODE)

    devices = list(
        Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'tts_voice__provider')
        .filter(code=device_code)
        .order_by('id')[:2]
    )
    if not devices:
        raise runtime_device_error('设备未登记', status.HTTP_404_NOT_FOUND, RUNTIME_ERROR_DEVICE_NOT_REGISTERED)
    if len(devices) > 1:
        raise runtime_device_error('设备码存在重复绑定，请联系后台处理', status.HTTP_409_CONFLICT, RUNTIME_ERROR_DUPLICATE_DEVICE_CODE)

    device = devices[0]
    if require_tenant and device.tenant_id is None:
        raise runtime_device_error('设备未绑定公司', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_UNBOUND_TENANT)
    if device.tenant is not None and not device.tenant.is_active:
        raise runtime_device_error('公司已停用', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_TENANT_DISABLED)
    if not device.is_enabled:
        raise runtime_device_error('设备已停用', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_DISABLED)
    if device.is_expired:
        raise runtime_device_error('设备授权已过期', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_EXPIRED)
    return device


def get_runtime_device_or_none(device_code: str, *, require_tenant: bool = True) -> Device | None:
    try:
        return get_runtime_device(device_code, require_tenant=require_tenant)
    except RuntimeDeviceError:
        return None


def validate_runtime_application_active(device: Device) -> None:
    application = getattr(device, 'application', None)
    if application is not None and not application.is_active:
        raise runtime_device_error('设备绑定应用未启用', status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_APPLICATION_INACTIVE)
