#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [,, projectRoot, commitHash] = process.argv;
const graph = JSON.parse(readFileSync(join(projectRoot, '.understand-anything', 'knowledge-graph.json'), 'utf8'));
const scan = JSON.parse(readFileSync(join(projectRoot, '.understand-anything', 'intermediate', 'scan-result.json'), 'utf8'));
writeFileSync(join(projectRoot, '.understand-anything', 'meta.json'), JSON.stringify({
  lastAnalyzedAt: graph.project.analyzedAt,
  gitCommitHash: commitHash,
  version: graph.version,
  analyzedFiles: scan.files?.length || 0,
}, null, 2), 'utf8');
