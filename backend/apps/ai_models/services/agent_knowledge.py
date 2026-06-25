import hashlib
import logging
import math
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable
from xml.etree import ElementTree

import httpx
from django.utils import timezone

from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk
from apps.ai_models.models import EmbeddingModel, RerankModel, TenantKnowledgeModelSettings

logger = logging.getLogger(__name__)

KEYWORD_INDEX_MODEL = 'keyword'
EMBEDDING_BATCH_SIZE = 10
TEXT_EXTENSIONS = {'txt', 'md'}
LEGACY_OFFICE_EXTENSIONS = {'doc', 'xls', 'ppt'}


@dataclass
class RetrievedChunk:
    document_id: int | None
    doc_title: str
    content: str
    score: float
    chunk_index: int | None = None


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


def _chunk_settings_for_document(doc: KnowledgeDocument) -> tuple[int, int]:
    knowledge_base = getattr(doc, 'knowledge_base', None)
    chunk_size = getattr(knowledge_base, 'chunk_size', 500) or 500
    chunk_overlap = getattr(knowledge_base, 'chunk_overlap', 50) or 0
    chunk_size = max(100, min(int(chunk_size), 4000))
    chunk_overlap = max(0, min(int(chunk_overlap), chunk_size - 1))
    return chunk_size, chunk_overlap


def _chunk_document_text(doc: KnowledgeDocument, content: str) -> list[str]:
    chunk_size, chunk_overlap = _chunk_settings_for_document(doc)
    return chunk_text(content, max_chunk_len=chunk_size, overlap=chunk_overlap)


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


def _decode_text(raw_content: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030', 'latin-1'):
        try:
            return raw_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_content.decode('utf-8', errors='ignore')


def _xml_text(xml_content: bytes) -> str:
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError:
        fallback = re.sub(r'<[^>]+>', ' ', _decode_text(xml_content))
        return re.sub(r'\s+', ' ', fallback).strip()

    parts: list[str] = []
    for element in root.iter():
        if element.text and element.text.strip():
            parts.append(element.text.strip())
    return '\n'.join(parts)


def _zip_xml_text(raw_content: bytes, name_patterns: tuple[str, ...]) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(BytesIO(raw_content)) as archive:
        for name in sorted(archive.namelist()):
            if any(name.startswith(pattern) and name.endswith('.xml') for pattern in name_patterns):
                parts.append(_xml_text(archive.read(name)))
    return '\n'.join(part for part in parts if part.strip())


def _extract_pdf_text(raw_content: bytes) -> str:
    decoded = raw_content.decode('latin-1', errors='ignore')
    literal_strings = re.findall(r'\((.*?)\)', decoded, flags=re.DOTALL)
    if literal_strings:
        text = '\n'.join(item.replace('\\n', '\n').replace('\\r', '\n').replace('\\t', ' ') for item in literal_strings)
        text = re.sub(r'\\([()\\])', r'\1', text)
        cleaned = re.sub(r'\s+', ' ', text).strip()
        if cleaned:
            return cleaned
    return _decode_text(raw_content)


def extract_document_text(doc: KnowledgeDocument) -> str:
    with doc.file.open('rb') as f:
        raw_content = f.read()

    extension = (doc.file_extension or '').lower().lstrip('.')
    if extension in TEXT_EXTENSIONS:
        return _decode_text(raw_content)
    if extension == 'pdf':
        return _extract_pdf_text(raw_content)
    if extension == 'docx':
        return _zip_xml_text(raw_content, ('word/document', 'word/header', 'word/footer', 'word/footnotes'))
    if extension == 'pptx':
        return _zip_xml_text(raw_content, ('ppt/slides/slide', 'ppt/notesSlides/notesSlide'))
    if extension == 'xlsx':
        return _zip_xml_text(raw_content, ('xl/sharedStrings', 'xl/worksheets/sheet'))
    if extension in LEGACY_OFFICE_EXTENSIONS:
        raise ValueError('暂不支持旧版二进制 Office 文档解析，请转为 docx/xlsx/pptx 或 txt/md 后重新上传')
    return _decode_text(raw_content)


def _read_document_text(doc: KnowledgeDocument) -> str:
    return extract_document_text(doc)


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


def _embedding_model_for_tenant(tenant) -> EmbeddingModel | None:
    if tenant is None:
        return _active_embedding_model()
    settings = (
        TenantKnowledgeModelSettings.objects
        .select_related('embedding_model')
        .filter(tenant=tenant, is_active=True)
        .first()
    )
    model = settings.embedding_model if settings else None
    if model and model.is_active and model.api_key and model.base_url and model.model:
        return model
    return None


def _rerank_model_for_tenant(tenant) -> RerankModel | None:
    if tenant is None:
        return _active_rerank_model()
    settings = (
        TenantKnowledgeModelSettings.objects
        .select_related('rerank_model')
        .filter(tenant=tenant, is_active=True)
        .first()
    )
    model = settings.rerank_model if settings else None
    if model and model.is_active and model.api_key and model.base_url and model.model:
        return model
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


def _response_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(payload, dict):
        error = payload.get('error')
        if isinstance(error, dict):
            message = error.get('message') or error.get('code')
            if message:
                return str(message)[:500]
        for key in ('message', 'code', 'request_id'):
            if payload.get(key):
                return str(payload[key])[:500]
    return response.text[:500]


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
        raise RuntimeError(f'Embedding API failed: status={response.status_code}, reason={_response_error_message(response)}')
    return _parse_embedding_response(response.json(), len(texts))


def _ensure_document_chunks(
    client: httpx.Client,
    doc: KnowledgeDocument,
    model_config: EmbeddingModel,
) -> list[KnowledgeDocumentChunk]:
    content = _read_document_text(doc)
    chunks = _chunk_document_text(doc, content)
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
    batch_size = EMBEDDING_BATCH_SIZE
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


def _ensure_keyword_chunks(doc: KnowledgeDocument) -> list[KnowledgeDocumentChunk]:
    content = _read_document_text(doc)
    chunks = _chunk_document_text(doc, content)
    existing = list(
        KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=KEYWORD_INDEX_MODEL).order_by('chunk_index')
    )
    current_hashes = [_content_hash(chunk) for chunk in chunks]
    if len(existing) == len(chunks) and all(item.content_hash == current_hashes[index] for index, item in enumerate(existing)):
        return existing

    if not chunks:
        KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=KEYWORD_INDEX_MODEL).delete()
        return []

    records = [
        KnowledgeDocumentChunk(
            document=doc,
            tenant=doc.tenant,
            chunk_index=index,
            content=chunk,
            content_hash=current_hashes[index],
            embedding=[],
            embedding_model=KEYWORD_INDEX_MODEL,
        )
        for index, chunk in enumerate(chunks)
    ]
    KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=KEYWORD_INDEX_MODEL).delete()
    KnowledgeDocumentChunk.objects.bulk_create(records)
    return list(KnowledgeDocumentChunk.objects.filter(document=doc, embedding_model=KEYWORD_INDEX_MODEL).order_by('chunk_index'))


