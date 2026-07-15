from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from asgiref.sync import sync_to_async
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F
from django.utils import timezone
from websockets.exceptions import ConnectionClosed

from apps.ai_models import llm_services, realtime_asr, realtime_tts
from apps.ai_models.models import RUNTIME_BACKEND_PLATFORM_LLM, RUNTIME_BACKEND_THIRD_PARTY_CHATBOT, TTSVoice
from apps.ai_models.services import third_party_chatbots
from apps.ai_models.services import tts as tts_services
from apps.devices.services.runtime import RuntimeDeviceError, get_runtime_device_or_none, validate_runtime_application_active
from apps.devices.views import DeviceVoiceChatView
from apps.devices.realtime import (
    add_device_event_subscriber,
    build_device_runtime_config_event,
    publish_device_event,
    remove_device_event_subscriber,
    resolve_device_event_subscription,
    resolve_runtime_config_event_subscription,
)
from apps.devices.tts_voice_config import (
    device_tts_session_config,
    has_device_tts_voice_config,
    normalize_device_tts_voice_config,
    public_device_tts_voice_config,
)
from apps.devices.websocket import (
    mark_device_offline_for_websocket,
    mark_device_online_for_websocket,
    touch_device_for_websocket,
)
from config.request_id import clean_trace_value, make_request_id

_AGENT_MEMORY_MAX_MESSAGES = 12
_AGENT_MEMORY: dict[str, list[dict[str, str]]] = {}
logger = logging.getLogger(__name__)


async def _close_asr_upstream_context(context) -> None:
    try:
        await context.__aexit__(None, None, None)
    except Exception:
        logger.exception('realtime.asr.close_upstream_failed')


def _close_asr_upstream_context_later(context) -> None:
    asyncio.create_task(_close_asr_upstream_context(context))


class RealtimeConnection:
    def __init__(self):
        self.device_events_subscriber = None
        self.device_events_command_id = None
        self.runtime_config_device_id = None
        self.device_status_device_id = None
        self.device_status_device_code = None
        self.device_status_command_id = None
        self.asr_session_id = None
        self.asr_upstream = None
        self.asr_upstream_context = None
        self.asr_upstream_task = None
        self.asr_accepting_audio = False
        self.asr_filter_filler_words = True
        self.llm_session_id = None
        self.llm_task = None
        self.tts_session_id = None
        self.tts_task = None
        self.agent_session_id = None
        self.agent_mode = None
        self.agent_device_code = None
        self.agent_request_id = None
        self.agent_trace_id = None
        self.agent_latest_text = ''
        self.agent_conversation_id = None
        self.agent_runtime_session_id = None
        self.agent_tts_queue = None
        self.agent_tts_worker = None
        self.agent_task = None

    async def close(self) -> None:
        await self.close_agent_session()
        await self.close_asr_session()
        await self.close_llm_session()
        await self.close_tts_session()
        self.close_device_events()
        if self.device_status_device_id is not None:
            try:
                offline_event = await sync_to_async(mark_device_offline_for_websocket, thread_sensitive=True)(
                    self.device_status_device_id,
                )
            except Exception:
                logger.warning(
                    'mark_device_offline_for_websocket failed during websocket close device_id=%s',
                    self.device_status_device_id,
                    exc_info=True,
                )
                offline_event = None
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
            self.runtime_config_device_id = None

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
        self.asr_accepting_audio = False
        self.asr_filter_filler_words = True

    async def close_llm_session(self) -> None:
        if self.llm_task is not None:
            if not self.llm_task.done():
                self.llm_task.cancel()
            await asyncio.gather(self.llm_task, return_exceptions=True)
            self.llm_task = None
        self.llm_session_id = None

    async def close_tts_session(self) -> None:
        if self.tts_task is not None:
            if not self.tts_task.done():
                self.tts_task.cancel()
            await asyncio.gather(self.tts_task, return_exceptions=True)
        self.tts_task = None
        self.tts_session_id = None

    async def close_agent_session(self) -> None:
        current_task = asyncio.current_task()
        session_id = self.agent_session_id
        request_id = self.agent_request_id
        trace_id = self.agent_trace_id
        device_code = self.agent_device_code
        had_agent_task = self.agent_task is not None
        had_tts_worker = self.agent_tts_worker is not None
        if self.agent_task is not None and self.agent_task is not current_task:
            if not self.agent_task.done():
                self.agent_task.cancel()
            await asyncio.gather(self.agent_task, return_exceptions=True)
        self.agent_task = None
        if self.agent_tts_worker is not None:
            if not self.agent_tts_worker.done():
                self.agent_tts_worker.cancel()
            await asyncio.gather(self.agent_tts_worker, return_exceptions=True)
        self.agent_tts_worker = None
        self.agent_session_id = None
        self.agent_mode = None
        self.agent_device_code = None
        self.agent_request_id = None
        self.agent_trace_id = None
        self.agent_latest_text = ''
        self.agent_conversation_id = None
        self.agent_runtime_session_id = None
        self.agent_tts_queue = None
        self.agent_tts_worker = None
        if session_id or had_agent_task or had_tts_worker:
            logger.info(
                'realtime.agent.session_closed agent_session=%s request_id=%s trace_id=%s device_code=%s had_agent_task=%s had_tts_worker=%s',
                session_id,
                request_id,
                trace_id,
                device_code,
                had_agent_task,
                had_tts_worker,
            )


async def realtime_websocket_application(scope, receive, send):
    await send({'type': 'websocket.accept'})
    connection = RealtimeConnection()
    send_monitor = _RealtimeSendMonitor(send, asyncio.Lock(), connection)
    send = send_monitor
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
                if connection.runtime_config_device_id is not None:
                    event = task.result()
                    await _send_runtime_config_subscribed(
                        send,
                        connection.runtime_config_device_id,
                        connection.device_events_command_id,
                        _runtime_config_action(event),
                    )
                    continue
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
        logger.info('realtime.websocket.closed %s', send_monitor.summary())
        await connection.close()


async def _send_runtime_config_subscribed(send, device_id: int, command_id, action: str) -> None:
    try:
        event = await sync_to_async(build_device_runtime_config_event, thread_sensitive=True)(
            device_id,
            command_id,
            action,
        )
    except Exception:
        logger.exception('realtime.runtime_config.subscribed_failed device_id=%s action=%s', device_id, action)
        await _send_error(
            send,
            command_id,
            'runtime_config_subscribed_failed',
            'Device runtime config subscription failed',
        )
        return
    if event is not None:
        await _send_json(send, event)


async def _handle_client_event(event, send, connection: RealtimeConnection) -> bool:
    event_type = event.get('type')
    if event_type == 'websocket.disconnect':
        summary = send.summary() if hasattr(send, 'summary') else ''
        logger.info('realtime.websocket.disconnect code=%s %s', event.get('code'), summary)
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
    if command_type == 'device.runtime_config.subscribe':
        await _handle_runtime_config_events_subscribe(send, connection, message)
        return False
    if command_type == 'device.runtime_config.unsubscribe':
        await _handle_runtime_config_events_unsubscribe(send, connection, message)
        return False
    if command_type == 'device.status.start':
        await _handle_device_status_start(send, connection, message)
        return False
    if command_type == 'device.status.ping':
        await _handle_device_status_ping(send, connection, message)
        return False
    if command_type == 'device.voice.bind':
        await _handle_device_voice_bind(send, connection, message)
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
        await _handle_llm_session_start(send, connection, message)
        return False
    if command_type == 'llm.session.cancel':
        await _handle_llm_session_cancel(send, connection, message)
        return False
    if command_type == 'agent.session.start':
        await _handle_agent_session_start(send, connection, message)
        return False
    if command_type == 'agent.session.finish':
        await _handle_agent_session_finish(send, connection, message)
        return False
    if command_type == 'agent.session.cancel':
        await _handle_agent_session_cancel(send, connection, message)
        return False

    await _send_error(
        send,
        command_id,
        'unknown_command',
        f'Unsupported realtime command: {command_type}',
    )
    return False


