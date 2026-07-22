from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterable

import httpx
import json
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_tea_openapi import models as open_api_models

from apps.ai_models.credential_crypto import decrypt_credential
from apps.ai_models.models import BailianKnowledgeConfig


class BailianKnowledgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadLease:
    lease_id: str
    url: str
    method: str
    headers: dict[str, str]


@dataclass(frozen=True)
class RetrievalNode:
    text: str
    score: float
    metadata: dict


def _required_config() -> tuple[BailianKnowledgeConfig, str]:
    config = BailianKnowledgeConfig.load()
    if not config.is_active or not config.is_configured:
        raise BailianKnowledgeError('百炼托管知识库尚未由超管完成配置或启用')
    return config, decrypt_credential(config.access_key_secret_encrypted)


def _client() -> tuple[BailianClient, BailianKnowledgeConfig]:
    config, access_key_secret = _required_config()
    sdk_config = open_api_models.Config(
        access_key_id=config.access_key_id,
        access_key_secret=access_key_secret,
        endpoint=config.endpoint,
    )
    return BailianClient(sdk_config), config


def _data(response):
    body = getattr(response, 'body', None)
    if body is None:
        raise BailianKnowledgeError('百炼响应缺少 body 字段')
    data = getattr(body, 'data', None)
    if data is None:
        code = str(getattr(body, 'code', '') or getattr(body, 'status', '') or 'UNKNOWN')
        message = str(getattr(body, 'message', '') or '响应缺少 data 字段').strip()
        raise BailianKnowledgeError(f'百炼请求失败（{code}）：{message}')
    return data


def apply_upload_lease(*, file_name: str, content_md5: str, file_size: int) -> UploadLease:
    client, config = _client()
    request = bailian_models.ApplyFileUploadLeaseRequest(
        file_name=file_name,
        md_5=content_md5,
        size_in_bytes=str(file_size),
    )
    data = _data(client.apply_file_upload_lease(config.category_id, config.workspace_id, request))
    param = getattr(data, 'param', None)
    lease_id = str(getattr(data, 'file_upload_lease_id', '') or '')
    url = str(getattr(param, 'url', '') or '')
    method = str(getattr(param, 'method', 'PUT') or 'PUT').upper()
    headers = {
        str(key): str(value)
        for key, value in dict(getattr(param, 'headers', {}) or {}).items()
        if value is not None
    }
    if not lease_id or not url:
        raise BailianKnowledgeError('百炼未返回有效的文件上传租约')
    return UploadLease(lease_id=lease_id, url=url, method=method, headers=headers)


def _file_chunks(file_obj: BinaryIO, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            return
        yield chunk


def upload_file(lease: UploadLease, file_obj: BinaryIO, *, file_size: int) -> None:
    headers = dict(lease.headers)
    headers.setdefault('Content-Length', str(file_size))
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        response = client.request(lease.method, lease.url, headers=headers, content=_file_chunks(file_obj))
    if response.status_code >= 400:
        raise BailianKnowledgeError(f'百炼文件上传失败（HTTP {response.status_code}）')


def add_file(*, lease_id: str, parser: str) -> str:
    client, config = _client()
    request = bailian_models.AddFileRequest(
        lease_id=lease_id,
        parser=parser,
        category_id=config.category_id,
    )
    file_id = str(getattr(_data(client.add_file(config.workspace_id, request)), 'file_id', '') or '')
    if not file_id:
        raise BailianKnowledgeError('百炼未返回有效的 FileId')
    return file_id


def describe_file(file_id: str) -> dict:
    client, config = _client()
    data = _data(client.describe_file(config.workspace_id, file_id, bailian_models.DescribeFileRequest()))
    return {
        'status': str(getattr(data, 'status', '') or ''),
        'error': str(getattr(data, 'parse_error_message', '') or ''),
        'parser': str(getattr(data, 'parser', '') or ''),
    }


def create_index(*, name: str, file_id: str) -> str:
    client, config = _client()
    request = bailian_models.CreateIndexRequest(
        name=name[:128],
        structure_type='unstructured',
        source_type='DATA_CENTER_FILE',
        sink_type='DEFAULT',
        document_ids=[file_id],
    )
    index_id = str(getattr(_data(client.create_index(config.workspace_id, request)), 'id', '') or '')
    if not index_id:
        raise BailianKnowledgeError('百炼未返回有效的 IndexId')
    return index_id


def submit_index(index_id: str) -> str:
    client, config = _client()
    data = _data(client.submit_index_job(config.workspace_id, bailian_models.SubmitIndexJobRequest(index_id=index_id)))
    job_id = str(getattr(data, 'id', '') or '')
    if not job_id:
        raise BailianKnowledgeError('百炼未返回有效的索引任务 ID')
    return job_id


def add_document_to_index(*, index_id: str, file_id: str) -> str:
    client, config = _client()
    request = bailian_models.SubmitIndexAddDocumentsJobRequest(
        index_id=index_id,
        document_ids=[file_id],
        source_type='DATA_CENTER_FILE',
    )
    job_id = str(getattr(_data(client.submit_index_add_documents_job(config.workspace_id, request)), 'id', '') or '')
    if not job_id:
        raise BailianKnowledgeError('百炼未返回有效的追加索引任务 ID')
    return job_id


def get_index_job_status(*, index_id: str, job_id: str) -> str:
    client, config = _client()
    request = bailian_models.GetIndexJobStatusRequest(index_id=index_id, job_id=job_id)
    return str(getattr(_data(client.get_index_job_status(config.workspace_id, request)), 'status', '') or '')


def retrieve(*, index_id: str, query: str, top_n: int, min_score: float) -> list[RetrievalNode]:
    client, config = _client()
    request = bailian_models.RetrieveRequest(
        index_id=index_id,
        query=query,
        dense_similarity_top_k=max(top_n * 4, top_n),
        rerank_top_n=top_n,
        rerank_min_score=min_score,
        enable_reranking=True,
    )
    nodes = getattr(_data(client.retrieve(config.workspace_id, request)), 'nodes', None) or []
    result = []
    for node in nodes:
        text = str(getattr(node, 'text', '') or '').strip()
        if not text:
            continue
        raw_metadata = getattr(node, 'metadata', {}) or {}
        if isinstance(raw_metadata, str):
            try:
                raw_metadata = json.loads(raw_metadata)
            except (TypeError, ValueError):
                raw_metadata = {}
        result.append(
        RetrievalNode(
            text=text,
            score=float(getattr(node, 'score', 0.0) or 0.0),
            metadata=dict(raw_metadata) if isinstance(raw_metadata, dict) else {},
        )
        )
    return result


def _is_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, 'status_code', None) or getattr(exc, 'statusCode', None)
    code = str(getattr(exc, 'code', '') or '').lower()
    return status_code == 404 or 'notfound' in code or 'not_found' in code


def delete_file(file_id: str) -> None:
    client, config = _client()
    try:
        client.delete_file(file_id, config.workspace_id, bailian_models.DeleteFileRequest())
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise


def delete_document(*, index_id: str, file_id: str) -> None:
    client, config = _client()
    try:
        client.delete_index_document(
            config.workspace_id,
            bailian_models.DeleteIndexDocumentRequest(index_id=index_id, document_ids=[file_id]),
        )
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise
    try:
        client.delete_file(file_id, config.workspace_id, bailian_models.DeleteFileRequest())
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise


def delete_index(index_id: str) -> None:
    client, config = _client()
    try:
        client.delete_index(config.workspace_id, bailian_models.DeleteIndexRequest(index_id=index_id))
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise
