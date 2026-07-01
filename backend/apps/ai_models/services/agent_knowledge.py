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

from apps.knowledge_base.models import KnowledgeBase, KnowledgeDocument, KnowledgeDocumentChunk, KnowledgeMediaAsset
from apps.resources.models import Resource
from apps.ai_models.models import EmbeddingModel, RerankModel, TenantKnowledgeModelSettings

logger = logging.getLogger(__name__)

KEYWORD_INDEX_MODEL = 'keyword'
EMBEDDING_BATCH_SIZE = 10
DEFAULT_VECTOR_MIN_SCORE = 0.2
TEXT_EXTENSIONS = {'txt', 'md'}
LEGACY_OFFICE_EXTENSIONS = {'doc', 'xls', 'ppt'}
RETRIEVAL_INTENT_TERMS = {
    '什么',
    '怎么',
    '如何',
    '多少',
    '哪里',
    '哪个',
    '哪些',
    '为什么',
    '能否',
    '是否',
    '介绍',
    '说明',
    '查询',
    '推荐',
    '流程',
    '政策',
    '价格',
    '费用',
    '时间',
    '地址',
}


@dataclass
class RetrievedChunk:
    document_id: int | None
    doc_title: str
    content: str
    score: float
    chunk_index: int | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str = ''
    retrieval_min_score: float = DEFAULT_VECTOR_MIN_SCORE


@dataclass
class RetrievedMediaAsset:
    asset: KnowledgeMediaAsset
    relevance: float


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


def _has_retrieval_intent(query: str) -> bool:
    """Returns whether a query carries enough information to search business knowledge."""
    normalized = re.sub(r'\s+', '', str(query or '').lower())
    if not normalized:
        return False
    if len(normalized) >= 6:
        return True
    if re.search(r'[?？]', normalized):
        return True
    if any(term in normalized for term in RETRIEVAL_INTENT_TERMS):
        return True
    if re.search(r'\d', normalized) and len(normalized) >= 2:
        return True

    keywords = extract_keywords(normalized)
    return len(keywords) >= 2


def _chunk_knowledge_base_id(chunk) -> int | None:
    knowledge_base = getattr(getattr(chunk, 'document', None), 'knowledge_base', None)
    return getattr(knowledge_base, 'id', None)


def _chunk_knowledge_base_name(chunk) -> str:
    knowledge_base = getattr(getattr(chunk, 'document', None), 'knowledge_base', None)
    return getattr(knowledge_base, 'name', '') or ''


def _knowledge_base_min_score(knowledge_base) -> float:
    value = getattr(knowledge_base, 'retrieval_min_score', DEFAULT_VECTOR_MIN_SCORE)
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return DEFAULT_VECTOR_MIN_SCORE


def _chunk_retrieval_min_score(chunk) -> float:
    knowledge_base = getattr(getattr(chunk, 'document', None), 'knowledge_base', None)
    return _knowledge_base_min_score(knowledge_base)


def _passes_vector_score_gate(chunk: RetrievedChunk) -> bool:
    return chunk.score >= chunk.retrieval_min_score


def _retrieved_chunk_from_stored_chunk(stored_chunk: KnowledgeDocumentChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=stored_chunk.document_id,
        doc_title=stored_chunk.document.title,
        content=stored_chunk.content,
        score=score,
        chunk_index=stored_chunk.chunk_index,
        knowledge_base_id=_chunk_knowledge_base_id(stored_chunk),
        knowledge_base_name=_chunk_knowledge_base_name(stored_chunk),
        retrieval_min_score=_chunk_retrieval_min_score(stored_chunk),
    )


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
        reranked.append(
            RetrievedChunk(
                chunks[index].document_id,
                chunks[index].doc_title,
                chunks[index].content,
                float(score),
                chunks[index].chunk_index,
                chunks[index].knowledge_base_id,
                chunks[index].knowledge_base_name,
                chunks[index].retrieval_min_score,
            )
        )

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


