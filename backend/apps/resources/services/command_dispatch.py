from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async
from django.db.models import Prefetch

from apps.resources.models import ControlCommand, ControlCommandRecognitionPolicy, TaskCommand, TaskCommandStep
from apps.resources.services import command_executor
from apps.resources.services.command_executor import ExecutionResult
from apps.resources.services.command_tools import (
    build_command_tools,
    command_index_map,
    strip_tools_meta,
)

logger = logging.getLogger(__name__)

DispatchCallback = Callable[[str], Awaitable[None]]
TtsSegmentCallback = Callable[[str], Awaitable[None]]


@dataclass(slots=True)
class DispatchOutcome:
    hit: bool
    reply_text: str
    tool_calls_summary: list[dict[str, Any]] | None = None
    matched_command_metas: list[dict[str, Any]] | None = None
    mode: str = 'tool'
    reply_source: str = 'fixed'
    highest_score: float | None = None
    second_highest_score: float | None = None
    candidate_count: int | None = None
    route: str | None = None
    confirmation_outcome: str | None = None
    execution_outcome: str | None = None


@dataclass(slots=True)
class CommandToolSelection:
    candidate_tools: list[dict[str, Any]]
    local_tool: dict[str, Any] | None = None
    highest_score: float = 0
    second_highest_score: float = 0
    candidate_count: int = 0


LOCAL_AUTO_EXECUTE_SCORE = 0.9
CONTROL_DIRECT_EXECUTION_MARGIN = 0.1
MAX_TOOL_CANDIDATES = 5
GENERATED_REPLY_PROMPT = '请根据指令执行结果用一句简短自然的中文向用户反馈，适合直接转成语音播报。'


async def build_command_dispatch_snapshots(
    *,
    tenant_id: int | None,
    command_metas: list[dict[str, Any]] | None,
    request=None,
) -> list[dict[str, Any]]:
    """Build complete runtime snapshots for commands actually dispatched."""
    if tenant_id is None or not command_metas:
        return []

    snapshots: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for meta in command_metas:
        key = (meta.get('kind'), meta.get('id'))
        if key in seen:
            continue
        seen.add(key)
        snapshot = await _build_runtime_command_snapshot(meta=meta, tenant_id=tenant_id, request=request)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


async def _build_runtime_command_snapshot(
    *,
    meta: dict[str, Any],
    tenant_id: int,
    request,
) -> dict[str, Any] | None:
    kind = meta.get('kind')
    command_id = meta.get('id')
    if kind == 'control':
        return await sync_to_async(_load_control_runtime_snapshot, thread_sensitive=True)(command_id, tenant_id)
    if kind == 'task':
        return await sync_to_async(_load_task_runtime_snapshot, thread_sensitive=True)(command_id, tenant_id, request)
    return None


def _load_control_runtime_snapshot(command_id: Any, tenant_id: int) -> dict[str, Any] | None:
    command = (
        ControlCommand.objects.select_related('group')
        .filter(id=command_id, tenant_id=tenant_id, is_active=True, group__is_active=True)
        .first()
    )
    if command is None:
        return None
    return {
        'commandType': 'control',
        'name': command.name,
        'command': command.command_code,
        'commandValueType': command.command_value_type,
        'callMethod': command.protocol,
        'backendSendEnabled': command.backend_send_enabled,
        'ip': command.host,
        'port': command.port,
    }


def _load_task_runtime_snapshot(command_id: Any, tenant_id: int, request) -> dict[str, Any] | None:
    inner_steps = TaskCommandStep.objects.select_related('control_command', 'point', 'resource').order_by('order', 'id')
    root_steps = (
        TaskCommandStep.objects.filter(parent__isnull=True)
        .select_related('control_command', 'point', 'resource')
        .prefetch_related(Prefetch('inner_tasks', queryset=inner_steps))
        .order_by('order', 'id')
    )
    command = (
        TaskCommand.objects.select_related('group')
        .prefetch_related(Prefetch('tasks', queryset=root_steps))
        .filter(id=command_id, tenant_id=tenant_id, is_active=True, group__is_active=True)
        .first()
    )
    if command is None:
        return None

    from apps.resources.serializers import build_task_command_list, build_task_step_runtime_data

    steps = list(command.tasks.all())
    return {
        'commandType': 'task',
        'name': command.name,
        'command': command.command_code,
        'tasks': [build_task_step_runtime_data(request, step) for step in steps],
        'command_list': build_task_command_list(steps),
    }


