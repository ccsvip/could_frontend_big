import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

const read = (path) => readFileSync(resolve(root, path), 'utf8');

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const routerSource = read('src/router/index.tsx');
const dashboardSource = read('src/layouts/dashboard-layout.tsx');
const adminPageSource = read('src/views/settings-llm/index.tsx');
const companyPagePath = resolve(root, 'src/views/llm-settings/index.tsx');

assert(routerSource.includes("path: 'settings/llm'"), 'router must register settings/llm');
assert(dashboardSource.includes("key: 'settings-llm'"), 'dashboard menu must include settings-llm');
assert(dashboardSource.includes("label: 'LLM设置'"), 'dashboard menu must label LLM设置');

assert(adminPageSource.includes('apiKeyMasked'), 'admin provider table must use masked key value');
assert(adminPageSource.includes('apiKeyConfigured'), 'admin provider table must use key configured flag');
assert(!/dataIndex:\s*['"]apiKey['"]/.test(adminPageSource), 'admin table must not display raw apiKey');

if (existsSync(companyPagePath)) {
  const companyPageSource = read('src/views/llm-settings/index.tsx');
  assert(!companyPageSource.includes('apiBaseUrl'), 'company LLM page must not display API base URL');
  assert(!companyPageSource.includes('apiKey'), 'company LLM page must not display API key');
  assert(!companyPageSource.includes('{provider.name}'), 'company LLM page must not display provider names');
  assert(!companyPageSource.includes('provider.avatarUrl'), 'company LLM page must not display provider logos');
}

console.log('LLM settings static checks passed');
