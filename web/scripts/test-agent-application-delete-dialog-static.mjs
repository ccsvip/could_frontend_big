import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/views/application-management/index.tsx', import.meta.url), 'utf8');
const failures = [];

if (source.includes('<AlertDialog.Trigger')) {
  failures.push('agent application delete dialog: delete button must open the dialog through controlled state, not AlertDialog.Trigger');
}

if (!source.includes('deleteApplicationId === app.id')) {
  failures.push('agent application delete dialog: missing controlled open state for each application card');
}

if (!source.includes('setDeleteApplicationId(app.id)')) {
  failures.push('agent application delete dialog: delete button must set the controlled dialog state');
}

const deleteDialogStart = source.indexOf('open={deleteApplicationId === app.id}');
const deleteDialogEnd = source.indexOf('</AlertDialog.Root>', deleteDialogStart);
const deleteDialogBlock =
  deleteDialogStart >= 0 && deleteDialogEnd > deleteDialogStart
    ? source.slice(deleteDialogStart, deleteDialogEnd + '</AlertDialog.Root>'.length)
    : '';

if (!deleteDialogBlock) {
  failures.push('agent application delete dialog: missing controlled delete dialog block');
}

if (deleteDialogBlock.includes('<AlertDialog.Action>')) {
  failures.push('agent application delete dialog: confirm button must call handleDelete directly, not through AlertDialog.Action');
}

if (deleteDialogBlock.includes('<AlertDialog.Cancel>')) {
  failures.push('agent application delete dialog: cancel button must close controlled state directly, not through AlertDialog.Cancel');
}

if (!deleteDialogBlock.includes('onClick={() => void handleDelete(app.id)}')) {
  failures.push('agent application delete dialog: confirm button must invoke handleDelete(app.id)');
}

if (!source.includes('删除后将移除智能体配置、对话设置、关联会话和消息')) {
  failures.push('agent application delete dialog: missing explicit destructive warning copy');
}

if (!source.includes('绑定的知识库、模型、音色和 ASR/TTS 配置不会被删除')) {
  failures.push('agent application delete dialog: missing shared resource retention copy');
}

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log('agent application delete dialog static checks passed');
