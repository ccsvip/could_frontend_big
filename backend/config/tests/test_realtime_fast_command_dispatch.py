from __future__ import annotations

from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase

from apps.resources.models import CommandGroup, ControlCommand, ControlCommandRecognitionPolicy
from apps.resources.services.command_executor import ExecutionResult
from apps.tenants.models import Tenant


def _run(coro):
    return async_to_sync(lambda: coro)()


class CommandDispatchPolicyTests(TestCase):
    def test_borderline_control_match_uses_llm_confirmation_and_keeps_configured_reply(self):
        tenant = Tenant.objects.create(name='命令策略公司', code='command-policy')
        group = CommandGroup.objects.create(
            tenant=tenant,
            name='控制指令',
            group_type=CommandGroup.TYPE_CONTROL,
        )
        command = ControlCommand.objects.create(
            tenant=tenant,
            group=group,
            name='播放杨荣亮视频',
            command_code='play_yang_video',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            backend_send_enabled=True,
            host='192.168.0.145',
            port=7414,
            execution_reply='正在播放杨荣亮视频。',
            reply_strategy=ControlCommand.REPLY_STRATEGY_FIXED,
            is_active=True,
        )
        ControlCommandRecognitionPolicy.objects.create(
            tenant=tenant,
            direct_execution_threshold='0.99',
            llm_confirmation_threshold='0.70',
        )

        from apps.resources.services.command_dispatch import try_dispatch_command

        async def fake_tool_stream(**kwargs):
            yield {
                'type': 'tool_calls',
                'tool_calls': [{
                    'id': 'call-1',
                    'type': 'function',
                    'function': {'name': 'play_yang_video', 'arguments': '{}'},
                }],
            }

        with (
            patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_tool_stream),
            patch(
                'apps.resources.services.command_executor.execute_control_command',
                new=AsyncMock(return_value=ExecutionResult(True, '指令已下发', 10, 'play_yang_video')),
            ),
        ):
            outcome = _run(try_dispatch_command(
                session={
                    'tenantId': tenant.id,
                    'modelConfig': {'name': 'test', 'apiBaseUrl': 'https://llm.example/v1', 'apiKey': 'secret'},
                    'messages': [],
                    'temperature': 0.3,
                    'maxTokens': 500,
                },
                question_text='请播放杨荣亮视频',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertTrue(outcome.hit)
        self.assertEqual(outcome.route, 'llm_confirmation')
        self.assertEqual(outcome.reply_text, '正在播放杨荣亮视频。')
        self.assertEqual(outcome.matched_command_metas, [{
            'kind': 'control',
            'id': command.id,
            'commandCode': 'play_yang_video',
            'name': '播放杨荣亮视频',
            'protocol': 'UDP',
            'host': '192.168.0.145',
            'port': 7414,
            'commandValueType': 'string',
            'backendSendEnabled': True,
            'executionReply': '正在播放杨荣亮视频。',
            'replyStrategy': 'fixed',
        }])
