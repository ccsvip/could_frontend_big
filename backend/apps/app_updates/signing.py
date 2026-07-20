from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.utils import timezone

from .models import AppRelease


class AppUpdateSigningError(RuntimeError):
    pass


@dataclass(frozen=True)
class SignedRelease:
    signature: str
    expires_at: str


def build_signature_payload(
    release: AppRelease,
    *,
    download_url: str,
    force_upgrade_version_code: int,
    expires_at: str,
) -> str:
    values = (
        release.release_id,
        release.package_name,
        release.version_name,
        str(release.version_code),
        release.version_info,
        release.file_name,
        download_url,
        str(release.file_size),
        release.sha256,
        str(force_upgrade_version_code),
        expires_at,
    )
    if any('\r' in value or '\n' in value for value in values):
        raise AppUpdateSigningError('签名字段包含非法换行符')
    return '\n'.join(values)


def _load_private_key():
    encoded = str(getattr(settings, 'APP_UPDATE_PRIVATE_KEY_BASE64', '') or '').strip()
    key_file = str(getattr(settings, 'APP_UPDATE_PRIVATE_KEY_FILE', '') or '').strip()
    try:
        if encoded:
            pem = base64.b64decode(encoded, validate=True)
        elif key_file:
            pem = Path(key_file).read_bytes()
        else:
            raise AppUpdateSigningError('应用升级签名私钥未配置')
        return serialization.load_pem_private_key(pem, password=None)
    except AppUpdateSigningError:
        raise
    except Exception as exc:
        raise AppUpdateSigningError('应用升级签名私钥无效') from exc


def sign_release(release: AppRelease, *, download_url: str, force_upgrade_version_code: int) -> SignedRelease:
    ttl = max(60, int(getattr(settings, 'APP_UPDATE_SIGNATURE_TTL_SECONDS', 7 * 24 * 3600)))
    expires = timezone.now().astimezone(dt_timezone.utc) + timedelta(seconds=ttl)
    expires_at = expires.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    payload = build_signature_payload(
        release,
        download_url=download_url,
        force_upgrade_version_code=force_upgrade_version_code,
        expires_at=expires_at,
    )
    signature = _load_private_key().sign(payload.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())
    return SignedRelease(signature=base64.b64encode(signature).decode('ascii'), expires_at=expires_at)