def build_document_index(document: KnowledgeDocument, *, force: bool = False) -> dict:
    if not document.file:
        KnowledgeDocument.objects.filter(pk=document.pk).update(
            index_status=KnowledgeDocument.IndexStatus.FAILED,
            index_error='当前文档文件不存在',
            indexed_at=None,
            chunk_count=0,
            index_model='',
        )
        return {'documentId': document.pk, 'status': KnowledgeDocument.IndexStatus.FAILED, 'chunkCount': 0}

    embedding_model = _embedding_model_for_tenant(document.tenant)
    expected_model = embedding_model.model if embedding_model else KEYWORD_INDEX_MODEL

    if (
        not force
        and document.index_status == KnowledgeDocument.IndexStatus.READY
        and document.index_model == expected_model
    ):
        return {
            'documentId': document.pk,
            'status': document.index_status,
            'chunkCount': document.chunk_count,
            'indexModel': document.index_model,
        }

    KnowledgeDocument.objects.filter(pk=document.pk).update(
        index_status=KnowledgeDocument.IndexStatus.INDEXING,
        index_error='',
        indexed_at=None,
    )
    document.index_status = KnowledgeDocument.IndexStatus.INDEXING
    document.index_error = ''
    document.indexed_at = None

    try:
        if embedding_model:
            with httpx.Client(timeout=30.0) as client:
                chunks = _ensure_document_chunks(client, document, embedding_model)
            index_model = embedding_model.model
            mode = 'vector'
        else:
            chunks = _ensure_keyword_chunks(document)
            index_model = KEYWORD_INDEX_MODEL
            mode = 'keyword'

        KnowledgeDocument.objects.filter(pk=document.pk).update(
            index_status=KnowledgeDocument.IndexStatus.READY,
            index_error='',
            indexed_at=timezone.now(),
            chunk_count=len(chunks),
            index_model=index_model,
        )
        return {
            'documentId': document.pk,
            'status': KnowledgeDocument.IndexStatus.READY,
            'chunkCount': len(chunks),
            'indexModel': index_model,
            'mode': mode,
        }
    except Exception as e:
        logger.exception('Failed to build knowledge document index id=%s error=%s', document.pk, e)
        KnowledgeDocument.objects.filter(pk=document.pk).update(
            index_status=KnowledgeDocument.IndexStatus.FAILED,
            index_error=str(e)[:1000],
            indexed_at=None,
            chunk_count=0,
            index_model=embedding_model.model if embedding_model else KEYWORD_INDEX_MODEL,
        )
        return {
            'documentId': document.pk,
            'status': KnowledgeDocument.IndexStatus.FAILED,
            'chunkCount': 0,
            'indexModel': embedding_model.model if embedding_model else KEYWORD_INDEX_MODEL,
            'error': str(e),
        }


