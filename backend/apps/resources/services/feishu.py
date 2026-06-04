"""Feishu (飞书) webhook notification service.

Sends text notifications to a configured Feishu custom-bot webhook.
Failures are logged and never raised to the caller so business operations
(e.g. creating/updating/deleting commands) are never blocked by notification
issues.

Environment configuration:
    FEISHU_WEBHOOK_URL    - Required. The custom-bot webhook URL provided by Feishu.
    FEISHU_WEBHOOK_SECRET - Optional. Used only when the bot has the
                            "签名校验" (signature verification) security strategy
                            enabled.
    HOST_IP               - Optional. Public host/IP shown in notification text.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import socket
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo('Asia/Shanghai')
DEFAULT_TIMEOUT_SECONDS = 5.0


def _build_signature(timestamp: int, secret: str) -> str:
    """Build the signature required by Feishu webhook when security key is enabled."""
    string_to_sign = f'{timestamp}\n{secret}'
    digest = hmac.new(
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode('utf-8')


def _format_beijing_now() -> str:
    """Return current Beijing time formatted as `YYYY-MM-DD HH:MM:SS`."""
    return datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')


def _is_localhost(ip: str) -> bool:
    """判断 IP 是否属于本地回环地址。"""
    return ip in ('127.0.0.1', '::1') or ip.startswith('127.')


def _resolve_server_ip() -> str:
    """解析当前服务端 IP，优先使用显式配置，避免容器主机名解析不稳定。"""
    host_ip = str(getattr(settings, 'HOST_IP', '')).strip()
    if host_ip:
        # HOST_IP 由部署环境显式声明，优先作为飞书通知里的宿主机地址。
        return 'localhost' if _is_localhost(host_ip) else host_ip

    configured_ip = str(getattr(settings, 'FEISHU_SERVER_IP', '') or getattr(settings, 'SERVER_IP', '')).strip()
    if configured_ip:
        # 本地回环地址统一返回 localhost
        if _is_localhost(configured_ip):
            return 'localhost'
        # 容器网络地址（如 172.x、198.18.x）说明是本地测试环境
        if configured_ip.startswith('172.') or configured_ip.startswith('198.18.'):
            return 'localhost'
        return configured_ip

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            if ip:
                # 本地回环地址统一返回 localhost
                if _is_localhost(ip):
                    return 'localhost'
                # 容器网络地址（如 172.x、198.18.x）说明是本地测试环境
                if ip.startswith('172.') or ip.startswith('198.18.'):
                    return 'localhost'
                return ip
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if _is_localhost(ip):
            return 'localhost'
        # 容器网络地址检查
        if ip.startswith('172.') or ip.startswith('198.18.'):
            return 'localhost'
        return ip
    except OSError:
        return 'localhost'  # 解析失败时默认返回 localhost


def _append_server_ip(text: str) -> str:
    if '服务器IP：' in text or '服务器IP:' in text:
        return text
    return f'{text}\n服务器IP：{_resolve_server_ip()}'


def send_feishu_text(text: str) -> bool:
    """Send a plain text message to the configured Feishu webhook.

    Returns True if the request was accepted by Feishu (HTTP 200 and
    `code == 0`), otherwise False. Never raises.
    """
    webhook_url = getattr(settings, 'FEISHU_WEBHOOK_URL', '').strip()
    if not webhook_url:
        logger.info('Feishu webhook is not configured; skipping notification: %s', text)
        return False

    final_text = _append_server_ip(text)
    secret = getattr(settings, 'FEISHU_WEBHOOK_SECRET', '').strip()
    payload: dict[str, Any] = {
        'msg_type': 'text',
        'content': {'text': final_text},
    }
    if secret:
        timestamp = int(time.time())
        payload['timestamp'] = str(timestamp)
        payload['sign'] = _build_signature(timestamp, secret)

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.post(webhook_url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning('Failed to call Feishu webhook: %s', exc)
        return False

    if response.status_code >= 400:
        logger.warning(
            'Feishu webhook returned HTTP %s: %s',
            response.status_code,
            response.text[:500],
        )
        return False

    try:
        body = response.json()
    except ValueError:
        logger.warning('Feishu webhook returned non-JSON response: %s', response.text[:500])
        return False

    code = body.get('code') if isinstance(body, dict) else None
    if code not in (0, None):
        logger.warning('Feishu webhook returned business error: %s', body)
        return False

    return True


def _resolve_username(user: Any) -> str:
    """Best-effort extraction of a human-readable username."""
    if user is None:
        return '匿名用户'
    is_authenticated = getattr(user, 'is_authenticated', None)
    if is_authenticated is False:
        return '未登录用户'
    for attribute in ('get_full_name', 'get_username'):
        getter = getattr(user, attribute, None)
        if callable(getter):
            try:
                value = getter()
            except Exception:  # pragma: no cover - defensive
                value = ''
            if value:
                return str(value).strip()
    for attribute in ('username', 'name', 'phone', 'email'):
        value = getattr(user, attribute, '')
        if value:
            return str(value).strip()
    return str(user) or '匿名用户'


def _resolve_company_name(user: Any) -> str:
    if isinstance(user, str) or user is None or getattr(user, 'is_authenticated', None) is False:
        return ''
    try:
        membership = getattr(user, 'membership', None)
    except Exception:  # pragma: no cover - defensive
        return ''
    tenant = getattr(membership, 'tenant', None)
    return str(getattr(tenant, 'name', '') or '').strip()


def notify_business_event(
    title: str,
    action: str,
    user: Any,
    target_label: str,
    target_name: str,
    extra_lines: list[str] | None = None,
    company_name: str = '',
) -> bool:
    """发送通用业务操作通知；调用方只提供领域文案和业务字段。"""
    action_map = {
        'create': ('📥', '新增'),
        'update': ('✏️', '编辑'),
        'delete': ('🗑️', '删除'),
        'download': ('📤', '下载'),
        'bulk_download': ('📦', '批量下载'),
        'review': ('✅', '审核'),
        'submit': ('📩', '提交'),
    }
    icon, action_label = action_map.get(action, ('🔔', action))
    safe_name = (target_name or '').strip() or '(未命名)'
    resolved_company_name = (company_name or _resolve_company_name(user)).strip()
    lines = [
        f'{icon} {title}',
        f'操作人：{_resolve_username(user)}',
        f'操作类型：{action_label}',
    ]
    if resolved_company_name:
        lines.append(f'公司名称：{resolved_company_name}')
    lines.append(f'{target_label}：{safe_name}')
    if extra_lines:
        lines.extend(line for line in extra_lines if line)
    lines.append(f'北京时间：{_format_beijing_now()}')
    return send_feishu_text('\n'.join(lines))


def notify_command_event(
    action: str,
    user: Any,
    command_type: str,
    command_name: str,
    command_code: str = '',
    extra_lines: list[str] | None = None,
    company_name: str = '',
) -> bool:
    """发送指令体系 CRUD 变更通知。"""
    lines = list(extra_lines or [])
    if command_code:
        lines.insert(0, f'指令标识：{command_code}')
    target_label = '指令名称' if '指令' in command_type else '名称'
    return notify_business_event_card(
        title=f'{command_type}变更通知',
        action=action,
        user=user,
        target_label=target_label,
        target_name=command_name,
        extra_lines=lines,
        company_name=company_name,
    )


def notify_control_command_event(action: str, user: Any, command_name: str) -> bool:
    """Send a Feishu notification describing a control-command event.

    Args:
        action: 'create' | 'update' | 'delete'.
        user: The Django user performing the action (may be None / Anonymous).
        command_name: The display name (title) of the affected control command.
    """
    return notify_command_event(action, user, '控制指令', command_name)


# ---------------------------------------------------------------------------
# 飞书消息卡片：指令名称变更通知
# ---------------------------------------------------------------------------

# 不同操作对应的卡片头部颜色与文案。
_COMMAND_CARD_ACTION_META: dict[str, tuple[str, str, str]] = {
    'create': ('green', '📥', '新增'),
    'update': ('blue', '✏️', '编辑'),
    'delete': ('red', '🗑️', '删除'),
}


_BUSINESS_CARD_ACTION_META: dict[str, tuple[str, str, str]] = {
    'create': ('green', '📄', '新增'),
    'update': ('blue', '✏️', '编辑'),
    'delete': ('red', '🗑️', '删除'),
    'download': ('blue', '📥', '下载'),
    'bulk_download': ('blue', '📦', '批量下载'),
    'review': ('green', '✅', '审核'),
    'submit': ('blue', '📨', '提交'),
}


def send_feishu_card(card: dict[str, Any]) -> bool:
    """向飞书 webhook 发送 interactive 消息卡片。失败仅记录日志，不抛异常。"""
    webhook_url = getattr(settings, 'FEISHU_WEBHOOK_URL', '').strip()
    if not webhook_url:
        logger.info('Feishu webhook is not configured; skipping card notification.')
        return False

    secret = getattr(settings, 'FEISHU_WEBHOOK_SECRET', '').strip()
    payload: dict[str, Any] = {
        'msg_type': 'interactive',
        'card': card,
    }
    if secret:
        timestamp = int(time.time())
        payload['timestamp'] = str(timestamp)
        payload['sign'] = _build_signature(timestamp, secret)

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.post(webhook_url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning('Failed to call Feishu webhook (card): %s', exc)
        return False

    if response.status_code >= 400:
        logger.warning(
            'Feishu webhook (card) returned HTTP %s: %s',
            response.status_code,
            response.text[:500],
        )
        return False

    try:
        body = response.json()
    except ValueError:
        logger.warning('Feishu webhook (card) returned non-JSON response: %s', response.text[:500])
        return False

    code = body.get('code') if isinstance(body, dict) else None
    if code not in (0, None):
        logger.warning('Feishu webhook (card) returned business error: %s', body)
        return False

    return True


def build_business_event_card(
    *,
    title: str,
    action: str,
    user: Any,
    target_label: str,
    target_name: str,
    extra_lines: list[str] | None = None,
    company_name: str = '',
) -> dict[str, Any]:
    template, icon, action_label = _BUSINESS_CARD_ACTION_META.get(action, ('grey', '🔔', action))
    safe_name = (target_name or '').strip() or '(未命名)'
    resolved_company_name = (company_name or _resolve_company_name(user)).strip()
    fields = [
        {
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**操作人**\n{_resolve_username(user)}'},
        },
        {
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**操作类型**\n{action_label}'},
        },
    ]
    if resolved_company_name:
        fields.append({
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**公司名称**\n{resolved_company_name}'},
        })
    elements: list[dict[str, Any]] = [
        {
            'tag': 'div',
            'fields': fields,
        },
        {
            'tag': 'div',
            'text': {'tag': 'lark_md', 'content': f'**{target_label}**\n{safe_name}'},
        },
    ]
    if extra_lines:
        elements.append({'tag': 'hr'})
        elements.extend(
            {
                'tag': 'div',
                'text': {'tag': 'lark_md', 'content': line},
            }
            for line in extra_lines
            if line
        )
    elements.append({'tag': 'hr'})
    elements.append({
        'tag': 'note',
        'elements': [
            {
                'tag': 'plain_text',
                'content': f'北京时间：{_format_beijing_now()} · 服务器IP：{_resolve_server_ip()}',
            },
        ],
    })
    return {
        'config': {'wide_screen_mode': True},
        'header': {
            'template': template,
            'title': {'tag': 'plain_text', 'content': f'{icon} {title}'},
        },
        'elements': elements,
    }


def notify_business_event_card(
    title: str,
    action: str,
    user: Any,
    target_label: str,
    target_name: str,
    extra_lines: list[str] | None = None,
    company_name: str = '',
) -> bool:
    return send_feishu_card(
        build_business_event_card(
            title=title,
            action=action,
            user=user,
            target_label=target_label,
            target_name=target_name,
            extra_lines=extra_lines,
            company_name=company_name,
        )
    )


def _diff_field_element(label: str, before: str, after: str) -> dict[str, Any]:
    """构建"变更前 → 变更后"的字段块。任意一边为空时显示占位符。"""
    placeholder = '（空）'
    before_text = before if before else placeholder
    after_text = after if after else placeholder
    if before == after:
        # 未发生变化，仍展示当前值（用于 create / delete 场景）
        body = f'**{label}**\n`{after_text}`'
    else:
        body = (
            f'**{label}**\n'
            f'变更前：`{before_text}`\n'
            f'变更后：`{after_text}`'
        )
    return {
        'tag': 'div',
        'text': {'tag': 'lark_md', 'content': body},
    }


def build_command_change_card(
    *,
    action: str,
    user_label: str,
    command_type: str,
    name_before: str,
    name_after: str,
    command_code_before: str,
    command_code_after: str,
    group_name: str = '',
    company_name: str = '',
) -> dict[str, Any]:
    """构建指令名称/指令变更的飞书消息卡片。

    Args:
        action: 'create' | 'update' | 'delete'。
        user_label: 操作人显示名（已解析为字符串）。
        command_type: '控制指令' | '任务指令'。
        name_before / name_after: 名称字段的变更前后值。
        command_code_before / command_code_after: 指令/指令名称字段的变更前后值。
            - 控制指令的弹窗字段叫"指令"
            - 任务指令的弹窗字段叫"指令名称"
            两者在数据库里都是 ``command_code``。
        group_name: 所属指令分组名称（可选，仅展示）。
    """
    template, icon, action_label = _COMMAND_CARD_ACTION_META.get(action, ('grey', '🔔', action))
    title = f'{icon} {command_type}变更通知（{action_label}）'

    # 控制指令的字段名是"指令"，任务指令的字段名是"指令名称"。
    code_label = '指令名称' if '任务' in command_type else '指令'

    fields = [
        {
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**操作人**\n{user_label or "匿名用户"}'},
        },
        {
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**操作类型**\n{action_label}'},
        },
    ]
    if company_name:
        fields.append({
            'is_short': True,
            'text': {'tag': 'lark_md', 'content': f'**公司名称**\n{company_name}'},
        })
    elements: list[dict[str, Any]] = [
        {
            'tag': 'div',
            'fields': fields,
        },
    ]
    if group_name:
        elements.append({
            'tag': 'div',
            'text': {'tag': 'lark_md', 'content': f'**所属分组**\n{group_name}'},
        })
    elements.append({'tag': 'hr'})
    elements.append(_diff_field_element('名称', name_before, name_after))
    elements.append(_diff_field_element(code_label, command_code_before, command_code_after))
    elements.append({'tag': 'hr'})
    elements.append({
        'tag': 'note',
        'elements': [
            {
                'tag': 'plain_text',
                'content': f'北京时间：{_format_beijing_now()}　·　服务器IP：{_resolve_server_ip()}',
            },
        ],
    })

    return {
        'config': {'wide_screen_mode': True},
        'header': {
            'template': template,
            'title': {'tag': 'plain_text', 'content': title},
        },
        'elements': elements,
    }


def notify_command_change(
    *,
    action: str,
    user: Any,
    command_type: str,
    name_before: str,
    name_after: str,
    command_code_before: str,
    command_code_after: str,
    group_name: str = '',
    company_name: str = '',
) -> bool:
    """发送指令名称变更通知（卡片形式，包含变更前后值）。"""
    card = build_command_change_card(
        action=action,
        user_label=_resolve_username(user) if not isinstance(user, str) else (user or '匿名用户'),
        command_type=command_type,
        name_before=name_before or '',
        name_after=name_after or '',
        command_code_before=command_code_before or '',
        command_code_after=command_code_after or '',
        group_name=group_name or '',
        company_name=company_name or _resolve_company_name(user),
    )
    return send_feishu_card(card)
