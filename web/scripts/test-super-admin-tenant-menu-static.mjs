import { readFileSync } from 'node:fs';

const layoutSource = readFileSync(new URL('../src/layouts/dashboard-layout.tsx', import.meta.url), 'utf8');
const routerSource = readFileSync(new URL('../src/router/index.tsx', import.meta.url), 'utf8');

const failures = [];

const expectIncludes = (source, needle, label) => {
  if (!source.includes(needle)) {
    failures.push(`${label}: missing ${needle}`);
  }
};

const sliceBetween = (source, startNeedle, endNeedle, label) => {
  const start = source.indexOf(startNeedle);
  const end = source.indexOf(endNeedle, start + startNeedle.length);
  if (start < 0 || end <= start) {
    failures.push(`${label}: missing block ${startNeedle}`);
    return '';
  }
  return source.slice(start, end);
};

const resourceModuleBlock = sliceBetween(
  layoutSource,
  "segment: 'resources'",
  "segment: 'knowledge-base'",
  'super admin tenant sidebar',
);
const aiModuleBlock = sliceBetween(
  layoutSource,
  "segment: 'ai-models'",
  'const buildSuperAdminMenus',
  'super admin tenant sidebar',
);

expectIncludes(resourceModuleBlock, 'children:', 'super admin tenant sidebar resources');
for (const segment of ['images', 'videos', 'scrolling-texts', 'voice-tones', 'models']) {
  expectIncludes(resourceModuleBlock, `segment: '${segment}'`, 'super admin tenant sidebar resources');
}

expectIncludes(aiModuleBlock, 'children:', 'super admin tenant sidebar ai-models');
for (const segment of ['asr', 'llm', 'tts', 'chat']) {
  expectIncludes(aiModuleBlock, `segment: '${segment}'`, 'super admin tenant sidebar ai-models');
}

const tenantScopedRouteStart = routerSource.indexOf("path: 'tenants/:tenantId'");
const tenantScopedRouteEnd = routerSource.indexOf("path: 'logs'", tenantScopedRouteStart);
const tenantScopedRouteBlock =
  tenantScopedRouteStart >= 0 && tenantScopedRouteEnd > tenantScopedRouteStart
    ? routerSource.slice(tenantScopedRouteStart, tenantScopedRouteEnd)
    : '';

if (!tenantScopedRouteBlock) {
  failures.push('super admin tenant routes: missing tenants/:tenantId route block');
}

const scopedRoutePaths = [
  'resources/images',
  'resources/videos',
  'resources/scrolling-texts',
  'resources/voice-tones',
  'resources/models',
  'ai-models/asr',
  'ai-models/llm',
  'ai-models/tts',
  'ai-models/chat',
];

for (const path of scopedRoutePaths) {
  expectIncludes(tenantScopedRouteBlock, `path: '${path}'`, 'super admin tenant routes');
}

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log('super admin tenant menu static checks passed');
