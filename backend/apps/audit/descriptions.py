from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_ACTION_LABELS = {
    'create': '新增',
    'update': '修改',
    'delete': '删除',
}

_SPECIAL_OPERATION_LABELS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^/api/v1/tenants/\d+/menus/?$'), '分配公司菜单'),
    (re.compile(r'^/api/v1/account-applications/\d+/approve/?$'), '通过账号申请'),
    (re.compile(r'^/api/v1/account-applications/\d+/reject/?$'), '拒绝账号申请'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/bind/?$'), '绑定设备到公司'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/ignore/?$'), '忽略设备授权请求'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/authorize/?$'), '再次授权设备'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/revoke/?$'), '撤销设备授权'),
]

_SPECIAL_ROUTE_LABELS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^/api/v1/resources/videos/upload-config/?$'), '视频上传'),
    (re.compile(r'^/api/v1/resources/videos/presign/?$'), '视频上传'),
    (re.compile(r'^/api/v1/settings/minio/quotas/?$'), '视频配额'),
    (re.compile(r'^/api/v1/settings/minio/?$'), 'MinIO 配置'),
    (re.compile(r'^/api/v1/settings/llm/providers/\d+/models/?$'), '平台LLM模型'),
    (re.compile(r'^/api/v1/settings/llm/providers(?:/|$)'), '平台LLM厂商'),
    (re.compile(r'^/api/v1/settings/llm/models(?:/|$)'), '平台LLM模型'),
    (re.compile(r'^/api/v1/settings/llm/test-settings/?$'), 'LLM测试设置'),
    (re.compile(r'^/api/v1/settings/llm/tenants/\d+/authorization/?$'), '公司LLM授权'),
    (re.compile(r'^/api/v1/tenants(?:/|$)'), '公司'),
    (re.compile(r'^/api/v1/resources/images(?:/|$)'), '图片资源'),
    (re.compile(r'^/api/v1/resources/videos(?:/|$)'), '视频资源'),
    (re.compile(r'^/api/v1/resources/scrolling-texts(?:/|$)'), '滚动文案'),
    (re.compile(r'^/api/v1/resources/voice-tones(?:/|$)'), '音色'),
    (re.compile(r'^/api/v1/resources/models(?:/|$)'), '数字人模型'),
    (re.compile(r'^/api/v1/knowledge-base(?:/|$)'), '知识库文档'),
    (re.compile(r'^/api/v1/ai-models/asr/replacement-rules(?:/|$)'), 'ASR替换词'),
    (re.compile(r'^/api/v1/ai-models/llm-providers(?:/|$)'), '模型供应商'),
    (re.compile(r'^/api/v1/ai-models/chat/conversations(?:/|$)'), '会话'),
    (re.compile(r'^/api/v1/commands/groups(?:/|$)'), '指令分组'),
    (re.compile(r'^/api/v1/commands/control(?:/|$)'), '控制指令'),
    (re.compile(r'^/api/v1/commands/tasks(?:/|$)'), '任务指令'),
    (re.compile(r'^/api/v1/commands/points(?:/|$)'), '指令点位'),
    (re.compile(r'^/api/v1/device-groups(?:/|$)'), '设备分组'),
    (re.compile(r'^/api/v1/device-applications(?:/|$)'), '设备应用'),
    (re.compile(r'^/api/v1/device-authorization-codes(?:/|$)'), '设备授权码'),
    (re.compile(r'^/api/v1/device-authorization-requests(?:/|$)'), '设备授权申请'),
    (re.compile(r'^/api/v1/devices(?:/|$)'), '设备'),
]

_RESOURCE_NAME_KEYS = (
    'name',
    'title',
    'displayName',
    'modelName',
    'filename',
    'fileName',
)


def describe_operation(*, request, response, action: str, method: str, path: str) -> str:
    action_label = _ACTION_LABELS.get(action, '操作')
    normalized_path = _normalize_path(path)
    response_data = getattr(response, 'data', None)
    operation_label = _describe_knowledge_review_operation(normalized_path, response_data)
    if not operation_label:
        operation_label = _describe_special_operation(normalized_path)
    route_label = operation_label or _describe_route(normalized_path)
    resource_name = _extract_resource_name(response_data)

    description = route_label if operation_label else f'{action_label}{route_label}'
    if resource_name:
        description = f'{description}：{resource_name}'
    return description[:255]


def _describe_route(path: str) -> str:
    normalized = _normalize_path(path)
    for pattern, label in _SPECIAL_ROUTE_LABELS:
        if pattern.match(normalized):
            return label

    if normalized.startswith('/api/v1/'):
        remainder = normalized[len('/api/v1/') :].strip('/')
        if remainder:
            top_level = remainder.split('/', 1)[0]
            return {
                'tenants': '公司',
                'resources': '资源',
                'knowledge-base': '知识库',
                'ai-models': 'AI 模型',
                'commands': '指令',
                'devices': '设备',
                'device-groups': '设备分组',
                'device-applications': '设备应用',
                'device-authorization-codes': '设备授权码',
                'device-authorization-requests': '设备授权申请',
                'settings': '系统设置',
                'audit': '审计',
            }.get(top_level, top_level.replace('-', ' '))

    return '接口'


def _describe_special_operation(path: str) -> str:
    for pattern, label in _SPECIAL_OPERATION_LABELS:
        if pattern.match(path):
            return label
    return ''


def _describe_knowledge_review_operation(path: str, response_data: Any) -> str:
    if not re.match(r'^/api/v1/knowledge-base/\d+/review/?$', path):
        return ''

    status_value = _extract_processing_status(response_data)
    if status_value == 'approved':
        return '通过知识库文档审核'
    if status_value == 'rejected':
        return '拒绝知识库文档审核'
    return '审核知识库文档'


def _normalize_path(path: str) -> str:
    return (path or '').split('?', 1)[0].strip()


def _extract_resource_name(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in _RESOURCE_NAME_KEYS:
            candidate = value.get(key)
            text = _clean_text(candidate)
            if text:
                return text

        for nested_key in ('data', 'result', 'results', 'item', 'items'):
            nested = value.get(nested_key)
            text = _extract_resource_name(nested)
            if text:
                return text

        for nested in value.values():
            if isinstance(nested, (Mapping, list, tuple)):
                text = _extract_resource_name(nested)
                if text:
                    return text

    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            text = _extract_resource_name(item)
            if text:
                return text

    return ''


def _extract_processing_status(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ('processingStatus', 'processing_status'):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        for nested_key in ('data', 'result', 'item'):
            status_value = _extract_processing_status(value.get(nested_key))
            if status_value:
                return status_value

        for nested in value.values():
            if isinstance(nested, (Mapping, list, tuple)):
                status_value = _extract_processing_status(nested)
                if status_value:
                    return status_value

    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            status_value = _extract_processing_status(item)
            if status_value:
                return status_value

    return ''


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip()