async def try_dispatch_command(
    *,
    session: dict[str, Any],
    question_text: str,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
    error_event_type: str = 'llm.error',
    command_id: Any = None,
    request_id: str = '',
    trace_id: str = '',
) -> DispatchOutcome | None:
    """Attempt to dispatch ``question_text`` against the current company's commands.

    Returns:
        - ``DispatchOutcome`` if command dispatch handled the request.
        - ``None`` when there is no plausible command candidate, so the caller falls
          back to the normal chat completion path.
    """
    from apps.ai_models import llm_services

    tenant_id = session.get('tenantId')
    tools = await sync_to_async(build_command_tools, thread_sensitive=True)(tenant_id)
    if not tools:
        return None

    policy = await _load_control_command_recognition_policy(tenant_id)
    control_tools = [tool for tool in tools if (tool.get('_command_meta') or {}).get('kind') == 'control']
    task_tools = [tool for tool in tools if (tool.get('_command_meta') or {}).get('kind') == 'task']
    control_selection = _select_command_tools(control_tools, question_text, auto_execute_score=None)

    is_control_confirmation = False
    route = ''
    if control_selection.highest_score >= policy[1]:
        selection = control_selection
        if (
            selection.highest_score >= policy[0]
            and selection.highest_score - selection.second_highest_score >= CONTROL_DIRECT_EXECUTION_MARGIN
        ):
            selection.local_tool = selection.candidate_tools[0]
            route = 'direct_execution'
        else:
            is_control_confirmation = True
            route = 'llm_confirmation'
    else:
        # 任务指令保持既有的本地匹配与 Tool Calling 行为，不受控制指令策略影响。
        selection = _select_command_tools(task_tools, question_text)
        if not selection.candidate_tools:
            if control_tools:
                return DispatchOutcome(
                    hit=False,
                    reply_text='',
                    tool_calls_summary=[],
                    mode='ordinary',
                    highest_score=control_selection.highest_score,
                    second_highest_score=control_selection.second_highest_score,
                    candidate_count=control_selection.candidate_count,
                    route='ordinary_conversation',
                    confirmation_outcome='not_required',
                    execution_outcome='not_executed',
                )
            return None
        route = 'task_command'

    if selection.local_tool is not None:
        outcome = await _execute_local_tool(
            tool=selection.local_tool,
            session=session,
            llm_services=llm_services,
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
            tenant_id=tenant_id,
        )
        if route == 'direct_execution':
            outcome.highest_score = selection.highest_score
            outcome.second_highest_score = selection.second_highest_score
            outcome.candidate_count = selection.candidate_count
            outcome.route = route
            outcome.confirmation_outcome = 'not_required'
            outcome.execution_outcome = 'succeeded' if outcome.tool_calls_summary and outcome.tool_calls_summary[0]['success'] else 'failed'
        return outcome

    model_config = session.get('modelConfig')
    if model_config is None:
        logger.warning('command_dispatch.missing_model_config tenant=%s', tenant_id)
        return await _selection_failed(
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
            tenant_id=tenant_id,
            reason='missing_model_config',
            selection=selection if is_control_confirmation else None,
            route=route if is_control_confirmation else None,
        )

    index = command_index_map(selection.candidate_tools)
    api_tools = strip_tools_meta(selection.candidate_tools)
    messages = list(session.get('messages') or [])
    messages.append({'role': 'user', 'content': question_text})
    tool_calls: list[dict[str, Any]] = []

    try:
        async for event in llm_services.stream_llm_chat_completion_with_tools(
            model_config=model_config,
            messages=messages,
            tools=api_tools,
            tool_choice='auto',
            temperature=session.get('temperature', 0.3),
            max_tokens=session.get('maxTokens') or 500,
            timeout=20,
        ):
            event_type = event.get('type')
            if event_type == 'tool_calls':
                tool_calls = event.get('tool_calls') or []
            elif event_type == 'delta':
                delta_text = event.get('text') or ''
                if delta_text and on_delta is not None:
                    await on_delta(delta_text)
    except Exception as exc:
        logger.warning(
            'command_dispatch.llm_first_round_failed tenant=%s candidates=%s error=%s',
            tenant_id,
            len(selection.candidate_tools),
            exc,
        )
        return await _selection_failed(
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
            tenant_id=tenant_id,
            reason='upstream_failed',
            selection=selection if is_control_confirmation else None,
            route=route if is_control_confirmation else None,
        )

    if not tool_calls:
        if is_control_confirmation:
            return await _selection_failed(
                on_delta=on_delta,
                on_tts_segment=on_tts_segment,
                tenant_id=tenant_id,
                reason='no_control_selected',
                selection=selection,
                route=route,
                confirmation_outcome='not_selected',
            )
        return None

    executed_calls: list[dict[str, Any]] = []
    matched_command_metas: list[dict[str, Any]] = []
    selected_control_executions: list[tuple[dict[str, Any], ExecutionResult, str]] = []
    tool_role_messages: list[dict[str, Any]] = []
    assistant_tool_calls = [
        {
            'id': call.get('id') or f'call_{i}',
            'type': 'function',
            'function': {
                'name': call.get('function', {}).get('name', ''),
                'arguments': call.get('function', {}).get('arguments', ''),
            },
        }
        for i, call in enumerate(tool_calls)
    ]
    tool_role_messages.append({'role': 'assistant', 'tool_calls': assistant_tool_calls})

    for call in tool_calls:
        function_payload = call.get('function') or {}
        name = function_payload.get('name', '')
        arguments_raw = function_payload.get('arguments', '')
        arguments = _parse_arguments(arguments_raw)
        tool = index.get(name)
        if tool is None:
            tool_role_messages.append({
                'role': 'tool',
                'tool_call_id': call.get('id') or name,
                'content': f'未找到指令 {name}',
            })
            executed_calls.append({'name': name, 'success': False, 'message': '未找到指令'})
            continue
        meta = tool.get('_command_meta') or {}
        matched_command_metas.append(meta)
        result = await _execute_tool(meta, arguments, name)
        if meta.get('kind') == 'control':
            selected_control_executions.append((meta, result, name))
        tool_role_messages.append({
            'role': 'tool',
            'tool_call_id': call.get('id') or name,
            'content': result.message,
        })
        executed_calls.append({
            'name': name,
            'success': result.success,
            'message': result.message,
            'latencyMs': result.latency_ms,
        })

    if is_control_confirmation and (len(executed_calls) != 1 or len(selected_control_executions) != 1):
        return await _selection_failed(
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
            tenant_id=tenant_id,
            reason='no_control_selected',
            selection=selection,
            route=route,
            confirmation_outcome='not_selected',
        )

    if len(executed_calls) == 1 and len(selected_control_executions) == 1:
        meta, result, command_code = selected_control_executions[0]
        command_name = str(meta.get('name') or command_code)
        reply_text, reply_source = await _resolve_local_execution_reply(
            meta=meta,
            command_name=command_name,
            result=result,
            session=session,
            llm_services=llm_services,
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
        )
        logger.info(
            'command_dispatch.tool_control_completed tenant=%s command=%s reply_source=%s',
            tenant_id,
            command_code,
            reply_source,
        )
        return DispatchOutcome(
            hit=True,
            reply_text=reply_text,
            tool_calls_summary=executed_calls,
            matched_command_metas=matched_command_metas,
            mode='tool',
            reply_source=reply_source,
            highest_score=selection.highest_score if is_control_confirmation else None,
            second_highest_score=selection.second_highest_score if is_control_confirmation else None,
            candidate_count=selection.candidate_count if is_control_confirmation else None,
            route=route if is_control_confirmation else None,
            confirmation_outcome='selected' if is_control_confirmation else None,
            execution_outcome='succeeded' if result.success else 'failed',
        )

    reply_text = await _generate_natural_reply(
        llm_services=llm_services,
        model_config=model_config,
        messages=messages,
        tool_role_messages=tool_role_messages,
        temperature=session.get('temperature', 0.7),
        max_tokens=session.get('maxTokens') or 1000,
        on_delta=on_delta,
        on_tts_segment=on_tts_segment,
        session=session,
    )

    if not reply_text:
        reply_text = _summarize_executed_calls(executed_calls)

    logger.info(
        'command_dispatch.completed tenant=%s hits=%s reply_length=%s',
        tenant_id,
        len(executed_calls),
        len(reply_text),
    )
    return DispatchOutcome(
        hit=True,
        reply_text=reply_text,
        tool_calls_summary=executed_calls,
        matched_command_metas=matched_command_metas,
        mode='tool',
    )


