from __future__ import annotations

import hashlib
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_models.models import TenantKnowledgeModelSettings

from . import bailian
from .models import KnowledgeBase, KnowledgeDocument


PARSE_SUCCESS = 'PARSE_SUCCESS'
PARSE_FAILED_STATUSES = {'PARSE_FAILED', 'FAILED', 'ERROR'}
INDEX_SUCCESS_STATUSES = {'COMPLETED', 'SUCCESS', 'SUCCEEDED'}
INDEX_FAILED_STATUSES = {'FAILED', 'ERROR', 'CANCELED', 'CANCELLED'}


def _assert_tenant_authorized(document: KnowledgeDocument) -> None:
    authorized = TenantKnowledgeModelSettings.objects.filter(
        tenant=document.tenant,
        is_active=True,
        managed_rag_enabled=True,
    ).exists()
    if not authorized:
        raise bailian.BailianKnowledgeError('当前公司尚未获得百炼托管知识库授权')


def _file_md5(document: KnowledgeDocument) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with document.file.open('rb') as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _update_document(document_id: int, **values) -> None:
    KnowledgeDocument.objects.filter(pk=document_id).update(**values)


def _wait_for_parse(document: KnowledgeDocument) -> None:
    max_attempts = int(getattr(settings, 'BAILIAN_PARSE_POLL_ATTEMPTS', 60))
    interval = float(getattr(settings, 'BAILIAN_POLL_INTERVAL_SECONDS', 5))
    for _ in range(max_attempts):
        result = bailian.describe_file(document.bailian_file_id)
        status = result['status']
        _update_document(document.pk, bailian_parse_status=status)
        document.bailian_parse_status = status
        if status == PARSE_SUCCESS:
            return
        if status in PARSE_FAILED_STATUSES:
            raise bailian.BailianKnowledgeError(result['error'] or f'百炼文件解析失败：{status}')
        time.sleep(interval)
    raise bailian.BailianKnowledgeError('等待百炼文件解析超时')


def _wait_for_index(*, index_id: str, job_id: str) -> None:
    max_attempts = int(getattr(settings, 'BAILIAN_INDEX_POLL_ATTEMPTS', 60))
    interval = float(getattr(settings, 'BAILIAN_POLL_INTERVAL_SECONDS', 5))
    for _ in range(max_attempts):
        status = bailian.get_index_job_status(index_id=index_id, job_id=job_id)
        KnowledgeBase.objects.filter(bailian_index_id=index_id).update(bailian_index_status=status)
        if status in INDEX_SUCCESS_STATUSES:
            return
        if status in INDEX_FAILED_STATUSES:
            raise bailian.BailianKnowledgeError(f'百炼索引任务失败：{status}')
        time.sleep(interval)
    raise bailian.BailianKnowledgeError('等待百炼索引任务超时')


def _upload_document(document: KnowledgeDocument, content_md5: str) -> str:
    lease = bailian.apply_upload_lease(
        file_name=document.file_name,
        content_md5=content_md5,
        file_size=int(document.file_size or document.file.size),
    )
    with document.file.open('rb') as file_obj:
        bailian.upload_file(lease, file_obj, file_size=int(document.file_size or document.file.size))
    return bailian.add_file(lease_id=lease.lease_id, parser=document.knowledge_base.parser)


def _submit_document_index(document: KnowledgeDocument) -> tuple[str, str]:
    with transaction.atomic():
        knowledge_base = KnowledgeBase.objects.select_for_update().get(pk=document.knowledge_base_id)
        if not knowledge_base.bailian_index_id:
            index_id = bailian.create_index(
                name=f'{document.tenant_id}-{knowledge_base.name}',
                file_id=document.bailian_file_id,
            )
            job_id = bailian.submit_index(index_id)
            knowledge_base.bailian_index_id = index_id
        else:
            index_id = knowledge_base.bailian_index_id
            job_id = bailian.add_document_to_index(
                index_id=index_id,
                file_id=document.bailian_file_id,
            )
        knowledge_base.bailian_index_job_id = job_id
        knowledge_base.bailian_index_status = 'RUNNING'
        knowledge_base.bailian_index_error = ''
        knowledge_base.save(
            update_fields=[
                'bailian_index_id',
                'bailian_index_job_id',
                'bailian_index_status',
                'bailian_index_error',
                'updated_at',
            ]
        )
    return index_id, job_id


def build_managed_document_index(document_id: int, *, force: bool = False) -> dict:
    document = (
        KnowledgeDocument.objects
        .select_related('tenant', 'knowledge_base')
        .get(pk=document_id)
    )
    if not document.file or document.knowledge_base_id is None:
        raise bailian.BailianKnowledgeError('文档文件或所属知识库不存在')

    try:
        _assert_tenant_authorized(document)
        content_md5 = _file_md5(document)
        if (
            not force
            and document.index_status == KnowledgeDocument.IndexStatus.READY
            and document.content_md5 == content_md5
            and document.bailian_file_id
        ):
            return {
                'documentId': document.pk,
                'status': document.index_status,
                'indexModel': 'bailian-managed-rag',
            }

        if force and document.bailian_file_id and document.knowledge_base.bailian_index_id:
            bailian.delete_document(
                index_id=document.knowledge_base.bailian_index_id,
                file_id=document.bailian_file_id,
            )
            document.bailian_file_id = ''
            _update_document(
                document.pk,
                bailian_file_id='',
                bailian_parse_status='',
                bailian_index_job_id='',
                bailian_synced_at=None,
            )

        _update_document(
            document.pk,
            index_status=KnowledgeDocument.IndexStatus.INDEXING,
            index_error='',
            indexed_at=None,
            content_md5=content_md5,
            bailian_parse_status='UPLOADING',
            sync_attempt=document.sync_attempt + 1,
        )
        document.content_md5 = content_md5

        if not document.bailian_file_id:
            document.bailian_file_id = _upload_document(document, content_md5)
            _update_document(
                document.pk,
                bailian_file_id=document.bailian_file_id,
                bailian_parse_status='PARSING',
            )

        _wait_for_parse(document)
        index_id, job_id = _submit_document_index(document)
        _update_document(document.pk, bailian_index_job_id=job_id)
        _wait_for_index(index_id=index_id, job_id=job_id)

        synced_at = timezone.now()
        _update_document(
            document.pk,
            index_status=KnowledgeDocument.IndexStatus.READY,
            index_error='',
            indexed_at=synced_at,
            chunk_count=0,
            index_model='bailian-managed-rag',
            bailian_synced_at=synced_at,
        )
        KnowledgeBase.objects.filter(pk=document.knowledge_base_id).update(
            bailian_index_status='COMPLETED',
            bailian_index_error='',
            bailian_synced_at=synced_at,
        )
        return {
            'documentId': document.pk,
            'status': KnowledgeDocument.IndexStatus.READY,
            'indexModel': 'bailian-managed-rag',
            'mode': 'managed',
        }
    except Exception as exc:
        error = str(exc)[:1000]
        _update_document(
            document.pk,
            index_status=KnowledgeDocument.IndexStatus.FAILED,
            index_error=error,
            indexed_at=None,
            index_model='bailian-managed-rag',
        )
        if document.knowledge_base_id:
            KnowledgeBase.objects.filter(pk=document.knowledge_base_id).update(bailian_index_error=error)
        return {
            'documentId': document.pk,
            'status': KnowledgeDocument.IndexStatus.FAILED,
            'indexModel': 'bailian-managed-rag',
            'error': error,
        }
