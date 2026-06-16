import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import ts from 'typescript';

const moduleUrl = new URL('../src/views/application-management/playback-request-guard.ts', import.meta.url);
const source = await readFile(moduleUrl, 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
    strict: true,
  },
});
const dataUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
const { createPlaybackRequestGuard } = await import(dataUrl);

const guard = createPlaybackRequestGuard();

const firstRequest = guard.begin('message-1', 'hello');
assert.equal(guard.isCurrent(firstRequest), true);
assert.equal(guard.isPending('message-1', 'hello'), true);
assert.equal(guard.isPending('message-1', 'hello again'), false);

const secondRequest = guard.begin('message-2', 'other');
assert.equal(guard.isCurrent(firstRequest), false);
assert.equal(guard.isCurrent(secondRequest), true);
assert.equal(guard.isPending('message-1', 'hello'), false);
assert.equal(guard.isPending('message-2', 'other'), true);

guard.complete(firstRequest);
assert.equal(guard.isPending('message-2', 'other'), true);

guard.complete(secondRequest);
assert.equal(guard.isPending('message-2', 'other'), false);
assert.equal(guard.isCurrent(secondRequest), false);

guard.cancel();
assert.equal(guard.isCurrent(secondRequest), false);