def _select_command_tools(
    tools: list[dict[str, Any]],
    question_text: str,
    auto_execute_score: float | None = LOCAL_AUTO_EXECUTE_SCORE,
) -> CommandToolSelection:
    normalized_question = _normalize_match_text(question_text)
    if not normalized_question:
        return CommandToolSelection(candidate_tools=[])

    scored_tools: list[tuple[float, dict[str, Any]]] = []
    for tool in tools:
        meta = tool.get('_command_meta') or {}
        score = max(
            _command_match_score(normalized_question, meta.get('name')),
            _command_match_score(normalized_question, meta.get('commandCode')),
        )
        if score > 0:
            scored_tools.append((score, tool))
    if not scored_tools:
        return CommandToolSelection(candidate_tools=[])

    scored_tools.sort(key=lambda item: (-item[0], item[1].get('_command_meta', {}).get('id', 0)))
    top_score, top_tool = scored_tools[0]
    second_score = scored_tools[1][0] if len(scored_tools) > 1 else 0
    candidate_tools = [tool for _, tool in scored_tools[:MAX_TOOL_CANDIDATES]]
    selection = CommandToolSelection(
        candidate_tools=candidate_tools,
        highest_score=top_score,
        second_highest_score=second_score,
        candidate_count=len(scored_tools),
    )
    if auto_execute_score is not None and (
        (top_score == 1 and second_score < 1)
        or (top_score >= auto_execute_score and top_score - second_score >= CONTROL_DIRECT_EXECUTION_MARGIN)
    ):
        selection.local_tool = top_tool
    return selection


