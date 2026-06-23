#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, basename } from 'node:path';
import { spawnSync } from 'node:child_process';

const [,, projectRoot, skillDir] = process.argv;
if (!projectRoot || !skillDir) {
  console.error('Usage: node build-deterministic-graph.mjs <projectRoot> <skillDir>');
  process.exit(1);
}

const intermediate = join(projectRoot, '.understand-anything', 'intermediate');
mkdirSync(intermediate, { recursive: true });

const batchesPayload = JSON.parse(readFileSync(join(intermediate, 'batches.json'), 'utf8'));
const batches = Array.isArray(batchesPayload) ? batchesPayload : batchesPayload.batches;
if (!Array.isArray(batches)) {
  throw new Error('batches.json must be an array or contain a batches array');
}

function nodeTypeFor(file) {
  const category = file.fileCategory;
  const path = file.path.toLowerCase();
  if (category === 'docs') return 'document';
  if (category === 'infra') return 'service';
  if (category === 'config') return 'config';
  if (path.includes('/migrations/') || path.includes('\\migrations\\')) return 'table';
  return 'file';
}

function complexityFor(lines) {
  if (lines <= 120) return 'simple';
  if (lines <= 400) return 'moderate';
  return 'complex';
}

function cleanName(value) {
  return String(value || 'anonymous').replace(/[:\r\n]/g, '_');
}

function fileSummary(file, result) {
  const parts = [];
  parts.push(`${file.path} (${file.language || 'unknown'})`);
  if (result.functions?.length) parts.push(`${result.functions.length} functions`);
  if (result.classes?.length) parts.push(`${result.classes.length} classes`);
  if (result.endpoints?.length) parts.push(`${result.endpoints.length} endpoints`);
  if (result.services?.length) parts.push(`${result.services.length} services`);
  if (result.sections?.length) parts.push(`${result.sections.length} document sections`);
  return parts.join('; ');
}

function pushEdge(edges, source, target, type, weight = 0.5) {
  if (!source || !target || source === target) return;
  edges.push({ source, target, type, direction: 'forward', weight });
}

let totalFiles = 0;
for (const batch of batches) {
  const inputPath = join(intermediate, `structure-input-${batch.batchIndex}.json`);
  const structurePath = join(intermediate, `structure-${batch.batchIndex}.json`);
  const outputPath = join(intermediate, `batch-${batch.batchIndex}.json`);
  writeFileSync(inputPath, JSON.stringify({
    projectRoot,
    batchFiles: batch.files,
    batchImportData: batch.batchImportData || {},
  }, null, 2), 'utf8');

  const proc = spawnSync(process.execPath, [
    join(skillDir, 'extract-structure.mjs'),
    inputPath,
    structurePath,
  ], { encoding: 'utf8' });

  if (proc.status !== 0) {
    console.error(proc.stderr || proc.stdout);
    process.exit(proc.status || 1);
  }

  const structure = JSON.parse(readFileSync(structurePath, 'utf8'));
  const resultByPath = new Map(structure.results.map((r) => [r.path, r]));
  const nodes = [];
  const edges = [];

  for (const file of batch.files) {
    const result = resultByPath.get(file.path) || {};
    const type = nodeTypeFor(file);
    const id = `${type}:${file.path}`;
    const tags = [file.language || 'unknown', file.fileCategory || 'file'].filter(Boolean);
    nodes.push({
      id,
      type,
      name: basename(file.path),
      filePath: file.path,
      summary: fileSummary(file, result),
      tags,
      complexity: complexityFor(result.totalLines || file.sizeLines || 0),
      language: file.language || 'unknown',
      lineRange: [1, result.totalLines || file.sizeLines || 1],
      metrics: result.metrics || {},
    });

    for (const target of batch.batchImportData?.[file.path] || []) {
      pushEdge(edges, id, `file:${target}`, 'imports', 0.7);
    }

    for (const fn of result.functions || []) {
      const fnId = `function:${file.path}:${cleanName(fn.name)}`;
      nodes.push({
        id: fnId,
        type: 'function',
        name: fn.name,
        filePath: file.path,
        summary: `Function ${fn.name} in ${file.path}`,
        tags: ['function', file.language || 'unknown'],
        complexity: complexityFor((fn.endLine || 0) - (fn.startLine || 0) + 1),
        lineRange: [fn.startLine || 1, fn.endLine || fn.startLine || 1],
        params: fn.params || [],
      });
      pushEdge(edges, id, fnId, 'contains', 1.0);
    }

    for (const cls of result.classes || []) {
      const clsId = `class:${file.path}:${cleanName(cls.name)}`;
      nodes.push({
        id: clsId,
        type: 'class',
        name: cls.name,
        filePath: file.path,
        summary: `Class or type ${cls.name} in ${file.path}`,
        tags: ['class', file.language || 'unknown'],
        complexity: complexityFor((cls.endLine || 0) - (cls.startLine || 0) + 1),
        lineRange: [cls.startLine || 1, cls.endLine || cls.startLine || 1],
        methods: cls.methods || [],
        properties: cls.properties || [],
      });
      pushEdge(edges, id, clsId, 'contains', 1.0);
    }

    for (const endpoint of result.endpoints || []) {
      const epName = `${endpoint.method || 'ROUTE'} ${endpoint.path || file.path}`;
      const epId = `endpoint:${file.path}:${cleanName(epName)}`;
      nodes.push({
        id: epId,
        type: 'endpoint',
        name: epName,
        filePath: file.path,
        summary: `Endpoint ${epName} defined in ${file.path}`,
        tags: ['endpoint', file.language || 'unknown'],
        complexity: 'simple',
        lineRange: [endpoint.startLine || 1, endpoint.endLine || endpoint.startLine || 1],
      });
      pushEdge(edges, id, epId, 'routes', 0.5);
    }

    for (const service of result.services || []) {
      const serviceId = `service:${file.path}:${cleanName(service.name)}`;
      nodes.push({
        id: serviceId,
        type: 'service',
        name: service.name,
        filePath: file.path,
        summary: `Service ${service.name} configured in ${file.path}`,
        tags: ['service', file.language || 'unknown'],
        complexity: 'simple',
        image: service.image,
        ports: service.ports || [],
      });
      pushEdge(edges, id, serviceId, 'configures', 0.6);
    }
  }

  writeFileSync(outputPath, JSON.stringify({ nodes, edges }, null, 2), 'utf8');
  totalFiles += batch.files.length;
  console.log(`batch ${batch.batchIndex}: ${batch.files.length} files, ${nodes.length} nodes, ${edges.length} edges`);
}

console.log(`completed ${batches.length} batches, ${totalFiles} files`);
