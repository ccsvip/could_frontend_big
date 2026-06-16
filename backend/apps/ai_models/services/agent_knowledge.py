import re
import logging
from django.core.files.base import ContentFile
from apps.knowledge_base.models import KnowledgeDocument

logger = logging.getLogger(__name__)


def chunk_text(text: str, max_chunk_len: int = 500, overlap: int = 50) -> list[str]:
    """Splits a document text into smaller chunks by paragraph or fixed length."""
    paragraphs = []
    # Replace carriage returns and split by double newlines for paragraphs
    raw_paragraphs = text.replace('\r\n', '\n').split('\n\n')
    for raw_p in raw_paragraphs:
        p = raw_p.strip()
        if not p:
            continue
        # If a single paragraph is too long, slice it with overlap
        if len(p) > max_chunk_len:
            start = 0
            while start < len(p):
                end = start + max_chunk_len
                paragraphs.append(p[start:end])
                start += max_chunk_len - overlap
        else:
            paragraphs.append(p)
    return paragraphs


def extract_keywords(query: str) -> set[str]:
    """Extracts keyword terms from the query for simple term-matching."""
    query = query.lower()
    # Remove common punctuation
    cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', query)
    terms = set()
    
    # English keywords (length >= 2)
    for word in re.findall(r'[a-zA-Z0-9]+', cleaned):
        if len(word) >= 2:
            terms.add(word)
            
    # Chinese blocks
    chinese_blocks = re.findall(r'[\u4e00-\u9fff]+', cleaned)
    for block in chinese_blocks:
        if len(block) <= 3:
            terms.add(block)
        else:
            # Overlapping bigrams and trigrams
            for i in range(len(block) - 1):
                terms.add(block[i:i+2])
            for i in range(len(block) - 2):
                terms.add(block[i:i+3])
                
    # Add whole cleaned query without spaces
    full_clean = re.sub(r'\s+', '', cleaned)
    if full_clean:
        terms.add(full_clean)
        
    return {t for t in terms if t}


def score_chunk(chunk: str, keywords: set[str], query: str) -> float:
    """Calculates a match score for a text chunk against keywords and query."""
    chunk_lower = chunk.lower()
    score = 0.0
    for kw in keywords:
        if kw in chunk_lower:
            score += len(kw)
    # Direct substring matching bonus
    if query.lower() in chunk_lower:
        score += len(query) * 2.0
    return score


def retrieve_knowledge_context(application, query: str, top_n: int = 5, max_chars: int = 3000) -> str:
    """
    Retrieves matching document fragments from txt/md documents bound to the application.
    Returns a formatted string containing the top matching fragments.
    """
    if not application or not query:
        return ""

    try:
        # Get bound documents that are txt/md, approved, and belong to the same tenant
        docs = application.knowledge_documents.filter(
            tenant=application.tenant,
            processing_status=KnowledgeDocument.STATUS_APPROVED,
            file_extension__in=['txt', 'md']
        )
        
        keywords = extract_keywords(query)
        if not keywords:
            return ""

        all_scored_chunks = []

        for doc in docs:
            try:
                # Use django storage API to read file
                with doc.file.open('r') as f:
                    content_bytes = f.read()
                    if isinstance(content_bytes, bytes):
                        content = content_bytes.decode('utf-8', errors='ignore')
                    else:
                        content = content_bytes
                
                chunks = chunk_text(content)
                for chunk in chunks:
                    score = score_chunk(chunk, keywords, query)
                    if score > 0:
                        all_scored_chunks.append({
                            'doc_title': doc.title,
                            'content': chunk,
                            'score': score
                        })
            except Exception as e:
                logger.warning("Failed to read knowledge document id=%s error=%s", doc.id, e)
                continue

        if not all_scored_chunks:
            return ""

        # Sort by score descending
        all_scored_chunks.sort(key=lambda x: x['score'], reverse=True)
        top_chunks = all_scored_chunks[:top_n]

        # Format into context string
        context_parts = []
        current_len = 0
        
        for chunk_info in top_chunks:
            part = f"---\n文档: {chunk_info['doc_title']}\n内容: {chunk_info['content']}\n"
            if current_len + len(part) > max_chars:
                break
            context_parts.append(part)
            current_len += len(part)

        if not context_parts:
            return ""

        header = (
            "你是一个智能体助手。以下是与用户当前问题相关的知识库参考内容。\n"
            "请严格参考这些内容进行回答。如果参考内容与用户问题相关，请优先基于参考内容回答；\n"
            "如果参考内容中没有相关信息或与用户问题无关，请忽略它们并使用你已有的知识回答，但不要向用户提及“根据参考内容”或“根据知识库”等字眼。\n\n"
            "【知识库参考信息】\n"
        )
        footer = "---\n"
        
        return header + "".join(context_parts) + footer
    except Exception as e:
        logger.exception("Error during knowledge base retrieval: %s", e)
        return ""


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

    # Create a system message with the context
    context_msg = {
        'role': 'system',
        'content': context_str
    }

    new_messages = []
    # If the first message is the system prompt, put context right after it
    if api_messages and api_messages[0]['role'] == 'system':
        new_messages.append(api_messages[0])
        new_messages.append(context_msg)
        new_messages.extend(api_messages[1:])
    else:
        new_messages.append(context_msg)
        new_messages.extend(api_messages)

    return new_messages
