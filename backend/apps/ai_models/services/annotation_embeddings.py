from __future__ import annotations

import hashlib
import logging

import httpx
from django.db.models import QuerySet
from django.utils import timezone

from apps.ai_models.models import AgentAnnotation, AgentAnnotationEmbedding, EmbeddingModel
from apps.ai_models.services.agent_knowledge import (
    _cosine_similarity,
    _embed_texts,
    _embedding_model_for_tenant,
)
from apps.ai_models.services.annotations import normalize_annotation_question

logger = logging.getLogger(__name__)

QUERY_EMBED_TIMEOUT_SECONDS = 0.3
INDEX_EMBED_TIMEOUT_SECONDS = 30.0


class EmbedQueryError(Exception):
    """Soft failure while embedding a query or annotation question."""


class EmbedQueryTimeout(EmbedQueryError):
    """Embedding timed out within the configured budget."""


def model_fingerprint(model: EmbeddingModel) -> str:
    dims = model.dimensions or 'default'
    return f'{model.code}|{model.model}|{dims}'


def parse_fingerprint(fingerprint: str) -> tuple[str, str, int]:
    parts = str(fingerprint or '').split('|')
    if len(parts) != 3:
        raise ValueError(f'Invalid embedding fingerprint: {fingerprint}')
    code, model_name, dims = parts
    dimensions = 0 if dims == 'default' else int(dims)
    return code, model_name, dimensions


def question_hash(normalized_question: str) -> str:
    return hashlib.sha256(str(normalized_question or '').encode('utf-8')).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return _cosine_similarity(left, right)


def resolve_embedding_model_for_fingerprint(fingerprint: str) -> EmbeddingModel | None:
    try:
        code, model_name, dimensions = parse_fingerprint(fingerprint)
    except (TypeError, ValueError):
        return None
    model = (
        EmbeddingModel.objects.filter(
            code=code,
            model=model_name,
            dimensions=dimensions,
            is_active=True,
        )
        .exclude(api_key='')
        .exclude(base_url='')
        .exclude(model='')
        .order_by('id')
        .first()
    )
    if model is None:
        return None
    if not (model.api_key and model.base_url and model.model):
        return None
    return model


def is_embedding_model_callable(model: EmbeddingModel | None) -> bool:
    return bool(
        model
        and model.is_active
        and model.api_key
        and model.base_url
        and model.model
    )


def embed_query(model: EmbeddingModel, text: str, *, timeout: float = QUERY_EMBED_TIMEOUT_SECONDS) -> list[float]:
    cleaned = str(text or '').strip()
    if not cleaned:
        raise EmbedQueryError('empty text')
    if not is_embedding_model_callable(model):
        raise EmbedQueryError('embedding model unavailable')
    try:
        with httpx.Client(timeout=timeout) as client:
            vectors = _embed_texts(client, model, [cleaned])
    except httpx.TimeoutException as exc:
        raise EmbedQueryTimeout(str(exc) or 'timeout') from exc
    except httpx.HTTPError as exc:
        raise EmbedQueryError(str(exc) or exc.__class__.__name__) from exc
    except Exception as exc:  # noqa: BLE001 - soft-fail path for match/index
        raise EmbedQueryError(str(exc) or exc.__class__.__name__) from exc
    if not vectors or not vectors[0]:
        raise EmbedQueryError('empty embedding response')
    return [float(value) for value in vectors[0]]


def upsert_annotation_embedding(
    annotation: AgentAnnotation,
    model: EmbeddingModel | None = None,
    *,
    timeout: float = INDEX_EMBED_TIMEOUT_SECONDS,
) -> AgentAnnotationEmbedding | None:
    if annotation is None or not annotation.is_active:
        return None
    model = model or _embedding_model_for_tenant(annotation.tenant)
    if not is_embedding_model_callable(model):
        return None

    fingerprint = model_fingerprint(model)
    normalized = normalize_annotation_question(annotation.question)
    q_hash = question_hash(normalized)
    dimensions = int(model.dimensions or 0)

    record, _created = AgentAnnotationEmbedding.objects.get_or_create(
        annotation=annotation,
        embedding_fingerprint=fingerprint,
        defaults={
            'tenant': annotation.tenant,
            'application_id': annotation.application_id,
            'embedding_model_name': model.model,
            'dimensions': dimensions,
            'question_hash': q_hash,
            'embedding': [],
            'status': AgentAnnotationEmbedding.STATUS_PENDING,
            'error_message': '',
        },
    )

    if (
        record.status == AgentAnnotationEmbedding.STATUS_READY
        and record.question_hash == q_hash
        and isinstance(record.embedding, list)
        and record.embedding
    ):
        return record

    record.tenant = annotation.tenant
    record.application_id = annotation.application_id
    record.embedding_model_name = model.model
    record.dimensions = dimensions
    record.question_hash = q_hash
    record.status = AgentAnnotationEmbedding.STATUS_PENDING
    record.error_message = ''
    record.save(
        update_fields=[
            'tenant',
            'application',
            'embedding_model_name',
            'dimensions',
            'question_hash',
            'status',
            'error_message',
            'updated_at',
        ]
    )

    try:
        vector = embed_query(model, normalized or annotation.question, timeout=timeout)
    except EmbedQueryError as exc:
        record.status = AgentAnnotationEmbedding.STATUS_FAILED
        record.embedding = []
        record.error_message = str(exc)[:1000]
        record.embedded_at = None
        record.save(update_fields=['status', 'embedding', 'error_message', 'embedded_at', 'updated_at'])
        logger.warning(
            'annotation.embed.failed annotation_id=%s fingerprint=%s error=%s',
            annotation.id,
            fingerprint,
            record.error_message,
        )
        return record

    record.embedding = vector
    record.status = AgentAnnotationEmbedding.STATUS_READY
    record.error_message = ''
    record.embedded_at = timezone.now()
    if dimensions <= 0:
        record.dimensions = len(vector)
    record.save(
        update_fields=[
            'embedding',
            'status',
            'error_message',
            'embedded_at',
            'dimensions',
            'updated_at',
        ]
    )
    return record


