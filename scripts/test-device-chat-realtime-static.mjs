import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const appSource = readFileSync(resolve(root, 'device-chat/app.js'), 'utf8');
const readmeSource = readFileSync(resolve(root, 'device-chat/README.md'), 'utf8');
const replacementTestSources = [
  'web/public/asr-replacement-test.html',
  'web/asr-replacement-test.html',
  'scripts/asr-replacement-test.html',
].map((path) => [path, readFileSync(resolve(root, path), 'utf8')]);

const checks = [
  {
    name: 'device chat opens unified realtime websocket',
    pass: appSource.includes("ASR_REALTIME_PATH: '/ws/realtime/'")
      && appSource.includes('new WebSocket(buildAsrRealtimeWebSocketUrl())'),
  },
  {
    name: 'browser websocket starts ASR with deviceCode command payload',
    pass: appSource.includes("type: 'asr.session.start'")
      && appSource.includes('payload: { deviceCode: state.deviceCode }'),
  },
  {
    name: 'pcm chunks are streamed after ASR is ready',
    pass: appSource.includes('sendRealtimeAudio(pcmBuffer)')
      && appSource.includes('!state.asrReady')
      && appSource.includes('socket.send(buffer)'),
  },
  {
    name: 'transcript events update question text immediately',
    pass: appSource.includes("payload.type === 'asr.transcript'")
      && appSource.includes('updateRealtimeQuestionText()'),
  },
  {
    name: 'recording stop sends ASR finish command',
    pass: appSource.includes("type: 'asr.session.finish'"),
  },
  {
    name: 'README documents realtime ASR behavior',
    pass: readmeSource.includes('/ws/realtime/')
      && readmeSource.includes('asr.session.start')
      && readmeSource.includes('实时语音识别'),
  },
  {
    name: 'ASR replacement test pages use unified realtime websocket',
    pass: replacementTestSources.every(([, source]) => source.includes('return `ws://${host}/ws/realtime/`;'))
      && replacementTestSources.every(([, source]) => !source.includes('/ws/asr/test/')),
  },
  {
    name: 'ASR replacement test pages start and finish sessions with commands',
    pass: replacementTestSources.every(([, source]) => source.includes("type: 'asr.session.start'"))
      && replacementTestSources.every(([, source]) => source.includes('deviceCode: currentDeviceCode()'))
      && replacementTestSources.every(([, source]) => source.includes("type: 'asr.session.finish'")),
  },
  {
    name: 'ASR replacement test pages wait for ready before streaming audio',
    pass: replacementTestSources.every(([, source]) => {
      const openIndex = source.indexOf('socket.onopen');
      const readyIndex = source.indexOf("if (payload.type === 'asr.ready')");
      const setupIndex = source.indexOf('setupAudioStreaming(state.stream, state.socket)');
      return openIndex !== -1
        && readyIndex !== -1
        && setupIndex !== -1
        && readyIndex < setupIndex
        && !source.slice(openIndex, readyIndex).includes('setupAudioStreaming(stream, socket)');
    }),
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
