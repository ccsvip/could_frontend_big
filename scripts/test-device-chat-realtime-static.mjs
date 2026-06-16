import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const appSource = readFileSync(resolve(root, 'device-chat/app.js'), 'utf8');
const readmeSource = readFileSync(resolve(root, 'device-chat/README.md'), 'utf8');

const checks = [
  {
    name: 'device chat opens realtime ASR websocket',
    pass: appSource.includes("ASR_REALTIME_PATH: '/ws/asr/test/'")
      && appSource.includes('new WebSocket(buildAsrRealtimeWebSocketUrl(state.deviceCode))'),
  },
  {
    name: 'browser websocket authenticates with deviceCode query param',
    pass: appSource.includes("url.searchParams.set('deviceCode', deviceCode)"),
  },
  {
    name: 'pcm chunks are streamed while recording',
    pass: appSource.includes('sendRealtimeAudio(pcmBuffer)')
      && appSource.includes('socket.send(buffer)'),
  },
  {
    name: 'transcript events update question text immediately',
    pass: appSource.includes("payload.type === 'asr.transcript'")
      && appSource.includes('updateRealtimeQuestionText()'),
  },
  {
    name: 'recording stop sends asr.finish',
    pass: appSource.includes("socket.send(JSON.stringify({ type: 'asr.finish' }))"),
  },
  {
    name: 'README documents realtime ASR behavior',
    pass: readmeSource.includes('/ws/asr/test/?deviceCode=DEVICE_001')
      && readmeSource.includes('实时识别'),
  },
];

const failures = checks.filter((check) => !check.pass);
if (failures.length > 0) {
  console.error('device-chat realtime ASR static checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log(`device-chat realtime ASR static checks passed (${checks.length} checks).`);