async def _load_control_command_recognition_policy(tenant_id: Any) -> tuple[float, float]:
    def load_policy() -> tuple[float, float]:
        if tenant_id is None:
            return (
                float(ControlCommandRecognitionPolicy.DIRECT_EXECUTION_THRESHOLD_DEFAULT),
                float(ControlCommandRecognitionPolicy.LLM_CONFIRMATION_THRESHOLD_DEFAULT),
            )
        policy, _ = ControlCommandRecognitionPolicy.objects.get_or_create(tenant_id=tenant_id)
        return float(policy.direct_execution_threshold), float(policy.llm_confirmation_threshold)

    return await sync_to_async(load_policy, thread_sensitive=True)()


def _command_match_score(normalized_question: str, candidate_text: Any) -> float:
    normalized_candidate = _normalize_match_text(candidate_text)
    if not normalized_candidate:
        return 0
    if normalized_question == normalized_candidate:
        return 1
    if len(normalized_candidate) >= 2 and normalized_candidate in normalized_question:
        return 0.98
    if min(len(normalized_question), len(normalized_candidate)) >= 6 and _is_single_edit_apart(
        normalized_question,
        normalized_candidate,
    ):
        return LOCAL_AUTO_EXECUTE_SCORE
    if min(len(normalized_question), len(normalized_candidate)) >= 6:
        ratio = SequenceMatcher(None, normalized_question, normalized_candidate).ratio()
        if ratio >= 0.85:
            return ratio
    if len(normalized_candidate) >= 2 and set(normalized_candidate).issubset(set(normalized_question)):
        return 0.7
    return 0


def _normalize_match_text(value: Any) -> str:
    return re.sub(r'[\s\W_]+', '', str(value or '').casefold(), flags=re.UNICODE)


def _is_single_edit_apart(first: str, second: str) -> bool:
    if abs(len(first) - len(second)) > 1:
        return False
    first_index = second_index = edits = 0
    while first_index < len(first) and second_index < len(second):
        if first[first_index] == second[second_index]:
            first_index += 1
            second_index += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(first) > len(second):
            first_index += 1
        elif len(second) > len(first):
            second_index += 1
        else:
            first_index += 1
            second_index += 1
    return edits + (len(first) - first_index) + (len(second) - second_index) <= 1


