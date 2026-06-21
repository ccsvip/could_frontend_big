import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Iterable

import httpx

from apps.knowledge_base.models import KnowledgeDocument, KnowledgeDocumentChunk
from apps.ai_models.models import EmbeddingModel, RerankModel

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    doc_title: str
    content: str
    score: float


def chunk_text(text: str, max_chunk_len: int = 500, overlap: int = 50) -> list[str]:
    """Splits a document text into smaller chunks by paragraph or fixed length."""
    paragraphs = []
    raw_paragraphs = text.replace('\r\n', '\n').split('\n\n')
    for raw_p in raw_paragraphs:
        p = raw_p.strip()
        if not p:
            continue
        if len(p) > max_chunk_len:
            start = 0
            step = max(1, max_chunk_len - overlap)
            while start < len(p):
                end = start + max_chunk_len
                paragraphs.append(p[start:end])
                start += step
        else:
            paragraphs.append(p)
    return paragraphs


def extract_keywords(query: str) -> set[str]:
    """Extracts keyword terms from the query for simple term-matching fallback."""
    query = query.lower()
    cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', query)
    terms = set()

    for word in re.findall(r'[a-zA-Z0-9]+', cleaned):
        if len(word) >= 2:
            terms.add(word)

    chinese_blocks = re.findall(r'[\u4e00-\u9fff]+', cleaned)
    for block in chinese_blocks:
        if len(block) <= 3:
            terms.add(block)
        else:
            for i in range(len(block) - 1):
                terms.add(block[i : i + 2])
            for i in range(len(block) - 2):
                terms.add(block[i : i + 3])

    full_clean = re.sub(r'\s+', '', cleaned)
    if full_clean:
        terms.add(full_clean)

    return {t for t in terms if t}


def score_chunk(chunk: str, keywords: set[str], query: str) -> float:
    """Calculates a keyword fallback score for a text chunk."""
    chunk_lower = chunk.lower()
    score = 0.0
    for kw in keywords:
        if kw in chunk_lower:
            score += len(kw)
    if query.lower() in chunk_lower:
        score += len(query) * 2.0
    return score


def _read_document_text(doc: KnowledgeDocument) -> str:
    with doc.file.open('rb') as f:
        raw_content = f.read()
    if isinstance(raw_content, bytes):
        return raw_content.decode('utf-8', errors='ignore')
    return str(raw_content)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _vector_norm(vector: Iterable[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = _vector_norm(left) * _vector_norm(right)
    if denominator == 0:
        return 0.0
    numerator = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    return numerator / denominator


def _dashscope_headers(api_key: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


def _active_embedding_model() -> EmbeddingModel | None:
    configured = (
        EmbeddingModel.objects.filter(is_active=True)
        .exclude(api_key='')
        .exclude(base_url='')
        .exclude(model='')
        .order_by('id')
        .first()
    )
    if configured:
        return configured
    default = EmbeddingModel.load_aliyun()
    if default.is_active and default.api_key and default.base_url and default.model:
        return default
    return None


def _active_rerank_model() -> RerankModel | None:
    configured = (
        RerankModel.objects.filter(is_active=True)
        .exclude(api_key='')
        .exclude(base_url='')
        .exclude(model='')
        .order_by('id')
        .first()
    )
    if configured:
        return configured
    default = RerankModel.load_aliyun()
    if default.is_active and default.api_key and default.base_url and default.model:
        return default
    return None


def _parse_embedding_response(payload: dict, expected_count: int) -> list[list[float]]:
    """Supports DashScope OpenAI-compatible and legacy embedding response shapes."""
    if isinstance(payload.get('data'), list):
        rows = sorted(payload['data'], key=lambda item: item.get('index', 0))
        embeddings = [row.get('embedding') for row in rows]
    else:
        output = payload.get('output') or {}
        rows = sorted(output.get('embeddings') or [], key=lambda item: item.get('text_index', item.get('index', 0)))
        embeddings = [row.get('embedding') for row in rows]

    result: list[list[float]] = []
    for embedding in embeddings:
        if isinstance(embedding, list):
            result.append([float(value) for value in embedding])

    if len(result) != expected_count:
        raise ValueError(f'Embedding response count mismatch: expected={expected_count}, actual={len(result)}')
    return result


def _embed_texts(client: httpx.Client, model_config: EmbeddingModel, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    payload = {
        'model': model_config.model,
        'input': texts,
    }
    if model_config.dimensions:
        payload['dimensions'] = model_config.dimensions
    response = client.post(
        model_config.base_url,
        json=payload,
        headers=_dashscope_headers(model_config.api_key),
    )
    if response.status_code >= 400:
        raise RuntimeError(f'Embedding API failed: status={response.status_code}, body={response.text[:500]}')
    return _parse_embedding_response(response.json(), len(texts))


def _ensure_document_chunks(
    client: httpx.Client,
    doc: KnowledgeDocument,
    model_config: EmbeddingModel,
) -> list[KnowledgeDocumentChunk]:
    content = _read_document_text(doc)
    chunks = chunk_text(content)
    existing = list(
        KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=model_config.model).order_by('chunk_index')
    )
    current_hashes = [_content_hash(chunk) for chunk in chunks]
    if (
        len(existing) == len(chunks)
        and all(item.content_hash == current_hashes[index] for index, item in enumerate(existing))
        and all(item.embedding for item in existing)
    ):
        return existing

    if not chunks:
        KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=model_config.model).delete()
        return []

    embeddings: list[list[float]] = []
    batch_size = 16
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        embeddings.extend(_embed_texts(client, model_config, batch))

    records = [
        KnowledgeDocumentChunk(
            document=doc,
            tenant=doc.tenant,
            chunk_index=index,
            content=chunk,
            content_hash=current_hashes[index],
            embedding=embeddings[index],
            embedding_model=model_config.model,
        )
        for index, chunk in enumerate(chunks)
    ]
    KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=model_config.model).delete()
    KnowledgeDocumentChunk.objects.bulk_create(records)
    return list(KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=model_config.model).order_by('chunk_index'))


