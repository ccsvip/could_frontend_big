from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.resources.models import Resource
from apps.resources.serializers import build_absolute_file_url


TEXT_BLOCK = 'text'
IMAGE_BLOCK = 'image'
VIDEO_BLOCK = 'video'
MEDIA_BLOCK_TYPES = {IMAGE_BLOCK, VIDEO_BLOCK}


def text_to_blocks(text: str) -> list[dict[str, Any]]:
    value = str(text or '').strip()
    return [{'type': TEXT_BLOCK, 'text': value}] if value else []


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    parts = [str(block.get('text') or '').strip() for block in blocks if block.get('type') == TEXT_BLOCK]
    return '\n'.join(part for part in parts if part)


def normalize_reply_blocks(value: Any, *, fallback_text: str = '', tenant=None) -> list[dict[str, Any]]:
    raw_blocks = value if isinstance(value, list) else []
    if not raw_blocks:
        raw_blocks = text_to_blocks(fallback_text)

    normalized: list[dict[str, Any]] = []
    media_refs: list[tuple[str, int]] = []
    for item in raw_blocks:
        if not isinstance(item, dict):
            continue
        block_type = str(item.get('type') or '').strip()
        if block_type == TEXT_BLOCK:
            text = str(item.get('text') or '').strip()
            if text:
                normalized.append({'type': TEXT_BLOCK, 'text': text})
            continue
        if block_type not in MEDIA_BLOCK_TYPES:
            continue
        try:
            resource_id = int(item.get('resourceId') or item.get('resource_id'))
        except (TypeError, ValueError):
            continue
        media_refs.append((block_type, resource_id))
        normalized.append({'type': block_type, 'resourceId': resource_id})

    if not normalized:
        return []

    if media_refs:
        _validate_media_refs(media_refs, tenant=tenant)
    return normalized


def serialize_reply_blocks(blocks: Any, *, tenant=None, request=None) -> list[dict[str, Any]]:
    normalized = normalize_reply_blocks(blocks, tenant=tenant)
    resource_ids = [block['resourceId'] for block in normalized if block.get('type') in MEDIA_BLOCK_TYPES]
    resources = _resource_map(resource_ids, tenant=tenant) if resource_ids else {}

    result: list[dict[str, Any]] = []
    for block in normalized:
        block_type = block.get('type')
        if block_type == TEXT_BLOCK:
            result.append({'type': TEXT_BLOCK, 'text': block.get('text') or ''})
            continue
        resource = resources.get(block.get('resourceId'))
        result.append({
            'type': block_type,
            'resourceId': block.get('resourceId'),
            'resourceName': resource.name if resource is not None else '',
            'url': _resource_url(resource, request=request) if resource is not None else '',
            'missing': resource is None,
        })
    return result


def build_published_annotation_snapshot(application) -> list[dict[str, Any]]:
    annotations = application.annotations.filter(is_active=True).order_by('id')
    snapshot = []
    for annotation in annotations:
        blocks = normalize_reply_blocks(annotation.answer_blocks, fallback_text=annotation.answer, tenant=application.tenant)
        snapshot.append({
            'id': annotation.id,
            'question': annotation.question,
            'answer': blocks_to_text(blocks),
            'answerBlocks': blocks,
            'isActive': annotation.is_active,
        })
    return snapshot


def serialize_published_annotation_blocks(annotation_snapshot: dict[str, Any], *, tenant=None, request=None) -> list[dict[str, Any]]:
    return serialize_reply_blocks(annotation_snapshot.get('answerBlocks') or [], tenant=tenant, request=request)


def _validate_media_refs(media_refs: list[tuple[str, int]], *, tenant=None) -> None:
    for block_type, resource_id in media_refs:
        resource = _resource_map([resource_id], tenant=tenant).get(resource_id)
        expected_type = Resource.TYPE_IMAGE if block_type == IMAGE_BLOCK else Resource.TYPE_VIDEO
        if resource is None or resource.resource_type != expected_type:
            raise ValueError('回复内容块引用的资源不存在或类型不匹配')


def _resource_map(resource_ids: list[int], *, tenant=None) -> dict[int, Resource]:
    queryset = Resource.objects.filter(id__in=resource_ids)
    if tenant is None:
        queryset = queryset.filter(tenant__isnull=True)
    else:
        queryset = queryset.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
    return {resource.id: resource for resource in queryset}


def _resource_url(resource: Resource | None, *, request=None) -> str:
    if resource is None:
        return ''
    if resource.object_key:
        from apps.resources.services.minio_client import build_public_object_url

        return build_public_object_url(resource.object_key)
    file_url = build_absolute_file_url(request, resource.file)
    if file_url:
        return file_url
    cloud_url = str(resource.cloud_url or '').strip()
    if cloud_url.startswith(('http://', 'https://', '/')):
        return cloud_url
    if cloud_url:
        media_url = f'/media/{cloud_url.lstrip("/")}'
        return request.build_absolute_uri(media_url) if request else media_url
    return ''
