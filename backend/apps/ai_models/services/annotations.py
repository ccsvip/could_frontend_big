from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_COSINE_THRESHOLD = 0.88


def normalize_annotation_question(value: str | None) -> str:
    text = str(value or '').strip()
    return ''.join(
        character
        for character in text
        if not unicodedata.category(character).startswith('P')
    ).strip()


@dataclass(frozen=True)
class AnnotationMatchPolicy:
    semantic_enabled: bool = True
    cosine_threshold: float = DEFAULT_COSINE_THRESHOLD
    rerank_enabled: bool = False
    rerank_threshold: float = 0.0
    semantic_top_k: int = 3


@dataclass(frozen=True)
class AnnotationMatch:
    annotation: Any
    match_type: Literal['exact', 'semantic']
    score: float
    fingerprint: str | None = None


def _global_semantic_enabled() -> bool:
    return bool(getattr(settings, 'ANNOTATION_SEMANTIC_MATCH_ENABLED', True))


def _coerce_threshold(value: Any, default: float = DEFAULT_COSINE_THRESHOLD) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return default
    if threshold <= 0 or threshold > 1:
        return default
    return threshold


def policy_from_application(application, *, published: bool = False) -> AnnotationMatchPolicy:
    if application is None:
        return AnnotationMatchPolicy(semantic_enabled=_global_semantic_enabled())

    config = None
    if published:
        config = getattr(application, 'published_config', None)
        if not isinstance(config, dict):
            config = None

    def _get(field: str, default):
        if config is not None and field in config:
            return config.get(field, default)
        return getattr(application, field, default)

    semantic_enabled = bool(_get('annotation_semantic_enabled', True)) and _global_semantic_enabled()
    return AnnotationMatchPolicy(
        semantic_enabled=semantic_enabled,
        cosine_threshold=_coerce_threshold(_get('annotation_cosine_threshold', DEFAULT_COSINE_THRESHOLD)),
        rerank_enabled=bool(_get('annotation_rerank_enabled', False)),
        rerank_threshold=_coerce_threshold(_get('annotation_rerank_threshold', 0.0), default=0.0),
        semantic_top_k=int(_get('annotation_semantic_top_k', 3) or 3),
    )


def _exact_match_live(queryset, normalized_question: str):
    ordered_queryset = queryset.filter(is_active=True).order_by('-updated_at', '-id')
    exact_match = ordered_queryset.filter(question__iexact=normalized_question).first()
    if exact_match is not None:
        return exact_match

    normalized_casefold = normalized_question.casefold()
    for annotation in ordered_queryset.only('id', 'question', 'answer', 'hit_count', 'last_hit_at', 'updated_at'):
        if normalize_annotation_question(annotation.question).casefold() == normalized_casefold:
            return annotation
    return None


def _exact_match_published(annotation_snapshots, normalized_question: str):
    normalized_casefold = normalized_question.casefold()
    for annotation in annotation_snapshots or []:
        if not isinstance(annotation, dict) or not annotation.get('isActive', True):
            continue
        if normalize_annotation_question(annotation.get('question')).casefold() == normalized_casefold:
            return annotation
    return None


def _log_match(
    *,
    match: AnnotationMatch,
    application_id: Any,
    source: str,
) -> None:
    annotation = match.annotation
    annotation_id = annotation.get('id') if isinstance(annotation, dict) else getattr(annotation, 'id', None)
    logger.info(
        'annotation.match source=%s match_type=%s score=%s fingerprint=%s application_id=%s annotation_id=%s',
        source,
        match.match_type,
        match.score,
        match.fingerprint or '',
        application_id,
        annotation_id,
    )


