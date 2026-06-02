from __future__ import annotations

from django.core import signing
from django.core.exceptions import ObjectDoesNotExist

from .models import Device

DEVICE_RUNTIME_TOKEN_SALT = 'solin.device-runtime'


def make_device_token(device: Device) -> str:
    return signing.dumps(
        {
            'device_id': device.id,
            'device_code': device.code,
            'tenant_id': device.tenant_id,
        },
        salt=DEVICE_RUNTIME_TOKEN_SALT,
    )


def resolve_device_token(token: str) -> Device | None:
    try:
        payload = signing.loads(token, salt=DEVICE_RUNTIME_TOKEN_SALT)
        device_id = payload.get('device_id')
        device_code = payload.get('device_code')
        tenant_id = payload.get('tenant_id')
        return Device.objects.select_related('tenant', 'application', 'group').get(
            id=device_id,
            code=device_code,
            tenant_id=tenant_id,
        )
    except (signing.BadSignature, ObjectDoesNotExist, TypeError, ValueError):
        return None
