from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_ACTION_LABELS = {
    'create': '新增',
    'update': '修改',
    'delete': '删除',
}

_SPECIAL_ROUTE_LABELS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^/api/v1/resources/videos/upload-config/?$'), '视频上传'),
    (re.compile(r'^/api/v1/resources/videos/presign/?$'), '视频上传'),
    (re.compile(r'^/api/v1/settings/minio/quotas/?$'), '视频配额'),
    (re.compile(r'^/api/v1/settings/minio/?$'), 'MinIO 配置'),
    (re.compile(r'^/api/v1/tenants(?:/|$)'), '公司'),
    (re.compile(r'^/api/v1/resources/images(?:/|$)'), '背景图资源'),
    (re.compile(r'^/api/v1/resources/videos(?:/|$)'), '视频资源'),
    (re.compile(r'^/api/v1/resources/scrolling-texts(?:/|$)'), '滚动文案'),
    (re.compile(r'^/api/v1/resources/voice-tones(?:/|$)'), '音色'),
    (re.compile(r'^/api/v1/resources/models(?:/|$)'), '数字人模型'),
    (re.compile(r'^/api/v1/knowledge-base(?:/|$)'), '知识库文档'),
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
    route_label = _describe_route(path)
    resource_name = _extract_resource_name(getattr(response, 'data', None))

    description = f'{action_label}{route_label}'
    if resource_name:
        description = f'{description}：{resource_name}'
    return description[:255]


def _describe_route(path: str) -> str:
    normalized = (path or '').split('?', 1)[0].strip()
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


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip()