def serialize_annotation_match_payload(
    match: AnnotationMatch | None,
    *,
    application=None,
    published: bool = False,
) -> dict[str, Any] | None:
    """API/log snapshot for an annotation hit (exact or semantic)."""
    if match is None:
        return None
    annotation = match.annotation
    annotation_id = annotation.get('id') if isinstance(annotation, dict) else getattr(annotation, 'id', None)
    question = annotation.get('question') if isinstance(annotation, dict) else getattr(annotation, 'question', '')
    policy = policy_from_application(application, published=published)
    return {
        'annotationId': annotation_id,
        'matchType': match.match_type,
        'score': round(float(match.score), 4),
        'question': str(question or ''),
        'threshold': round(float(policy.cosine_threshold), 4),
    }


def _semantic_match_live(
    *,
    queryset,
    question_text: str,
    tenant,
    application,
    policy: AnnotationMatchPolicy,
) -> AnnotationMatch | None:
    if not policy.semantic_enabled or application is None:
        return None

    from apps.ai_models.services.annotation_embeddings import (
        EmbedQueryError,
        cosine_similarity,
        embed_query,
        ready_embeddings_for_application,
        select_live_fingerprint_and_model,
    )

    fingerprint, model = select_live_fingerprint_and_model(tenant, application)
    if not fingerprint or model is None:
        return None

    corpus = ready_embeddings_for_application(application, fingerprint)
    if not corpus:
        return None

    try:
        query_vector = embed_query(model, question_text, timeout=0.3)
    except EmbedQueryError as exc:
        logger.info(
            'annotation.match.semantic_embed_miss application_id=%s fingerprint=%s reason=%s',
            getattr(application, 'id', None),
            fingerprint,
            str(exc)[:200],
        )
        return None

    best_score = -1.0
    best_annotation_id = None
    query_dim = len(query_vector)
    for row in corpus:
        vector = row.embedding if isinstance(row.embedding, list) else None
        if not vector or len(vector) != query_dim:
            continue
        score = cosine_similarity(query_vector, vector)
        if score > best_score:
            best_score = score
            best_annotation_id = row.annotation_id

    if best_annotation_id is None or best_score < policy.cosine_threshold:
        return None

    annotation = queryset.filter(id=best_annotation_id, is_active=True).first()
    if annotation is None:
        annotation = next((row.annotation for row in corpus if row.annotation_id == best_annotation_id), None)
    if annotation is None:
        return None

    return AnnotationMatch(
        annotation=annotation,
        match_type='semantic',
        score=float(best_score),
        fingerprint=fingerprint,
    )


def _published_embedding_candidates(annotation_snapshots) -> dict[str, list[tuple[dict, list[float]]]]:
    by_fingerprint: dict[str, list[tuple[dict, list[float]]]] = {}
    for annotation in annotation_snapshots or []:
        if not isinstance(annotation, dict) or not annotation.get('isActive', True):
            continue
        embedding = annotation.get('embedding')
        if not isinstance(embedding, dict):
            continue
        fingerprint = embedding.get('fingerprint')
        vector = embedding.get('vector')
        if not fingerprint or not isinstance(vector, list) or not vector:
            continue
        by_fingerprint.setdefault(str(fingerprint), []).append((annotation, [float(v) for v in vector]))
    return by_fingerprint


def _select_published_fingerprint(
    by_fingerprint: dict[str, list[tuple[dict, list[float]]]],
    tenant,
) -> tuple[str | None, Any]:
    from apps.ai_models.services.agent_knowledge import _embedding_model_for_tenant
    from apps.ai_models.services.annotation_embeddings import (
        is_embedding_model_callable,
        model_fingerprint,
        resolve_embedding_model_for_fingerprint,
    )

    if not by_fingerprint:
        return None, None

    current_model = _embedding_model_for_tenant(tenant)
    if is_embedding_model_callable(current_model):
        prefer = model_fingerprint(current_model)
        if prefer in by_fingerprint:
            return prefer, current_model

    # Prefer any snapshot fingerprint whose model is still callable.
    for fingerprint in by_fingerprint:
        model = resolve_embedding_model_for_fingerprint(fingerprint)
        if is_embedding_model_callable(model):
            return fingerprint, model
    return None, None


