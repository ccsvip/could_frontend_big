from __future__ import annotations

import asyncio
import json
from typing import Any

from asgiref.sync import sync_to_async
from django.db.models import F
from django.utils import timezone

from apps.ai_models import llm_services, realtime_asr, realtime_tts
from apps.devices.views import DeviceVoiceChatView
from apps.devices.realtime import (
    add_device_event_subscriber,
    publish_device_event,
    remove_device_event_subscriber,
    resolve_device_event_subscription,
)
from apps.devices.websocket import (
    mark_device_offline_for_websocket,
    mark_device_online_for_websocket,
    touch_device_for_websocket,
)
from config.request_id import clean_trace_value, make_request_id


class RealtimeConnection:
    def __init__(self):
        self.device_events_subscriber = None
        self.device_events_command_id = None
        self.device_status_device_id = None
        self.device_status_device_code = None
        self.device_status_command_id = None
        self.asr_session_id = None
        self.asr_upstream = None
        self.asr_upstream_context = None
        self.asr_upstream_task = None
        self.tts_session_id = None
        self.tts_task = None

    async def close(self) -> None:
        await self.close_asr_session()
        await self.close_tts_session()
        self.close_device_events()
        if self.device_status_device_id is not None:
            offline_event = await sync_to_async(mark_device_offline_for_websocket, thread_sensitive=True)(
                self.device_status_device_id,
            )
            self.device_status_device_id = None
            self.device_status_device_code = None
            self.device_status_command_id = None
            if offline_event is not None:
                await publish_device_event(offline_event)

    def close_device_events(self) -> None:
        if self.device_events_subscriber is not None:
            remove_device_event_subscriber(self.device_events_subscriber)
            self.device_events_subscriber = None
            self.device_events_command_id = None

    async def close_asr_session(self) -> None:
        if self.asr_upstream_task is not None:
            self.asr_upstream_task.cancel()
            await asyncio.gather(self.asr_upstream_task, return_exceptions=True)
            self.asr_upstream_task = None
        if self.asr_upstream_context is not None:
            await self.asr_upstream_context.__aexit__(None, None, None)
            self.asr_upstream_context = None
        self.asr_upstream = None
        self.asr_session_id = None

    async def close_tts_session(self) -> None:
        if self.tts_task is not None:
            if not self.tts_task.done():
                self.tts_task.cancel()
            await asyncio.gather(self.tts_task, return_exceptions=True)
            self.tts_task = None
        self.tts_session_id = None


async def realtime_websocket_application(scope, receive, send):
    await send({'type': 'websocket.accept'})
    send = _locked_send(send, asyncio.Lock())
    connection = RealtimeConnection()
    receive_task = asyncio.create_task(receive())

    try:
        while True:
            tasks = {receive_task}
            if connection.device_events_subscriber is not None:
                tasks.add(asyncio.create_task(connection.device_events_subscriber.queue.get()))
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            queue_tasks = [task for task in done if task is not receive_task]
            for task in pending:
                if task is not receive_task:
                    task.cancel()

            for task in queue_tasks:
                await _send_json(
                    send,
                    {
                        'type': 'devices.event',
                        'id': connection.device_events_command_id,
                        'payload': task.result(),
                    },
                )

            if receive_task in done:
                event = receive_task.result()
                if await _handle_client_event(event, send, connection):
                    return
                receive_task = asyncio.create_task(receive())
    finally:
        if not receive_task.done():
            receive_task.cancel()
        await connection.close()


