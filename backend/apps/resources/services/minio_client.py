from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from urllib.parse import urlparse
from typing import TYPE_CHECKING

from django.conf import settings as django_settings
from django.db.models import Sum

if TYPE_CHECKING:
    from minio import Minio
    from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)

DEFAULT_REGION = 'us-east-1'
PRESIGNED_PUT_TTL_SECONDS = 7 * 24 * 3600


class MinioConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class MinioSettings:
    storage_backend: str
    endpoint: str
    internal_endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str
    secure: bool
    region: str
    public_base_url: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_public_base_url: str
    video_max_size_bytes: int
    allow_video_cloud_url: bool
    is_active: bool


def _strip(value: object) -> str:
    return str(value).strip() if value is not None else ''


def _bool_from_env(name: str, default: bool) -> bool:
    raw = getattr(django_settings, name, None)
    if raw is None:
        raw = os.getenv(name)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}


def _int_from_env(name: str, default: int) -> int:
    raw = str(getattr(django_settings, name, os.getenv(name, ''))).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_minio_settings() -> MinioSettings:
    from apps.resources.models import MinioConfig

    try:
        cfg = MinioConfig.load()
    except Exception:
        logger.warning('MinioConfig is unavailable; falling back to environment only')
        cfg = None

    storage_backend = _strip(getattr(cfg, 'storage_backend', '')) or 'local'
    endpoint = _strip(getattr(cfg, 'endpoint', '')) or _strip(getattr(django_settings, 'MINIO_ENDPOINT', os.getenv('MINIO_ENDPOINT', '')))
    internal_endpoint = _strip(getattr(django_settings, 'MINIO_INTERNAL_ENDPOINT', os.getenv('MINIO_INTERNAL_ENDPOINT', '')))
    access_key = _strip(getattr(cfg, 'access_key', '')) or _strip(getattr(django_settings, 'MINIO_ACCESS_KEY', os.getenv('MINIO_ACCESS_KEY', '')))
    secret_key = _strip(getattr(cfg, 'secret_key', '')) or _strip(getattr(django_settings, 'MINIO_SECRET_KEY', os.getenv('MINIO_SECRET_KEY', '')))
    bucket_name = _strip(getattr(cfg, 'bucket_name', '')) or _strip(getattr(django_settings, 'MINIO_BUCKET_NAME', os.getenv('MINIO_BUCKET_NAME', '')))
    region = _strip(getattr(cfg, 'region', '')) or _strip(getattr(django_settings, 'MINIO_REGION', os.getenv('MINIO_REGION', ''))) or DEFAULT_REGION
    public_base_url = _strip(getattr(cfg, 'public_base_url', '')) or _strip(getattr(django_settings, 'MINIO_PUBLIC_BASE_URL', os.getenv('MINIO_PUBLIC_BASE_URL', '')))
    r2_account_id = _strip(getattr(cfg, 'r2_account_id', '')) or _strip(getattr(django_settings, 'R2_ACCOUNT_ID', os.getenv('R2_ACCOUNT_ID', '')))
    r2_access_key_id = _strip(getattr(cfg, 'r2_access_key_id', '')) or _strip(getattr(django_settings, 'R2_ACCESS_KEY_ID', os.getenv('R2_ACCESS_KEY_ID', '')))
    r2_secret_access_key = _strip(getattr(cfg, 'r2_secret_access_key', '')) or _strip(getattr(django_settings, 'R2_SECRET_ACCESS_KEY', os.getenv('R2_SECRET_ACCESS_KEY', '')))
    r2_bucket_name = _strip(getattr(cfg, 'r2_bucket_name', '')) or _strip(getattr(django_settings, 'R2_BUCKET_NAME', os.getenv('R2_BUCKET_NAME', '')))
    r2_public_base_url = _strip(getattr(cfg, 'r2_public_base_url', '')) or _strip(getattr(django_settings, 'R2_PUBLIC_BASE_URL', os.getenv('R2_PUBLIC_BASE_URL', '')))

    if cfg is not None:
        secure = bool(cfg.secure)
        is_active = bool(cfg.is_active)
        video_max_mb = int(cfg.video_max_size_mb or 0) or _int_from_env('MINIO_VIDEO_MAX_SIZE_MB', 1024)
    else:
        secure = _bool_from_env('MINIO_SECURE', False)
        is_active = _bool_from_env('MINIO_ENABLED', True)
        video_max_mb = _int_from_env('MINIO_VIDEO_MAX_SIZE_MB', 1024)

    return MinioSettings(
        storage_backend=storage_backend,
        endpoint=endpoint,
        internal_endpoint=internal_endpoint or endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket_name=bucket_name,
        secure=secure,
        region=region,
        public_base_url=public_base_url.rstrip('/'),
        r2_account_id=r2_account_id,
        r2_access_key_id=r2_access_key_id,
        r2_secret_access_key=r2_secret_access_key,
        r2_bucket_name=r2_bucket_name,
        r2_public_base_url=r2_public_base_url.rstrip('/'),
        video_max_size_bytes=max(1, video_max_mb) * 1024 * 1024,
        allow_video_cloud_url=bool(getattr(cfg, 'allow_video_cloud_url', True)) if cfg is not None else _bool_from_env('MINIO_ALLOW_VIDEO_CLOUD_URL', True),
        is_active=is_active,
    )


