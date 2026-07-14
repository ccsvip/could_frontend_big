import asyncio
from unittest.mock import patch

from django.test import TestCase

from apps.resources.models import CommandGroup, ControlCommand
from apps.resources.services.command_executor import (
    ExecutionResult,
    encode_payload,
    execute_control_command,
)
from apps.tenants.models import Tenant


def _run(coro):
    return asyncio.run(coro)


class EncodePayloadTests(TestCase):
    def test_string_encoding(self):
        self.assertEqual(encode_payload('hello', 'string'), b'hello')

    def test_ascii_encoding(self):
        self.assertEqual(encode_payload('hello', 'ascii'), b'hello')

    def test_hex_encoding(self):
        self.assertEqual(encode_payload('48656c6c6f', 'hex'), b'Hello')

    def test_hex_encoding_strips_spaces(self):
        self.assertEqual(encode_payload('48 65 6c 6c 6f', 'hex'), b'Hello')

    def test_hex_encoding_invalid_raises(self):
        with self.assertRaises(ValueError):
            encode_payload('xyz', 'hex')

    def test_empty_payload(self):
        self.assertEqual(encode_payload('', 'string'), b'')

    def test_unknown_type_defaults_to_utf8(self):
        self.assertEqual(encode_payload('测试', ''), b'\xe6\xb5\x8b\xe8\xaf\x95')


class ExecuteControlCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='公司A', code='company-a')
        self.group = CommandGroup.objects.create(
            name='客厅',
            group_type=CommandGroup.TYPE_CONTROL,
            tenant=self.tenant,
        )
        self.cmd = ControlCommand.objects.create(
            group=self.group,
            name='开灯',
            command_code='open_light',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='127.0.0.1',
            port=9000,
            is_active=True,
            tenant=self.tenant,
        )
        self.tcp_cmd = ControlCommand.objects.create(
            group=self.group,
            name='查询',
            command_code='query',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_ASCII,
            protocol=ControlCommand.PROTOCOL_TCP,
            host='127.0.0.1',
            port=9001,
            is_active=True,
            tenant=self.tenant,
        )

    def test_udp_send_success(self):
        with patch('apps.resources.services.command_executor._send_udp', return_value=None) as mock_send:
            result = _run(execute_control_command(self.cmd, {'content': 'open_light'}))
        self.assertTrue(result.success)
        self.assertEqual(result.message, '指令已下发')
        self.assertEqual(result.payload, 'open_light')
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        self.assertEqual(args[0], '127.0.0.1')
        self.assertEqual(args[1], 9000)
        self.assertEqual(args[2], b'open_light')

    def test_tcp_send_success_with_response(self):
        with patch('apps.resources.services.command_executor._send_tcp', return_value='OK') as mock_send:
            result = _run(execute_control_command(self.tcp_cmd, {'content': 'query'}))
        self.assertTrue(result.success)
        self.assertEqual(result.response, 'OK')
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][2], b'query')

    def test_timeout_returns_failure(self):
        with patch('apps.resources.services.command_executor._send_udp', side_effect=asyncio.TimeoutError):
            result = _run(execute_control_command(self.cmd))
        self.assertFalse(result.success)
        self.assertIn('超时', result.message)

    def test_os_error_returns_failure(self):
        with patch('apps.resources.services.command_executor._send_udp', side_effect=OSError('refused')):
            result = _run(execute_control_command(self.cmd))
        self.assertFalse(result.success)
        self.assertIn('失败', result.message)

    def test_arguments_content_overrides_command_code(self):
        with patch('apps.resources.services.command_executor._send_udp', return_value=None) as mock_send:
            _run(execute_control_command(self.cmd, {'content': 'custom_value'}))
        self.assertEqual(mock_send.call_args[0][2], b'custom_value')

    def test_hex_command_encoded_correctly(self):
        hex_cmd = ControlCommand.objects.create(
            group=self.group,
            name='hex指令',
            command_code='AAAA',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_HEX,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='127.0.0.1',
            port=9002,
            is_active=True,
            tenant=self.tenant,
        )
        with patch('apps.resources.services.command_executor._send_udp', return_value=None) as mock_send:
            _run(execute_control_command(hex_cmd))
        self.assertEqual(mock_send.call_args[0][2], b'\xaa\xaa')

    def test_execution_result_as_dict(self):
        result = ExecutionResult(True, 'OK', 50, 'cmd', 'resp')
        data = result.as_dict()
        self.assertEqual(data['success'], True)
        self.assertEqual(data['latencyMs'], 50)
        self.assertEqual(data['response'], 'resp')
