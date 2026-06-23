#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';

const [,, projectRoot, commitHash] = process.argv;
if (!projectRoot || !commitHash) {
  console.error('Usage: node finalize-graph.mjs <projectRoot> <commitHash>');
  process.exit(1);
}

const intermediate = join(projectRoot, '.understand-anything', 'intermediate');
const scan = JSON.parse(readFileSync(join(intermediate, 'scan-result.json'), 'utf8'));
const assembled = JSON.parse(readFileSync(join(intermediate, 'assembled-graph.json'), 'utf8'));

const layerPatterns = [
  { patterns: ['routes', 'controller', 'handler', 'endpoint', 'api'], name: 'API Layer', description: 'HTTP endpoints, route handlers, and API clients' },
  { patterns: ['service', 'usecase', 'use-case', 'business'], name: 'Service Layer', description: 'Business logic and application services' },
  { patterns: ['model', 'entity', 'schema', 'database', 'db', 'migration', 'repository', 'repo'], name: 'Data Layer', description: 'Data models, database access, and persistence' },
  { patterns: ['component', 'view', 'page', 'screen', 'layout', 'widget', 'ui'], name: 'UI Layer', description: 'User interface components and views' },
  { patterns: ['middleware', 'interceptor', 'guard', 'filter', 'pipe'], name: 'Middleware Layer', description: 'Request/response middleware and guards' },
  { patterns: ['client', 'integration', 'external', 'sdk', 'vendor', 'adapter'], name: 'External Services', description: 'External service integrations, SDKs, and adapters' },
  { patterns: ['worker', 'job', 'queue', 'cron', 'consumer', 'processor', 'scheduler', 'background'], name: 'Background Tasks', description: 'Background workers, job processors, and scheduled tasks' },
  { patterns: ['util', 'helper', 'lib', 'common', 'shared'], name: 'Utility Layer', description: 'Shared utilities, helpers, and common libraries' },
  { patterns: ['test', 'spec', '__test__', '__spec__', '__tests__', '__specs__'], name: 'Test Layer', description: 'Test files and test utilities' },
  { patterns: ['config', 'setting', 'env'], name: 'Configuration Layer', description: 'Application configuration and environment settings' },
];

function layerId(name) {
  return `layer:${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;
}

function matchLayer(filePath) {
  const segments = filePath.replace(/\\/g, '/').toLowerCase().split('/');
  for (const layer of layerPatterns) {
    for (const segment of segments) {
      if (layer.patterns.some((pattern) => segment === pattern || segment === `${pattern}s`)) {
        return layer;
      }
    }
  }
  return { name: 'Core', description: 'Core application files' };
}

const fileLevelTypes = new Set(['file', 'config', 'document', 'service', 'pipeline', 'table', 'schema', 'resource', 'endpoint']);
const layerMap = new Map();
for (const node of assembled.nodes) {
  if (!fileLevelTypes.has(node.type) || !node.filePath) continue;
  const layer = matchLayer(node.filePath);
  const id = layerId(layer.name);
  if (!layerMap.has(id)) layerMap.set(id, { id, name: layer.name, description: layer.description, nodeIds: [] });
  layerMap.get(id).nodeIds.push(node.id);
}
const layers = [...layerMap.values()].filter((layer) => layer.nodeIds.length);

const importantPaths = [
  'README.md',
  'docker-compose.yaml',
  'backend/config/urls.py',
  'backend/apps/accounts/views.py',
  'backend/apps/ai_models/views.py',
  'web/src/main.tsx',
  'web/src/router/index.tsx',
  'web/src/layouts/dashboard-layout.tsx',
];
const nodeIds = new Set(assembled.nodes.map((node) => node.id));
const byPath = new Map(assembled.nodes.filter((node) => node.filePath).map((node) => [node.filePath, node.id]));
const tour = [];
const overviewIds = importantPaths.map((path) => byPath.get(path)).filter(Boolean);
if (overviewIds.length) {
  tour.push({
    order: 1,
    title: '项目总览',
    description: '从说明、部署配置和主要入口理解项目的整体边界。',
    nodeIds: overviewIds,
  });
}
for (const layer of layers.slice(0, 8)) {
  tour.push({
    order: tour.length + 1,
    title: layer.name,
    description: `${layer.description}。该步骤聚焦 ${layer.nodeIds.slice(0, 8).map((id) => basename(assembled.nodes.find((node) => node.id === id)?.filePath || id)).join(', ')} 等文件。`,
    nodeIds: layer.nodeIds.slice(0, 40).filter((id) => nodeIds.has(id)),
  });
}

const graph = {
  version: '1.0.0',
  project: {
    name: scan.projectName || scan.project?.name || basename(projectRoot),
    languages: scan.languages || scan.project?.languages || [],
    frameworks: scan.frameworks || scan.project?.frameworks || [],
    description: scan.description || scan.projectDescription || scan.project?.description || 'Indexed project knowledge graph',
    analyzedAt: new Date().toISOString(),
    gitCommitHash: commitHash,
  },
  nodes: assembled.nodes,
  edges: assembled.edges,
  layers,
  tour,
};

writeFileSync(join(intermediate, 'assembled-graph.json'), JSON.stringify(graph, null, 2), 'utf8');
writeFileSync(join(projectRoot, '.understand-anything', 'knowledge-graph.json'), JSON.stringify(graph, null, 2), 'utf8');

console.log(JSON.stringify({
  nodes: graph.nodes.length,
  edges: graph.edges.length,
  layers: graph.layers.length,
  tourSteps: graph.tour.length,
}, null, 2));