def _require_complete(settings: MinioSettings) -> None:
    missing = [
        name
        for name, value in (
            ('endpoint', settings.endpoint),
            ('access_key', settings.access_key),
            ('secret_key', settings.secret_key),
            ('bucket_name', settings.bucket_name),
        )
        if not value
    ]
    if missing:
        logger.error('MinIO settings are incomplete: %s', ', '.join(missing))
        raise MinioConfigError('视频上传服务暂不可用，请稍后重试')


def _normalize_endpoint(endpoint: str) -> tuple[str, bool | None]:
    value = endpoint.strip().rstrip('/')
    if '://' not in value:
        return value, None
    parsed = urlparse(value)
    return parsed.netloc or parsed.path, parsed.scheme == 'https'


def _build_client(settings: MinioSettings, *, endpoint: str | None = None) -> 'Minio':
    from minio import Minio

    selected_endpoint, endpoint_secure = _normalize_endpoint(endpoint or settings.endpoint)

    return Minio(
        endpoint=selected_endpoint,
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        secure=settings.secure if endpoint_secure is None else endpoint_secure,
        region=settings.region,
    )


def _build_r2_client(settings: MinioSettings) -> 'Minio':
    from minio import Minio

    endpoint = f'{settings.r2_account_id}.r2.cloudflarestorage.com'
    return Minio(
        endpoint=endpoint,
        access_key=settings.r2_access_key_id,
        secret_key=settings.r2_secret_access_key,
        secure=True,
        region='auto',
    )


def _ensure_bucket(client: 'Minio', settings: MinioSettings) -> None:
    import json

    from minio.error import S3Error

    bucket = settings.bucket_name
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket, location=settings.region)
    except S3Error as exc:
        raise MinioConfigError(f'检查或创建 bucket 失败：{bucket}') from exc

    policy = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Effect': 'Allow',
                'Principal': {'AWS': ['*']},
                'Action': ['s3:GetObject'],
                'Resource': [f'arn:aws:s3:::{bucket}/*'],
            }
        ],
    }
    try:
        client.set_bucket_policy(bucket, json.dumps(policy))
    except S3Error:
        logger.debug('set_bucket_policy skipped for bucket=%s', bucket, exc_info=True)


def tenant_object_prefix(tenant: 'Tenant') -> str:
    if tenant is None or not getattr(tenant, 'id', None):
        raise MinioConfigError('缺少租户上下文，无法上传视频')
    return f'tenants/{tenant.id}/'


def build_video_object_key(filename: str, *, tenant: 'Tenant') -> str:
    return build_resource_object_key(filename, tenant=tenant, resource_type='video')


def build_resource_object_key(filename: str, *, tenant: 'Tenant', resource_type: str) -> str:
    name = (filename or '').strip().replace('\\', '/')
    ext = PurePosixPath(name).suffix.lower() if name else ''
    if not ext:
        ext = '.png' if resource_type == 'image' else '.mp4'
    today = datetime.utcnow()
    folder = 'images' if resource_type == 'image' else 'videos'
    return f'{tenant_object_prefix(tenant)}{folder}/{today:%Y/%m/%d}/{uuid.uuid4().hex}{ext}'


def validate_tenant_object_key(object_key: str, *, tenant: 'Tenant') -> str:
    value = _strip(object_key).lstrip('/')
    if not value:
        return ''
    prefix = tenant_object_prefix(tenant)
    if not value.startswith(prefix):
        raise MinioConfigError('视频对象不属于当前公司')
    return value


