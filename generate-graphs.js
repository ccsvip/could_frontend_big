const fs = require('fs');
const path = require('path');

const batch31Input = JSON.parse(fs.readFileSync('.understand-anything/tmp/ua-file-analyzer-input-31.json', 'utf8'));
const batch31Result = JSON.parse(fs.readFileSync('.understand-anything/tmp/ua-file-extract-results-31.json', 'utf8'));
const batch32Input = JSON.parse(fs.readFileSync('.understand-anything/tmp/ua-file-analyzer-input-32.json', 'utf8'));
const batch32Result = JSON.parse(fs.readFileSync('.understand-anything/tmp/ua-file-extract-results-32.json', 'utf8'));

// Dictionaries for zh summaries and tags
const dict = {
  'wiki/404.html': { t: 'file', s: '项目的自定义 404 错误页面，提供未找到页面的友好提示。', tg: ['error-page', 'markup', 'frontend'], c: 'simple' },
  'wiki/TTS鏁欑▼.md': { t: 'document', s: 'TTS (Text-to-Speech) 模块的接入与使用教程，指导如何调用语音合成功能。', tg: ['documentation', 'tutorial', 'tts', 'audio'], c: 'simple' },
  'wiki/TTS教程.md': { t: 'document', s: 'TTS (Text-to-Speech) 模块的接入与使用教程，指导如何调用语音合成功能。', tg: ['documentation', 'tutorial', 'tts', 'audio'], c: 'simple' },
  'wiki/android-device-runtime-simulator.html': { t: 'file', s: '安卓设备运行时模拟器页面，用于在浏览器中模拟安卓客户端行为和调试。', tg: ['simulator', 'testing', 'android', 'development'], c: 'moderate' },
  'wiki/asr-websocket-tutorial.md': { t: 'document', s: 'ASR WebSocket 最小接入教程，包含环境变量配置、会话流程及客户端代码示例。', tg: ['documentation', 'tutorial', 'websocket', 'asr'], c: 'moderate' },
  'wiki/container-dependencies.md': { t: 'document', s: '详细记录了 Solin 容器的依赖关系、启动顺序和数据流走向，是后端架构的重要指导文档。', tg: ['documentation', 'architecture', 'docker', 'infrastructure'], c: 'moderate' },
  'wiki/design-audit.html': { t: 'file', s: 'UI/UX 设计审查页面，包含视觉样式和交互组件的检查清单和参考。', tg: ['design', 'ui-ux', 'audit'], c: 'moderate' },
  'wiki/device-api-latest.html': { t: 'file', s: '最新版本的设备 API 文档或接口展示页面，供前端和设备端开发者参考。', tg: ['api-docs', 'device', 'reference'], c: 'moderate' },
  'wiki/sentry-mcp-codex-guide.html': { t: 'file', s: 'Sentry MCP 与 Codex 集成指南的 HTML 渲染版本，包含鉴权和故障排查步骤。', tg: ['sentry', 'guide', 'monitoring'], c: 'moderate' },
  'wiki/sentry-mcp-codex-guide.md': { t: 'document', s: 'Sentry MCP 与 Codex 集成指南，指导开发者如何配置凭证和在 Codex 中使用 Sentry 工具。', tg: ['documentation', 'sentry', 'guide', 'monitoring'], c: 'moderate' },
  'wiki/voices_qwen3.json': { t: 'config', s: '针对 Qwen3 模型的语音配置文件，定义了可用声音列表及其相关参数。', tg: ['configuration', 'voice', 'qwen3'], c: 'moderate' },

  '.claude/skills/caveman/SKILL.md': { t: 'document', s: 'Caveman 技能配置文件，定义了一种极简沟通模式，通过去除冗余词汇来降低 token 消耗。', tg: ['skill', 'prompt', 'configuration'], c: 'simple' },
  '.claude/skills/design-an-interface/SKILL.md': { t: 'document', s: '接口设计技能配置，指导 AI 如何通过并行子代理生成和比较多种界面设计方案。', tg: ['skill', 'design', 'interface'], c: 'simple' },
  '.claude/skills/diagnose/scripts/hitl-loop.template.sh': { t: 'file', s: 'Human-in-the-loop (HITL) 诊断脚本模板，用于在调试过程中构建人工干预循环。', tg: ['script', 'testing', 'diagnostics'], c: 'simple' },
  '.claude/skills/diagnose/SKILL.md': { t: 'document', s: '诊断技能说明文档，定义了解决复杂 bug 和性能倒退的标准化调试工作流。', tg: ['skill', 'debugging', 'workflow'], c: 'simple' },
  '.claude/skills/edit-article/SKILL.md': { t: 'document', s: '文章编辑技能配置，指导 AI 如何重构和润色文章段落以提升清晰度。', tg: ['skill', 'editing', 'content'], c: 'simple' },
  '.claude/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh': { t: 'file', s: 'Git 安全拦截脚本，用于防止在自动执行过程中意外运行破坏性的 Git 命令。', tg: ['script', 'git', 'security', 'hooks'], c: 'simple' },
  '.claude/skills/git-guardrails-claude-code/SKILL.md': { t: 'document', s: 'Git 安全护栏技能说明，描述了如何配置钩子拦截高风险的 Git 变更操作。', tg: ['skill', 'git', 'security'], c: 'simple' },
  '.claude/skills/grill-me/SKILL.md': { t: 'document', s: '质询技能配置，要求 AI 对用户的计划和设计进行严格盘问，直至达成共识。', tg: ['skill', 'planning', 'review'], c: 'simple' },
  '.claude/skills/handoff/SKILL.md': { t: 'document', s: '交接技能配置，用于将当前对话上下文压缩为供其他代理阅读的移交文档。', tg: ['skill', 'context', 'handoff'], c: 'simple' },
  '.claude/skills/impeccable/scripts/command-metadata.json': { t: 'config', s: 'Impeccable 技能相关的命令元数据配置，定义了可用命令及其参数列表。', tg: ['configuration', 'metadata', 'skill'], c: 'simple' },
  '.claude/skills/impeccable/scripts/detect-csp.mjs': { t: 'file', s: 'CSP（内容安全策略）检测脚本，用于在浏览器自动化测试时检查页面安全策略。', tg: ['script', 'security', 'csp', 'browser'], c: 'moderate' },
  '.claude/skills/impeccable/scripts/detect.mjs': { t: 'file', s: '自动化检测脚本入口，负责调用具体的检测器进行页面分析。', tg: ['script', 'testing', 'entry-point'], c: 'simple' },
  '.claude/skills/impeccable/scripts/detector/browser/injected/index.mjs': { t: 'file', s: '注入到浏览器上下文执行的核心检测脚本，用于提取和分析 DOM 信息。', tg: ['script', 'browser', 'injection', 'dom'], c: 'complex' },
  '.claude/skills/impeccable/scripts/detector/detect-antipatterns-browser.js': { t: 'file', s: '反模式检测脚本，用于扫描浏览器页面中的常见 UI 和交互反模式。', tg: ['script', 'browser', 'anti-pattern', 'testing'], c: 'complex' },
  '.claude/skills/impeccable/scripts/live-browser-dom.js': { t: 'file', s: '实时浏览器 DOM 交互脚本，封装了页面元素的定位与操作方法。', tg: ['script', 'browser', 'dom', 'automation'], c: 'moderate' },
  '.claude/skills/impeccable/scripts/live-browser-session.js': { t: 'file', s: '浏览器会话管理脚本，用于在自动化测试过程中维护浏览器连接和上下文。', tg: ['script', 'browser', 'session', 'automation'], c: 'moderate' },
  '.claude/skills/impeccable/scripts/live-browser.js': { t: 'file', s: '实时浏览器核心控制器，协调 DOM 操作、会话管理以及自动化行为。', tg: ['script', 'browser', 'controller', 'automation'], c: 'complex' },
  '.claude/skills/impeccable/scripts/live/ui-core.mjs': { t: 'file', s: 'UI 核心测试脚本，提供基础的界面交互和断言功能。', tg: ['script', 'ui', 'testing', 'core'], c: 'moderate' },
  '.claude/skills/impeccable/scripts/modern-screenshot.umd.js': { t: 'file', s: '现代化网页截图工具的 UMD 构建版本，用于生成页面的高质量快照。', tg: ['script', 'screenshot', 'utility'], c: 'simple' },
  '.claude/skills/impeccable/scripts/palette.mjs': { t: 'file', s: '色彩面板提取脚本，负责从页面中解析和生成 UI 的主题色配置。', tg: ['script', 'color', 'theme', 'ui'], c: 'moderate' },
  '.claude/skills/impeccable/scripts/pin.mjs': { t: 'file', s: '模块固定与锁定脚本，用于在测试或部署期间固定特定组件的版本或状态。', tg: ['script', 'utility', 'deployment'], c: 'moderate' },
  '.claude/skills/impeccable/SKILL.md': { t: 'document', s: 'Impeccable 技能主文档，涵盖了前端界面的极致优化和设计审查规则。', tg: ['skill', 'design', 'frontend', 'optimization'], c: 'moderate' },
  '.claude/skills/migrate-to-shoehorn/SKILL.md': { t: 'document', s: 'Shoehorn 迁移技能文档，指导如何将测试代码中的类型断言替换为更安全的方案。', tg: ['skill', 'testing', 'migration', 'typescript'], c: 'moderate' },
  '.claude/skills/obsidian-vault/SKILL.md': { t: 'document', s: 'Obsidian Vault 技能配置，说明了如何管理和组织本地知识库的笔记结构。', tg: ['skill', 'knowledge-base', 'obsidian'], c: 'simple' },
  '.claude/skills/qa/SKILL.md': { t: 'document', s: 'QA 会话技能指南，定义了交互式测试、问题追踪和 GitHub Issue 的提报流程。', tg: ['skill', 'qa', 'testing', 'issue-tracking'], c: 'moderate' }
};

