import asyncio
from unittest.mock import patch, AsyncMock

from asgiref.sync import async_to_sync
from django.test import TestCase

from apps.resources.models import CommandGroup, ControlCommand, ControlCommandRecognitionPolicy, TaskCommand, TaskCommandStep
from apps.tenants.models import Tenant


def _run(coro):
    return async_to_sync(lambda: coro)()


class CommandDispatchTests(TestCase):
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
            backend_send_enabled=True,
            host='127.0.0.1',
            port=9000,
            is_active=True,
            tenant=self.tenant,
        )
        self.session = {
            'tenantId': self.tenant.id,
            'modelConfig': {
                'name': 'qwen',
                'apiBaseUrl': 'http://localhost/v1',
                'apiKey': 'key',
                'enableWebSearch': False,
            },
            'messages': [{'role': 'system', 'content': '你是助手'}],
            'temperature': 0.3,
            'maxTokens': 500,
        }

    def _make_tool_call_event(self, name, arguments='{}', call_id='call_1'):
        return {
            'type': 'tool_calls',
            'tool_calls': [
                {
                    'id': call_id,
                    'type': 'function',
                    'function': {'name': name, 'arguments': arguments},
                }
            ],
        }

    def _make_delta_event(self, text):
        return {'type': 'delta', 'text': text}

    def _make_done_event(self):
        return {'type': 'done'}

    def test_build_command_dispatch_snapshots_returns_control_runtime_snapshot(self):
        from apps.resources.services.command_dispatch import build_command_dispatch_snapshots

        result = _run(build_command_dispatch_snapshots(
            tenant_id=self.tenant.id,
            command_metas=[{'kind': 'control', 'id': self.cmd.id}],
        ))

        self.assertEqual(
            result,
            [{
                'commandType': 'control',
                'name': self.cmd.name,
                'command': 'open_light',
                'commandValueType': ControlCommand.COMMAND_VALUE_TYPE_STRING,
                'callMethod': ControlCommand.PROTOCOL_UDP,
                'backendSendEnabled': True,
                'ip': '127.0.0.1',
                'port': 9000,
            }],
        )

    def test_build_command_dispatch_snapshots_returns_complete_task_runtime_snapshot(self):
        from apps.resources.services.command_dispatch import build_command_dispatch_snapshots

        task_group = CommandGroup.objects.create(
            name='任务组',
            group_type=CommandGroup.TYPE_TASK,
            tenant=self.tenant,
        )
        task = TaskCommand.objects.create(
            group=task_group,
            name='播放欢迎词',
            command_code='play_welcome',
            tenant=self.tenant,
            is_active=True,
        )
        TaskCommandStep.objects.create(
            task_command=task,
            order=1,
            task_type=TaskCommandStep.TYPE_TEXT,
            text_content='欢迎来到展厅',
        )

        result = _run(build_command_dispatch_snapshots(
            tenant_id=self.tenant.id,
            command_metas=[{'kind': 'task', 'id': task.id}],
        ))

        self.assertEqual(
            result,
            [{
                'commandType': 'task',
                'name': '播放欢迎词',
                'command': 'play_welcome',
                'tasks': [
                    {
                        'order': 1,
                        'type': 'text',
                        'delaySeconds': 0,
                        'content': {'text': '欢迎来到展厅'},
                    },
                ],
                'command_list': [],
            }],
        )

    def test_returns_none_when_no_commands(self):
        empty_tenant = Tenant.objects.create(name='空公司', code='empty')
        from apps.resources.services.command_dispatch import try_dispatch_command

        session = {**self.session, 'tenantId': empty_tenant.id}
        result = _run(try_dispatch_command(
            session=session,
            question_text='开灯',
            on_delta=None,
            on_tts_segment=None,
        ))
        self.assertIsNone(result)

    def test_low_score_control_text_returns_ordinary_conversation_diagnostics(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        async def fake_stream(**kwargs):
            yield self._make_delta_event('你好')
            yield self._make_done_event()

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_stream):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='你好',
                on_delta=None,
                on_tts_segment=None,
            ))
        self.assertIsNotNone(result)
        self.assertFalse(result.hit)
        self.assertEqual(result.route, 'ordinary_conversation')
        self.assertEqual(result.execution_outcome, 'not_executed')

    def test_dispatches_command_and_generates_natural_reply(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        self.cmd.reply_strategy = ControlCommand.REPLY_STRATEGY_GENERATED
        self.cmd.save(update_fields=['reply_strategy'])

        first_round_events = [
            self._make_tool_call_event('open_light', '{"title": "开灯", "content": "开灯"}'),
            self._make_done_event(),
        ]

        async def fake_tool_stream(**kwargs):
            for event in first_round_events:
                yield event

        async def fake_chat_stream(**kwargs):
            yield '已为您打开客厅的灯'
            yield ''

        deltas = []
        tts_segments = []

        async def on_delta(text):
            deltas.append(text)

        async def on_tts(text):
            tts_segments.append(text)

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_tool_stream), \
             patch('apps.ai_models.llm_services.stream_llm_chat_completion', new=fake_chat_stream), \
             patch('apps.resources.services.command_executor.execute_control_command', new=AsyncMock(return_value=__import__('apps.resources.services.command_executor', fromlist=['ExecutionResult']).ExecutionResult(True, '指令已下发', 50, 'open_light'))):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=on_delta,
                on_tts_segment=on_tts,
            ))

        self.assertIsNotNone(result)
        self.assertTrue(result.hit)
        self.assertEqual(result.reply_source, 'generated')
        self.assertIn('已为您打开客厅的灯', result.reply_text)
        self.assertEqual(len(result.tool_calls_summary), 1)
        self.assertTrue(result.tool_calls_summary[0]['success'])
        self.assertIn('已为您打开客厅的灯', ''.join(deltas))

    def test_limited_tool_selection_uses_control_command_custom_reply_without_second_generation(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        self.cmd.execution_reply = '客厅灯已打开。'
        self.cmd.save(update_fields=['execution_reply'])

        async def fake_tool_stream(**kwargs):
            yield self._make_tool_call_event('open_light')
            yield self._make_done_event()

        with (
            patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_tool_stream),
            patch('apps.ai_models.llm_services.stream_llm_chat_completion') as natural_reply_stream,
            patch(
                'apps.resources.services.command_executor.execute_control_command',
                new=AsyncMock(
                    return_value=__import__(
                        'apps.resources.services.command_executor', fromlist=['ExecutionResult'],
                    ).ExecutionResult(True, '指令已下发', 50, 'open_light'),
                ),
            ),
        ):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertEqual(result.reply_text, '客厅灯已打开。')
        self.assertEqual(result.reply_source, 'custom')
        natural_reply_stream.assert_not_called()

    def test_tool_selection_sends_only_matching_company_candidates(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        ControlCommand.objects.create(
            group=self.group,
            name='打开空调',
            command_code='open_ac',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='127.0.0.1',
            port=9001,
            is_active=True,
            tenant=self.tenant,
        )
        candidate_sets = []

        async def fake_tool_stream(**kwargs):
            candidate_sets.append(kwargs['tools'])
            yield self._make_tool_call_event('open_light')
            yield self._make_done_event()

        async def fake_chat_stream(**kwargs):
            yield '已为您打开客厅的灯'

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_tool_stream), \
             patch('apps.ai_models.llm_services.stream_llm_chat_completion', new=fake_chat_stream), \
             patch('apps.resources.services.command_executor.execute_control_command', new=AsyncMock(return_value=__import__('apps.resources.services.command_executor', fromlist=['ExecutionResult']).ExecutionResult(True, '指令已下发', 50, 'open_light'))):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertEqual(result.mode, 'tool')
        self.assertEqual(len(candidate_sets), 1)
        self.assertEqual([tool['function']['name'] for tool in candidate_sets[0]], ['open_light'])

    def test_dispatches_exact_local_command_without_model_config(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        session = {**self.session, 'modelConfig': None}
        with patch('apps.resources.services.command_executor._send_udp', new=AsyncMock(return_value=None)):
            result = _run(try_dispatch_command(
                session=session,
                question_text='开灯',
                on_delta=None,
                on_tts_segment=None,
            ))
        self.assertIsNotNone(result)
        self.assertEqual(result.mode, 'local')
        self.assertEqual(result.reply_text, '已执行：开灯。')

    def test_fixed_reply_uses_current_company_policy(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        ControlCommandRecognitionPolicy.objects.create(
            tenant=self.tenant,
            fixed_execution_reply='好的，已为您执行。',
        )

        with patch('apps.resources.services.command_executor._send_udp', new=AsyncMock(return_value=None)):
            result = _run(try_dispatch_command(
                session={**self.session, 'modelConfig': None},
                question_text='开灯',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertEqual(result.reply_text, '好的，已为您执行。')
        self.assertEqual(result.reply_source, 'fixed')

    def test_disabled_backend_send_skips_tcp_and_keeps_configured_reply(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        self.cmd.backend_send_enabled = False
        self.cmd.protocol = ControlCommand.PROTOCOL_TCP
        self.cmd.execution_reply = '客厅灯已打开。'
        self.cmd.save(update_fields=['backend_send_enabled', 'protocol', 'execution_reply'])
        deltas = []
        tts_segments = []

        async def on_delta(text):
            deltas.append(text)

        async def on_tts(text):
            tts_segments.append(text)

        with patch(
            'apps.resources.services.command_executor.execute_control_command',
            new=AsyncMock(),
        ) as execute_command:
            result = _run(try_dispatch_command(
                session={**self.session, 'modelConfig': None},
                question_text='开灯',
                on_delta=on_delta,
                on_tts_segment=on_tts,
            ))

        self.assertIsNotNone(result)
        self.assertTrue(result.hit)
        self.assertEqual(result.reply_text, '客厅灯已打开。')
        self.assertEqual(result.reply_source, 'custom')
        self.assertEqual(result.tool_calls_summary[0]['message'], '指令已触发')
        self.assertEqual(deltas, ['客厅灯已打开。'])
        self.assertEqual(tts_segments, ['客厅灯已打开。'])
        execute_command.assert_not_awaited()

    def test_disabled_backend_send_does_not_expose_delivery_status_to_generated_reply(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        self.cmd.backend_send_enabled = False
        self.cmd.protocol = ControlCommand.PROTOCOL_TCP
        self.cmd.execution_reply = ''
        self.cmd.reply_strategy = ControlCommand.REPLY_STRATEGY_GENERATED
        self.cmd.save(update_fields=['backend_send_enabled', 'protocol', 'execution_reply', 'reply_strategy'])
        generated_messages = []

        async def fake_chat_stream(**kwargs):
            generated_messages.extend(kwargs['messages'])
            yield '客厅灯已打开。'

        with (
            patch('apps.ai_models.llm_services.stream_llm_chat_completion', new=fake_chat_stream),
            patch(
                'apps.resources.services.command_executor.execute_control_command',
                new=AsyncMock(),
            ) as execute_command,
        ):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='开灯',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertEqual(result.reply_text, '客厅灯已打开。')
        self.assertEqual(result.reply_source, 'generated')
        generated_prompt = generated_messages[0]['content']
        self.assertNotIn('前端发送', generated_prompt)
        self.assertNotIn('后端未下发', generated_prompt)
        execute_command.assert_not_awaited()

    def test_generated_local_command_without_model_config_falls_back_to_fixed_reply(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        self.cmd.reply_strategy = ControlCommand.REPLY_STRATEGY_GENERATED
        self.cmd.save(update_fields=['reply_strategy'])
        session = {**self.session, 'modelConfig': None}

        with patch('apps.resources.services.command_executor._send_udp', new=AsyncMock(return_value=None)):
            result = _run(try_dispatch_command(
                session=session,
                question_text='开灯',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertEqual(result.reply_text, '已执行：开灯。')
        self.assertEqual(result.reply_source, 'generated_fallback')

    def test_returns_dispatch_failure_when_limited_tool_selection_raises(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        async def failing_stream(**kwargs):
            raise RuntimeError('upstream error')
            yield  # noqa: unreachable

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=failing_stream):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=None,
                on_tts_segment=None,
            ))
        self.assertIsNotNone(result)
        self.assertTrue(result.hit)
        self.assertEqual(result.mode, 'selection_failed')
        self.assertEqual(result.reply_text, '指令识别服务暂时不可用，请稍后重试。')

    def test_unconfirmed_control_candidate_returns_repeat_prompt_without_execution(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        async def no_tool_stream(**kwargs):
            yield self._make_done_event()

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=no_tool_stream):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=None,
                on_tts_segment=None,
            ))

        self.assertIsNotNone(result)
        self.assertTrue(result.hit)
        self.assertEqual(result.mode, 'selection_failed')
        self.assertEqual(result.confirmation_outcome, 'not_selected')
        self.assertEqual(result.execution_outcome, 'not_executed')
        self.assertEqual(result.reply_text, '我没有确认要执行的控制指令，请再说一次。')

    def test_unknown_control_tool_selection_is_rejected_without_execution(self):
        from apps.resources.services.command_dispatch import try_dispatch_command

        async def fake_tool_stream(**kwargs):
            yield self._make_tool_call_event('nonexistent_cmd', '{}', 'call_x')
            yield self._make_done_event()

        with patch('apps.ai_models.llm_services.stream_llm_chat_completion_with_tools', new=fake_tool_stream):
            result = _run(try_dispatch_command(
                session=self.session,
                question_text='请帮我把灯打开',
                on_delta=None,
                on_tts_segment=None,
            ))
        self.assertIsNotNone(result)
        self.assertTrue(result.hit)
        self.assertEqual(result.mode, 'selection_failed')
        self.assertEqual(result.route, 'llm_confirmation')
        self.assertEqual(result.confirmation_outcome, 'not_selected')
        self.assertEqual(result.execution_outcome, 'not_executed')
        self.assertEqual(result.tool_calls_summary, [])

    def test_tenant_isolation(self):
        other_tenant = Tenant.objects.create(name='公司B', code='company-b')
        other_group = CommandGroup.objects.create(
            name='卧室',
            group_type=CommandGroup.TYPE_CONTROL,
            tenant=other_tenant,
        )
        ControlCommand.objects.create(
            group=other_group,
            name='空调',
            command_code='ac_on',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='10.0.0.1',
            port=9001,
            is_active=True,
            tenant=other_tenant,
        )
        from apps.resources.services.command_tools import build_command_tools

        tools_a = build_command_tools(self.tenant.id)
        tools_b = build_command_tools(other_tenant.id)
        names_a = [t['function']['name'] for t in tools_a]
        names_b = [t['function']['name'] for t in tools_b]
        self.assertIn('open_light', names_a)
        self.assertNotIn('ac_on', names_a)
        self.assertIn('ac_on', names_b)
        self.assertNotIn('open_light', names_b)
