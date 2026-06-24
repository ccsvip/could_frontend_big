import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const files = [
  '../src/views/application-management/use-agent-audio.ts',
  '../src/views/asr-management/index.tsx',
];

for (const file of files) {
  const source = await readFile(new URL(file, import.meta.url), 'utf8');
  const onopenMatch = source.match(/socket\.onopen\s*=\s*\(\)\s*=>\s*{(?<body>[\s\S]*?)\n\s*};/);
  assert.ok(onopenMatch?.groups?.body, `${file} should define socket.onopen`);
  assert.equal(
    onopenMatch.groups.body.includes('setupAudioStreaming'),
    false,
    `${file} must not stream PCM before asr.ready`,
  );

  const readyIndex = source.indexOf("payload.type === 'asr.ready'");
  assert.notEqual(readyIndex, -1, `${file} should handle asr.ready`);
  assert.notEqual(
    source.indexOf('setupAudioStreaming', readyIndex),
    -1,
    `${file} should start PCM streaming after asr.ready`,
  );
}
