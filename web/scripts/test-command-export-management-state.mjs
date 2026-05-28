const {
  collectCommandGroupPages,
  getCommandGroupExportActionState,
} = await import('../src/views/command-management/command-export-state.ts');

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const allowedGroup = {
  id: 1,
  name: '允许导出分组',
  groupType: 'control',
  groupTypeLabel: '控制指令',
  exportEnabled: true,
  isActive: true,
  created_at: '2026-05-04T07:39:10Z',
  updated_at: '2026-05-04T07:39:10Z',
};

const forbiddenGroup = {
  ...allowedGroup,
  id: 2,
  name: '禁止导出分组',
  exportEnabled: false,
};

const requestedPages = [];
const groups = await collectCommandGroupPages(async (page) => {
  requestedPages.push(page);
  if (page === 1) return { next: '/api/v1/commands/groups/?page=2', results: [allowedGroup] };
  if (page === 2) return { next: null, results: [forbiddenGroup] };
  throw new Error(`不应该请求第 ${page} 页`);
});

assert(requestedPages.join(',') === '1,2', '导出管理必须逐页收集全部指令管理分组');
assert(groups.length === 2, '导出管理列表必须展示允许和禁止导出的分组');
assert(groups[1].name === '禁止导出分组', '禁止导出的分组不能从导出管理列表中过滤掉');

const enabledAction = getCommandGroupExportActionState({ group: allowedGroup, downloading: false });
assert(enabledAction.disabled === false, '允许导出的分组应可点击导出指令');
assert(enabledAction.disabledReason === undefined, '允许导出的分组不需要禁用原因');

const forbiddenAction = getCommandGroupExportActionState({ group: forbiddenGroup, downloading: false });
assert(forbiddenAction.disabled === true, '禁止导出的分组仍显示导出指令按钮，但按钮必须置灰');
assert(forbiddenAction.disabledReason === '该指令管理已禁止导出', '禁止导出时应给出禁用原因');

const downloadingAction = getCommandGroupExportActionState({ group: allowedGroup, downloading: true });
assert(downloadingAction.disabled === true, '下载中应禁用其他导出指令按钮');
