#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [,, projectRoot, commitHash] = process.argv;
const scan = JSON.parse(readFileSync(join(projectRoot, '.understand-anything', 'intermediate', 'scan-result.json'), 'utf8'));
const files = (scan.files || []).filter((file) => file.fileCategory === 'code' || file.fileCategory === 'script').map((file) => file.path);
writeFileSync(join(projectRoot, '.understand-anything', 'intermediate', 'fingerprint-input.json'), JSON.stringify({
  projectRoot,
  sourceFilePaths: files,
  gitCommitHash: commitHash,
}, null, 2), 'utf8');
console.log(`fingerprint input files=${files.length}`);