def invalidate_annotation_embeddings(annotation: AgentAnnotation) -> None:
    AgentAnnotationEmbedding.objects.filter(annotation=annotation).delete()


def sync_annotation_embedding(
    annotation: AgentAnnotation,
    *,
    question_changed: bool = False,
    model: EmbeddingModel | None = None,
) -> AgentAnnotationEmbedding | None:
    if question_changed:
        invalidate_annotation_embeddings(annotation)
    if not annotation.is_active:
        return None
    try:
        return upsert_annotation_embedding(annotation, model=model)
    except Exception:  # noqa: BLE001 - never break CRUD on embed failure
        logger.exception(
            'annotation.embed.sync_unexpected annotation_id=%s application_id=%s',
            getattr(annotation, 'id', None),
            getattr(annotation, 'application_id', None),
        )
        return None


def reindex_annotation_embeddings(
    *,
    tenant=None,
    application=None,
    force: bool = False,
    model: EmbeddingModel | None = None,
) -> dict[str, int]:
    queryset: QuerySet[AgentAnnotation] = AgentAnnotation.objects.filter(is_active=True).select_related(
        'application',
        'tenant',
    )
    if application is not None:
        queryset = queryset.filter(application=application)
        tenant = tenant or getattr(application, 'tenant', None)
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)

    stats = {'total': 0, 'ready': 0, 'failed': 0, 'skipped': 0}
    for annotation in queryset.iterator():
        stats['total'] += 1
        target_model = model or _embedding_model_for_tenant(annotation.tenant)
        if not is_embedding_model_callable(target_model):
            stats['skipped'] += 1
            continue
        fingerprint = model_fingerprint(target_model)
        if force:
            AgentAnnotationEmbedding.objects.filter(
                annotation=annotation,
                embedding_fingerprint=fingerprint,
            ).delete()
        record = upsert_annotation_embedding(annotation, model=target_model)
        if record is None:
            stats['skipped'] += 1
        elif record.status == AgentAnnotationEmbedding.STATUS_READY:
            stats['ready'] += 1
        else:
            stats['failed'] += 1
    return stats


def ready_embeddings_for_application(
    application,
    fingerprint: str,
) -> list[AgentAnnotationEmbedding]:
    if application is None or not fingerprint:
        return []
    return list(
        AgentAnnotationEmbedding.objects.filter(
            application=application,
            embedding_fingerprint=fingerprint,
            status=AgentAnnotationEmbedding.STATUS_READY,
            annotation__is_active=True,
        ).select_related('annotation')
    )


def list_ready_fingerprints_for_application(application) -> list[str]:
    if application is None:
        return []
    return list(
        AgentAnnotationEmbedding.objects.filter(
            application=application,
            status=AgentAnnotationEmbedding.STATUS_READY,
            annotation__is_active=True,
        )
        .order_by('embedding_fingerprint')
        .values_list('embedding_fingerprint', flat=True)
        .distinct()
    )


def select_live_fingerprint_and_model(tenant, application) -> tuple[str | None, EmbeddingModel | None]:
    current_model = _embedding_model_for_tenant(tenant)
    if is_embedding_model_callable(current_model):
        prefer = model_fingerprint(current_model)
        if ready_embeddings_for_application(application, prefer):
            return prefer, current_model

    for fingerprint in list_ready_fingerprints_for_application(application):
        if current_model is not None and fingerprint == model_fingerprint(current_model):
            continue
        fallback_model = resolve_embedding_model_for_fingerprint(fingerprint)
        if is_embedding_model_callable(fallback_model) and ready_embeddings_for_application(application, fingerprint):
            return fingerprint, fallback_model

    if is_embedding_model_callable(current_model):
        # Allow query embed even without prebuilt vectors? No — empty corpus is useless.
        return None, None
    return None, None


def snapshot_embedding_payload(annotation: AgentAnnotation, fingerprint: str | None) -> dict | None:
    if not fingerprint:
        return None
    record = (
        AgentAnnotationEmbedding.objects.filter(
            annotation=annotation,
            embedding_fingerprint=fingerprint,
            status=AgentAnnotationEmbedding.STATUS_READY,
        )
        .only(
            'embedding_fingerprint',
            'embedding_model_name',
            'dimensions',
            'embedding',
            'question_hash',
        )
        .first()
    )
    if record is None or not isinstance(record.embedding, list) or not record.embedding:
        return None
    return {
        'fingerprint': record.embedding_fingerprint,
        'model': record.embedding_model_name,
        'dimensions': record.dimensions,
        'vector': list(record.embedding),
        'questionHash': record.question_hash,
    }


def current_fingerprint_for_tenant(tenant) -> str | None:
    model = _embedding_model_for_tenant(tenant)
    if not is_embedding_model_callable(model):
        return None
    return model_fingerprint(model)
