from __future__ import annotations

import hashlib
import re
from typing import BinaryIO

from rest_framework.exceptions import APIException

from apps.resources.models import Resource


SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')


class DuplicateImageError(APIException):
    status_code = 409
    default_code = 'duplicate_image'

    def __init__(self, existing_resource: Resource):
        self.response_data = {
            'existingResource': {
                'id': existing_resource.id,
                'category': existing_resource.category,
                'isDigitalHumanBackground': existing_resource.is_digital_human_background,
            },
        }
        super().__init__('该图片已存在', code=self.default_code)


def normalize_sha256(value: object) -> str:
    normalized = str(value or '').strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError('contentHash 必须是 64 位 SHA-256')
    return normalized


def calculate_sha256(file_obj: BinaryIO) -> str:
    original_position = file_obj.tell() if hasattr(file_obj, 'tell') else None
    digest = hashlib.sha256()
    chunks = file_obj.chunks() if hasattr(file_obj, 'chunks') else iter(lambda: file_obj.read(1024 * 1024), b'')
    for chunk in chunks:
        digest.update(chunk)
    if hasattr(file_obj, 'seek'):
        file_obj.seek(original_position or 0)
    return digest.hexdigest()


def find_duplicate_image(*, tenant, content_hash: str, exclude_id: int | None = None) -> Resource | None:
    queryset = Resource.objects.filter(
        tenant=tenant,
        resource_type=Resource.TYPE_IMAGE,
        content_hash=content_hash,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)
    return queryset.only('id', 'category', 'is_digital_human_background').first()
