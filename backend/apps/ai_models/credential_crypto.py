from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    configured_key = str(getattr(settings, 'BAILIAN_CREDENTIAL_ENCRYPTION_KEY', '') or '').strip()
    if configured_key:
        try:
            return Fernet(configured_key.encode('ascii'))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ImproperlyConfigured('BAILIAN_CREDENTIAL_ENCRYPTION_KEY 不是有效的 Fernet 密钥') from exc

    secret_key = str(getattr(settings, 'SECRET_KEY', '') or '')
    if not secret_key:
        raise ImproperlyConfigured('缺少百炼凭据加密密钥')
    derived = hashlib.sha256(f'bailian-knowledge:{secret_key}'.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_credential(value: str) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        return ''
    return _fernet().encrypt(normalized.encode('utf-8')).decode('ascii')


def decrypt_credential(value: str) -> str:
    normalized = str(value or '').strip()
    if not normalized:
        return ''
    try:
        return _fernet().decrypt(normalized.encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured('百炼 AccessKey Secret 无法解密，请由超管重新配置') from exc
