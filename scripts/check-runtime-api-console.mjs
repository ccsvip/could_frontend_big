import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const htmlPath = join(root, 'device-chat', 'runtime-api-console.html');
const html = readFileSync(htmlPath, 'utf8');

const requiredSnippets = [
  '<title>设备运行时接口控制台</title>',
  'id="deviceCodeInput"',
  'id="apiBaseInput"',
  'data-section="voiceTones"',
  'data-section="images"',
  'data-section="scrollingTexts"',
  'data-section="models"',
  'data-section="videos"',
  'data-section="llmWs"',
  'data-section="agentChat"',
  '/device-auth/activate/',
  '/device-runtime/config/',
  '/device-runtime/resources/',
  '/ai-models/tts/options/',
  '/ai-models/asr/device-status/',
  '/device/voice-chat',
  '/ai-models/tts/runtime/',
  '/ws/realtime/',
  'X-Device-Code',
  'X-Request-ID',
  'X-Trace-ID',
  'credentials: \'omit\'',
  'resourceType',
  'scrollingTexts',
  'voiceId',
  'wrapWav',
  'openingMessage',
  'suggestedQuestions',
  'tenantName',
  'expiresAt',
  'asr.session.start',
  'asr.session.finish',
  'getUserMedia',
  'pcm_s16le',
  'originalText',
  'replacementApplied',
  'llm.session.start',
  'llm.delta',
  'llm.done',
  'tts.session.start',
  '实时问题',
  '开始问答',
  '自动播放',
  'typewriterText',
  'playPcmChunk',
];

const forbiddenSnippets = [
  'Authorization',
  'localStorage.setItem',
  'sessionStorage.setItem',
  'admin123456',
  'Bearer ',
];

const missing = requiredSnippets.filter((snippet) => !html.includes(snippet));
const forbidden = forbiddenSnippets.filter((snippet) => html.includes(snippet));

if (missing.length || forbidden.length) {
  if (missing.length) {
    console.error('Missing required runtime console snippets:');
    for (const snippet of missing) console.error(`- ${snippet}`);
  }
  if (forbidden.length) {
    console.error('Forbidden snippets found in runtime console:');
    for (const snippet of forbidden) console.error(`- ${snippet}`);
  }
  process.exit(1);
}

console.log('runtime-api-console static contract passed');