def build_public_object_url(object_key: str, settings: MinioSettings | None = None, *, backend: str = '') -> str:
    if not object_key:
        return ''
    cfg = settings or get_minio_settings()
    if backend == 'r2':
        if cfg.r2_public_base_url:
            return f'{cfg.r2_public_base_url}/{object_key.lstrip("/")}'
        return ''
    if not cfg.bucket_name:
        return ''
    if cfg.public_base_url:
        return f'{cfg.public_base_url}/{object_key.lstrip("/")}'
    if not cfg.endpoint:
        return ''
    scheme = 'https' if cfg.secure else 'http'
    return f'{scheme}://{cfg.endpoint}/{cfg.bucket_name}/{object_key.lstrip("/")}'


def get_tenant_video_usage_bytes(tenant: 'Tenant') -> int:
    if tenant is None or not getattr(tenant, 'id', None):
        return 0

    from apps.resources.models import Resource

    total = Resource.objects.filter(
        tenant=tenant,
        resource_type=Resource.TYPE_VIDEO,
        object_key__gt='',
    ).aggregate(total=Sum('object_size'))['total']
    return int(total or 0)


def get_tenant_video_quota_summary(tenant: 'Tenant') -> dict:
    if tenant is None or not getattr(tenant, 'id', None):
        return {
            'quotaLimited': False,
            'quotaMB': None,
            'quotaBytes': None,
            'usedBytes': 0,
            'remainingBytes': None,
            'usedMB': 0,
            'remainingMB': None,
        }

    from apps.resources.models import TenantVideoQuota

    quota, _ = TenantVideoQuota.objects.get_or_create(tenant=tenant, defaults={'quota_mb': None})
    used_bytes = get_tenant_video_usage_bytes(tenant)
    if quota.quota_mb is None:
        return {
            'quotaLimited': False,
            'quotaMB': None,
            'quotaBytes': None,
            'usedBytes': used_bytes,
            'remainingBytes': None,
            'usedMB': round(used_bytes / 1024 / 1024, 2),
            'remainingMB': None,
        }

    quota_mb = int(quota.quota_mb or 0)
    quota_bytes = quota_mb * 1024 * 1024
    remaining_bytes = max(0, quota_bytes - used_bytes)
    return {
        'quotaLimited': True,
        'quotaMB': quota_mb,
        'quotaBytes': quota_bytes,
        'usedBytes': used_bytes,
        'remainingBytes': remaining_bytes,
        'usedMB': round(used_bytes / 1024 / 1024, 2),
        'remainingMB': round(remaining_bytes / 1024 / 1024, 2),
    }


def presign_video_put_url(*, filename: str, content_type: str, file_size: int, tenant: 'Tenant') -> dict:
    return presign_resource_put_url(resource_type='video', filename=filename, content_type=content_type, file_size=file_size, tenant=tenant)


def _require_r2_complete(settings: MinioSettings) -> None:
    missing = [
        name
        for name, value in (
            ('r2_account_id', settings.r2_account_id),
            ('r2_access_key_id', settings.r2_access_key_id),
            ('r2_secret_access_key', settings.r2_secret_access_key),
            ('r2_bucket_name', settings.r2_bucket_name),
            ('r2_public_base_url', settings.r2_public_base_url),
        )
        if not value
    ]
    if missing:
        logger.error('R2 settings are incomplete: %s', ', '.join(missing))
        raise MinioConfigError('R2 存储桶配置不完整，请先在存储位置中补全配置')


def presign_resource_put_url(*, resource_type: str, filename: str, content_type: str, file_size: int, tenant: 'Tenant') -> dict:
    settings = get_minio_settings()
    if settings.storage_backend == 'r2':
        return _presign_r2_resource_put_url(settings=settings, resource_type=resource_type, filename=filename, content_type=content_type, file_size=file_size, tenant=tenant)
    if resource_type != 'video':
        raise MinioConfigError('当前存储位置未启用图片直传')
    if not settings.is_active:
        raise MinioConfigError('视频上传暂不可用，请稍后再试或填写已有的视频链接。')
    _require_complete(settings)
    if file_size <= 0:
        raise MinioConfigError('文件大小必须大于 0')
    if file_size > settings.video_max_size_bytes:
        max_mb = settings.video_max_size_bytes // (1024 * 1024)
        raise MinioConfigError(f'视频大小超出限制（最多 {max_mb}MB）')

    quota = get_tenant_video_quota_summary(tenant)
    if quota['quotaLimited'] and file_size > int(quota['remainingBytes'] or 0):
        raise MinioConfigError('视频容量额度不足，请联系超级管理员调整额度')

    object_key = build_video_object_key(filename, tenant=tenant)
    safe_content_type = (content_type or '').strip() or 'application/octet-stream'
    bucket_client = _build_client(settings, endpoint=settings.internal_endpoint)
    _ensure_bucket(bucket_client, settings)
    presign_client = _build_client(settings)
    upload_url = presign_client.presigned_put_object(
        bucket_name=settings.bucket_name,
        object_name=object_key,
        expires=timedelta(seconds=PRESIGNED_PUT_TTL_SECONDS),
    )
    return {
        'uploadUrl': upload_url,
        'objectKey': object_key,
        'publicUrl': build_public_object_url(object_key, settings),
        'bucket': settings.bucket_name,
        'expiresIn': PRESIGNED_PUT_TTL_SECONDS,
        'maxSizeBytes': settings.video_max_size_bytes,
        'objectSize': file_size,
        **quota,
        'headers': {'Content-Type': safe_content_type},
    }


