from __future__ import annotations

from dataclasses import dataclass

from rest_framework import status

from apps.error_codes.catalogue import RealtimeErrorDefinition, require_error_definition_by_key
from apps.devices.models import Device


@dataclass(slots=True)
class RuntimeDeviceError(Exception):
    definition: RealtimeErrorDefinition
    status_code: int
    message: str | None = None

    def __post_init__(self) -> None:
        if self.message is None:
            self.message = self.definition.default_message
        Exception.__init__(self, self.message)

    @property
    def code(self) -> str:
        return self.definition.code

    @property
    def business_status_code(self) -> int:
        return self.definition.legacy_status_code or 44000

    def as_payload(self) -> dict[str, object]:
        return {
            'code': self.code,
            'statusCode': self.business_status_code,
            'message': self.message,
        }


RUNTIME_ERROR_EMPTY_DEVICE_CODE = require_error_definition_by_key('DEVICE_CODE_REQUIRED')
RUNTIME_ERROR_DEVICE_NOT_REGISTERED = require_error_definition_by_key('DEVICE_NOT_REGISTERED')
RUNTIME_ERROR_DUPLICATE_DEVICE_CODE = require_error_definition_by_key('DEVICE_CODE_DUPLICATED')
RUNTIME_ERROR_DEVICE_UNBOUND_TENANT = require_error_definition_by_key('DEVICE_TENANT_UNBOUND')
RUNTIME_ERROR_TENANT_DISABLED = require_error_definition_by_key('DEVICE_TENANT_DISABLED')
RUNTIME_ERROR_DEVICE_DISABLED = require_error_definition_by_key('DEVICE_DISABLED')
RUNTIME_ERROR_DEVICE_EXPIRED = require_error_definition_by_key('DEVICE_EXPIRED')
RUNTIME_ERROR_AGENT_UNBOUND = require_error_definition_by_key('DEVICE_AGENT_UNBOUND')
RUNTIME_ERROR_APPLICATION_INACTIVE = require_error_definition_by_key('DEVICE_APPLICATION_INACTIVE')


def runtime_device_error(
    message: str | None,
    status_code: int,
    error: RealtimeErrorDefinition,
) -> RuntimeDeviceError:
    return RuntimeDeviceError(error, status_code, message)


def get_runtime_device(
    device_code: str,
    *,
    require_tenant: bool = False,
    allow_expired: bool = False,
) -> Device:
    """Resolve and validate an Android runtime device by deviceCode.

    This is the shared seam for public device runtime endpoints and realtime
    device identity. It intentionally returns domain errors rather than DRF
    responses so callers can choose their own transport shape.
    """
    device_code = str(device_code or '').strip()
    if not device_code:
        raise runtime_device_error(None, status.HTTP_400_BAD_REQUEST, RUNTIME_ERROR_EMPTY_DEVICE_CODE)

    devices = list(
        Device.objects.select_related('tenant', 'application__agent_application', 'agent_application', 'tts_voice__provider')
        .filter(code=device_code)
        .order_by('id')[:2]
    )
    if not devices:
        raise runtime_device_error(None, status.HTTP_404_NOT_FOUND, RUNTIME_ERROR_DEVICE_NOT_REGISTERED)
    if len(devices) > 1:
        raise runtime_device_error(None, status.HTTP_409_CONFLICT, RUNTIME_ERROR_DUPLICATE_DEVICE_CODE)

    device = devices[0]
    if require_tenant and device.tenant_id is None:
        raise runtime_device_error(None, status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_UNBOUND_TENANT)
    if device.tenant is not None and not device.tenant.is_active:
        raise runtime_device_error(None, status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_TENANT_DISABLED)
    if not device.is_enabled:
        raise runtime_device_error(None, status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_DISABLED)
    if device.is_expired and not allow_expired:
        raise runtime_device_error(None, status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_DEVICE_EXPIRED)
    return device


def validate_runtime_application_active(device: Device) -> None:
    application = getattr(device, 'application', None)
    if application is not None and not application.is_active:
        raise runtime_device_error(None, status.HTTP_403_FORBIDDEN, RUNTIME_ERROR_APPLICATION_INACTIVE)
