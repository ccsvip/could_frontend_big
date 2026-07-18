from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_models.models import AgentApplication, LLMModel, LLMProvider, TenantLLMModelGrant
from apps.devices.models import Device, DeviceApplication, DeviceChatLog
from apps.resources.models import CommandGroup, ControlCommand
from apps.resources.services.command_executor import ExecutionResult
from apps.tenants.test_utils import TenantTestMixin

User = get_user_model()


class RealtimeCommandDispatchTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='command-dispatch-user', password='test123456')
        self.setup_tenant(self.user)
        provider = LLMProvider.objects.create(
            name='Dispatch LLM Provider',
            provider_type='openai',
            api_base_url='https://llm.example/v1',
            api_key='secret',
            is_active=True,
        )
        model = LLMModel.objects.create(provider=provider, name='dispatch-model', is_active=True)
        TenantLLMModelGrant.objects.create(tenant=self.tenant, model=model, is_active=True)
        agent_application = AgentApplication.objects.create(
            tenant=self.tenant,
            name='Dispatch Agent',
            llm_model=model,
            system_prompt='你是设备助手。',
        )
        device_application = DeviceApplication.objects.create(
            tenant=self.tenant,
            name='Dispatch App',
            code='dispatch-app',
            agent_application=agent_application,
        )
        Device.objects.create(
            tenant=self.tenant,
            application=device_application,
            name='Dispatch Device',
            code='ANDROID-DISPATCH-001',
            authorization_type=Device.AUTHORIZATION_PERMANENT,
        )
        group = CommandGroup.objects.create(
            name='客厅',
            group_type=CommandGroup.TYPE_CONTROL,
            tenant=self.tenant,
        )
        self.command = ControlCommand.objects.create(
            group=group,
            name='开灯',
            command_code='open_light',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            backend_send_enabled=True,
            host='127.0.0.1',
            port=9000,
            execution_reply='客厅灯已打开。',
            reply_strategy=ControlCommand.REPLY_STRATEGY_FIXED,
            is_active=True,
            tenant=self.tenant,
        )

    async def _open_communicator(self):
        from config.asgi import application

        communicator = ApplicationCommunicator(
            application,
            {
                'type': 'websocket',
                'path': '/ws/realtime/',
                'query_string': b'',
                'headers': [],
            },
        )
        await communicator.send_input({'type': 'websocket.connect'})
        self.assertEqual((await communicator.receive_output(timeout=1))['type'], 'websocket.accept')
        return communicator

    async def _send_question(self, communicator, *, command_id: str, text: str, event_type: str = 'llm.session.start'):
        await communicator.send_input({
            'type': 'websocket.receive',
            'text': json.dumps({
                'type': event_type,
                'id': command_id,
                'payload': {
                    'deviceCode': 'ANDROID-DISPATCH-001',
                    'text': text,
                    'requestId': f'req-{command_id}',
                    'traceId': f'trace-{command_id}',
                },
            }),
        })

    def test_llm_session_keeps_configured_reply_and_returns_complete_command(self):
        async def run_websocket():
            communicator = await self._open_communicator()

            async def unexpected_upstream_call(**kwargs):
                raise AssertionError('高置信度固定回复不应调用上游 LLM')
                yield  # pragma: no cover

            with (
                patch('apps.ai_models.llm_services.stream_llm_chat_completion', new=unexpected_upstream_call),
                patch(
                    'apps.resources.services.command_executor.execute_control_command',
                    new=AsyncMock(return_value=ExecutionResult(True, '指令已下发', 12, 'open_light')),
                ) as execute_command,
            ):
                await self._send_question(communicator, command_id='dispatch-match', text='open_light')
                events = []
                for _ in range(6):
                    event = json.loads((await communicator.receive_output(timeout=1))['text'])
                    events.append(event)
                    if event['type'] == 'llm.done':
                        break

                done = events[-1]
                self.assertEqual(done['type'], 'llm.done')
                self.assertEqual(done['payload']['answerText'], '客厅灯已打开。')
                dispatch = done['payload']['commandDispatch']
                self.assertTrue(dispatch['hit'])
                self.assertEqual(dispatch['replySource'], 'custom')
                self.assertEqual(dispatch['toolCalls'][0]['name'], 'open_light')
                self.assertEqual(dispatch['commands'], [{
                    'commandType': 'control',
                    'name': '开灯',
                    'command': 'open_light',
                    'commandValueType': 'string',
                    'callMethod': 'UDP',
                    'backendSendEnabled': True,
                    'ip': '127.0.0.1',
                    'port': 9000,
                }])
                self.assertIn('客厅灯已打开。', ''.join(
                    event['payload']['text'] for event in events if event['type'] == 'llm.delta'
                ))
                self.assertIn('llm.tts_segment', [event['type'] for event in events])
                execute_command.assert_awaited_once()

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
        log = DeviceChatLog.objects.get(code='ANDROID-DISPATCH-001')
        self.assertEqual(log.answer_text, '客厅灯已打开。')

    def test_third_party_session_dispatches_command_before_calling_chatbot(self):
        Provider = apps.get_model('ai_models', 'ThirdPartyChatbotProvider')
        Chatbot = apps.get_model('ai_models', 'ThirdPartyChatbotApplication')
        Grant = apps.get_model('ai_models', 'TenantThirdPartyChatbotGrant')
        Integration = apps.get_model('ai_models', 'ThirdPartyChatbotIntegration')
        provider = Provider.objects.create(
            name='Third-party Dispatch Provider',
            provider_type='configured_api_chatbot',
            api_base_url='https://chatbot.example/api',
            api_key='secret',
            is_active=True,
        )
        chatbot = Chatbot.objects.create(
            provider=provider,
            name='Third-party Dispatch Chatbot',
            external_application_id='dispatch-chatbot',
            is_active=True,
        )
        Grant.objects.create(tenant=self.tenant, chatbot=chatbot, is_active=True)
        Integration.objects.create(
            scheme_type='scheme_b',
            name='Third-party Dispatch Scheme',
            provider=provider,
            chatbot=chatbot,
            config={'steps': []},
            is_active=True,
        )
        agent_application = AgentApplication.objects.get(name='Dispatch Agent')
        agent_application.runtime_backend_type = 'third_party_chatbot'
        agent_application.third_party_chatbot = chatbot
        agent_application.save(update_fields=['runtime_backend_type', 'third_party_chatbot', 'updated_at'])

        async def run_websocket():
            communicator = await self._open_communicator()

            with (
                patch(
                    'apps.resources.services.command_executor.execute_control_command',
                    new=AsyncMock(return_value=ExecutionResult(True, '指令已下发', 12, 'open_light')),
                ) as execute_command,
                patch(
                    'config.realtime.third_party_chatbots.send_chatbot_message',
                    side_effect=AssertionError('命中控制指令时不应调用第三方机器人'),
                ) as send_chatbot_message,
            ):
                await self._send_question(communicator, command_id='third-party-dispatch-match', text='open_light')
                events = []
                for _ in range(6):
                    event = json.loads((await communicator.receive_output(timeout=1))['text'])
                    events.append(event)
                    if event['type'] == 'llm.done':
                        break

                done = events[-1]
                self.assertEqual(done['type'], 'llm.done')
                self.assertEqual(done['payload']['answerText'], '客厅灯已打开。')
                self.assertTrue(done['payload']['commandDispatch']['hit'])
                self.assertEqual(done['payload']['commandDispatch']['commands'][0]['command'], 'open_light')
                execute_command.assert_awaited_once()
                send_chatbot_message.assert_not_called()

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_agent_session_keeps_dispatch_reply_and_returns_complete_command(self):
        async def run_websocket():
            communicator = await self._open_communicator()
            async def fake_agent_tts_stream(*args, **kwargs):
                return None

            with patch(
                'apps.resources.services.command_executor.execute_control_command',
                new=AsyncMock(return_value=ExecutionResult(True, '指令已下发', 12, 'open_light')),
            ), patch('config.realtime._run_agent_tts_stream', side_effect=fake_agent_tts_stream):
                await self._send_question(
                    communicator,
                    command_id='agent-command-match',
                    text='open_light',
                    event_type='agent.session.start',
                )
                events = []
                for _ in range(10):
                    message = await communicator.receive_output(timeout=1)
                    if 'text' not in message:
                        continue
                    event = json.loads(message['text'])
                    events.append(event)
                    if event['type'] == 'agent.done':
                        break

                self.assertEqual(events[0]['type'], 'agent.started')
                self.assertIn('llm.delta', [event['type'] for event in events])
                self.assertIn('llm.tts_segment', [event['type'] for event in events])
                done = next(event for event in events if event['type'] == 'llm.done')
                self.assertEqual(done['payload']['answerText'], '客厅灯已打开。')
                self.assertEqual(done['payload']['commandDispatch']['commands'][0]['command'], 'open_light')
                self.assertEqual(events[-1]['type'], 'agent.done')

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()

    def test_command_miss_falls_back_to_normal_chat(self):
        async def run_websocket():
            communicator = await self._open_communicator()
            chat_calls = []

            async def fake_chat_stream(**kwargs):
                chat_calls.append(kwargs)
                yield '你好，我是设备助手。'

            with patch('apps.ai_models.llm_services.stream_llm_chat_completion', new=fake_chat_stream):
                await self._send_question(communicator, command_id='dispatch-miss', text='你好')
                events = []
                for _ in range(6):
                    event = json.loads((await communicator.receive_output(timeout=1))['text'])
                    events.append(event)
                    if event['type'] == 'llm.done':
                        break

                done = events[-1]
                self.assertEqual(done['payload']['answerText'], '你好，我是设备助手。')
                self.assertTrue(done['payload']['commandDispatch']['commands'] == [])
                self.assertEqual(len(chat_calls), 1)

            await communicator.send_input({'type': 'websocket.disconnect', 'code': 1000})
            await communicator.wait(timeout=1)

        async_to_sync(run_websocket)()