async def _handle_client_event(event, send, connection: RealtimeConnection) -> bool:
    event_type = event.get('type')
    if event_type == 'websocket.disconnect':
        return True
    if event_type != 'websocket.receive':
        return False

    if 'bytes' in event:
        await _handle_binary_frame(send, connection, event.get('bytes') or b'')
        return False

    if 'text' not in event:
        await _send_error(send, None, 'invalid_message', 'Realtime commands must be JSON text messages')
        return False

    message = _parse_message(event.get('text') or '')
    if message is None:
        await _send_error(send, None, 'invalid_json', 'Realtime command must be valid JSON')
        return False

    command_type = message.get('type')
    command_id = message.get('id')
    if not isinstance(command_type, str) or not command_type.strip():
        await _send_error(send, command_id, 'invalid_command', 'Realtime command type is required')
        return False

    command_type = command_type.strip()
    if command_type == 'ping':
        await _send_json(send, {'type': 'pong', 'id': command_id, 'payload': {}})
        return False
    if command_type == 'devices.events.subscribe':
        await _handle_device_events_subscribe(send, connection, message)
        return False
    if command_type == 'devices.events.unsubscribe':
        await _handle_device_events_unsubscribe(send, connection, message)
        return False
    if command_type == 'device.status.start':
        await _handle_device_status_start(send, connection, message)
        return False
    if command_type == 'device.status.ping':
        await _handle_device_status_ping(send, connection, message)
        return False
    if command_type == 'asr.session.start':
        await _handle_asr_session_start(send, connection, message)
        return False
    if command_type == 'asr.session.finish':
        await _handle_asr_session_finish(send, connection, message)
        return False
    if command_type == 'asr.session.cancel':
        await _handle_asr_session_cancel(send, connection, message)
        return False
    if command_type == 'tts.session.start':
        await _handle_tts_session_start(send, connection, message)
        return False
    if command_type == 'tts.session.cancel':
        await _handle_tts_session_cancel(send, connection, message)
        return False
    if command_type == 'llm.session.start':
        await _handle_llm_session_start(send, message)
        return False

    await _send_error(
        send,
        command_id,
        'unknown_command',
        f'Unsupported realtime command: {command_type}',
    )
    return False


async def _handle_binary_frame(send, connection: RealtimeConnection, audio_bytes: bytes) -> None:
    if not audio_bytes:
        return
    if connection.asr_upstream is None:
        await _send_error(send, None, 'media_session_not_started', 'Binary frames require an active media session')
        return
    await connection.asr_upstream.send(json.dumps(realtime_asr._audio_append_event(audio_bytes)))


