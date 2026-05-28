from __future__ import annotations

from typing import Any, Iterable

from apps.resources.services.feishu import notify_business_event

from .models import KnowledgeDocument


def _document_display_name(document: KnowledgeDocument) -> str:
    return document.title or document.file_name or f'文档 #{document.pk}'


def notify_knowledge_document_event(action: str, user: Any, document: KnowledgeDocument) -> bool:
    """发送知识库单文档操作通知。"""
    return notify_business_event(
        title='知识库文档操作通知',
        action=action,
        user=user,
        target_label='文档标题',
        target_name=_document_display_name(document),
        extra_lines=[
            f'文档ID：{document.pk}',
            f'文件名：{document.file_name or "未记录"}',
        ],
    )


def notify_knowledge_document_deleted(user: Any, *, document_id: int | None, title: str, file_name: str) -> bool:
    """发送知识库文档删除通知，避免删除后模型主键被清空。"""
    return notify_business_event(
        title='知识库文档操作通知',
        action='delete',
        user=user,
        target_label='文档标题',
        target_name=title or file_name or f'文档 #{document_id}',
        extra_lines=[
            f'文档ID：{document_id}',
            f'文件名：{file_name or "未记录"}',
        ],
    )


def notify_knowledge_bulk_download(user: Any, documents: Iterable[KnowledgeDocument]) -> bool:
    """发送知识库批量下载通知。"""
    document_list = list(documents)
    names = '、'.join(_document_display_name(document) for document in document_list)
    return notify_business_event(
        title='知识库文档操作通知',
        action='bulk_download',
        user=user,
        target_label='文档标题',
        target_name=names or '批量文档',
        extra_lines=[f'文档数量：{len(document_list)}'],
    )