def _runtime_config_action(event: dict[str, Any]) -> str:
    event_type = str(event.get('type') or '')
    if event_type == 'device.wake_words.changed':
        return 'wakeWordsChanged'
    if event_type == 'device.voice_configuration.changed':
        return 'voiceConfigurationChanged'
    if event_type == 'device.scrolling_texts.changed':
        return 'scrollingTextsChanged'
    return str(event.get('action') or 'runtimeAvailabilityChanged')


async def _handle_binary_frame(send, connection: RealtimeConnection, audio_bytes: bytes) -> None:
    if not audio_bytes:
        return
    if connection.asr_upstream is None or not connection.asr_accepting_audio:
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


async def _handle_runtime_config_events_subscribe(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    subscription = await sync_to_async(resolve_runtime_config_event_subscription, thread_sensitive=True)(device_code)
    if subscription is None:
        await _send_error(send, command_id, 'device_not_found', 'Device is not available')
        return

    connection.close_device_events()
    connection.device_events_subscriber = add_device_event_subscriber(
        subscription['tenant_id'],
        device_code=subscription['device_code'],
    )
    connection.device_events_command_id = command_id
    connection.runtime_config_device_id = subscription['device_id']
    await _send_runtime_config_subscribed(send, subscription['device_id'], command_id, 'initial')


async def _handle_runtime_config_events_unsubscribe(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    connection.close_device_events()
    await _send_json(
        send,
        {
            'type': 'device.runtime_config.unsubscribed',
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
    connection.close_device_events()

    device = await sync_to_async(mark_device_online_for_websocket, thread_sensitive=True)(device_code)
    if device is None:
        await _send_error(send, command_id, 'device_not_found', 'Device is not available')
        return

    connection.device_status_device_id = device.id
    connection.device_status_device_code = device.code
    connection.device_status_command_id = command_id
    if device.tenant_id is not None:
        connection.device_events_subscriber = add_device_event_subscriber(
            device.tenant_id,
            device_code=device.code,
        )
        connection.device_events_command_id = command_id

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
        await upstream.send(json.dumps(realtime_asr._session_update_event(
            vad_threshold=getattr(config, 'vad_threshold', 0.0),
            vad_silence_duration_ms=getattr(config, 'vad_silence_duration_ms', 400),
        )))
    except Exception as exc:
        await _send_json(send, _trace_payload('asr.error', command_id, request_id, trace_id, message=str(exc)[:200]))
        return

    connection.asr_session_id = command_id
    connection.asr_upstream = upstream
    connection.asr_upstream_context = upstream_context
    connection.asr_accepting_audio = True
    connection.asr_filter_filler_words = getattr(config, 'filter_filler_words', True)
    connection.asr_upstream_task = asyncio.create_task(
        _asr_upstream_to_client(upstream, send, connection, command_id, replacement_pairs),
    )
    await _send_json(send, _trace_payload('asr.ready', command_id, request_id, trace_id))


async def _handle_asr_session_finish(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    if connection.asr_upstream is None:
        await _send_json(send, {'type': 'asr.error', 'id': message.get('id'), 'message': 'ASR session is not started'})
        return
    connection.asr_accepting_audio = False
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


async def _handle_llm_session_start(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    await connection.close_llm_session()
    command_id = message.get('id')
    connection.llm_session_id = command_id
    connection.llm_task = asyncio.create_task(_run_llm_session(send, connection, command_id, message))


async def _handle_llm_session_cancel(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    session_id = connection.llm_session_id
    if connection.llm_task is None:
        await _send_json(send, {'type': 'llm.error', 'id': message.get('id'), 'message': 'LLM session is not started'})
        return
    await connection.close_llm_session()
    await _send_json(
        send,
        {
            'type': 'llm.cancelled',
            'id': message.get('id'),
            'payload': {'sessionId': session_id},
        },
    )


async def _handle_agent_session_start(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    await connection.close_agent_session()
    await connection.close_asr_session()
    await connection.close_llm_session()
    await connection.close_tts_session()

    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    input_text = str(payload.get('text') or payload.get('questionText') or payload.get('question') or '').strip()
    request_id = _request_id_from_payload(payload)
    trace_id = _trace_id_from_payload(payload, request_id)
    mode = 'text' if input_text else 'voice'
    incoming_session_id = str(
        payload.get('sessionId')
        or payload.get('session_id')
        or payload.get('conversationId')
        or payload.get('conversation_id')
        or ''
    ).strip()
    if not device_code:
        await _send_json(send, _trace_payload('agent.error', command_id, request_id, trace_id, message='Device code is required'))
        return

    try:
        await sync_to_async(_validate_agent_runtime_start, thread_sensitive=True)(device_code)
    except Exception as exc:
        await _send_json(send, _trace_payload('agent.error', command_id, request_id, trace_id, **_realtime_error_payload(exc)))
        return

    connection.agent_session_id = command_id
    connection.agent_mode = mode
    connection.agent_device_code = device_code
    connection.agent_request_id = request_id
    connection.agent_trace_id = trace_id
    connection.agent_latest_text = input_text
    connection.agent_runtime_session_id = payload.get('sessionId') or payload.get('session_id')
    connection.agent_conversation_id = payload.get('conversationId') or payload.get('conversation_id')
    connection.agent_tts_queue = asyncio.Queue()
    connection.agent_tts_worker = asyncio.create_task(
        _agent_tts_worker(send, connection, command_id, device_code, request_id, trace_id, payload),
    )
    await _send_json(
        send,
        _trace_payload(
            'agent.started',
            command_id,
            request_id,
            trace_id,
            payload={'deviceCode': device_code, 'mode': mode},
        ),
    )
    if input_text:
        _start_agent_llm_task(send, connection, input_text)
        return

    await _start_agent_asr_session(send, connection, message)


async def _handle_agent_session_finish(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    if connection.agent_session_id is None:
        await _send_json(send, {'type': 'agent.error', 'id': message.get('id'), 'message': 'Agent session is not started'})
        return
    if connection.asr_upstream is None:
        text = connection.agent_latest_text.strip()
        if text:
            _start_agent_llm_task(send, connection, text)
            return
        await _send_json(send, {'type': 'agent.error', 'id': connection.agent_session_id, 'message': 'ASR session is not started'})
        return
    connection.asr_accepting_audio = False
    await connection.asr_upstream.send(json.dumps(realtime_asr._session_finish_event()))


async def _handle_agent_session_cancel(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    session_id = connection.agent_session_id
    request_id = connection.agent_request_id
    trace_id = connection.agent_trace_id
    device_code = connection.agent_device_code
    logger.info(
        'realtime.agent.cancel_requested agent_session=%s request_id=%s trace_id=%s device_code=%s',
        session_id,
        request_id,
        trace_id,
        device_code,
    )
    await connection.close_asr_session()
    await connection.close_llm_session()
    await connection.close_tts_session()
    await connection.close_agent_session()
    await _send_json(
        send,
        {
            'type': 'agent.cancelled',
            'id': message.get('id'),
            'payload': {'sessionId': session_id},
        },
    )


def _start_agent_llm_task(send, connection: RealtimeConnection, text: str) -> asyncio.Task | None:
    if connection.agent_task is not None and not connection.agent_task.done():
        return connection.agent_task
    connection.agent_task = asyncio.create_task(_run_agent_llm_and_finish(send, connection, text))
    return connection.agent_task


async def _try_dispatch_command_for_session(
    send,
    session: dict[str, Any],
    question_text: str,
    command_id,
    request_id: str,
    trace_id: str,
    on_tts_segment,
    error_event_type: str,
):
    """Attempt local command dispatch before normal chat completion."""
    from apps.resources.services.command_dispatch import try_dispatch_command

    async def on_delta(text: str) -> None:
        await _send_json(
            send,
            {
                'type': 'llm.delta',
                'id': command_id,
                'requestId': request_id,
                'traceId': trace_id,
                'payload': {'text': text},
            },
        )

    async def on_tts(text: str) -> None:
        await _send_llm_tts_segment(send, command_id, request_id, trace_id, text)
        if on_tts_segment is not None:
            await on_tts_segment(text)

    try:
        return await try_dispatch_command(
            session=session,
            question_text=question_text,
            on_delta=on_delta,
            on_tts_segment=on_tts,
            error_event_type=error_event_type,
            command_id=command_id,
            request_id=request_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.warning(
            'realtime.command_dispatch_failed device_code=%s request_id=%s error=%s',
            session.get('deviceCode'),
            request_id,
            exc,
        )
        return None


async def _stream_runtime_answer_deltas(session: dict[str, Any], dispatch_outcome):
    if dispatch_outcome is not None and dispatch_outcome.hit:
        return
    async for delta in llm_services.stream_llm_chat_completion(
        model_config=session['modelConfig'],
        messages=session['messages'],
        temperature=session['temperature'],
        max_tokens=session['maxTokens'],
    ):
        yield delta


async def _run_llm_session(send, connection: RealtimeConnection, command_id, message: dict[str, Any]) -> None:
    try:
        await _run_llm_session_body(send, command_id, message)
    except asyncio.CancelledError:
        raise
    finally:
        if connection.llm_task is asyncio.current_task():
            connection.llm_task = None
            connection.llm_session_id = None


async def _run_llm_session_body(
    send,
    command_id,
    message: dict[str, Any],
    on_tts_segment: Callable[[str], Awaitable[None]] | None = None,
    error_event_type: str = 'llm.error',
) -> str | None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    question_text = str(payload.get('text') or payload.get('questionText') or payload.get('question') or '').strip()
    request_id = _request_id_from_payload(payload)
    trace_id = _trace_id_from_payload(payload, request_id)
    if not device_code:
        await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message='Device code is required'))
        return None
    if not question_text:
        await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message='Question text is required'))
        return None

    incoming_session_id = str(
        payload.get('sessionId')
        or payload.get('session_id')
        or payload.get('conversationId')
        or payload.get('conversation_id')
        or ''
    ).strip()

    try:
        session = await sync_to_async(_prepare_device_llm_session, thread_sensitive=True)(device_code, question_text, payload)
    except Exception as exc:
        await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, **_realtime_error_payload(exc)))
        return None

    if session.get('backendType') == RUNTIME_BACKEND_PLATFORM_LLM:
        logger.info(
            '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：incoming_session_id 会话ID：%s',
            question_text,
            incoming_session_id or None,
        )
        logger.info(
            '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：session.sessionId 会话ID：%s',
            question_text,
            session.get('sessionId'),
        )

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
            'sessionId': session.get('sessionId'),
            'conversationId': session.get('conversationId'),
        },
    }
    await _send_json(send, started_payload)

    answer_text = ''
    dispatch_outcome = None
    answer_blocks = session.get('annotationBlocks') or None
    knowledge_media_blocks = session.get('knowledgeMediaBlocks') or []
    if session.get('annotationAnswer') is not None:
        answer_text = session['annotationAnswer']
        delta_payload = {'text': answer_text}
        if _has_media_reply_blocks(answer_blocks):
            delta_payload['blocks'] = answer_blocks
        await _send_json(
            send,
            {
                'type': 'llm.delta',
                'id': command_id,
                'requestId': request_id,
                'traceId': trace_id,
                'payload': delta_payload,
            },
        )
        for segment in _split_llm_tts_segments(answer_text, session):
            await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
            if on_tts_segment is not None:
                await on_tts_segment(segment)
    else:
        if session.get('backendType') == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
            tts_buffer = ''
            if session.get('thirdPartySupportsStreaming'):
                try:
                    async for delta in _stream_third_party_session_message(session, question_text):
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
                        tts_buffer += delta
                        segments, tts_buffer = _pop_llm_tts_segments(tts_buffer, session)
                        for segment in segments:
                            await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
                            if on_tts_segment is not None:
                                await on_tts_segment(segment)
                except Exception as exc:
                    await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message=str(exc)[:200]))
                    return None
                final_segments, _ = _pop_llm_tts_segments(tts_buffer, session, flush=True)
                for segment in final_segments:
                    await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
                    if on_tts_segment is not None:
                        await on_tts_segment(segment)
            else:
                try:
                    answer_text = await sync_to_async(_send_third_party_session_message, thread_sensitive=True)(session, question_text)
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
                    for segment in _split_llm_tts_segments(answer_text, session):
                        await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
                        if on_tts_segment is not None:
                            await on_tts_segment(segment)
                except Exception as exc:
                    await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message=str(exc)[:200]))
                    return None
        else:
            dispatch_outcome = await _try_dispatch_command_for_session(
                send, session, question_text, command_id, request_id, trace_id, on_tts_segment, error_event_type
            )
            if dispatch_outcome is not None and dispatch_outcome.hit:
                answer_text = dispatch_outcome.reply_text
            tts_buffer = ''
            try:
                async for delta in _stream_runtime_answer_deltas(session, dispatch_outcome):
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
                    tts_buffer += delta
                    segments, tts_buffer = _pop_llm_tts_segments(tts_buffer, session)
                    for segment in segments:
                        await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
                        if on_tts_segment is not None:
                            await on_tts_segment(segment)
            except Exception as exc:
                await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message=str(exc)[:200]))
                return None
            final_segments, _ = _pop_llm_tts_segments(tts_buffer, session, flush=True)
            for segment in final_segments:
                await _send_llm_tts_segment(send, command_id, request_id, trace_id, segment)
                if on_tts_segment is not None:
                    await on_tts_segment(segment)

    if not answer_text:
        await _send_json(send, _trace_payload(error_event_type, command_id, request_id, trace_id, message='LLM 没有返回有效回复'))
        return None
    if answer_blocks is None and knowledge_media_blocks:
        from apps.ai_models.services.reply_blocks import text_to_blocks

        answer_blocks = [*text_to_blocks(answer_text), *knowledge_media_blocks]

    command_dispatch_diagnostics = _command_dispatch_diagnostics(dispatch_outcome)
    command_dispatch_snapshots: list[dict[str, Any]] = []
    if dispatch_outcome is not None and dispatch_outcome.hit:
        from apps.resources.services.command_dispatch import build_command_dispatch_snapshots

        command_dispatch_snapshots = await build_command_dispatch_snapshots(
            tenant_id=session.get('tenantId'),
            command_metas=dispatch_outcome.matched_command_metas,
        )
    conversation_id = session.get('conversationId')
    if session.get('backendType') == RUNTIME_BACKEND_PLATFORM_LLM:
        logger.info(
            '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：session.sessionId 会话ID：%s',
            question_text,
            session.get('sessionId'),
        )
    if conversation_id is not None:
        await sync_to_async(_append_runtime_conversation_messages, thread_sensitive=True)(conversation_id, question_text, answer_text, answer_blocks)
    else:
        _remember_agent_exchange(session.get('memoryKey'), question_text, answer_text)
    try:
        await sync_to_async(_record_realtime_device_chat_log, thread_sensitive=True)(
            session,
            question_text,
            answer_text,
            request_id,
            trace_id,
            answer_blocks,
            command_dispatch_diagnostics,
        )
    except Exception:
        logger.exception('realtime.agent_chat.log_failed device_code=%s request_id=%s', session.get('deviceCode'), request_id)

    done_payload = {
        'deviceCode': session['deviceCode'],
        'questionText': question_text,
        'answerText': answer_text,
        'agentApplicationId': session['agentApplicationId'],
        'agentApplicationName': session['agentApplicationName'],
        'applicationId': session['applicationId'],
        'applicationName': session['applicationName'],
        'sessionId': session.get('sessionId'),
        'conversationId': conversation_id,
    }
    if _has_media_reply_blocks(answer_blocks):
        done_payload['answerBlocks'] = answer_blocks
    if dispatch_outcome is not None:
        done_payload['commandDispatch'] = {
            'hit': bool(dispatch_outcome.hit),
            'mode': dispatch_outcome.mode,
            'replySource': dispatch_outcome.reply_source,
            'toolCalls': dispatch_outcome.tool_calls_summary or [],
            'commands': command_dispatch_snapshots,
        }
        done_payload['commandDispatch'].update(command_dispatch_diagnostics)
    await _send_json(
        send,
        {
            'type': 'llm.done',
            'id': command_id,
            'requestId': request_id,
            'traceId': trace_id,
            'payload': done_payload,
        },
    )
    return answer_text