def _approved_text_documents_for_ids(
    application,
    *,
    knowledge_document_ids: list[int] | None = None,
    knowledge_base_ids: list[int] | None = None,
) -> list[KnowledgeDocument]:
    tenant_filter = {'tenant': application.tenant} if application.tenant_id else {'tenant__isnull': True}
    document_query = KnowledgeDocument.objects.none()
    if knowledge_document_ids:
        document_query = document_query | KnowledgeDocument.objects.filter(id__in=knowledge_document_ids, **tenant_filter)
    if knowledge_base_ids:
        document_query = document_query | KnowledgeDocument.objects.filter(knowledge_base_id__in=knowledge_base_ids, **tenant_filter)
    return list(document_query.distinct())


def _approved_text_documents_for_knowledge_base(knowledge_base: KnowledgeBase) -> list[KnowledgeDocument]:
    return list(
        knowledge_base.documents.filter(
            tenant=knowledge_base.tenant,
        ).distinct()
    )


def _doc_knowledge_base_id(doc: KnowledgeDocument) -> int | None:
    return doc.knowledge_base_id


def _doc_knowledge_base_name(doc: KnowledgeDocument) -> str:
    knowledge_base = getattr(doc, 'knowledge_base', None)
    return getattr(knowledge_base, 'name', '') or ''


def _retrieve_keyword_chunks(docs: list[KnowledgeDocument], query: str, top_n: int) -> list[RetrievedChunk]:
    keywords = extract_keywords(query)
    if not keywords:
        return []

    all_scored_chunks: list[RetrievedChunk] = []
    stored_chunks = list(
        KnowledgeDocumentChunk.objects.filter(
            document__in=docs,
            embedding_model=KEYWORD_INDEX_MODEL,
        ).select_related('document', 'document__knowledge_base')
    )
    for stored_chunk in stored_chunks:
        score = score_chunk(stored_chunk.content, keywords, query)
        if score > 0:
            all_scored_chunks.append(_retrieved_chunk_from_stored_chunk(stored_chunk, score))

    if all_scored_chunks:
        all_scored_chunks.sort(key=lambda item: item.score, reverse=True)
        return all_scored_chunks[:top_n]

    for doc in docs:
        try:
            content = _read_document_text(doc)
            for chunk_index, chunk in enumerate(_chunk_document_text(doc, content)):
                score = score_chunk(chunk, keywords, query)
                if score > 0:
                    all_scored_chunks.append(
                        RetrievedChunk(
                            doc.id,
                            doc.title,
                            chunk,
                            score,
                            chunk_index,
                            _doc_knowledge_base_id(doc),
                            _doc_knowledge_base_name(doc),
                            _knowledge_base_min_score(getattr(doc, 'knowledge_base', None)),
                        )
                    )
        except Exception as e:
            logger.warning('Failed to read knowledge document id=%s error=%s', doc.id, e)
            continue

    all_scored_chunks.sort(key=lambda item: item.score, reverse=True)
    return all_scored_chunks[:top_n]


def _retrieve_keyword_knowledge_context(application, query: str, top_n: int, max_chars: int, docs: list[KnowledgeDocument] | None = None) -> str:
    return _format_context(_retrieve_keyword_chunks(docs if docs is not None else _bound_approved_text_documents(application), query, top_n), max_chars)


MEDIA_RELEVANCE_THRESHOLD = 0.22


def _asset_text(asset: KnowledgeMediaAsset) -> str:
    resource = asset.resource
    parts = [
        asset.resource_name,
        asset.keywords,
        asset.description,
        asset.vlm_keywords,
        asset.vlm_description,
        resource.name if resource is not None else '',
        resource.description if resource is not None else '',
    ]
    return ' '.join(str(part or '') for part in parts).strip()


def _asset_match_terms(asset: KnowledgeMediaAsset) -> set[str]:
    resource = asset.resource
    raw_values = [
        asset.resource_name,
        asset.keywords,
        asset.vlm_keywords,
        resource.name if resource is not None else '',
    ]
    terms: set[str] = set()
    for value in raw_values:
        for term in re.split(r'[\s,，、;；|/]+', str(value or '')):
            normalized = re.sub(r'\s+', '', term.strip().lower())
            if len(normalized) >= 2:
                terms.add(normalized)
    return terms


def _direct_media_term_score(asset: KnowledgeMediaAsset, query: str) -> float:
    normalized_query = re.sub(r'\s+', '', str(query or '').lower())
    if not normalized_query:
        return 0.0
    matched_weight = 0.0
    for term in _asset_match_terms(asset):
        if term in normalized_query:
            matched_weight += min(len(term), 6)
    return min(matched_weight / 3.0, 1.0)


def _score_media_asset(
    asset: KnowledgeMediaAsset,
    *,
    query: str,
    chunks: list[RetrievedChunk],
    query_multimodal_embedding: list[float] | None = None,
) -> float:
    text = _asset_text(asset)
    if not text:
        return 0.0

    multimodal_score = 0.0
    if query_multimodal_embedding and asset.multimodal_embedding:
        multimodal_score = max(_cosine_similarity(query_multimodal_embedding, asset.multimodal_embedding), 0.0)

    query_keywords = extract_keywords(query)
    query_raw_score = score_chunk(text, query_keywords, query) if query_keywords else 0.0
    query_score = min(query_raw_score / 12.0, 1.0)
    query_score = max(query_score, _direct_media_term_score(asset, query))

    chunk_scores: list[float] = []
    for chunk in chunks[:3]:
        chunk_keywords = extract_keywords(chunk.content[:500])
        chunk_scores.append(min(score_chunk(text, chunk_keywords, chunk.content[:120]) / 16.0, 1.0))
    chunk_score = max(chunk_scores, default=0.0)
    priority_score = min(max(asset.priority, 0) / 20.0, 1.0)
    text_relevance_score = min(query_score * 0.65 + chunk_score * 0.25 + priority_score * 0.1, 1.0)

    if multimodal_score:
        blended_score = min(multimodal_score * 0.7 + query_score * 0.2 + chunk_score * 0.05 + priority_score * 0.05, 1.0)
        return max(blended_score, text_relevance_score)
    return min(query_score * 0.45 + chunk_score * 0.5 + priority_score * 0.05, 1.0)


def match_media_assets_for_chunks(*, query: str, chunks: list[RetrievedChunk], tenant=None) -> list[RetrievedMediaAsset]:
    knowledge_base_ids = {
        chunk.knowledge_base_id
        for chunk in chunks
        if chunk.knowledge_base_id is not None
    }
    if not knowledge_base_ids:
        return []

    queryset = (
        KnowledgeMediaAsset.objects.filter(
            knowledge_base_id__in=knowledge_base_ids,
            is_enabled=True,
            resource__isnull=False,
            resource_type__in=[Resource.TYPE_IMAGE, Resource.TYPE_VIDEO],
        )
        .select_related('resource', 'knowledge_base')
        .order_by('-priority', '-updated_at', '-id')
    )
    if tenant is None:
        queryset = queryset.filter(tenant__isnull=True)
    else:
        queryset = queryset.filter(tenant=tenant)

    query_multimodal_embedding: list[float] = []
    if queryset.filter(multimodal_embedding__isnull=False).exclude(multimodal_embedding=[]).exists():
        try:
            from apps.knowledge_base.media_indexing import embed_media_query

            query_multimodal_embedding = embed_media_query(query, tenant=tenant)
        except Exception as e:
            logger.warning('Failed to build media query embedding error=%s', e)

    scored: list[RetrievedMediaAsset] = []
    for asset in queryset:
        relevance = _score_media_asset(
            asset,
            query=query,
            chunks=chunks,
            query_multimodal_embedding=query_multimodal_embedding,
        )
        threshold = getattr(asset.knowledge_base, 'media_min_relevance', MEDIA_RELEVANCE_THRESHOLD) if asset.knowledge_base_id else MEDIA_RELEVANCE_THRESHOLD
        if relevance >= threshold:
            scored.append(RetrievedMediaAsset(asset=asset, relevance=relevance))

    scored.sort(key=lambda item: (item.relevance, item.asset.priority, item.asset.updated_at), reverse=True)
    selected: list[RetrievedMediaAsset] = []
    selected_by_base: dict[int, int] = {}
    for item in scored:
        if item.asset.resource_type not in {Resource.TYPE_IMAGE, Resource.TYPE_VIDEO}:
            continue
        knowledge_base_id = int(item.asset.knowledge_base_id or 0)
        media_max_assets = int(getattr(item.asset.knowledge_base, 'media_max_assets', 0) or 0)
        if media_max_assets > 0 and selected_by_base.get(knowledge_base_id, 0) >= media_max_assets:
            continue
        selected_by_base[knowledge_base_id] = selected_by_base.get(knowledge_base_id, 0) + 1
        selected.append(item)
    return selected