def _rerank_chunks(
    client: httpx.Client,
    model_config: RerankModel,
    query: str,
    chunks: list[RetrievedChunk],
    top_n: int,
) -> list[RetrievedChunk]:
    if not chunks:
        return []
    documents = [chunk.content for chunk in chunks]
    payload = {
        'model': model_config.model,
        'input': {
            'query': query,
            'documents': documents,
        },
        'parameters': {
            'top_n': min(top_n, len(documents)),
            'return_documents': False,
        },
    }
    response = client.post(
        model_config.base_url,
        json=payload,
        headers=_dashscope_headers(model_config.api_key),
    )
    if response.status_code >= 400:
        raise RuntimeError(f'Rerank API failed: status={response.status_code}, body={response.text[:500]}')

    results = ((response.json().get('output') or {}).get('results') or [])
    reranked: list[RetrievedChunk] = []
    for row in results:
        index = row.get('index')
        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            continue
        score = row.get('relevance_score', row.get('score', chunks[index].score))
        reranked.append(RetrievedChunk(chunks[index].doc_title, chunks[index].content, float(score)))

    return reranked or chunks[:top_n]


def _format_context(chunks: list[RetrievedChunk], max_chars: int) -> str:
    context_parts = []
    current_len = 0

    for chunk_info in chunks:
        part = f"---\n文档: {chunk_info.doc_title}\n相关度: {chunk_info.score:.4f}\n内容: {chunk_info.content}\n"
        if current_len + len(part) > max_chars:
            break
        context_parts.append(part)
        current_len += len(part)

    if not context_parts:
        return ''

    header = (
        '你是一个智能体助手。以下是与用户当前问题相关的知识库参考内容。\n'
        '请严格参考这些内容进行回答。如果参考内容与用户问题相关，请优先基于参考内容回答；\n'
        '如果参考内容中没有相关信息或与用户问题无关，请忽略它们并使用你已有的知识回答，但不要向用户提及“根据参考内容”或“根据知识库”等字眼。\n\n'
        '【知识库参考信息】\n'
    )
    footer = '---\n'
    return header + ''.join(context_parts) + footer


