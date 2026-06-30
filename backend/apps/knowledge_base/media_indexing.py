from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings
from django.utils import timezone

from apps.resources.models import Resource
from apps.resources.services.minio_client import build_public_object_url

from .models import KnowledgeMediaAsset

logger = logging.getLogger(__name__)


class KnowledgeMediaIndexError(RuntimeError):
    pass


def _setting(name: str, default: str = '') -> str:
    return str(getattr(settings, name, default) or '').strip()


def _dashscope_api_key() -> str:
    return (
        _setting('ALIYUN_MULTIMODAL_API_KEY')
        or _setting('ALIYUN_MULTIMODAL_EMBEDDING_API_KEY')
        or _setting('DASHSCOPE_API_KEY')
        or _setting('MULTIMODAL_API_KEY')
    )


def _headers(api_key: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _resource_public_url(resource: Resource | None) -> str:
    if resource is None:
        return ''
    if resource.object_key:
        return build_public_object_url(resource.object_key)
    return resource.cloud_url or ''


def _first_embedding(payload: Any) -> list[float]:
    if isinstance(payload, dict):
        value = payload.get('embedding')
        if isinstance(value, list) and value and all(isinstance(item, (int, float)) for item in value):
            return [float(item) for item in value]
        for child in payload.values():
            result = _first_embedding(child)
            if result:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = _first_embedding(item)
            if result:
                return result
    return []


def _extract_vlm_text(payload: dict) -> str:
    choices = payload.get('choices') or (payload.get('output') or {}).get('choices') or []
    if choices:
        message = choices[0].get('message') or {}
        content = message.get('content')
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get('text') or item.get('content')
                    if text:
                        parts.append(str(text))
            return '\n'.join(parts).strip()
    output_text = (payload.get('output') or {}).get('text')
    return str(output_text or '').strip()


def _generate_vlm_description(client: httpx.Client, asset: KnowledgeMediaAsset, url: str, api_key: str) -> str:
    if asset.resource_type != Resource.TYPE_IMAGE:
        return ''

    base_url = _setting('ALIYUN_VLM_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    model = _setting('ALIYUN_VLM_MODEL', 'qwen-vl-plus')
    prompt = (
        '请用中文客观描述这张图片，重点写清楚画面主体、场景、可用于回答哪些用户问题。'
        '不要编造图片中不存在的信息，控制在120字以内。'
    )
    response = client.post(
        base_url,
        headers=_headers(api_key),
        json={
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'image_url', 'image_url': {'url': url}},
                        {'type': 'text', 'text': prompt},
                    ],
                }
            ],
        },
    )
    if response.status_code >= 400:
        raise KnowledgeMediaIndexError(f'VLM API failed: status={response.status_code}, reason={response.text[:500]}')
    return _extract_vlm_text(response.json())


def _generate_multimodal_embedding(client: httpx.Client, *, text: str, url: str, resource_type: str, api_key: str) -> tuple[list[float], str]:
    base_url = _setting('ALIYUN_MULTIMODAL_EMBEDDING_BASE_URL', 'https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding')
    model = _setting('ALIYUN_MULTIMODAL_EMBEDDING_MODEL', 'qwen3-vl-embedding')
    content: dict[str, str] = {}
    if text:
        content['text'] = text
    if url:
        if resource_type == Resource.TYPE_VIDEO:
            content['video'] = url
        else:
            content['image'] = url
    if not content:
        return [], model

    response = client.post(
        base_url,
        headers=_headers(api_key),
        json={
            'model': model,
            'input': {'contents': [content]},
            'parameters': {'enable_fusion': True},
        },
    )
    if response.status_code >= 400:
        raise KnowledgeMediaIndexError(f'Multimodal embedding API failed: status={response.status_code}, reason={response.text[:500]}')
    return _first_embedding(response.json()), model


def embed_media_query(query: str, tenant=None) -> list[float]:
    api_key = _dashscope_api_key()
    if not api_key or not query:
        return []
    with httpx.Client(timeout=30.0) as client:
        embedding, _ = _generate_multimodal_embedding(
            client,
            text=query,
            url='',
            resource_type=Resource.TYPE_IMAGE,
            api_key=api_key,
        )
    return embedding


def build_media_asset_index(asset_id: int, *, force: bool = False) -> dict:
    asset = KnowledgeMediaAsset.objects.select_related('resource', 'knowledge_base').filter(pk=asset_id).first()
    if asset is None:
        return {'assetId': asset_id, 'status': 'missing'}
    if asset.embedding_status == KnowledgeMediaAsset.EmbeddingStatus.READY and not force:
        return {'assetId': asset_id, 'status': asset.embedding_status}

    KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
        embedding_status=KnowledgeMediaAsset.EmbeddingStatus.PROCESSING,
        embedding_error='',
    )
    asset.embedding_status = KnowledgeMediaAsset.EmbeddingStatus.PROCESSING
    asset.embedding_error = ''

    api_key = _dashscope_api_key()
    if not api_key:
        error = '未配置百炼多模态 API Key'
        KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
            embedding_status=KnowledgeMediaAsset.EmbeddingStatus.FAILED,
            embedding_error=error,
        )
        return {'assetId': asset.pk, 'status': KnowledgeMediaAsset.EmbeddingStatus.FAILED, 'error': error}

    url = _resource_public_url(asset.resource)
    if not url:
        error = '素材缺少可供百炼访问的公网地址'
        KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
            embedding_status=KnowledgeMediaAsset.EmbeddingStatus.FAILED,
            embedding_error=error,
        )
        return {'assetId': asset.pk, 'status': KnowledgeMediaAsset.EmbeddingStatus.FAILED, 'error': error}

    try:
        with httpx.Client(timeout=60.0) as client:
            vlm_description = _generate_vlm_description(client, asset, url, api_key) or asset.vlm_description
            text_for_embedding = ' '.join(
                part
                for part in (
                    asset.resource_name,
                    asset.description,
                    asset.keywords,
                    vlm_description,
                )
                if part
            )
            multimodal_embedding, multimodal_model = _generate_multimodal_embedding(
                client,
                text=text_for_embedding,
                url=url,
                resource_type=asset.resource_type,
                api_key=api_key,
            )

            description_embedding = []
            from apps.ai_models.services.agent_knowledge import _embed_texts, _embedding_model_for_tenant

            embedding_model = _embedding_model_for_tenant(asset.tenant)
            if embedding_model and text_for_embedding:
                description_embedding = _embed_texts(client, embedding_model, [text_for_embedding])[0]

        KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
            vlm_description=vlm_description,
            description_embedding=description_embedding,
            multimodal_embedding=multimodal_embedding,
            embedding_status=KnowledgeMediaAsset.EmbeddingStatus.READY,
            embedding_error='',
            embedding_model=multimodal_model,
            embedding_processed_at=timezone.now(),
        )
        return {'assetId': asset.pk, 'status': KnowledgeMediaAsset.EmbeddingStatus.READY}
    except Exception as exc:
        logger.exception('Failed to build knowledge media asset index id=%s error=%s', asset.pk, exc)
        KnowledgeMediaAsset.objects.filter(pk=asset.pk).update(
            embedding_status=KnowledgeMediaAsset.EmbeddingStatus.FAILED,
            embedding_error=str(exc)[:1000],
        )
        return {'assetId': asset.pk, 'status': KnowledgeMediaAsset.EmbeddingStatus.FAILED, 'error': str(exc)}