def serialize_media_assets(media_assets: list[RetrievedMediaAsset]) -> list[dict]:
    return [
        {
            'id': item.asset.id,
            'resourceId': item.asset.resource_id,
            'resourceName': item.asset.resource_name,
            'resourceType': item.asset.resource_type,
            'keywords': item.asset.keywords,
            'description': item.asset.description,
            'relevance': round(item.relevance, 2),
            'knowledgeBaseId': item.asset.knowledge_base_id,
            'knowledgeBaseName': item.asset.knowledge_base.name if item.asset.knowledge_base_id else '',
        }
        for item in media_assets
    ]


def media_assets_to_reply_blocks(media_assets: list[RetrievedMediaAsset]) -> list[dict]:
    blocks: list[dict] = []
    for item in media_assets:
        if item.asset.resource_id is None:
            continue
        block_type = 'image' if item.asset.resource_type == Resource.TYPE_IMAGE else 'video'
        blocks.append({'type': block_type, 'resourceId': item.asset.resource_id})
    return blocks


def _serialized_media_assets_to_reply_blocks(media_assets: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    for item in media_assets:
        resource_id = item.get('resourceId')
        resource_type = item.get('resourceType')
        if not resource_id or resource_type not in {Resource.TYPE_IMAGE, Resource.TYPE_VIDEO}:
            continue
        blocks.append({'type': 'image' if resource_type == Resource.TYPE_IMAGE else 'video', 'resourceId': resource_id})
    return blocks


def _merge_media_reply_blocks(primary: list[dict], fallback: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for block in [*primary, *fallback]:
        try:
            key = (str(block.get('type') or ''), int(block.get('resourceId') or 0))
        except (TypeError, ValueError):
            continue
        if key[0] not in {'image', 'video'} or key[1] <= 0 or key in seen:
            continue
        seen.add(key)
        merged.append({'type': key[0], 'resourceId': key[1]})
    return merged


def _chunks_from_recall_result(result: dict) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for item in result.get('chunks') or []:
        try:
            score = float(item.get('score') or 0)
        except (TypeError, ValueError):
            score = 0.0
        chunks.append(
            RetrievedChunk(
                document_id=item.get('documentId'),
                doc_title=item.get('documentTitle') or '',
                content=item.get('content') or '',
                score=score,
                chunk_index=item.get('chunkIndex'),
                knowledge_base_id=item.get('knowledgeBaseId'),
                knowledge_base_name=item.get('knowledgeBaseName') or '',
            )
        )
    return chunks


def match_media_assets_for_reply_text(
    *,
    recall_result: dict,
    user_query: str,
    reply_text: str,
    tenant=None,
) -> list[RetrievedMediaAsset]:
    chunks = _chunks_from_recall_result(recall_result)
    if not chunks or not str(reply_text or '').strip():
        return []
    media_query = '\n'.join(part for part in [user_query, reply_text] if str(part or '').strip())
    return match_media_assets_for_chunks(query=media_query, chunks=chunks, tenant=tenant)


def media_blocks_for_reply_text(
    *,
    recall_result: dict,
    user_query: str,
    reply_text: str,
    tenant=None,
) -> list[dict]:
    reply_matched_blocks = media_assets_to_reply_blocks(
        match_media_assets_for_reply_text(
            recall_result=recall_result,
            user_query=user_query,
            reply_text=reply_text,
            tenant=tenant,
        )
    )
    recalled_blocks = _serialized_media_assets_to_reply_blocks(recall_result.get('mediaAssets') or [])
    return _merge_media_reply_blocks(reply_matched_blocks, recalled_blocks)


def _serialize_recall_result(
    *,
    chunks: list[RetrievedChunk],
    mode: str,
    embedding_model: EmbeddingModel | None,
    rerank_model: RerankModel | None,
    query: str = '',
    tenant=None,
    retrieval_skipped: bool = False,
    skip_reason: str = '',
    include_media: bool = True,
) -> dict:
    media_assets = match_media_assets_for_chunks(query=query, chunks=chunks, tenant=tenant) if chunks and include_media else []
    return {
        'mode': mode,
        'retrievalSkipped': retrieval_skipped,
        'skipReason': skip_reason,
        'embeddingModelAlias': embedding_model.name if embedding_model else '',
        'rerankModelAlias': rerank_model.name if rerank_model else '',
        'chunks': [
            {
                'documentId': chunk.document_id,
                'documentTitle': chunk.doc_title,
                'chunkIndex': chunk.chunk_index,
                'content': chunk.content,
                'score': chunk.score,
                'knowledgeBaseId': chunk.knowledge_base_id,
                'knowledgeBaseName': chunk.knowledge_base_name,
            }
            for chunk in chunks
        ],
        'mediaAssets': serialize_media_assets(media_assets),
    }


def retrieve_knowledge_chunks(
    *,
    query: str,
    application=None,
    knowledge_base: KnowledgeBase | None = None,
    tenant=None,
    top_n: int = 5,
    knowledge_document_ids: list[int] | None = None,
    knowledge_base_ids: list[int] | None = None,
    include_media: bool = True,
) -> dict:
    if not query:
        return _serialize_recall_result(chunks=[], mode='empty', embedding_model=None, rerank_model=None, include_media=include_media)
    if not _has_retrieval_intent(query):
        return _serialize_recall_result(
            chunks=[],
            mode='skipped',
            embedding_model=None,
            rerank_model=None,
            query=query,
            tenant=tenant,
            retrieval_skipped=True,
            skip_reason='low_information_query',
            include_media=include_media,
        )

    if knowledge_base is not None:
        docs = _approved_text_documents_for_knowledge_base(knowledge_base)
        tenant = knowledge_base.tenant
    elif application is not None:
        if knowledge_document_ids is None and knowledge_base_ids is None:
            docs = _bound_approved_text_documents(application)
        else:
            docs = _approved_text_documents_for_ids(
                application,
                knowledge_document_ids=knowledge_document_ids,
                knowledge_base_ids=knowledge_base_ids,
            )
        tenant = application.tenant
    else:
        docs = []

    if not docs:
        return _serialize_recall_result(chunks=[], mode='empty', embedding_model=None, rerank_model=None, include_media=include_media)

    embedding_model = _embedding_model_for_tenant(tenant)
    if not embedding_model:
        return _serialize_recall_result(
            chunks=_retrieve_keyword_chunks(docs, query, top_n),
            mode='keyword',
            embedding_model=None,
            rerank_model=None,
            query=query,
            tenant=tenant,
            include_media=include_media,
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
                ).select_related('document', 'document__knowledge_base')
            )
            scored_chunks = [
                _retrieved_chunk_from_stored_chunk(
                    chunk,
                    _cosine_similarity(query_embedding, chunk.embedding or []),
                )
                for chunk in stored_chunks
            ]
            scored_chunks = [chunk for chunk in scored_chunks if _passes_vector_score_gate(chunk)]
            scored_chunks.sort(key=lambda item: item.score, reverse=True)
            candidates = scored_chunks[: max(top_n * 4, top_n)]
            if not candidates:
                return _serialize_recall_result(
                    chunks=[],
                    mode='vector',
                    embedding_model=embedding_model,
                    rerank_model=None,
                    query=query,
                    tenant=tenant,
                    include_media=include_media,
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
            query=query,
            tenant=tenant,
            include_media=include_media,
        )
    except Exception as e:
        logger.exception('Error during vector knowledge base retrieval, fallback to keyword retrieval: %s', e)
        return _serialize_recall_result(
            chunks=_retrieve_keyword_chunks(docs, query, top_n),
            mode='keyword',
            embedding_model=embedding_model,
            rerank_model=None,
            query=query,
            tenant=tenant,
            include_media=include_media,
        )


def retrieve_knowledge_context(
    application,
    query: str,
    top_n: int = 5,
    max_chars: int = 3000,
    *,
    knowledge_document_ids: list[int] | None = None,
    knowledge_base_ids: list[int] | None = None,
) -> str:
    """
    Retrieves matching document fragments from txt/md documents bound to the application.

    Preferred path: DashScope embedding recall + DashScope rerank.
    Fallback path: local keyword matching when the external model is not configured or fails.
    """
    if not application or not query:
        return ''
    if not _has_retrieval_intent(query):
        return ''

    docs = None
    try:
        if knowledge_document_ids is None and knowledge_base_ids is None:
            docs = _bound_approved_text_documents(application)
        else:
            docs = _approved_text_documents_for_ids(
                application,
                knowledge_document_ids=knowledge_document_ids,
                knowledge_base_ids=knowledge_base_ids,
            )
        if not docs:
            return ''

        embedding_model = _embedding_model_for_tenant(application.tenant)
        if not embedding_model:
            return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars, docs)

        with httpx.Client(timeout=30.0) as client:
            embedding_preparation_failed = False
            for doc in docs:
                result = build_document_index(doc)
                if result.get('status') == KnowledgeDocument.IndexStatus.FAILED:
                    embedding_preparation_failed = True
                    logger.warning('Failed to prepare knowledge document embeddings id=%s error=%s', doc.id, result.get('error'))

            if embedding_preparation_failed:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars, docs)

            query_embedding = _embed_texts(client, embedding_model, [query])[0]
            stored_chunks = list(
                KnowledgeDocumentChunk.objects.filter(
                    document__in=docs,
                    embedding_model=embedding_model.model,
                ).select_related('document', 'document__knowledge_base')
            )
            if not stored_chunks:
                return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars, docs)

            scored_chunks = [
                    _retrieved_chunk_from_stored_chunk(
                        chunk,
                        _cosine_similarity(query_embedding, chunk.embedding or []),
                    )
                for chunk in stored_chunks
            ]
            scored_chunks = [chunk for chunk in scored_chunks if _passes_vector_score_gate(chunk)]
            scored_chunks.sort(key=lambda item: item.score, reverse=True)
            candidates = scored_chunks[: max(top_n * 4, top_n)]
            if not candidates:
                return ''

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
        return _retrieve_keyword_knowledge_context(application, query, top_n, max_chars, docs)


