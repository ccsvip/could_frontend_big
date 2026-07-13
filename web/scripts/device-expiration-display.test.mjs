import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let server;
let resolveDeviceExpirationDisplay;

before(async () => {
  server = await createServer({ root, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom' });
  ({ resolveDeviceExpirationDisplay } = await server.ssrLoadModule(
    '/src/views/device-management/device-expiration-display.ts',
  ));
});

after(async () => {
  await server?.close();
});

test('设备到期时间展示遵循已确认的三态矩阵', () => {
  const expiresAt = '2027-07-13T23:59:59+08:00';
  const cases = [
    {
      input: { authorizationType: 'permanent', expiresAt: null, isSoftwareTrial: false },
      expected: { softwareExpiration: '永久', modelExpiration: '永久' },
    },
    {
      input: { authorizationType: 'trial', expiresAt, isSoftwareTrial: false },
      expected: { softwareExpiration: '永久', modelExpiration: '2027-07-13' },
    },
    {
      input: { authorizationType: 'trial', expiresAt, isSoftwareTrial: true },
      expected: { softwareExpiration: '2027-07-13', modelExpiration: '2027-07-13' },
    },
  ];

  for (const { input, expected } of cases) {
    assert.deepEqual(resolveDeviceExpirationDisplay(input), expected);
  }
});