async def _execute_local_tool(
    *,
    tool: dict[str, Any],
    session: dict[str, Any],
    llm_services,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
    tenant_id: Any,
) -> DispatchOutcome:
    meta = tool.get('_command_meta') or {}
    command_code = str(meta.get('commandCode') or '')
    result = await _execute_tool(meta, {}, command_code)
    command_name = str(meta.get('name') or command_code)
    reply_text, reply_source = await _resolve_local_execution_reply(
        meta=meta,
        command_name=command_name,
        result=result,
        session=session,
        llm_services=llm_services,
        on_delta=on_delta,
        on_tts_segment=on_tts_segment,
    )
    tool_call = {
        'name': command_code,
        'success': result.success,
        'message': result.message,
        'latencyMs': result.latency_ms,
    }
    logger.info(
        'command_dispatch.local_completed tenant=%s command=%s success=%s latency_ms=%s',
        tenant_id,
        command_code,
        result.success,
        result.latency_ms,
    )
    return DispatchOutcome(
        hit=True,
        reply_text=reply_text,
        tool_calls_summary=[tool_call],
        matched_command_metas=[meta],
        mode='local',
        reply_source=reply_source,
    )


async def _execute_tool(meta: dict[str, Any], arguments: dict[str, Any], command_code: str) -> ExecutionResult:
    kind = meta.get('kind')
    if kind == 'control':
        return await _execute_control(meta, arguments)
    if kind == 'task':
        return await _execute_task(meta, arguments)
    return ExecutionResult(False, '未知指令类型', 0, command_code)


async def _resolve_local_execution_reply(
    meta: dict[str, Any],
    command_name: str,
    result: ExecutionResult,
    session: dict[str, Any],
    llm_services,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
) -> tuple[str, str]:
    if result.success:
        execution_reply = str(meta.get('executionReply') or '').strip()
        if execution_reply:
            await _emit_reply(execution_reply, on_delta, on_tts_segment)
            return execution_reply, 'custom'
        if meta.get('replyStrategy') == ControlCommand.REPLY_STRATEGY_GENERATED:
            generated_reply = await _generate_control_execution_reply(
                command_name=command_name,
                result=result,
                session=session,
                llm_services=llm_services,
                on_delta=on_delta,
                on_tts_segment=on_tts_segment,
            )
            if generated_reply:
                return generated_reply, 'generated'
            reply_text = f'已执行：{command_name}。'
            await _emit_reply(reply_text, on_delta, on_tts_segment)
            return reply_text, 'generated_fallback'
        reply_text = f'已执行：{command_name}。'
        await _emit_reply(reply_text, on_delta, on_tts_segment)
        return reply_text, 'fixed'
    reply_text = f'执行失败：{command_name}。{result.message}'
    await _emit_reply(reply_text, on_delta, on_tts_segment)
    return reply_text, 'failed'


async def _generate_control_execution_reply(
    *,
    command_name: str,
    result: ExecutionResult,
    session: dict[str, Any],
    llm_services,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
) -> str:
    model_config = session.get('modelConfig')
    if model_config is None:
        return ''
    try:
        return await _generate_natural_reply(
            llm_services=llm_services,
            model_config=model_config,
            messages=[{
                'role': 'user',
                'content': f'控制指令“{command_name}”执行结果：{result.message}',
            }],
            tool_role_messages=[],
            temperature=session.get('temperature', 0.7),
            max_tokens=session.get('maxTokens') or 1000,
            on_delta=on_delta,
            on_tts_segment=on_tts_segment,
            session=session,
        )
    except Exception as exc:
        logger.warning('command_dispatch.generated_reply_failed command=%s error=%s', command_name, exc)
        return ''


async def _selection_failed(
    *,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
    tenant_id: Any,
    reason: str,
    selection: CommandToolSelection | None = None,
    route: str | None = None,
    confirmation_outcome: str = 'unavailable',
) -> DispatchOutcome:
    reply_text = '我没有确认要执行的控制指令，请再说一次。' if reason == 'no_control_selected' else '指令识别服务暂时不可用，请稍后重试。'
    await _emit_reply(reply_text, on_delta, on_tts_segment)
    logger.warning('command_dispatch.selection_failed tenant=%s reason=%s', tenant_id, reason)
    return DispatchOutcome(
        hit=True,
        reply_text=reply_text,
        tool_calls_summary=[],
        mode='selection_failed',
        highest_score=selection.highest_score if selection is not None else None,
        second_highest_score=selection.second_highest_score if selection is not None else None,
        candidate_count=selection.candidate_count if selection is not None else None,
        route=route,
        confirmation_outcome=confirmation_outcome,
        execution_outcome='not_executed' if selection is not None else None,
    )