def _format_context_from_recall_result(result: dict, max_chars: int = 3000) -> str:
    chunks = result.get('chunks') or []
    context_parts = []
    current_len = 0
    for chunk in chunks:
        part = (
            f"---\n文档: {chunk.get('documentTitle') or ''}\n"
            f"相关度: {float(chunk.get('score') or 0):.4f}\n"
            f"内容: {chunk.get('content') or ''}\n"
        )
        if current_len + len(part) > max_chars:
            break
        context_parts.append(part)
        current_len += len(part)
    if not context_parts:
        return ''

    media_assets = result.get('mediaAssets') or []
    media_context = ''
    if media_assets:
        media_lines = [
            f"- {item.get('resourceName') or ''}（{item.get('resourceType') or ''}，相关度 {item.get('relevance') or 0}）：{item.get('description') or item.get('keywords') or ''}"
            for item in media_assets
        ]
        media_context = '\n【可配套展示的素材候选】\n' + '\n'.join(media_lines) + '\n'

    header = (
        '你是一个智能体助手。以下是与用户当前问题相关的知识库参考内容。\n'
        '请严格参考这些内容进行回答。如果参考内容与用户问题相关，请优先基于参考内容回答；\n'
        '如果参考内容中没有相关信息或与用户问题无关，请忽略它们并使用你已有的知识回答，但不要向用户提及“根据参考内容”或“根据知识库”等字眼。\n\n'
        '【知识库参考信息】\n'
    )
    return header + ''.join(context_parts) + media_context + '---\n'


