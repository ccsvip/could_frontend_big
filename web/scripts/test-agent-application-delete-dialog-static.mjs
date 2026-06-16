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