function processBatch(input, result, batchIndex) {
  const nodes = [];
  const edges = [];
  const importData = input.batchImportData || {};

  // Process all files from input
  for (const fileDef of input.batchFiles) {
    const p = fileDef.path;
    let res = result.results.find(r => r.path === p);
    
    // For skipped files
    if (!res && result.filesSkipped && result.filesSkipped.includes(p)) {
      res = { path: p, language: fileDef.language, fileCategory: fileDef.fileCategory };
    }
    
    const meta = dict[p] || { t: 'file', s: '未分类的源代码或资源文件。', tg: ['source'], c: 'simple' };
    const nodeId = meta.t + ':' + p;

    nodes.push({
      id: nodeId,
      type: meta.t,
      name: path.basename(p),
      filePath: p,
      summary: meta.s,
      tags: meta.tg,
      complexity: meta.c
    });

    // Create imports edges
    if (importData[p]) {
      for (const targetPath of importData[p]) {
        edges.push({
          source: nodeId,
          target: 'file:' + targetPath,
          type: 'imports',
          direction: 'forward',
          weight: 0.7
        });
      }
    }

    // Process functions and classes
    if (res && res.functions) {
      for (const f of res.functions) {
        if ((f.endLine - f.startLine + 1) >= 10 || res.exports?.some(e => e.name === f.name)) {
          const fid = 'function:' + p + ':' + f.name;
          nodes.push({
            id: fid,
            type: 'function',
            name: f.name,
            filePath: p,
            lineRange: [f.startLine, f.endLine],
            summary: f.name + ' 功能函数，提供局部逻辑处理或对外接口。',
            tags: ['function', 'logic'],
            complexity: 'simple'
          });
          edges.push({
            source: nodeId,
            target: fid,
            type: 'contains',
            direction: 'forward',
            weight: 1.0
          });
        }
      }
    }

    if (res && res.classes) {
      for (const c of res.classes) {
        if ((c.endLine - c.startLine + 1) >= 20 || (c.methods && c.methods.length >= 2) || res.exports?.some(e => e.name === c.name)) {
          const cid = 'class:' + p + ':' + c.name;
          nodes.push({
            id: cid,
            type: 'class',
            name: c.name,
            filePath: p,
            lineRange: [c.startLine, c.endLine],
            summary: c.name + ' 类实现，封装了相关的状态和行为方法。',
            tags: ['class', 'oop'],
            complexity: 'moderate'
          });
          edges.push({
            source: nodeId,
            target: cid,
            type: 'contains',
            direction: 'forward',
            weight: 1.0
          });
        }
      }
    }
  }

  // Ensure output dir
  if (!fs.existsSync('.understand-anything/intermediate')) {
    fs.mkdirSync('.understand-anything/intermediate', { recursive: true });
  }

  fs.writeFileSync('.understand-anything/intermediate/batch-' + batchIndex + '.json', JSON.stringify({ nodes, edges }, null, 2), 'utf8');
}

processBatch(batch31Input, batch31Result, 31);
processBatch(batch32Input, batch32Result, 32);

console.log('Done!');