async def _handle_device_events_subscribe(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    token = str(payload.get('token') or '').strip()
    tenant_id_param = str(payload.get('tenantId') or payload.get('tenant') or '').strip()
    subscription = await sync_to_async(resolve_device_event_subscription, thread_sensitive=True)(
        token,
        tenant_id_param,
    )
    if subscription is None:
        await _send_error(send, command_id, 'unauthorized', 'Device event subscription is not authorized')
        return

    connection.close_device_events()
    connection.device_events_subscriber = add_device_event_subscriber(subscription['tenant_id'])
    connection.device_events_command_id = command_id
    await _send_json(
        send,
        {
            'type': 'devices.events.subscribed',
            'id': command_id,
            'payload': {'tenantId': subscription['tenant_id']},
        },
    )


async def _handle_device_events_unsubscribe(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    connection.close_device_events()
    await _send_json(
        send,
        {
            'type': 'devices.events.unsubscribed',
            'id': message.get('id'),
            'payload': {},
        },
    )


async def _handle_device_status_start(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    if not device_code:
        await _send_error(send, command_id, 'invalid_device', 'Device code is required')
        return

    await _clear_device_status(connection)
    device = await sync_to_async(mark_device_online_for_websocket, thread_sensitive=True)(device_code)
    if device is None:
        await _send_error(send, command_id, 'device_not_found', 'Device is not available')
        return

    connection.device_status_device_id = device.id
    connection.device_status_device_code = device.code
    connection.device_status_command_id = command_id
    await publish_device_event(
        {
            'type': 'device.status',
            'tenantId': device.tenant_id,
            'applicationId': device.application_id,
            'agentApplicationId': device.agent_application_id,
            'deviceCode': device.code,
            'status': 'online',
            'isEnabled': device.is_enabled,
        }
    )
    await _send_json(
        send,
        {
            'type': 'device.status.started',
            'id': command_id,
            'payload': {
                'deviceCode': device.code,
                'status': 'online',
            },
        },
    )


async def _handle_asr_session_start(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    token = str(payload.get('token') or '').strip()
    query_params = _payload_query_params(payload, 'tenantId', 'tenant', 'deviceCode', 'device_code')
    request_id = _request_id_from_payload(payload)
    trace_id = _trace_id_from_payload(payload, request_id)

    resolved_connection = await sync_to_async(realtime_asr.resolve_asr_realtime_connection, thread_sensitive=True)(
        token,
        headers=[],
        query_params=query_params,
    )
    if resolved_connection is None:
        await _send_json(send, _trace_payload('asr.error', command_id, request_id, trace_id, message='ASR session is not authorized'))
        return

    config = await sync_to_async(realtime_asr.get_effective_asr_config, thread_sensitive=True)()
    if not config.is_active or not realtime_asr.is_asr_configured(config):
        await _send_json(send, _trace_payload('asr.error', command_id, request_id, trace_id, message='ASR 服务未就绪'))
        return

    replacement_pairs = await sync_to_async(realtime_asr.load_asr_replacement_pairs, thread_sensitive=True)(
        resolved_connection.get('tenant_id'),
    )

    await connection.close_asr_session()
    try:
        upstream_context = realtime_asr.websockets.connect(
            realtime_asr.build_asr_ws_url(config),
            additional_headers=[
                ('Authorization', f'Bearer {config.api_key}'),
                ('OpenAI-Beta', 'realtime=v1'),
                ('X-DashScope-WorkSpace', config.workspace_id),
            ],
            user_agent_header='solin-admin/1.0',
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 * 1024 * 1024,
        )
        upstream = await upstream_context.__aenter__()
        await upstream.send(json.dumps(realtime_asr._session_update_event()))
    except Exception as exc:
        await _send_json(send, _trace_payload('asr.error', command_id, request_id, trace_id, message=str(exc)[:200]))
        return

    connection.asr_session_id = command_id
    connection.asr_upstream = upstream
    connection.asr_upstream_context = upstream_context
    connection.asr_upstream_task = asyncio.create_task(
        _asr_upstream_to_client(upstream, send, command_id, replacement_pairs),
    )
    await _send_json(send, _trace_payload('asr.ready', command_id, request_id, trace_id))


async def _handle_asr_session_finish(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    if connection.asr_upstream is None:
        await _send_json(send, {'type': 'asr.error', 'id': message.get('id'), 'message': 'ASR session is not started'})
        return
    await connection.asr_upstream.send(json.dumps(realtime_asr._session_finish_event()))


async def _handle_asr_session_cancel(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    session_id = connection.asr_session_id
    if connection.asr_upstream is None:
        await _send_json(send, {'type': 'asr.error', 'id': message.get('id'), 'message': 'ASR session is not started'})
        return
    await connection.close_asr_session()
    await _send_json(
        send,
        {
            'type': 'asr.cancelled',
            'id': message.get('id'),
            'payload': {'sessionId': session_id},
        },
    )


async def _handle_tts_session_start(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    await connection.close_tts_session()
    command_id = message.get('id')
    connection.tts_session_id = command_id
    connection.tts_task = asyncio.create_task(_run_tts_session(send, connection, command_id, message))


async def _handle_tts_session_cancel(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    session_id = connection.tts_session_id
    if connection.tts_task is None:
        await _send_json(send, {'type': 'tts.error', 'id': message.get('id'), 'message': 'TTS session is not started'})
        return
    await connection.close_tts_session()
    await _send_json(
        send,
        {
            'type': 'tts.cancelled',
            'id': message.get('id'),
            'payload': {'sessionId': session_id},
        },
    )


async def _handle_llm_session_start(send, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    question_text = str(payload.get('text') or payload.get('questionText') or payload.get('question') or '').strip()
    request_id = _request_id_from_payload(payload)
    trace_id = _trace_id_from_payload(payload, request_id)
    if not device_code:
        await _send_json(send, _trace_payload('llm.error', command_id, request_id, trace_id, message='Device code is required'))
        return
    if not question_text:
        await _send_json(send, _trace_payload('llm.error', command_id, request_id, trace_id, message='Question text is required'))
        return

    try:
        session = await sync_to_async(_prepare_device_llm_session, thread_sensitive=True)(device_code, question_text)
    except Exception as exc:
        await _send_json(send, _trace_payload('llm.error', command_id, request_id, trace_id, message=str(exc)[:200]))
        return

    started_payload = {
        'type': 'llm.started',
        'id': command_id,
        'requestId': request_id,
        'traceId': trace_id,
        'payload': {
            'deviceCode': session['deviceCode'],
            'questionText': question_text,
            'agentApplicationId': session['agentApplicationId'],
            'agentApplicationName': session['agentApplicationName'],
            'applicationId': session['applicationId'],
            'applicationName': session['applicationName'],
        },
    }
    await _send_json(send, started_payload)

    answer_text = ''
    if session.get('annotationAnswer') is not None:
        answer_text = session['annotationAnswer']
        await _send_json(
            send,
            {
                'type': 'llm.delta',
                'id': command_id,
                'requestId': request_id,
                'traceId': trace_id,
                'payload': {'text': answer_text},
            },
        )
    else:
        try:
            async for delta in llm_services.stream_llm_chat_completion(
                model_config=session['modelConfig'],
                messages=session['messages'],
                temperature=session['temperature'],
                max_tokens=session['maxTokens'],
            ):
                answer_text += delta
                await _send_json(
                    send,
                    {
                        'type': 'llm.delta',
                        'id': command_id,
                        'requestId': request_id,
                        'traceId': trace_id,
                        'payload': {'text': delta},
                    },
                )
        except Exception as exc:
            await _send_json(send, _trace_payload('llm.error', command_id, request_id, trace_id, message=str(exc)[:200]))
            return

    if not answer_text:
        await _send_json(send, _trace_payload('llm.error', command_id, request_id, trace_id, message='LLM 没有返回有效回复'))
        return

    await _send_json(
        send,
        {
            'type': 'llm.done',
            'id': command_id,
            'requestId': request_id,
            'traceId': trace_id,
            'payload': {
                'deviceCode': session['deviceCode'],
                'questionText': question_text,
                'answerText': answer_text,
                'agentApplicationId': session['agentApplicationId'],
                'agentApplicationName': session['agentApplicationName'],
                'applicationId': session['applicationId'],
                'applicationName': session['applicationName'],
            },
        },
    )


def _prepare_device_llm_session(device_code: str, question_text: str) -> dict[str, Any]:
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(device_code)
    agent_application = device.effective_agent_application
    if agent_application is None or not agent_application.is_active:
        raise RuntimeError('设备未绑定可用智能体')

    annotation = DeviceVoiceChatView._find_annotation(agent_application, question_text)
    if annotation is not None:
        now = timezone.now()
        annotation.__class__.objects.filter(id=annotation.id).update(
            hit_count=F('hit_count') + 1,
            last_hit_at=now,
        )
        return {
            'deviceCode': device.code,
            'annotationAnswer': annotation.answer,
            'agentApplicationId': agent_application.id,
            'agentApplicationName': agent_application.name,
            'applicationId': device.application_id,
            'applicationName': device.application.name if device.application else '',
        }

    model = agent_application.llm_model
    if model is None:
        settings = llm_services.get_tenant_llm_settings(device.tenant)
        model = settings.default_model if settings is not None else None
    if not llm_services.is_llm_model_effective_for_tenant(device.tenant, model):
        raise RuntimeError('请先为设备绑定智能体配置可用 LLM 模型')

    system_prompt = (
        agent_application.system_prompt.strip()
        if agent_application.system_prompt.strip()
        else '你是数字人设备的中文语音问答助手。回答要自然、简洁，适合直接转成语音播报。'
    )
    system_prompt += f' 当前设备智能体：{agent_application.name}。'
    if device.application is not None:
        system_prompt += f' 当前设备资源应用：{device.application.name}。'

    return {
        'deviceCode': device.code,
        'modelConfig': {
            'name': model.name,
            'apiBaseUrl': model.provider.api_base_url,
            'apiKey': model.provider.api_key,
            'enableWebSearch': model.enable_web_search,
        },
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': question_text},
        ],
        'temperature': agent_application.temperature,
        'maxTokens': None if agent_application.max_tokens_unlimited else agent_application.max_tokens,
        'annotationAnswer': None,
        'agentApplicationId': agent_application.id,
        'agentApplicationName': agent_application.name,
        'applicationId': device.application_id,
        'applicationName': device.application.name if device.application else '',
    }


def _run_device_llm_answer(device_code: str, question_text: str) -> dict[str, Any]:
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(device_code)
    agent_application = device.effective_agent_application
    if agent_application is None or not agent_application.is_active:
        raise RuntimeError('设备未绑定可用智能体')
    answer_text = DeviceVoiceChatView._generate_answer(device, question_text)
    return {
        'deviceCode': device.code,
        'answerText': answer_text,
        'agentApplicationId': agent_application.id,
        'agentApplicationName': agent_application.name,
        'applicationId': device.application_id,
        'applicationName': device.application.name if device.application else '',
    }


async def _run_tts_session(send, connection: RealtimeConnection, command_id, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    try:
        payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
        token = str(payload.get('token') or '').strip()
        query_params = _payload_query_params(payload, 'tenantId', 'tenant', 'deviceCode', 'device_code')

        resolved_connection = await sync_to_async(realtime_tts.resolve_tts_realtime_connection, thread_sensitive=True)(
            token,
            query_params=query_params,
        )
        if resolved_connection is None:
            await _send_json(send, {'type': 'tts.error', 'id': command_id, 'message': 'TTS session is not authorized'})
            return

        provider = await sync_to_async(realtime_tts.resolve_tts_provider, thread_sensitive=True)(
            payload.get('providerCode'),
        )
        config = await sync_to_async(realtime_tts.get_effective_tts_config, thread_sensitive=True)(provider)
        if not realtime_tts.is_tts_configured(config):
            raise RuntimeError('TTS 服务未配置或未启用')

        voice = await sync_to_async(realtime_tts.resolve_tts_voice, thread_sensitive=True)(
            resolved_connection,
            payload.get('voiceId'),
            provider,
        )
        if voice is None:
            raise RuntimeError('TTS 音色未配置')

        text = realtime_tts.normalize_tts_text(str(payload.get('text') or ''), config)
        await realtime_tts._stream_tts_audio(
            text=text,
            voice=voice,
            config=config,
            send=_with_command_id(send, command_id),
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        await _send_json(send, {'type': 'tts.error', 'id': command_id, 'message': str(exc)[:200]})
    finally:
        if connection.tts_task is asyncio.current_task():
            connection.tts_task = None
            connection.tts_session_id = None


async def _asr_upstream_to_client(upstream, send, command_id, replacement_pairs: list[tuple[str, str]]) -> None:
    async for raw_message in upstream:
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue

        transcript_payload = realtime_asr.extract_transcript_payload(event, replacement_pairs=replacement_pairs)
        if transcript_payload is not None:
            transcript_payload['id'] = command_id
            await _send_json(send, transcript_payload)
            continue

        if event.get('type') == 'session.finished':
            await _send_json(send, {'type': 'asr.done', 'id': command_id})
            return


def _with_command_id(send, command_id):
    async def send_with_command_id(event):
        if 'text' not in event:
            await send(event)
            return

        try:
            payload = json.loads(event.get('text') or '')
        except json.JSONDecodeError:
            await send(event)
            return
        if isinstance(payload, dict):
            payload['id'] = command_id
            await _send_json(send, payload)
            return
        await send(event)

    return send_with_command_id


def _payload_query_params(payload: dict[str, Any], *names: str) -> dict[str, list[str]]:
    params: dict[str, list[str]] = {}
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip():
            params[name] = [str(value).strip()]
    return params


def _request_id_from_payload(payload: dict[str, Any]) -> str:
    return clean_trace_value(
        payload.get('requestId')
        or payload.get('request_id')
        or payload.get('xRequestId')
        or payload.get('x-request-id')
    ) or make_request_id()


def _trace_id_from_payload(payload: dict[str, Any], fallback_request_id: str) -> str:
    return clean_trace_value(
        payload.get('traceId')
        or payload.get('trace_id')
        or payload.get('xTraceId')
        or payload.get('x-trace-id')
    ) or fallback_request_id


def _trace_payload(event_type: str, command_id, request_id: str, trace_id: str, **extra) -> dict[str, Any]:
    return {
        'type': event_type,
        'id': command_id,
        'requestId': request_id,
        'traceId': trace_id,
        **extra,
    }


async def _handle_device_status_ping(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    if connection.device_status_device_id is None:
        await _send_error(send, message.get('id'), 'device_status_not_started', 'Device status session is not started')
        return
    await sync_to_async(touch_device_for_websocket, thread_sensitive=True)(connection.device_status_device_id)
    await _send_json(
        send,
        {
            'type': 'device.status.pong',
            'id': message.get('id'),
            'payload': {'deviceCode': connection.device_status_device_code},
        },
    )


async def _clear_device_status(connection: RealtimeConnection) -> None:
    if connection.device_status_device_id is None:
        return
    offline_event = await sync_to_async(mark_device_offline_for_websocket, thread_sensitive=True)(
        connection.device_status_device_id,
    )
    connection.device_status_device_id = None
    connection.device_status_device_code = None
    connection.device_status_command_id = None
    if offline_event is not None:
        await publish_device_event(offline_event)


def _parse_message(raw_text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


async def _send_error(send, command_id, code: str, message: str) -> None:
    await _send_json(
        send,
        {
            'type': 'error',
            'id': command_id,
            'error': {
                'code': code,
                'message': message,
            },
        },
    )


async def _send_json(send, payload: dict[str, Any]) -> None:
    await send({'type': 'websocket.send', 'text': json.dumps(payload, ensure_ascii=False)})


def _locked_send(send, lock: asyncio.Lock):
    async def send_locked(event):
        async with lock:
            await send(event)

    return send_locked
