from __future__ import annotations

from typing import Any

from apps.resources.models import CommandGroup, ControlCommand, TaskCommand


def build_control_command_tools(tenant_id: int | None) -> list[dict[str, Any]]:
    """Build OpenAI-compatible tool schemas for active control commands of a tenant."""
    if tenant_id is None:
        return []
    commands = list(
        ControlCommand.objects.select_related('group')
        .filter(tenant_id=tenant_id, is_active=True, group__is_active=True)
        .order_by('id')
    )
    return [build_control_command_tool(cmd) for cmd in commands]


def build_control_command_tool(cmd: ControlCommand) -> dict[str, Any]:
    description = cmd.name.strip() or cmd.command_code
    return {
        'type': 'function',
        'function': {
            'name': cmd.command_code,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string', 'description': description},
                    'content': {'type': 'string', 'description': description},
                },
            },
        },
        # 自定义元数据，便于命中后定位指令（不进入上游 LLM 请求体，由 dispatch 剥离）。
        '_command_meta': {
            'kind': 'control',
            'id': cmd.id,
            'commandCode': cmd.command_code,
            'name': cmd.name,
            'protocol': cmd.protocol,
            'host': cmd.host,
            'port': cmd.port,
            'commandValueType': cmd.command_value_type,
            'backendSendEnabled': cmd.backend_send_enabled,
            'executionReply': cmd.execution_reply,
            'replyStrategy': cmd.reply_strategy,
        },
    }


def build_task_command_tools(tenant_id: int | None) -> list[dict[str, Any]]:
    """Build OpenAI-compatible tool schemas for active task commands of a tenant."""
    if tenant_id is None:
        return []
    commands = list(
        TaskCommand.objects.select_related('group')
        .filter(tenant_id=tenant_id, is_active=True)
        .order_by('id')
    )
    return [build_task_command_tool(cmd) for cmd in commands]


def build_task_command_tool(cmd: TaskCommand) -> dict[str, Any]:
    description = cmd.name.strip() or cmd.command_code
    return {
        'type': 'function',
        'function': {
            'name': cmd.command_code,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string', 'description': description},
                    'content': {'type': 'string', 'description': description},
                },
            },
        },
        '_command_meta': {
            'kind': 'task',
            'id': cmd.id,
            'commandCode': cmd.command_code,
            'name': cmd.name,
        },
    }


def build_command_tools(tenant_id: int | None) -> list[dict[str, Any]]:
    """Combine control and task command tools for a tenant."""
    return [*build_control_command_tools(tenant_id), *build_task_command_tools(tenant_id)]


def strip_meta(tool: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the tool schema without the internal `_command_meta` field."""
    return {k: v for k, v in tool.items() if k != '_command_meta'}


def strip_tools_meta(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [strip_meta(tool) for tool in tools]


def find_tool_by_name(tools: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for tool in tools:
        if tool.get('function', {}).get('name') == name:
            return tool
    return None


def has_command_tools(tenant_id: int | None) -> bool:
    if tenant_id is None:
        return False
    return (
        ControlCommand.objects.filter(tenant_id=tenant_id, is_active=True).exists()
        or TaskCommand.objects.filter(tenant_id=tenant_id, is_active=True).exists()
    )


def command_index_map(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map command_code -> tool (with _command_meta) for quick lookup."""
    result: dict[str, dict[str, Any]] = {}
    for tool in tools:
        name = tool.get('function', {}).get('name')
        if name:
            result[name] = tool
    return result
