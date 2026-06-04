from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from .services.feishu import notify_command_change, notify_command_event

logger = logging.getLogger(__name__)


def _resolve_notification_user(user: Any) -> str:
    """将 Django User 转换为可序列化的操作人名称，供 Celery 任务使用。"""
    if user is None or getattr(user, 'is_authenticated', None) is False:
        return '匿名用户'

    for attribute in ('get_full_name', 'get_username'):
        getter = getattr(user, attribute, None)
        if callable(getter):
            try:
                value = getter()
            except Exception:  # pragma: no cover - 防御第三方 User 实现异常
                value = ''
            if value:
                return str(value).strip()

    for attribute in ('username', 'name', 'phone', 'email'):
        value = getattr(user, attribute, '')
        if value:
            return str(value).strip()

    return str(user) or '匿名用户'


def _resolve_notification_company(user: Any) -> str:
    """将操作人所属公司转换为可序列化名称，供 Celery 任务使用。"""
    if user is None or getattr(user, 'is_authenticated', None) is False:
        return ''
    try:
        membership = getattr(user, 'membership', None)
    except Exception:  # pragma: no cover - 防御第三方 User 实现异常
        return ''
    tenant = getattr(membership, 'tenant', None)
    return str(getattr(tenant, 'name', '') or '').strip()


@shared_task
def notify_command_event_task(
    action: str,
    user_label: str,
    command_type: str,
    command_name: str,
    command_code: str = '',
    extra_lines: list[str] | None = None,
    company_name: str = '',
) -> str:
    notified = notify_command_event(action, user_label, command_type, command_name, command_code, extra_lines, company_name)
    return f'command_event_notified:{action}:{notified}'


def enqueue_command_notification(
    action: str,
    user: Any,
    command_type: str,
    command_name: str,
    command_code: str = '',
    extra_lines: list[str] | None = None,
) -> bool:
    """只投递飞书通知任务，不在接口请求中等待 webhook 结果。"""
    user_label = _resolve_notification_user(user)
    company_name = _resolve_notification_company(user)
    try:
        notify_command_event_task.delay(action, user_label, command_type, command_name, command_code, extra_lines or [], company_name)
    except Exception as exc:  # pragma: no cover - broker 故障只影响通知投递，不影响业务接口
        logger.warning('Failed to enqueue command notification: %s', exc)
        return False
    return True


@shared_task
def notify_command_change_task(
    action: str,
    user_label: str,
    command_type: str,
    name_before: str,
    name_after: str,
    command_code_before: str,
    command_code_after: str,
    group_name: str = '',
    company_name: str = '',
) -> str:
    """以卡片形式发送指令名称变更通知。仅在调用方判定字段确实变更后才投递。"""
    notified = notify_command_change(
        action=action,
        user=user_label,
        command_type=command_type,
        name_before=name_before,
        name_after=name_after,
        command_code_before=command_code_before,
        command_code_after=command_code_after,
        group_name=group_name,
        company_name=company_name,
    )
    return f'command_change_notified:{action}:{notified}'


def enqueue_command_change_notification(
    *,
    action: str,
    user: Any,
    command_type: str,
    name_before: str,
    name_after: str,
    command_code_before: str,
    command_code_after: str,
    group_name: str = '',
) -> bool:
    """只投递指令名称变更卡片通知任务。"""
    user_label = _resolve_notification_user(user)
    company_name = _resolve_notification_company(user)
    try:
        notify_command_change_task.delay(
            action,
            user_label,
            command_type,
            name_before or '',
            name_after or '',
            command_code_before or '',
            command_code_after or '',
            group_name or '',
            company_name,
        )
    except Exception as exc:  # pragma: no cover - broker 故障只影响通知投递，不影响业务接口
        logger.warning('Failed to enqueue command change notification: %s', exc)
        return False
    return True