async def _send_llm_tts_segment(send, command_id, request_id: str, trace_id: str, text: str) -> None:
    segment = str(text or '').strip()
    if not segment:
        return
    await _send_json(
        send,
        {
            'type': 'llm.tts_segment',
            'id': command_id,
            'requestId': request_id,
            'traceId': trace_id,
            'payload': {'text': segment},
        },
    )


def _agent_memory_key(device, agent_application=None) -> str:
    if agent_application is None:
        agent_application = getattr(device, 'effective_agent_application', None)
    agent_application_id = getattr(agent_application, 'id', None)
    if agent_application is None:
        knowledge_version = 'none'
    elif agent_application.published_at:
        knowledge_version = f'published:{agent_application.published_version}:{agent_application.published_at.isoformat()}'
    else:
        knowledge_base_ids = ','.join(
            str(item)
            for item in agent_application.knowledge_bases.order_by('id').values_list('id', flat=True)
        )
        knowledge_document_ids = ','.join(
            str(item)
            for item in agent_application.knowledge_documents.order_by('id').values_list('id', flat=True)
        )
        knowledge_version = (
            f'{agent_application.updated_at.isoformat()}:'
            f'kb={knowledge_base_ids or "none"}:'
            f'doc={knowledge_document_ids or "none"}'
        )
    return f'{device.tenant_id}:{device.code}:agent:{agent_application_id or "none"}:{knowledge_version}'