def build_document_index_by_id(document_id: int, *, force: bool = False) -> dict:
    document = KnowledgeDocument.objects.select_related('tenant').get(pk=document_id)
    return build_document_index(document, force=force)


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
        raise RuntimeError(f'Rerank API failed: status={response.status_code}, reason={_response_error_message(response)}')

    results = ((response.json().get('output') or {}).get('results') or [])
    reranked: list[RetrievedChunk] = []
    for row in results:
        index = row.get('index')
        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            continue
        score = row.get('relevance_score', row.get('score', chunks[index].score))
        reranked.append(RetrievedChunk(chunks[index].document_id, chunks[index].doc_title, chunks[index].content, float(score), chunks[index].chunk_index))

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
    tenant_filter = {'tenant': application.tenant} if application.tenant_id else {'tenant__isnull': True}
    document_query = application.knowledge_documents.filter(**tenant_filter)
    if hasattr(application, 'knowledge_bases'):
        base_docs = KnowledgeDocument.objects.filter(knowledge_base__in=application.knowledge_bases.all(), **tenant_filter)
        document_query = document_query | base_docs
    return list(document_query.distinct())


def _approved_text_documents_for_knowledge_base(knowledge_base: KnowledgeBase) -> list[KnowledgeDocument]:
    return list(
        knowledge_base.documents.filter(
            tenant=knowledge_base.tenant,
        ).distinct()
    )


def _retrieve_keyword_chunks(docs: list[KnowledgeDocument], query: str, top_n: int) -> list[RetrievedChunk]:
    keywords = extract_keywords(query)
    if not keywords:
        return []

    all_scored_chunks: list[RetrievedChunk] = []
    stored_chunks = list(
        KnowledgeDocumentChunk.objects.filter(
            document__in=docs,
            embedding_model=KEYWORD_INDEX_MODEL,
        ).select_related('document')
    )
    for stored_chunk in stored_chunks:
        score = score_chunk(stored_chunk.content, keywords, query)
        if score > 0:
            all_scored_chunks.append(
                RetrievedChunk(
                    stored_chunk.document_id,
                    stored_chunk.document.title,
                    stored_chunk.content,
                    score,
                    stored_chunk.chunk_index,
                )
            )

    if all_scored_chunks:
        all_scored_chunks.sort(key=lambda item: item.score, reverse=True)
        return all_scored_chunks[:top_n]

    for doc in docs:
        try:
            content = _read_document_text(doc)
            for chunk_index, chunk in enumerate(_chunk_document_text(doc, content)):
                score = score_chunk(chunk, keywords, query)
                if score > 0:
                    all_scored_chunks.append(RetrievedChunk(doc.id, doc.title, chunk, score, chunk_index))
        except Exception as e:
            logger.warning('Failed to read knowledge document id=%s error=%s', doc.id, e)
            continue

    all_scored_chunks.sort(key=lambda item: item.score, reverse=True)
    return all_scored_chunks[:top_n]


def _retrieve_keyword_knowledge_context(application, query: str, top_n: int, max_chars: int) -> str:
    return _format_context(_retrieve_keyword_chunks(_bound_approved_text_documents(application), query, top_n), max_chars)