def _bound_approved_text_documents(application) -> list[KnowledgeDocument]:
    if application.tenant_id:
        docs = application.knowledge_documents.filter(tenant=application.tenant)
    else:
        docs = application.knowledge_documents.filter(tenant__isnull=True)
    return list(
        docs.filter(
            processing_status=KnowledgeDocument.STATUS_APPROVED,
            file_extension__in=['txt', 'md'],
        ).distinct()
    )


def _retrieve_keyword_knowledge_context(application, query: str, top_n: int, max_chars: int) -> str:
    docs = _bound_approved_text_documents(application)
    keywords = extract_keywords(query)
    if not keywords:
        return ''

    all_scored_chunks: list[RetrievedChunk] = []
    for doc in docs:
        try:
            content = _read_document_text(doc)
            for chunk in chunk_text(content):
                score = score_chunk(chunk, keywords, query)
                if score > 0:
                    all_scored_chunks.append(RetrievedChunk(doc.title, chunk, score))
        except Exception as e:
            logger.warning('Failed to read knowledge document id=%s error=%s', doc.id, e)
            continue

    all_scored_chunks.sort(key=lambda item: item.score, reverse=True)
    return _format_context(all_scored_chunks[:top_n], max_chars)


def retrieve_knowledge_context(application, query: str, top_n: int = 5, max_chars: int = 3000) -> str:
    """
    Retrieves matching document fragments from txt/md documents bound to the application.

    Preferred path: DashScope embedding recall + DashScope rerank.
    Fallback path: local keyword matching when the external model is not configured or fails.
    """
    if not application or not query:
        return ''

    try:
        docs = _bound_approved_text_documents(application)
        if not docs:
            return ''

        embedding_model = _active_embedding_model()
        if not embedding_model:
            return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

        with httpx.Client(timeout=30.0) as client:
            embedding_preparation_failed = False
            for doc in docs:
                try:
                    _ensure_document_chunks(client, doc, embedding_model)
                except Exception as e:
                    embedding_preparation_failed = True
                    logger.warning('Failed to prepare knowledge document embeddings id=%s error=%s', doc.id, e)

            if embedding_preparation_failed:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

            query_embedding = _embed_texts(client, embedding_model, [query])[0]
            stored_chunks = list(
                KnowledgeDocumentChunk.objects.filter(
                    document__in=docs,
                    embedding_model=embedding_model.model,
                ).select_related('document')
            )
            if not stored_chunks:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

            scored_chunks = [
                RetrievedChunk(
                    doc_title=chunk.document.title,
                    content=chunk.content,
                    score=_cosine_similarity(query_embedding, chunk.embedding or []),
                )
                for chunk in stored_chunks
            ]
            scored_chunks = [chunk for chunk in scored_chunks if chunk.score > 0]
            scored_chunks.sort(key=lambda item: item.score, reverse=True)
            candidates = scored_chunks[: max(top_n * 4, top_n)]
            if not candidates:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

            rerank_model = _active_rerank_model()
            if rerank_model:
                try:
                    candidates = _rerank_chunks(client, rerank_model, query, candidates, top_n)
                except Exception as e:
                    logger.warning('Failed to rerank knowledge chunks application_id=%s error=%s', application.id, e)
            else:
                candidates = candidates[:top_n]

        return _format_context(candidates[:top_n], max_chars)
    except Exception as e:
        logger.exception('Error during vector knowledge base retrieval, fallback to keyword retrieval: %s', e)
        return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)


def inject_knowledge_context(conversation, api_messages, query: str) -> list[dict]:
    """
    Injects retrieved knowledge context into the OpenAI-compatible API messages list.
    The injected context goes right after the system prompt (if any), but before any history/user messages.
    """
    if not conversation.application:
        return api_messages

    context_str = retrieve_knowledge_context(conversation.application, query)
    if not context_str:
        return api_messages

    context_msg = {
        'role': 'system',
        'content': context_str,
    }

    new_messages = []
    if api_messages and api_messages[0]['role'] == 'system':
        new_messages.append(api_messages[0])
        new_messages.append(context_msg)
        new_messages.extend(api_messages[1:])
    else:
        new_messages.append(context_msg)
        new_messages.extend(api_messages)

    return new_messages