def _get_agent_memory(memory_key: str) -> list[dict[str, str]]:
    return [dict(item) for item in _AGENT_MEMORY.get(memory_key, [])]


def _remember_agent_exchange(memory_key: str | None, question_text: str, answer_text: str) -> None:
    if not memory_key:
        return
    question = str(question_text or '').strip()
    answer = str(answer_text or '').strip()
    if not question or not answer:
        return
    history = _AGENT_MEMORY.setdefault(memory_key, [])
    history.extend([
        {'role': 'user', 'content': question},
        {'role': 'assistant', 'content': answer},
    ])
    if len(history) > _AGENT_MEMORY_MAX_MESSAGES:
        del history[:-_AGENT_MEMORY_MAX_MESSAGES]


def _record_realtime_device_chat_log(
    session: dict[str, Any],
    question_text: str,
    answer_text: str,
    request_id: str,
    trace_id: str,
    answer_blocks: list[dict] | None = None,
    command_dispatch_diagnostics: dict[str, Any] | None = None,
) -> None:
    from apps.devices.models import DeviceChatLog
    from apps.devices.services.chat_logs import record_device_chat_log
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(str(session.get('deviceCode') or ''))
    record_device_chat_log(
        device,
        question_text,
        answer_text,
        source=DeviceChatLog.SOURCE_WEBSOCKET,
        request_id=request_id,
        trace_id=trace_id,
        model_name=str(session.get('modelName') or ''),
        conversation_id=session.get('conversationId'),
        runtime_session_id=str(session.get('sessionId') or ''),
        answer_blocks=answer_blocks,
        command_dispatch_diagnostics=command_dispatch_diagnostics,
    )


def _command_dispatch_diagnostics(dispatch_outcome) -> dict[str, Any]:
    if dispatch_outcome is None or dispatch_outcome.route is None:
        return {}
    return {
        'highestScore': dispatch_outcome.highest_score,
        'secondHighestScore': dispatch_outcome.second_highest_score,
        'candidateCount': dispatch_outcome.candidate_count,
        'route': dispatch_outcome.route,
        'confirmationOutcome': dispatch_outcome.confirmation_outcome,
        'executionOutcome': dispatch_outcome.execution_outcome,
    }


def _send_third_party_session_message(session: dict[str, Any], question_text: str) -> str:
    chatbot, conversation = _resolve_third_party_session_context(session)
    return third_party_chatbots.send_chatbot_message(chatbot, question_text, conversation=conversation)


def _resolve_third_party_session_context(session: dict[str, Any]):
    from apps.ai_models.models import ChatConversation, ThirdPartyChatbotApplication

    chatbot = (
        ThirdPartyChatbotApplication.objects
        .select_related('provider', 'integration')
        .filter(id=session.get('thirdPartyChatbotId'))
        .first()
    )
    if chatbot is None:
        raise RuntimeError('第三方会话机器人不存在')

    conversation = None
    conversation_id = session.get('conversationId')
    if conversation_id is not None:
        conversation = (
            ChatConversation.objects
            .select_related('third_party_chatbot__provider')
            .filter(id=conversation_id, third_party_chatbot=chatbot)
            .first()
        )
    return chatbot, conversation


async def _stream_third_party_session_message(session: dict[str, Any], question_text: str):
    chatbot, conversation = await sync_to_async(_resolve_third_party_session_context, thread_sensitive=True)(session)
    async for text in third_party_chatbots.stream_chatbot_message(chatbot, question_text, conversation=conversation):
        if text:
            yield str(text)


def _is_client_disconnected(exc: BaseException) -> bool:
    if isinstance(exc, ConnectionClosed):
        return True
    return exc.__class__.__name__ in {'ClientDisconnected', 'ClientConnectionResetError'}


