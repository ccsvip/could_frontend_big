import { normalizeControlCommandReplyPreferences } from '../src/views/command-management/control-command-reply-preferences.ts';

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const legacyPreferences = normalizeControlCommandReplyPreferences({});
assert(legacyPreferences.executionReply === '', '历史导入缺少执行回复时必须兼容为空字符串');
assert(legacyPreferences.replyStrategy === 'fixed', '历史导入缺少回复策略时必须兼容为固定回复');

const generatedPreferences = normalizeControlCommandReplyPreferences({
  executionReply: '  ',
  replyStrategy: 'generated',
});
assert(generatedPreferences.executionReply === '', '执行回复必须去除首尾空白');
assert(generatedPreferences.replyStrategy === 'generated', '明确选择智能生成时必须保留策略');

const customPreferences = normalizeControlCommandReplyPreferences({
  executionReply: '  会议室屏幕已打开。  ',
  replyStrategy: 'fixed',
});
assert(customPreferences.executionReply === '会议室屏幕已打开。', '自定义执行回复必须保留正文并去除首尾空白');
assert(customPreferences.replyStrategy === 'fixed', '固定回复策略必须保持不变');