def _presign_r2_resource_put_url(*, settings: MinioSettings, resource_type: str, filename: str, content_type: str, file_size: int, tenant: 'Tenant') -> dict:
    if not settings.is_active:
        raise MinioConfigError('R2 上传暂不可用，请稍后再试')
    _require_r2_complete(settings)
    if file_size <= 0:
        raise MinioConfigError('文件大小必须大于 0')
    if resource_type == 'video' and file_size > settings.video_max_size_bytes:
        max_mb = settings.video_max_size_bytes // (1024 * 1024)
        raise MinioConfigError(f'视频大小超出限制（最多 {max_mb}MB）')

    quota = get_tenant_video_quota_summary(tenant) if resource_type == 'video' else {
        'quotaLimited': False,
        'quotaMB': None,
        'quotaBytes': None,
        'usedBytes': 0,
        'remainingBytes': None,
        'usedMB': 0,
        'remainingMB': None,
    }
    if resource_type == 'video' and quota['quotaLimited'] and file_size > int(quota['remainingBytes'] or 0):
        raise MinioConfigError('视频容量额度不足，请联系超级管理员调整额度')

    object_key = build_resource_object_key(filename, tenant=tenant, resource_type=resource_type)
    safe_content_type = (content_type or '').strip() or 'application/octet-stream'
    client = _build_r2_client(settings)
    upload_url = client.presigned_put_object(
        bucket_name=settings.r2_bucket_name,
        object_name=object_key,
        expires=timedelta(seconds=PRESIGNED_PUT_TTL_SECONDS),
    )
    return {
        'uploadUrl': upload_url,
        'objectKey': object_key,
        'storageBackend': 'r2',
        'publicUrl': build_public_object_url(object_key, settings, backend='r2'),
        'bucket': settings.r2_bucket_name,
        'expiresIn': PRESIGNED_PUT_TTL_SECONDS,
        'maxSizeBytes': settings.video_max_size_bytes,
        'objectSize': file_size,
        **quota,
        'headers': {'Content-Type': safe_content_type},
    }


def delete_object(object_key: str, *, backend: str = '') -> bool:
    if not object_key:
        return False
    try:
        settings = get_minio_settings()
        if backend == 'r2':
            _require_r2_complete(settings)
            client = _build_r2_client(settings)
            client.remove_object(settings.r2_bucket_name, object_key)
        else:
            _require_complete(settings)
            client = _build_client(settings, endpoint=settings.internal_endpoint)
            client.remove_object(settings.bucket_name, object_key)
        return True
    except Exception as exc:
        logger.warning('Failed to delete MinIO object %s: %s', object_key, exc)
        return False


def get_video_upload_config(tenant: 'Tenant' = None) -> dict:
    settings = get_minio_settings()
    enabled = settings.is_active and bool(settings.endpoint) and bool(settings.bucket_name)
    if settings.storage_backend == 'r2':
        enabled = settings.is_active and bool(settings.r2_account_id) and bool(settings.r2_access_key_id) and bool(settings.r2_secret_access_key) and bool(settings.r2_bucket_name) and bool(settings.r2_public_base_url)
    return {
        'enabled': enabled,
        'storageBackend': settings.storage_backend,
        'maxSizeBytes': settings.video_max_size_bytes,
        'maxSizeMB': settings.video_max_size_bytes // (1024 * 1024),
        'bucketName': settings.r2_bucket_name if settings.storage_backend == 'r2' else settings.bucket_name,
        'expiresIn': PRESIGNED_PUT_TTL_SECONDS,
        'allowCloudUrl': settings.allow_video_cloud_url,
        **get_tenant_video_quota_summary(tenant),
    }


def get_resource_upload_config(tenant: 'Tenant' = None) -> dict:
    settings = get_minio_settings()
    video_config = get_video_upload_config(tenant)
    return {
        **video_config,
        'imageDirectUploadEnabled': settings.storage_backend == 'r2' and video_config['enabled'],
    }