async def _start_agent_asr_session(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = connection.agent_session_id
    request_id = connection.agent_request_id or make_request_id()
    trace_id = connection.agent_trace_id or request_id
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    token = str(payload.get('token') or '').strip()
    query_params = _payload_query_params(payload, 'tenantId', 'tenant', 'deviceCode', 'device_code')

    resolved_connection = await sync_to_async(realtime_asr.resolve_asr_realtime_connection, thread_sensitive=True)(
        token,
        headers=[],
        query_params=query_params,
    )
    if resolved_connection is None:
        await _send_json(send, _trace_payload('agent.error', command_id, request_id, trace_id, message='ASR session is not authorized'))
        return

    config = await sync_to_async(realtime_asr.get_effective_asr_config, thread_sensitive=True)()
    if not config.is_active or not realtime_asr.is_asr_configured(config):
        await _send_json(send, _trace_payload('agent.error', command_id, request_id, trace_id, message='ASR 服务未就绪'))
        return

    replacement_pairs = await sync_to_async(realtime_asr.load_asr_replacement_pairs, thread_sensitive=True)(
        resolved_connection.get('tenant_id'),
    )

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
        await upstream.send(json.dumps(realtime_asr._session_update_event(
            vad_threshold=getattr(config, 'vad_threshold', 0.0),
            vad_silence_duration_ms=getattr(config, 'vad_silence_duration_ms', 400),
        )))
    except Exception as exc:
        await _send_json(send, _trace_payload('agent.error', command_id, request_id, trace_id, message=str(exc)[:200]))
        return

    connection.asr_session_id = command_id
    connection.asr_upstream = upstream
    connection.asr_upstream_context = upstream_context
    connection.asr_accepting_audio = True
    connection.asr_filter_filler_words = getattr(config, 'filter_filler_words', True)
    connection.asr_upstream_task = asyncio.create_task(
        _agent_asr_upstream_to_client(upstream, send, connection, replacement_pairs),
    )
    await _send_json(send, _trace_payload('asr.ready', command_id, request_id, trace_id))


async def _agent_asr_upstream_to_client(upstream, send, connection: RealtimeConnection, replacement_pairs: list[tuple[str, str]]) -> None:
    command_id = connection.agent_session_id
    request_id = connection.agent_request_id or make_request_id()
    trace_id = connection.agent_trace_id or request_id
    finish_sent = False
    try:
        async for raw_message in upstream:
            try:
                event = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(event, dict):
                continue

            if event.get('type') == 'input_audio_buffer.speech_stopped':
                if connection.asr_accepting_audio:
                    connection.asr_accepting_audio = False
                    await _send_json(
                        send,
                        {
                            'type': 'asr.input_stopped',
                            'id': command_id,
                            'requestId': request_id,
                            'traceId': trace_id,
                            'reason': 'vad',
                        },
                    )
                    # VAD may stop accepting audio before the upstream sends its final transcript.
                    # Explicitly finish so the ASR session cannot remain open indefinitely.
                    if not finish_sent:
                        finish_sent = True
                        await upstream.send(json.dumps(realtime_asr._session_finish_event()))
                continue

            transcript_payload = realtime_asr.extract_transcript_payload(
                event,
                replacement_pairs=replacement_pairs,
                filter_filler_words=connection.asr_filter_filler_words,
            )
            if transcript_payload is not None:
                transcript_payload['id'] = command_id
                transcript_payload['requestId'] = request_id
                transcript_payload['traceId'] = trace_id
                await _send_json(send, transcript_payload)
                text = str(transcript_payload.get('text') or '').strip()
                if text:
                    connection.agent_latest_text = text
                if transcript_payload.get('final') and not finish_sent:
                    finish_sent = True
                    connection.asr_accepting_audio = False
                    await upstream.send(json.dumps(realtime_asr._session_finish_event()))
                continue

            if realtime_asr.is_final_transcript_event(event):
                connection.asr_accepting_audio = False
                connection.agent_latest_text = ''
                if not finish_sent:
                    finish_sent = True
                    await upstream.send(json.dumps(realtime_asr._session_finish_event()))
                continue

            if event.get('type') == 'session.finished':
                await _send_json(send, {'type': 'asr.done', 'id': command_id, 'requestId': request_id, 'traceId': trace_id})
                text = connection.agent_latest_text.strip()
                await _clear_finished_asr_session(connection, keep_current_task=True)
                if text:
                    _start_agent_llm_task(send, connection, text)
                    await asyncio.sleep(0)
                else:
                    await connection.close_agent_session()
                return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if _is_client_disconnected(exc):
            return
        raise
    finally:
        if connection.asr_upstream_task is asyncio.current_task():
            connection.asr_upstream_task = None


async def _clear_finished_asr_session(connection: RealtimeConnection, *, keep_current_task: bool = False) -> None:
    upstream_context = connection.asr_upstream_context
    current_task = asyncio.current_task()
    connection.asr_upstream = None
    connection.asr_upstream_context = None
    if not keep_current_task or connection.asr_upstream_task is not current_task:
        connection.asr_upstream_task = None
    connection.asr_session_id = None
    connection.asr_accepting_audio = False
    if upstream_context is not None:
        _close_asr_upstream_context_later(upstream_context)


async def _run_agent_llm_and_finish(send, connection: RealtimeConnection, question_text: str) -> None:
    current_task = asyncio.current_task()
    command_id = connection.agent_session_id
    request_id = connection.agent_request_id or make_request_id()
    trace_id = connection.agent_trace_id or request_id
    device_code = connection.agent_device_code or ''
    message = {
        'id': command_id,
        'payload': {
            'deviceCode': device_code,
            'text': question_text,
            'requestId': request_id,
            'traceId': trace_id,
        },
    }
    if connection.agent_runtime_session_id not in (None, ''):
        message['payload']['sessionId'] = connection.agent_runtime_session_id
    elif connection.agent_conversation_id not in (None, ''):
        message['payload']['conversationId'] = connection.agent_conversation_id

    try:
        answer_text = await _run_llm_session_body(
            send,
            command_id,
            message,
            on_tts_segment=lambda segment: _queue_agent_tts_segment(connection, segment),
            error_event_type='agent.error',
        )
        if connection.agent_tts_queue is not None:
            await connection.agent_tts_queue.put(None)
            if connection.agent_tts_worker is not None:
                await asyncio.gather(connection.agent_tts_worker, return_exceptions=True)
                connection.agent_tts_worker = None
        if answer_text is None:
            return
        try:
            await _send_json(send, _trace_payload('agent.done', command_id, request_id, trace_id, payload={'deviceCode': device_code, 'questionText': question_text}))
        except RuntimeError as exc:
            if 'Unexpected ASGI message' not in str(exc):
                raise
            # 客户端已断开连接后 asgi_send 会抛 RuntimeError；agent.done 只是尽力通知，无需上报
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if not _is_client_disconnected(exc):
            raise
    finally:
        if connection.agent_task in (None, current_task):
            await connection.close_agent_session()


def _validate_agent_runtime_start(device_code: str) -> None:
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(device_code)
    validate_runtime_application_active(device)
    agent_application = device.effective_agent_application
    if agent_application is None or not agent_application.runtime_config().get('is_active'):
        raise RuntimeError('设备未绑定可用智能体')


async def _queue_agent_tts_segment(connection: RealtimeConnection, segment: str) -> None:
    if connection.agent_tts_queue is not None and segment:
        await connection.agent_tts_queue.put(segment)
        await asyncio.sleep(0)


async def _agent_tts_worker(send, connection: RealtimeConnection, command_id, device_code: str, request_id: str, trace_id: str, payload: dict[str, Any]) -> None:
    queue = connection.agent_tts_queue
    if queue is None:
        return
    try:
        first_segment = await queue.get()
        if first_segment is None:
            return
        await _run_agent_tts_stream(send, command_id, queue, device_code, request_id, trace_id, first_segment, payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            'Agent TTS stream failed: request_id=%s trace_id=%s command_id=%s device_code=%s',
            request_id,
            trace_id,
            command_id,
            device_code,
        )
        await _send_json(
            send,
            _trace_payload('tts.error', command_id, request_id, trace_id, message=str(exc)[:200]),
        )


async def _run_agent_tts_stream(send, command_id, queue: asyncio.Queue, device_code: str, request_id: str, trace_id: str, first_segment: str, payload: dict[str, Any]) -> None:
    logger.info(
        'realtime.agent.tts_started agent_session=%s request_id=%s trace_id=%s device_code=%s first_segment_length=%s',
        command_id,
        request_id,
        trace_id,
        device_code,
        len(first_segment or ''),
    )
    query_params = _payload_query_params({'deviceCode': device_code}, 'deviceCode')
    session_config = payload.get('sessionConfig') or payload.get('ttsSessionConfig')
    resolved_connection = await sync_to_async(realtime_tts.resolve_tts_realtime_connection, thread_sensitive=True)(
        '',
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
    if session_config is None:
        session_config = await sync_to_async(_resolve_connection_tts_session_config, thread_sensitive=True)(resolved_connection, config)
    model_code = tts_services.get_tts_model_profile_code_from_session(session_config, config.model)

    voice = await sync_to_async(realtime_tts.resolve_tts_voice, thread_sensitive=True)(
        resolved_connection,
        payload.get('voiceId'),
        provider,
        model_code=model_code,
    )
    if voice is None:
        raise RuntimeError('TTS 音色未配置或当前模型不支持该音色')

    await realtime_tts._stream_tts_segments_audio(
        segments=_agent_tts_segments(first_segment, queue),
        voice=voice,
        config=config,
        session_config=session_config,
        exclude_patterns=payload.get('ttsFilterExcludePatterns') or [],
        send=_with_command_id(send, command_id),
    )
    logger.info(
        'realtime.agent.tts_done agent_session=%s request_id=%s trace_id=%s device_code=%s',
        command_id,
        request_id,
        trace_id,
        device_code,
    )


def _resolve_connection_tts_session_config(connection: dict[str, Any], config) -> dict[str, Any]:
    device_id = connection.get('device_id')
    if device_id:
        from apps.devices.models import Device

        device = Device.objects.select_related('tenant').filter(id=device_id).first()
        if device is not None:
            return device_tts_session_config(device, config.provider)

    tenant_id = connection.get('tenant_id')
    if not tenant_id:
        return config.tts_session_config

    from apps.tenants.models import Tenant

    tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
    settings_obj = tts_services.get_tenant_tts_settings(tenant)
    if settings_obj is None:
        return config.tts_session_config
    return settings_obj.tts_session_config or config.tts_session_config


async def _agent_tts_segments(first_segment: str, queue: asyncio.Queue):
    if first_segment:
        yield first_segment
    while True:
        segment = await queue.get()
        if segment is None:
            return
        if segment:
            yield segment


def _pop_llm_tts_segments(buffer: str, session: dict[str, Any], *, flush: bool = False) -> tuple[list[str], str]:
    return tts_services.pop_tts_text_segments(
        buffer,
        filter_punctuation=str(session.get('ttsFilterPunctuation') or ''),
        filter_emoji=bool(session.get('ttsFilterEmoji')),
        exclude_patterns=session.get('ttsFilterExcludePatterns') or [],
        flush=flush,
    )


def _split_llm_tts_segments(text: str, session: dict[str, Any]) -> list[str]:
    segments, _ = _pop_llm_tts_segments(text, session, flush=True)
    return segments


def _has_media_reply_blocks(blocks) -> bool:
    return any(isinstance(block, dict) and block.get('type') in {'image', 'video'} for block in blocks or [])


def _payload_session_id(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_id = payload.get('sessionId') or payload.get('session_id')
    if raw_id in (None, ''):
        return None
    session_id = str(raw_id).strip()
    return session_id or None


def _new_runtime_session_id() -> str:
    return str(uuid.uuid4())


def _conversation_session_id(conversation) -> str | None:
    if conversation is None:
        return None
    external_session = conversation.external_session if isinstance(conversation.external_session, dict) else {}
    session_id = str(external_session.get('runtimeSessionId') or '').strip()
    return session_id or None


def _ensure_runtime_session_id(conversation) -> str | None:
    if conversation is None:
        return None
    session_id = _conversation_session_id(conversation)
    if session_id:
        return session_id
    external_session = conversation.external_session if isinstance(conversation.external_session, dict) else {}
    session_id = _new_runtime_session_id()
    conversation.external_session = {**external_session, 'runtimeSessionId': session_id}
    conversation.save(update_fields=['external_session'])
    return session_id


def _payload_conversation_id(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw_id = payload.get('conversationId') or payload.get('conversation_id')
    if raw_id in (None, ''):
        return None
    try:
        conversation_id = int(raw_id)
    except (TypeError, ValueError):
        raise RuntimeError('conversationId 必须是有效整数')
    if conversation_id <= 0:
        raise RuntimeError('conversationId 必须是有效整数')
    return conversation_id

def _runtime_conversation_user(agent_application, tenant):
    if getattr(agent_application, 'created_by_id', None):
        return agent_application.created_by

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(membership__tenant=tenant).order_by('-membership__is_tenant_admin', 'id').first()
    if user is not None:
        return user

    username = f'runtime_tenant_{tenant.id}'
    user, _ = User.objects.get_or_create(username=username, defaults={'is_active': False})
    return user


def _resolve_runtime_conversation(
    device,
    agent_application,
    model,
    runtime_config: dict[str, Any],
    payload: dict[str, Any] | None,
    third_party_chatbot=None,
):
    from apps.ai_models.models import ChatConversation

    session_id = _payload_session_id(payload)
    if session_id is not None:
        conversation = (
            ChatConversation.objects
            .select_related('llm_model__provider', 'third_party_chatbot__provider', 'application')
            .filter(
                tenant=device.tenant,
                application=agent_application,
                external_session__runtimeSessionId=session_id,
            )
            .first()
        )
        if conversation is None:
            raise RuntimeError('sessionId 不存在或不属于当前设备智能体')
        return conversation

    conversation_id = _payload_conversation_id(payload)
    if conversation_id is not None:
        conversation = (
            ChatConversation.objects
            .select_related('llm_model__provider', 'third_party_chatbot__provider', 'application')
            .filter(id=conversation_id, tenant=device.tenant, application=agent_application)
            .first()
        )
        if conversation is None:
            raise RuntimeError('conversationId 不存在或不属于当前设备智能体')
        _ensure_runtime_session_id(conversation)
        return conversation

    user = _runtime_conversation_user(agent_application, device.tenant)
    return ChatConversation.objects.create(
        title=f'{runtime_config.get("name") or agent_application.name} 运行时会话',
        user=user,
        llm_model=model,
        runtime_backend_type=runtime_config.get('runtime_backend_type') or RUNTIME_BACKEND_PLATFORM_LLM,
        third_party_chatbot=third_party_chatbot,
        external_session={'runtimeSessionId': _new_runtime_session_id()},
        summary='',
        system_prompt=runtime_config.get('system_prompt') or '',
        temperature=runtime_config.get('temperature', 0.7),
        max_tokens=runtime_config.get('max_tokens', 1000),
        max_tokens_unlimited=runtime_config.get('max_tokens_unlimited', False),
        application=agent_application,
        tenant=device.tenant,
    )

def _append_runtime_conversation_messages(conversation_id: int | None, question_text: str, answer_text: str, answer_blocks=None) -> None:
    if conversation_id is None:
        return

    from apps.ai_models.models import ChatConversation, ChatMessage

    conversation = ChatConversation.objects.filter(id=conversation_id).first()
    if conversation is None:
        return
    ChatMessage.objects.create(
        conversation=conversation,
        role=ChatMessage.ROLE_USER,
        content=question_text,
        content_blocks=[{'type': 'text', 'text': question_text}],
    )
    ChatMessage.objects.create(
        conversation=conversation,
        role=ChatMessage.ROLE_ASSISTANT,
        content=answer_text,
        content_blocks=answer_blocks or [{'type': 'text', 'text': answer_text}],
    )
    conversation.save(update_fields=['updated_at'])


def _prepare_device_llm_session(device_code: str, question_text: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(device_code)
    validate_runtime_application_active(device)
    agent_application = device.effective_agent_application
    if agent_application is None or not agent_application.runtime_config().get('is_active'):
        raise RuntimeError('设备未绑定可用智能体')
    runtime_config = agent_application.runtime_config()
    runtime_backend_type = runtime_config.get('runtime_backend_type') or RUNTIME_BACKEND_PLATFORM_LLM
    memory_key = _agent_memory_key(device, agent_application)

    model = None
    chatbot = None
    conversation = None
    if runtime_backend_type == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
        from apps.ai_models.models import ThirdPartyChatbotApplication

        runtime_chatbot_id = runtime_config.get('third_party_chatbot_id')
        if runtime_chatbot_id:
            chatbot = ThirdPartyChatbotApplication.objects.select_related('provider', 'integration').filter(id=runtime_chatbot_id).first()
        if chatbot is None:
            chatbot = agent_application.third_party_chatbot
        if not third_party_chatbots.is_chatbot_effective_for_tenant(device.tenant, chatbot):
            raise RuntimeError('请先为设备绑定智能体配置可用第三方会话机器人')
        conversation = _resolve_runtime_conversation(
            device,
            agent_application,
            None,
            runtime_config,
            payload,
            third_party_chatbot=chatbot,
        )
    else:
        runtime_backend_type = RUNTIME_BACKEND_PLATFORM_LLM
        runtime_model_id = runtime_config.get('llm_model_id')
        if runtime_model_id:
            from apps.ai_models.models import LLMModel

            model = LLMModel.objects.select_related('provider').filter(id=runtime_model_id).first()
        if model is None:
            model = agent_application.llm_model
        if model is None:
            settings = llm_services.get_tenant_llm_settings(device.tenant)
            model = settings.default_model if settings is not None else None
        if not llm_services.is_llm_model_effective_for_tenant(device.tenant, model):
            raise RuntimeError('请先为设备绑定智能体配置可用 LLM 模型')
        conversation = _resolve_runtime_conversation(device, agent_application, model, runtime_config, payload)
    if runtime_backend_type == RUNTIME_BACKEND_PLATFORM_LLM:
        logger.info(
            '[VOICE-SESSION-DIAG] 当前问题：%s 会话ID变量名：runtime_session_id 会话ID：%s',
            question_text,
            _conversation_session_id(conversation),
        )

    annotation = DeviceVoiceChatView._find_annotation(agent_application, question_text)
    if annotation is not None:
        now = timezone.now()
        annotation_id = annotation.get('id') if isinstance(annotation, dict) else annotation.id
        from apps.ai_models.models import AgentAnnotation

        AgentAnnotation.objects.filter(id=annotation_id).update(
            hit_count=F('hit_count') + 1,
            last_hit_at=now,
        )
        annotation_answer = annotation.get('answer') if isinstance(annotation, dict) else annotation.answer
        from apps.ai_models.services.reply_blocks import serialize_published_annotation_blocks, serialize_reply_blocks

        annotation_blocks = (
            serialize_published_annotation_blocks(annotation, tenant=agent_application.tenant)
            if isinstance(annotation, dict)
            else serialize_reply_blocks(annotation.answer_blocks, tenant=agent_application.tenant)
        )
    else:
        annotation_answer = None
        annotation_blocks = None

    base_session = {
        'deviceCode': device.code,
        'backendType': runtime_backend_type,
        'memoryKey': memory_key,
        'sessionId': _conversation_session_id(conversation),
        'conversationId': conversation.id if conversation is not None else None,
        'annotationAnswer': annotation_answer,
        'annotationBlocks': annotation_blocks,
        'agentApplicationId': agent_application.id,
        'agentApplicationName': runtime_config.get('name') or agent_application.name,
        'applicationId': device.application_id,
        'applicationName': device.application.name if device.application else '',
        'tenantId': device.tenant_id,
        'ttsFilterPunctuation': runtime_config.get('tts_filter_punctuation') or '',
        'ttsFilterEmoji': runtime_config.get('tts_filter_emoji'),
        'ttsFilterExcludePatterns': runtime_config.get('tts_filter_exclude_patterns') or [],
    }

    if runtime_backend_type == RUNTIME_BACKEND_THIRD_PARTY_CHATBOT:
        return {
            **base_session,
            'thirdPartyChatbotId': chatbot.id,
            'thirdPartySupportsStreaming': third_party_chatbots.supports_streaming(
                chatbot.integration.config if getattr(chatbot, 'integration', None) is not None else None
            ),
            'modelName': chatbot.name,
        }

    system_prompt = (
        str(runtime_config.get('system_prompt') or '').strip()
        if str(runtime_config.get('system_prompt') or '').strip()
        else '你是数字人设备的中文语音问答助手。回答要自然、简洁，适合直接转成语音播报。'
    )
    messages = [{'role': 'system', 'content': system_prompt}]

    from apps.ai_models.services.agent_knowledge import retrieve_knowledge_context_with_media
    from apps.ai_models.services.reply_blocks import serialize_reply_blocks

    knowledge_context, media_blocks = retrieve_knowledge_context_with_media(
        agent_application,
        question_text,
        knowledge_document_ids=runtime_config.get('knowledge_document_ids') or [],
        knowledge_base_ids=runtime_config.get('knowledge_base_ids') or [],
    )
    media_blocks = serialize_reply_blocks(media_blocks, tenant=agent_application.tenant)
    if knowledge_context:
        messages.append({'role': 'system', 'content': knowledge_context})
    if conversation is not None:
        messages.extend(
            {'role': role, 'content': content}
            for role, content in conversation.messages.order_by('created_at').values_list('role', 'content')
        )
    else:
        messages.extend(_get_agent_memory(memory_key))
    messages.append({'role': 'user', 'content': question_text})

    return {
        **base_session,
        'modelConfig': {
            'name': model.name,
            'apiBaseUrl': model.provider.api_base_url,
            'apiKey': model.provider.api_key,
            'enableWebSearch': model.enable_web_search,
        },
        'messages': messages,
        'knowledgeMediaBlocks': media_blocks,
        'temperature': runtime_config.get('temperature', 0.7),
        'maxTokens': None if runtime_config.get('max_tokens_unlimited') else runtime_config.get('max_tokens', 1000),
        'modelName': model.name,
    }


def _run_device_llm_answer(device_code: str, question_text: str) -> dict[str, Any]:
    from apps.devices.services.runtime import get_runtime_device

    device = get_runtime_device(device_code)
    validate_runtime_application_active(device)
    agent_application = device.effective_agent_application
    if agent_application is None or not agent_application.runtime_config().get('is_active'):
        raise RuntimeError('设备未绑定可用智能体')
    runtime_config = agent_application.runtime_config()
    answer_text, answer_blocks = DeviceVoiceChatView._generate_answer(device, question_text)
    return {
        'deviceCode': device.code,
        'answerText': answer_text,
        'answerBlocks': answer_blocks,
        'agentApplicationId': agent_application.id,
        'agentApplicationName': runtime_config.get('name') or agent_application.name,
        'applicationId': device.application_id,
        'applicationName': device.application.name if device.application else '',
    }


async def _run_tts_session(send, connection: RealtimeConnection, command_id, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    try:
        await _run_tts_session_body(send, command_id, message)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception('TTS session failed: command_id=%s', command_id)
        await _send_json(send, {'type': 'tts.error', 'id': command_id, 'message': str(exc)[:200]})
    finally:
        if connection.tts_task is asyncio.current_task():
            connection.tts_task = None
            connection.tts_session_id = None


async def _run_tts_session_body(send, command_id, message: dict[str, Any]) -> None:
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

    text = realtime_tts.normalize_tts_text(str(payload.get('text') or ''), config)
    session_config = payload.get('sessionConfig') or payload.get('ttsSessionConfig')
    if session_config is None:
        session_config = await sync_to_async(_resolve_connection_tts_session_config, thread_sensitive=True)(resolved_connection, config)
    model_code = tts_services.get_tts_model_profile_code_from_session(session_config, config.model)

    voice = await sync_to_async(realtime_tts.resolve_tts_voice, thread_sensitive=True)(
        resolved_connection,
        payload.get('voiceId'),
        provider,
        model_code=model_code,
    )
    if voice is None:
        raise RuntimeError('TTS 音色未配置或当前模型不支持该音色')
    await realtime_tts._stream_tts_audio(
        text=text,
        voice=voice,
        config=config,
        session_config=session_config,
        send=_with_command_id(send, command_id),
    )


async def _asr_upstream_to_client(upstream, send, connection: RealtimeConnection, command_id, replacement_pairs: list[tuple[str, str]]) -> None:
    finish_sent = False
    async for raw_message in upstream:
        try:
            event = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue

        transcript_payload = realtime_asr.extract_transcript_payload(
            event,
            replacement_pairs=replacement_pairs,
            filter_filler_words=getattr(connection, 'asr_filter_filler_words', True),
        )
        if transcript_payload is not None:
            transcript_payload['id'] = command_id
            await _send_json(send, transcript_payload)
            if transcript_payload.get('final') and not finish_sent:
                finish_sent = True
                connection.asr_accepting_audio = False
                await upstream.send(json.dumps(realtime_asr._session_finish_event()))
            continue

        if realtime_asr.is_filtered_filler_final_event(
            event,
            replacement_pairs=replacement_pairs,
            filter_filler_words=getattr(connection, 'asr_filter_filler_words', True),
        ):
            continue

        if realtime_asr.is_final_transcript_event(event) and not finish_sent:
            finish_sent = True
            connection.asr_accepting_audio = False
            await upstream.send(json.dumps(realtime_asr._session_finish_event()))
            continue

        if event.get('type') == 'session.finished':
            connection.asr_accepting_audio = False
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


def _realtime_error_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, RuntimeDeviceError):
        return exc.as_payload()
    return {'message': str(exc)[:200]}


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


async def _handle_device_voice_bind(send, connection: RealtimeConnection, message: dict[str, Any]) -> None:
    command_id = message.get('id')
    payload = message.get('payload') if isinstance(message.get('payload'), dict) else {}
    device_code = str(payload.get('deviceCode') or payload.get('device_code') or '').strip()
    voice_payload = payload.get('voice')

    if not device_code:
        await _send_error(send, command_id, 'invalid_device', 'Device code is required')
        return

    device = await sync_to_async(get_runtime_device_or_none, thread_sensitive=True)(device_code, require_tenant=True)
    if device is None:
        await _send_error(send, command_id, 'device_not_found', 'Device is not available')
        return

    voice_id = None
    if isinstance(voice_payload, dict):
        raw_id = voice_payload.get('id')
        voice_id = int(raw_id) if isinstance(raw_id, (int, float)) and raw_id > 0 else None
    elif isinstance(voice_payload, (int, float)) and voice_payload > 0:
        voice_id = int(voice_payload)

    bound_voice = None
    if voice_id is not None:
        bound_voice = await sync_to_async(
            lambda: TTSVoice.objects.select_related('provider').filter(
                id=voice_id, is_active=True, is_visible=True, provider__is_active=True,
            ).first(),
            thread_sensitive=True,
        )()
        if bound_voice is None:
            await _send_error(send, command_id, 'voice_not_found', 'Voice is not available')
            return

    previous_voice_id = device.tts_voice_id
    previous_voice_config = dict(device.tts_voice_config or {})
    next_voice_config = previous_voice_config
    if bound_voice is None:
        next_voice_config = {}
    elif isinstance(voice_payload, dict) and has_device_tts_voice_config(voice_payload):
        next_voice_config = normalize_device_tts_voice_config(voice_payload)
    elif previous_voice_id != bound_voice.id:
        next_voice_config = {}

    device.tts_voice = bound_voice
    device.tts_voice_config = next_voice_config
    await sync_to_async(device.save, thread_sensitive=True)(update_fields=['tts_voice', 'tts_voice_config'])

    if previous_voice_id != device.tts_voice_id or previous_voice_config != dict(device.tts_voice_config or {}):
        await publish_device_event({
            'type': 'device.voice_configuration.changed',
            'action': 'voiceConfigurationChanged',
            'operation': 'update',
            'resource': 'voiceConfiguration',
            'tenantId': device.tenant_id,
            'deviceCode': device.code,
            'deviceCodes': [device.code],
            'refresh': {
                'endpoint': '/api/v1/device-runtime/config/',
                'reason': 'voiceConfigurationChanged',
            },
        })

    voice_config_payload = None
    if bound_voice is not None:
        voice_config_payload = await sync_to_async(public_device_tts_voice_config, thread_sensitive=True)(
            device,
            bound_voice.provider,
        )

    await _send_json(send, {
        'type': 'device.voice.bound',
        'id': command_id,
        'payload': {
            'deviceCode': device.code,
            'voiceId': bound_voice.id if bound_voice else None,
            'voiceName': bound_voice.display_name if bound_voice else '',
            'voiceCode': bound_voice.voice_code if bound_voice else '',
            'voiceConfig': voice_config_payload,
        },
    })


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
    await send({'type': 'websocket.send', 'text': json.dumps(payload, ensure_ascii=False, cls=DjangoJSONEncoder)})


class _RealtimeSendMonitor:
    def __init__(self, send, lock: asyncio.Lock, connection: RealtimeConnection):
        self._send = send
        self._lock = lock
        self._connection = connection
        self.connected_at = time.monotonic()
        self.last_send_at = self.connected_at
        self.last_event_type = None
        self.last_text_event_type = None
        self.text_count = 0
        self.binary_count = 0
        self.binary_bytes = 0
        self.tts_started = False
        self.tts_done = False
        self.agent_done = False

    async def __call__(self, event):
        self._record_event(event)
        async with self._lock:
            try:
                await self._send(event)
            except Exception as exc:
                logger.warning('realtime.websocket.send_failed %s exception=%s', self.summary(), repr(exc))
                raise

    def _record_event(self, event) -> None:
        self.last_send_at = time.monotonic()
        if 'bytes' in event:
            self.last_event_type = 'binary'
            self.binary_count += 1
            self.binary_bytes += len(event.get('bytes') or b'')
            return
        if 'text' in event:
            self.last_event_type = 'text'
            self.text_count += 1
            try:
                payload = json.loads(event.get('text') or '')
            except json.JSONDecodeError:
                return
            if isinstance(payload, dict):
                event_type = str(payload.get('type') or '') or None
                self.last_text_event_type = event_type
                if event_type == 'tts.segment_start':
                    self.tts_started = True
                elif event_type == 'tts.done':
                    self.tts_done = True
                elif event_type == 'agent.done':
                    self.agent_done = True

    def summary(self) -> str:
        now = time.monotonic()
        return (
            f'agent_session={self._connection.agent_session_id} '
            f'requestId={self._connection.agent_request_id} '
            f'traceId={self._connection.agent_trace_id} '
            f'device_code={self._connection.agent_device_code} '
            f'connected_age={now - self.connected_at:.3f} '
            f'last_send_age={now - self.last_send_at:.3f} '
            f'last_event_type={self.last_event_type} '
            f'last_text_event_type={self.last_text_event_type} '
            f'tx_text={self.text_count} '
            f'tx_binary={self.binary_count} '
            f'tx_binary_bytes={self.binary_bytes} '
            f'tts_started={self.tts_started} '
            f'tts_done={self.tts_done} '
            f'agent_done={self.agent_done}'
        )
