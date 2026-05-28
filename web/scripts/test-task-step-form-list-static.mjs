import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

const component = read('../src/views/command-management/task-step-form-list.tsx');
const workspace = read('../src/views/command-management/workspace.tsx');
const tasks = read('../src/views/command-management/tasks.tsx');
const styles = read('../src/styles/index.css');

const checks = [
  {
    name: '共享子任务表单声明 5000 字文本上限',
    ok: component.includes('TEXT_TASK_MAX_LENGTH = 5000'),
  },
  {
    name: '文本子任务输入启用 5000 字 maxLength',
    ok: /<Input\.TextArea[\s\S]*maxLength=\{TEXT_TASK_MAX_LENGTH\}/.test(component),
  },
  {
    name: '文本子任务输入展示字数统计',
    ok: /<Input\.TextArea[\s\S]*showCount/.test(component),
  },
  {
    name: '子任务卡片有 hover 样式类',
    ok: component.includes('task-step-card--interactive'),
  },
  {
    name: '子任务卡片支持拖拽开始事件',
    ok: component.includes('onDragStart'),
  },
  {
    name: '子任务卡片支持拖拽放置事件',
    ok: component.includes('onDrop'),
  },
  {
    name: '长列表拖拽时支持边缘自动滚动',
    ok: component.includes('DRAG_AUTO_SCROLL_EDGE_SIZE') && component.includes('requestAnimationFrame(runDragAutoScroll)'),
  },
  {
    name: '拖拽结束会停止边缘自动滚动',
    ok: component.includes('stopDragAutoScroll') && component.includes('window.cancelAnimationFrame'),
  },
  {
    name: '任务指令弹窗提供内部滚动容器',
    ok: component.includes('taskCommandModalBodyStyle') && component.includes('overflowY') && workspace.includes('styles={{ body: taskCommandModalBodyStyle }}'),
  },
  {
    name: '任务指令弹窗提供粗绿色滚动条样式',
    ok: styles.includes('.task-command-modal .ant-modal-body::-webkit-scrollbar') && styles.includes('background: #0f766e'),
  },
  {
    name: '子任务卡片区分上方和下方插入位置',
    ok: component.includes("type DropPosition = 'before' | 'after'") && component.includes('event.clientY < rect.top + rect.height / 2'),
  },
  {
    name: '子任务卡片提供脉冲插入线样式',
    ok: styles.includes('task-step-card--drop-before::before') && styles.includes('task-step-drop-pulse'),
  },
  {
    name: '子任务卡片提供抓手鼠标样式',
    ok: component.includes('cursor-grab'),
  },
  {
    name: '子任务卡片支持按序号插入移动',
    ok: component.includes('getMoveIndexAfterOrder') && component.includes('插到第') && component.includes('InsertRowBelowOutlined'),
  },
  {
    name: '指令工作台复用共享子任务表单',
    ok: workspace.includes('<TaskStepFormList'),
  },
  {
    name: '任务指令页复用共享子任务表单',
    ok: tasks.includes('<TaskStepFormList'),
  },
  {
    name: '任务指令弹窗关闭后再重置表单，避免关闭动画闪烁',
    ok: workspace.includes('afterOpenChange') && workspace.includes('cleanupTaskModal') && tasks.includes('afterOpenChange') && tasks.includes('cleanupFormModal'),
  },
  {
    name: '导航子任务支持配置子子任务列表',
    ok: component.includes("name={[field.name, 'innerTasks']}") && component.includes('子子任务列表'),
  },
  {
    name: '子子任务类型选项排除导航指令',
    ok: component.includes("taskTypeOptions.filter((option) => option.value !== 'navigation')") && component.includes('allowNavigation={false}'),
  },
  {
    name: '任务步骤 payload 包含导航子任务 innerTasks',
    ok: component.includes('payload.innerTasks = (step.innerTasks ?? []).map(buildStepPayload)'),
  },
  {
    name: '导航子任务提供等待子子任务完成选项',
    ok: component.includes('waitForInnerTasks') && component.includes('等待子子任务完成') && component.includes('checkedChildren="等待"'),
  },
];

const failures = checks.filter((check) => !check.ok);

if (failures.length > 0) {
  console.error(`子任务表单静态检查失败：${failures.length}/${checks.length}`);
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log(`子任务表单静态检查通过：${checks.length}/${checks.length}`);