def retrieve_knowledge_context_with_media(
    application,
    query: str,
    top_n: int = 5,
    max_chars: int = 3000,
    *,
    knowledge_document_ids: list[int] | None = None,
    knowledge_base_ids: list[int] | None = None,
) -> tuple[str, list[dict]]:
    if not application or not query:
        return '', []
    result = retrieve_knowledge_chunks(
        query=query,
        application=application,
        top_n=top_n,
        knowledge_document_ids=knowledge_document_ids,
        knowledge_base_ids=knowledge_base_ids,
    )
    context = _format_context_from_recall_result(result, max_chars=max_chars)
    blocks = [
        {
            'type': 'image' if item.get('resourceType') == Resource.TYPE_IMAGE else 'video',
            'resourceId': item.get('resourceId'),
        }
        for item in result.get('mediaAssets') or []
        if item.get('resourceId') and item.get('resourceType') in {Resource.TYPE_IMAGE, Resource.TYPE_VIDEO}
    ]
    return context, blocks


def retrieve_knowledge_context_with_recall(
    application,
    query: str,
    top_n: int = 5,
    max_chars: int = 3000,
    *,
    knowledge_document_ids: list[int] | None = None,
    knowledge_base_ids: list[int] | None = None,
) -> tuple[str, dict]:
    if not application or not query:
        return '', {}
    result = retrieve_knowledge_chunks(
        query=query,
        application=application,
        top_n=top_n,
        knowledge_document_ids=knowledge_document_ids,
        knowledge_base_ids=knowledge_base_ids,
        include_media=True,
    )
    context = _format_context_from_recall_result(result, max_chars=max_chars)
    return context, result


