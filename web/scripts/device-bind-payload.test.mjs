import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let server;
let buildBindPayload;

before(async () => {
  server = await createServer({ root, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom' });
  ({ buildBindPayload } = await server.ssrLoadModule('/src/views/device-authorization-center/utils.ts'));
});

after(async () => {
  await server?.close();
});

test('设备绑定载荷传递软件试用标记并对永久授权强制关闭', () => {
  const expiresAt = { toISOString: () => '2027-07-13T15:59:59.000Z' };

  assert.deepEqual(
    buildBindPayload({
      tenantId: 1,
      authorizationType: 'trial',
      expiresAt,
      isSoftwareTrial: true,
      isEnabled: true,
    }),
    {
      tenantId: 1,
      authorizationType: 'trial',
      expiresAt: '2027-07-13T15:59:59.000Z',
      isSoftwareTrial: true,
      isEnabled: true,
    },
  );

  assert.deepEqual(
    buildBindPayload({
      tenantId: 1,
      authorizationType: 'permanent',
      expiresAt: null,
      isSoftwareTrial: true,
      isEnabled: true,
    }),
    {
      tenantId: 1,
      authorizationType: 'permanent',
      expiresAt: null,
      isSoftwareTrial: false,
      isEnabled: true,
    },
  );
});
