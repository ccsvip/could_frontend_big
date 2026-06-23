#!/usr/bin/env node
const fs = require('fs');
const graphPath = process.argv[2];
const outputPath = process.argv[3];
const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
const issues = [];
const warnings = [];
if (!Array.isArray(graph.nodes)) issues.push('nodes is not an array');
if (!Array.isArray(graph.edges)) issues.push('edges is not an array');
if (!Array.isArray(graph.layers)) issues.push('layers is not an array');
if (!Array.isArray(graph.tour)) issues.push('tour is not an array');
const ids = new Set((graph.nodes || []).map((node) => node.id));
for (const [i, node] of (graph.nodes || []).entries()) {
  if (!node.id) issues.push(`node ${i} missing id`);
  if (!node.type) issues.push(`node ${node.id || i} missing type`);
  if (!node.name) issues.push(`node ${node.id || i} missing name`);
  if (!node.summary) warnings.push(`node ${node.id || i} missing summary`);
}
for (const [i, edge] of (graph.edges || []).entries()) {
  if (!ids.has(edge.source)) issues.push(`edge ${i} missing source ${edge.source}`);
  if (!ids.has(edge.target)) issues.push(`edge ${i} missing target ${edge.target}`);
}
for (const layer of graph.layers || []) {
  if (!layer.id || !layer.name || !layer.description || !Array.isArray(layer.nodeIds)) {
    issues.push(`invalid layer ${layer.id || layer.name || '<unknown>'}`);
  }
  for (const id of layer.nodeIds || []) {
    if (!ids.has(id)) issues.push(`layer ${layer.id} references missing node ${id}`);
  }
}
for (const step of graph.tour || []) {
  if (typeof step.order !== 'number' || !step.title || !step.description || !Array.isArray(step.nodeIds)) {
    issues.push(`invalid tour step ${step.title || step.order || '<unknown>'}`);
  }
  for (const id of step.nodeIds || []) {
    if (!ids.has(id)) issues.push(`tour ${step.title} references missing node ${id}`);
  }
}
const stats = {
  totalNodes: graph.nodes?.length || 0,
  totalEdges: graph.edges?.length || 0,
  totalLayers: graph.layers?.length || 0,
  tourSteps: graph.tour?.length || 0,
  nodeTypes: Object.fromEntries(Object.entries((graph.nodes || []).reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {})).sort()),
  edgeTypes: Object.fromEntries(Object.entries((graph.edges || []).reduce((acc, edge) => {
    acc[edge.type] = (acc[edge.type] || 0) + 1;
    return acc;
  }, {})).sort()),
};
fs.writeFileSync(outputPath, JSON.stringify({ issues, warnings, stats }, null, 2));
if (issues.length) process.exit(1);