async def _emit_reply(
    reply_text: str,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
) -> None:
    if on_delta is not None:
        await on_delta(reply_text)
    if on_tts_segment is not None:
        await on_tts_segment(reply_text)


async def _generate_natural_reply(
    *,
    llm_services,
    model_config: dict[str, Any],
    messages: list[dict[str, Any]],
    tool_role_messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int | None,
    on_delta: DispatchCallback | None,
    on_tts_segment: TtsSegmentCallback | None,
    session: dict[str, Any],
) -> str:
    from config.realtime import _pop_llm_tts_segments, _split_llm_tts_segments  # noqa: F401

    follow_up_messages = [*messages, *tool_role_messages]
    follow_up_messages.append({
        'role': 'system',
        'content': GENERATED_REPLY_PROMPT,
    })

    reply_text = ''
    tts_buffer = ''
    try:
        async for delta in llm_services.stream_llm_chat_completion(
            model_config=model_config,
            messages=follow_up_messages,
            temperature=temperature,
            max_tokens=max_tokens or 1000,
        ):
            if not delta:
                continue
            reply_text += delta
            if on_delta is not None:
                await on_delta(delta)
            tts_buffer += delta
            segments, tts_buffer = _pop_llm_tts_segments(tts_buffer, session)
            if on_tts_segment is not None:
                for segment in segments:
                    await on_tts_segment(segment)
    except Exception as exc:
        logger.warning('command_dispatch.second_round_failed error=%s', exc)
        if not reply_text:
            raise
    final_segments, _ = _pop_llm_tts_segments(tts_buffer, session, flush=True)
    if on_tts_segment is not None:
        for segment in final_segments:
            await on_tts_segment(segment)
    return reply_text


async def _execute_control(meta: dict[str, Any], arguments: dict[str, Any]) -> ExecutionResult:
    try:
        cmd = await _load_control_command(meta['id'])
    except ControlCommand.DoesNotExist:
        return ExecutionResult(False, '指令已失效', 0, meta.get('commandCode', ''))
    return await _dispatch_control_command(cmd, arguments)


async def _dispatch_control_command(cmd: ControlCommand, arguments: dict[str, Any]) -> ExecutionResult:
    if not cmd.backend_send_enabled:
        return ExecutionResult(
            success=True,
            message='指令已触发',
            latency_ms=0,
            payload=cmd.command_code,
        )
    return await command_executor.execute_control_command(cmd, arguments)


async def _execute_task(meta: dict[str, Any], arguments: dict[str, Any]) -> ExecutionResult:
    try:
        task = await _load_task_command(meta['id'])
    except TaskCommand.DoesNotExist:
        return ExecutionResult(False, '任务指令已失效', 0, meta.get('commandCode', ''))

    steps = await sync_to_async(list, thread_sensitive=True)(task.tasks.order_by('order', 'id'))
    executed = 0
    failed: list[str] = []
    for step in steps:
        if step.task_type != 'command' or step.control_command_id is None:
            continue
        try:
            control = await _load_control_command(step.control_command_id)
        except ControlCommand.DoesNotExist:
            failed.append(f'步骤#{step.order} 指令缺失')
            continue
        result = await _dispatch_control_command(control, arguments)
        executed += 1
        if not result.success:
            failed.append(f'步骤#{step.order} {result.message}')
    if failed:
        return ExecutionResult(
            success=False,
            message=f'任务指令部分失败：{";".join(failed)}',
            latency_ms=0,
            payload=meta.get('commandCode', ''),
        )
    return ExecutionResult(
        success=True,
        message=f'任务指令已执行（{executed} 步）' if executed else '任务指令已触发',
        latency_ms=0,
        payload=meta.get('commandCode', ''),
    )


async def _load_control_command(command_id: int) -> ControlCommand:
    return await sync_to_async(ControlCommand.objects.get, thread_sensitive=True)(id=command_id)


async def _load_task_command(task_id: int) -> TaskCommand:
    return await sync_to_async(TaskCommand.objects.get, thread_sensitive=True)(id=task_id)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else None
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _summarize_executed_calls(calls: list[dict[str, Any]]) -> str:
    if not calls:
        return '抱歉，未能识别到可执行的指令。'
    parts = []
    for call in calls:
        if call.get('success'):
            parts.append(f"已执行 {call['name']}")
        else:
            parts.append(f"{call['name']} 执行失败：{call.get('message', '未知原因')}")
    return '；'.join(parts) + '。'
