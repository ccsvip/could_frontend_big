from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from apps.resources.models import ControlCommand

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
TCP_READ_BACK_TIMEOUT_SECONDS = 3.0


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    message: str
    latency_ms: int
    payload: str
    response: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'latencyMs': self.latency_ms,
            'payload': self.payload,
            'response': self.response,
        }


def encode_payload(command_code: str, value_type: str) -> bytes:
    raw = command_code or ''
    value_type = (value_type or '').lower()
    if value_type == 'hex':
        try:
            return bytes.fromhex(raw.replace(' ', ''))
        except ValueError as exc:
            raise ValueError(f'指令 {raw!r} 不是有效 hex 编码') from exc
    if value_type == 'ascii':
        return raw.encode('ascii', errors='replace')
    return raw.encode('utf-8')


async def execute_control_command(
    cmd: ControlCommand,
    arguments: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Asynchronously dispatch a control command over UDP/TCP and return the result."""
    arguments = arguments or {}
    payload_bytes = _build_payload_bytes(cmd, arguments)
    started = time.perf_counter()
    protocol = (cmd.protocol or ControlCommand.PROTOCOL_UDP).upper()
    try:
        if protocol == ControlCommand.PROTOCOL_TCP:
            response = await _send_tcp(cmd.host, cmd.port, payload_bytes, timeout)
        else:
            response = await _send_udp(cmd.host, cmd.port, payload_bytes, timeout)
    except asyncio.TimeoutError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            'command_executor.timeout command=%s host=%s port=%s protocol=%s latency_ms=%s',
            cmd.command_code, cmd.host, cmd.port, protocol, latency_ms,
        )
        return ExecutionResult(
            success=False,
            message=f'指令下发超时（{protocol}）',
            latency_ms=latency_ms,
            payload=cmd.command_code,
        )
    except OSError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            'command_executor.send_failed command=%s host=%s port=%s protocol=%s error=%s',
            cmd.command_code, cmd.host, cmd.port, protocol, exc,
        )
        return ExecutionResult(
            success=False,
            message=f'指令下发失败：{exc}',
            latency_ms=latency_ms,
            payload=cmd.command_code,
        )
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        'command_executor.dispatched command=%s host=%s port=%s protocol=%s latency_ms=%s',
        cmd.command_code, cmd.host, cmd.port, protocol, latency_ms,
    )
    return ExecutionResult(
        success=True,
        message='指令已下发',
        latency_ms=latency_ms,
        payload=cmd.command_code,
        response=response,
    )


def _build_payload_bytes(cmd: ControlCommand, arguments: dict[str, Any]) -> bytes:
    content = str(arguments.get('content') or arguments.get('title') or '').strip()
    code = content if content else (cmd.command_code or '')
    return encode_payload(code, cmd.command_value_type)


async def _send_udp(host: str, port: int, payload: bytes, timeout: float) -> str | None:
    loop = asyncio.get_running_loop()
    transport, _ = await asyncio.wait_for(
        loop.create_datagram_endpoint(_NoopProtocol, remote_addr=(host, port)),
        timeout=timeout,
    )
    try:
        transport.sendto(payload)
        return None
    finally:
        transport.close()


async def _send_tcp(host: str, port: int, payload: bytes, timeout: float) -> str | None:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port),
        timeout=timeout,
    )
    try:
        writer.write(payload)
        await writer.drain()
        try:
            response = await asyncio.wait_for(reader.read(4096), timeout=TCP_READ_BACK_TIMEOUT_SECONDS)
            return response.decode('utf-8', errors='replace') or None
        except asyncio.TimeoutError:
            return None
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError):
            pass


class _NoopProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):  # noqa: ANN001
        self.transport = transport

    def error_received(self, exc):  # noqa: ANN001
        logger.warning('command_executor.udp_error_received error=%s', exc)
