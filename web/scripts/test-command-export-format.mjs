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
assertKeys(toolSet, ['tool_set_name', 'tools'], '分组层字段必须严格匹配 OpenAI tool 导出格式');
assertKeys(tool, ['type', 'function'], '工具层字段必须严格匹配 OpenAI tool 导出格式');
assert(tool.type === 'function', 'type 必须为 function');
assertKeys(tool.function, ['name', 'description', 'parameters'], 'function 字段必须严格匹配 OpenAI tool 导出格式');
assert(tool.function.name === 'open_light', 'function.name 必须使用对应指令名称变量 command');
assert(tool.function.description === '开灯', 'description 必须使用对应指令显示名称');
assertKeys(tool.function.parameters, ['type', 'properties'], 'parameters 字段必须严格匹配 OpenAI tool 导出格式');
assert(tool.function.parameters.type === 'object', 'parameters.type 必须为 object');
assertKeys(tool.function.parameters.properties, ['title', 'content'], 'properties 字段必须严格匹配 OpenAI tool 导出格式');
assert(tool.function.parameters.properties.title.type === 'string', 'title.type 必须为 string');
assert(tool.function.parameters.properties.title.description === '开灯', 'title.description 必须使用对应指令显示名称');
assert(tool.function.parameters.properties.content.type === 'string', 'content.type 必须为 string');
assert(tool.function.parameters.properties.content.description === '开灯', 'content.description 必须使用对应指令显示名称');
