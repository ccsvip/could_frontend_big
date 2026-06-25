from celery import shared_task

from apps.ai_models.services.agent_knowledge import build_document_index_by_id
from config.business_cache import clear_business_cache_namespace


@shared_task
def build_knowledge_document_index(document_id: int, force: bool = False) -> dict:
    result = build_document_index_by_id(document_id, force=force)
    clear_business_cache_namespace('knowledge_base')
    return result