def inject_knowledge_context(conversation, api_messages, query: str) -> list[dict]:
    """
    Injects retrieved knowledge context into the OpenAI-compatible API messages list.
    The injected context goes right after the system prompt (if any), but before any history/user messages.
    """
    if not conversation.application:
        return api_messages

    runtime_config = conversation.application.runtime_config()
    context_str = retrieve_knowledge_context(
        conversation.application,
        query,
        knowledge_document_ids=runtime_config.get('knowledge_document_ids') or [],
        knowledge_base_ids=runtime_config.get('knowledge_base_ids') or [],
    )
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


def inject_knowledge_context_with_recall(conversation, api_messages, query: str) -> tuple[list[dict], dict]:
    if not conversation.application:
        return api_messages, {}

    runtime_config = conversation.application.runtime_config()
    context_str, recall_result = retrieve_knowledge_context_with_recall(
        conversation.application,
        query,
        knowledge_document_ids=runtime_config.get('knowledge_document_ids') or [],
        knowledge_base_ids=runtime_config.get('knowledge_base_ids') or [],
    )
    if not context_str:
        return api_messages, {}

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

    return new_messages, recall_result


def inject_knowledge_context_with_media(conversation, api_messages, query: str) -> tuple[list[dict], list[dict]]:
    if not conversation.application:
        return api_messages, []

    runtime_config = conversation.application.runtime_config()
    context_str, media_blocks = retrieve_knowledge_context_with_media(
        conversation.application,
        query,
        knowledge_document_ids=runtime_config.get('knowledge_document_ids') or [],
        knowledge_base_ids=runtime_config.get('knowledge_base_ids') or [],
    )
    if not context_str:
        return api_messages, []

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

    return new_messages, media_blocks