def _serialize_recall_result(*, chunks: list[RetrievedChunk], mode: str, embedding_model: EmbeddingModel | None, rerank_model: RerankModel | None) -> dict:
    return {
        'mode': mode,
        'embeddingModelAlias': embedding_model.name if embedding_model else '',
        'rerankModelAlias': rerank_model.name if rerank_model else '',
        'chunks': [
            {
                'documentId': chunk.document_id,
                'documentTitle': chunk.doc_title,
                'chunkIndex': chunk.chunk_index,
                'content': chunk.content,
                'score': chunk.score,
            }
            for chunk in chunks
        ],
    }


def retrieve_knowledge_chunks(
    *,
    query: str,
    application=None,
    knowledge_base: KnowledgeBase | None = None,
    tenant=None,
    top_n: int = 5,
) -> dict:
    if not query:
        return _serialize_recall_result(chunks=[], mode='empty', embedding_model=None, rerank_model=None)

    if knowledge_base is not None:
        docs = _approved_text_documents_for_knowledge_base(knowledge_base)
        tenant = knowledge_base.tenant
    elif application is not None:
        docs = _bound_approved_text_documents(application)
        tenant = application.tenant
    else:
        docs = []

    if not docs:
        return _serialize_recall_result(chunks=[], mode='empty', embedding_model=None, rerank_model=None)

    embedding_model = _embedding_model_for_tenant(tenant)
    if not embedding_model:
        return _serialize_recall_result(
            chunks=_retrieve_keyword_chunks(docs, query, top_n),
            mode='keyword',
            embedding_model=None,
            rerank_model=None,
        )

    try:
        with httpx.Client(timeout=30.0) as client:
            for doc in docs:
                build_document_index(doc)

            query_embedding = _embed_texts(client, embedding_model, [query])[0]
            stored_chunks = list(
                KnowledgeDocumentChunk.objects.filter(
                    document__in=docs,
                    embedding_model=embedding_model.model,
                ).select_related('document')
            )
            scored_chunks = [
                RetrievedChunk(
                    document_id=chunk.document_id,
                    doc_title=chunk.document.title,
                    content=chunk.content,
                    score=_cosine_similarity(query_embedding, chunk.embedding or []),
                    chunk_index=chunk.chunk_index,
                )
                for chunk in stored_chunks
            ]
            scored_chunks = [chunk for chunk in scored_chunks if chunk.score > 0]
            scored_chunks.sort(key=lambda item: item.score, reverse=True)
            candidates = scored_chunks[: max(top_n * 4, top_n)]
            if not candidates:
                return _serialize_recall_result(
                    chunks=_retrieve_keyword_chunks(docs, query, top_n),
                    mode='keyword',
                    embedding_model=embedding_model,
                    rerank_model=None,
                )

            rerank_model = _rerank_model_for_tenant(tenant)
            if rerank_model:
                try:
                    candidates = _rerank_chunks(client, rerank_model, query, candidates, top_n)
                except Exception as e:
                    logger.warning('Failed to rerank knowledge chunks error=%s', e)
            else:
                candidates = candidates[:top_n]

        return _serialize_recall_result(
            chunks=candidates[:top_n],
            mode='vector',
            embedding_model=embedding_model,
            rerank_model=rerank_model,
        )
    except Exception as e:
        logger.exception('Error during vector knowledge base retrieval, fallback to keyword retrieval: %s', e)
        return _serialize_recall_result(
            chunks=_retrieve_keyword_chunks(docs, query, top_n),
            mode='keyword',
            embedding_model=embedding_model,
            rerank_model=None,
        )


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

        embedding_model = _embedding_model_for_tenant(application.tenant)
        if not embedding_model:
            return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

        with httpx.Client(timeout=30.0) as client:
            embedding_preparation_failed = False
            for doc in docs:
                result = build_document_index(doc)
                if result.get('status') == KnowledgeDocument.IndexStatus.FAILED:
                    embedding_preparation_failed = True
                    logger.warning('Failed to prepare knowledge document embeddings id=%s error=%s', doc.id, result.get('error'))

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
                        document_id=chunk.document_id,
                        doc_title=chunk.document.title,
                        content=chunk.content,
                        score=_cosine_similarity(query_embedding, chunk.embedding or []),
                        chunk_index=chunk.chunk_index,
                    )
                for chunk in stored_chunks
            ]
            scored_chunks = [chunk for chunk in scored_chunks if chunk.score > 0]
            scored_chunks.sort(key=lambda item: item.score, reverse=True)
            candidates = scored_chunks[: max(top_n * 4, top_n)]
            if not candidates:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars)

            rerank_model = _rerank_model_for_tenant(application.tenant)
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
