from django.test import TestCase

from apps.resources.models import CommandGroup, ControlCommand, TaskCommand
from apps.resources.services.command_tools import (
    build_command_tools,
    build_control_command_tool,
    build_control_command_tools,
    build_task_command_tools,
    command_index_map,
    find_tool_by_name,
    has_command_tools,
    strip_meta,
    strip_tools_meta,
)
from apps.tenants.models import Tenant


class CommandToolsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='公司A', code='company-a')
        self.other_tenant = Tenant.objects.create(name='公司B', code='company-b')
        self.group = CommandGroup.objects.create(
            name='客厅指令',
            group_type=CommandGroup.TYPE_CONTROL,
            tenant=self.tenant,
        )
        self.active_cmd = ControlCommand.objects.create(
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
        self.inactive_cmd = ControlCommand.objects.create(
            group=self.group,
            name='关灯',
            command_code='close_light',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='127.0.0.1',
            port=9000,
            is_active=False,
            tenant=self.tenant,
        )
        self.other_tenant_cmd = ControlCommand.objects.create(
            group=None,
            name='空调',
            command_code='ac_on',
            command_value_type=ControlCommand.COMMAND_VALUE_TYPE_STRING,
            protocol=ControlCommand.PROTOCOL_UDP,
            host='10.0.0.1',
            port=9001,
            is_active=True,
            tenant=self.other_tenant,
        )

    def test_build_control_command_tool_uses_openai_format(self):
        tool = build_control_command_tool(self.active_cmd)
        self.assertEqual(tool['type'], 'function')
        self.assertEqual(tool['function']['name'], 'open_light')
        self.assertEqual(tool['function']['description'], '开灯')
        params = tool['function']['parameters']
        self.assertEqual(params['type'], 'object')
        self.assertEqual(params['properties']['title']['type'], 'string')
        self.assertEqual(params['properties']['content']['description'], '开灯')
        meta = tool['_command_meta']
        self.assertEqual(meta['kind'], 'control')
        self.assertEqual(meta['commandCode'], 'open_light')
        self.assertEqual(meta['host'], '127.0.0.1')
        self.assertFalse(meta['backendSendEnabled'])

    def test_build_control_command_tools_filters_inactive_and_other_tenant(self):
        tools = build_control_command_tools(self.tenant.id)
        names = [t['function']['name'] for t in tools]
        self.assertIn('open_light', names)
        self.assertNotIn('close_light', names)
        self.assertNotIn('ac_on', names)

        self.group.is_active = False
        self.group.save(update_fields=['is_active'])

        disabled_group_names = [tool['function']['name'] for tool in build_control_command_tools(self.tenant.id)]
        self.assertNotIn('open_light', disabled_group_names)

    def test_build_command_tools_combines_control_and_task(self):
        task_group = CommandGroup.objects.create(
            name='任务组',
            group_type=CommandGroup.TYPE_TASK,
            tenant=self.tenant,
        )
        TaskCommand.objects.create(
            group=task_group,
            name='执行巡检',
            command_code='patrol',
            is_active=True,
            tenant=self.tenant,
        )
        tools = build_command_tools(self.tenant.id)
        names = [t['function']['name'] for t in tools]
        self.assertIn('open_light', names)
        self.assertIn('patrol', names)

    def test_strip_meta_removes_internal_field(self):
        tool = build_control_command_tool(self.active_cmd)
        stripped = strip_meta(tool)
        self.assertNotIn('_command_meta', stripped)
        self.assertEqual(stripped['type'], 'function')

    def test_strip_tools_meta_removes_all_internal_fields(self):
        tools = build_control_command_tools(self.tenant.id)
        stripped = strip_tools_meta(tools)
        for tool in stripped:
            self.assertNotIn('_command_meta', tool)

    def test_find_tool_by_name_returns_match(self):
        tools = build_command_tools(self.tenant.id)
        found = find_tool_by_name(tools, 'open_light')
        self.assertIsNotNone(found)
        self.assertEqual(found['_command_meta']['commandCode'], 'open_light')
        self.assertIsNone(find_tool_by_name(tools, 'nonexistent'))

    def test_command_index_map(self):
        tools = build_command_tools(self.tenant.id)
        index = command_index_map(tools)
        self.assertIn('open_light', index)

    def test_has_command_tools_respects_tenant(self):
        self.assertTrue(has_command_tools(self.tenant.id))
        self.assertFalse(has_command_tools(self.other_tenant.id + 9999))
        self.assertFalse(has_command_tools(None))

    def test_build_tools_for_none_tenant_returns_empty(self):
        self.assertEqual(build_control_command_tools(None), [])
        self.assertEqual(build_task_command_tools(None), [])
        self.assertEqual(build_command_tools(None), [])
