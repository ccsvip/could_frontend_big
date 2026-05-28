const { buildCommandGroupExportPayload } = await import('../src/views/command-management/command-export-format.ts');

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const assertKeys = (value, expected, message) => {
  assert(JSON.stringify(Object.keys(value)) === JSON.stringify(expected), message);
};

const group = {
  id: 7,
  name: '中控指令',
  groupType: 'control',
  groupTypeLabel: '控制指令',
  exportEnabled: true,
  isActive: true,
  created_at: '2026-05-04T07:39:10Z',
  updated_at: '2026-05-04T07:39:10Z',
};

const controlCommands = [
  {
    id: 10,
    groupId: 7,
    groupName: '中控指令',
    name: '开灯',
    command: 'open_light',
    ip: '127.0.0.1',
    port: 9000,
    callMethod: 'UDP',
    isActive: true,
    created_at: '2026-05-04T07:39:10Z',
    updated_at: '2026-05-04T07:39:10Z',
  },
  {
    id: 11,
    groupId: 8,
    groupName: '其他指令',
    name: '关灯',
    command: 'close_light',
    ip: '127.0.0.1',
    port: 9000,
    callMethod: 'UDP',
    isActive: true,
    created_at: '2026-05-04T07:39:10Z',
    updated_at: '2026-05-04T07:39:10Z',
  },
];

const payload = buildCommandGroupExportPayload(group, controlCommands, []);
const [toolSet] = payload;
const [tool] = toolSet.tools;

assert(payload.length === 1, '必须只导出当前指令管理分组');
assert(toolSet.tool_set_name === '中控指令', 'tool_set_name 必须来自当前指令管理名称');
assert(toolSet.tools.length === 1, '必须只导出当前分组下的指令');
assertKeys(toolSet, ['tool_set_name', 'tools'], '分组层字段必须严格匹配 base.json');
assertKeys(tool, ['tool_definition', 'response_type', 'usage_examples'], '工具层字段必须严格匹配 base.json');
assertKeys(tool.tool_definition, ['name', 'description', 'parameters'], 'tool_definition 字段必须严格匹配 base.json');
assertKeys(tool.tool_definition.parameters, ['type', 'properties'], 'parameters 字段必须严格匹配 base.json');
assertKeys(tool.tool_definition.parameters.properties, ['title', 'content'], 'properties 字段必须严格匹配 base.json');
assertKeys(tool.usage_examples[0], ['text', 'tool_call'], 'usage_examples 字段必须严格匹配 base.json');
assertKeys(tool.usage_examples[0].tool_call, ['arguments'], 'tool_call 字段必须严格匹配 base.json');
assertKeys(tool.usage_examples[0].tool_call.arguments, ['title', 'content'], 'arguments 字段必须严格匹配 base.json');
assert(tool.tool_definition.name === 'open_light', 'tool_definition.name 必须使用对应指令名称变量 command');
assert(tool.tool_definition.description === '开灯', 'description 必须使用对应指令显示名称');
assert(tool.response_type === 'ON_EXECUTION_RESULT', 'response_type 必须匹配 base.json');
assert(tool.usage_examples[0].text === '请执行开灯', 'usage_examples.text 必须按指令生成');
assert(tool.usage_examples[0].tool_call.arguments.title === '开灯', 'title 参数必须按指令生成');
assert(tool.usage_examples[0].tool_call.arguments.content === '开灯', 'content 参数必须按指令生成');