def _semantic_match_published(
    *,
    annotation_snapshots,
    question_text: str,
    tenant,
    application,
    policy: AnnotationMatchPolicy,
) -> AnnotationMatch | None:
    if not policy.semantic_enabled:
        return None

    from apps.ai_models.services.annotation_embeddings import (
        EmbedQueryError,
        cosine_similarity,
        embed_query,
    )

    by_fingerprint = _published_embedding_candidates(annotation_snapshots)
    fingerprint, model = _select_published_fingerprint(by_fingerprint, tenant)
    if not fingerprint or model is None:
        return None

    corpus = by_fingerprint.get(fingerprint) or []
    if not corpus:
        return None

    try:
        query_vector = embed_query(model, question_text, timeout=0.3)
    except EmbedQueryError as exc:
        logger.info(
            'annotation.match.published_embed_miss application_id=%s fingerprint=%s reason=%s',
            getattr(application, 'id', None),
            fingerprint,
            str(exc)[:200],
        )
        return None

    best_score = -1.0
    best_annotation = None
    query_dim = len(query_vector)
    for annotation, vector in corpus:
        if len(vector) != query_dim:
            continue
        score = cosine_similarity(query_vector, vector)
        if score > best_score:
            best_score = score
            best_annotation = annotation

    if best_annotation is None or best_score < policy.cosine_threshold:
        return None

    return AnnotationMatch(
        annotation=best_annotation,
        match_type='semantic',
        score=float(best_score),
        fingerprint=fingerprint,
    )


def match_annotation(
    *,
    question_text: str,
    annotations,
    tenant=None,
    policy: AnnotationMatchPolicy | None = None,
    source: Literal['live', 'published'] = 'live',
    application=None,
) -> AnnotationMatch | None:
    normalized_question = normalize_annotation_question(question_text)
    if not normalized_question:
        return None

    resolved_policy = policy or policy_from_application(application, published=(source == 'published'))

    if source == 'published':
        exact = _exact_match_published(annotations, normalized_question)
    else:
        exact = _exact_match_live(annotations, normalized_question)

    if exact is not None:
        match = AnnotationMatch(annotation=exact, match_type='exact', score=1.0, fingerprint=None)
        _log_match(match=match, application_id=getattr(application, 'id', None), source=source)
        return match

    if not resolved_policy.semantic_enabled:
        return None

    # MVP: never call rerank even if policy.rerank_enabled is True.
    if source == 'published':
        match = _semantic_match_published(
            annotation_snapshots=annotations,
            question_text=normalized_question,
            tenant=tenant,
            application=application,
            policy=resolved_policy,
        )
    else:
        match = _semantic_match_live(
            queryset=annotations,
            question_text=normalized_question,
            tenant=tenant,
            application=application,
            policy=resolved_policy,
        )

    if match is not None:
        _log_match(match=match, application_id=getattr(application, 'id', None), source=source)
    return match


def find_matching_annotation(
    queryset,
    question_text: str,
    *,
    tenant=None,
    application=None,
    policy: AnnotationMatchPolicy | None = None,
):
    resolved_application = application
    resolved_tenant = tenant
    if resolved_application is None:
        try:
            sample = queryset.filter(is_active=True).select_related('application', 'tenant').first()
        except Exception:  # noqa: BLE001
            sample = None
        if sample is not None:
            resolved_application = sample.application
            resolved_tenant = resolved_tenant or sample.tenant

    match = match_annotation(
        question_text=question_text,
        annotations=queryset,
        tenant=resolved_tenant,
        application=resolved_application,
        policy=policy,
        source='live',
    )
    return match.annotation if match is not None else None


def find_matching_published_annotation(
    annotation_snapshots,
    question_text: str,
    *,
    tenant=None,
    application=None,
    policy: AnnotationMatchPolicy | None = None,
):
    match = match_annotation(
        question_text=question_text,
        annotations=annotation_snapshots,
        tenant=tenant,
        application=application,
        policy=policy,
        source='published',
    )
    return match.annotation if match is not None else None
