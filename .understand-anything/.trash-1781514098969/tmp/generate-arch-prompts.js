const fs = require('fs');
const path = require('path');

const pluginRoot = 'C:/Users/amigo/.understand-anything-plugin';
let sysPrompt = fs.readFileSync(path.join(pluginRoot, 'agents/architecture-analyzer.md'), 'utf8');

const scan = JSON.parse(fs.readFileSync('.understand-anything/intermediate/scan-result.json', 'utf8'));
const languages = scan.languages;
const frameworks = scan.frameworks.map(f => f.toLowerCase().replace(/ /g, '-'));

let langCtx = '\n## Language Context\n';
languages.forEach(l => {
  const p = path.join(pluginRoot, 'languages', l + '.md');
  if (fs.existsSync(p)) langCtx += fs.readFileSync(p, 'utf8') + '\n';
});
sysPrompt += langCtx;

let fwCtx = '\n';
frameworks.forEach(f => {
  const p = path.join(pluginRoot, 'frameworks', f + '.md');
  if (fs.existsSync(p)) fwCtx += fs.readFileSync(p, 'utf8') + '\n';
});
sysPrompt += fwCtx;

const locPath = path.join(pluginRoot, 'locales/zh.md');
if (fs.existsSync(locPath)) {
  sysPrompt += '\n## Output Language Guidelines\n' + fs.readFileSync(locPath, 'utf8');
}

fs.writeFileSync('.understand-anything/tmp/arch-system-prompt.txt', sysPrompt);

// check if dir-tree.txt exists, else use fallback
let dirTree = '';
if (fs.existsSync('.understand-anything/tmp/dir-tree.txt')) {
  dirTree = fs.readFileSync('.understand-anything/tmp/dir-tree.txt', 'utf8');
} else {
  dirTree = 'See earlier context.';
}

const invokePrompt = `Analyze this codebase's structure to identify architectural layers.
Project root: C:/SVN_CODE/branches/real/could_frontend
Write output to: C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate/layers.json
Project: ${scan.projectName} - ${scan.projectDescription}

**Important Note**: The file nodes and edges data has ALREADY been prepared for you. You do not need to generate ua-arch-input.json.
It is located at: C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-arch-input.json
Please proceed directly to writing and executing the structural analysis script.

**Additional context from main session:**

Frameworks detected: ${scan.frameworks.join(', ')}

Directory tree (top 2 levels):
${dirTree}

Use the directory tree, language context, and framework addendums to inform layer assignments. Directory structure is strong evidence for layer boundaries. Non-code files (config, docs, infrastructure, data) should be assigned to appropriate layers.

> **Language directive**: Generate all textual content (summaries, descriptions, tags, titles, languageNotes, languageLesson) in **zh**. Maintain technical accuracy while using natural, native-level phrasing in the target language. Keep technical terms in English when no standard translation exists (e.g., "middleware", "hook", "barrel").
`;
fs.writeFileSync('.understand-anything/tmp/arch-invoke-prompt.txt', invokePrompt);
console.log('Prompts created.');
