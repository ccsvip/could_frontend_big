const fs = require('fs');
const path = require('path');

const summaries = {
  '.claude/skills/impeccable/reference/optimize.md': {
    summary: '性能与体验优化规范文档，提供针对前端界面及交互的极致优化指南。',
    tags: ['documentation', 'optimization', 'performance', 'skill']
  },
  '.claude/skills/impeccable/reference/overdrive.md': {
    summary: '高级与深度优化指南，探讨超越常规的极端性能和体验提升策略。',
    tags: ['documentation', 'advanced-optimization', 'performance', 'skill']
  },
  '.claude/skills/impeccable/reference/polish.md': {
    summary: '界面打磨和细节完善规范，指导如何提升前端视觉和交互的细腻度。',
    tags: ['documentation', 'ui-polish', 'design', 'skill']
  },
  '.claude/skills/impeccable/reference/product.md': {
    summary: '产品级考量和规范，关注功能与用户体验在产品层面的对齐与落地。',
    tags: ['documentation', 'product-design', 'user-experience', 'skill']
  },
  '.claude/skills/impeccable/reference/quieter.md': {
    summary: '降低视觉噪音、简化界面的设计指南，提倡简约和克制的设计哲学。',
    tags: ['documentation', 'minimalism', 'ui-design', 'skill']
  },
  '.claude/skills/impeccable/reference/shape.md': {
    summary: '界面形态和结构设计指南，涵盖从布局结构到组件形态的设计原则。',
    tags: ['documentation', 'layout-design', 'ui-structure', 'skill']
  },
  '.claude/skills/impeccable/reference/typeset.md': {
    summary: '排版和字体设计规范，包含字体选择、层级划分及可读性优化的详细规则。',
    tags: ['documentation', 'typography', 'design', 'skill']
  },
  '.claude/skills/improve-codebase-architecture/DEEPENING.md': {
    summary: '架构深化与重构指南，提供在现有代码基础上进行深层次模块解耦与优化的策略。',
    tags: ['documentation', 'architecture', 'refactoring', 'skill']
  },
  '.claude/skills/improve-codebase-architecture/HTML-REPORT.md': {
    summary: '架构分析 HTML 报告生成规范，指导如何将架构分析结果可视化并输出为报告。',
    tags: ['documentation', 'reporting', 'architecture', 'skill']
  },
  '.claude/skills/improve-codebase-architecture/INTERFACE-DESIGN.md': {
    summary: '接口设计与抽象规范，定义模块边界和接口契约的设计原则。',
    tags: ['documentation', 'interface-design', 'architecture', 'skill']
  },
  '.claude/skills/improve-codebase-architecture/LANGUAGE.md': {
    summary: '架构领域的统一语言规范，确保在设计和重构时使用一致的业务和技术词汇。',
    tags: ['documentation', 'ubiquitous-language', 'architecture', 'skill']
  },
  '.claude/skills/improve-codebase-architecture/SKILL.md': {
    summary: '架构优化技能的整体说明文档，介绍如何发现和改进代码库架构问题。',
    tags: ['documentation', 'architecture-improvement', 'overview', 'skill']
  },
  '.claude/skills/prototype/LOGIC.md': {
    summary: '原型开发中的逻辑层实现指南，指导如何快速构建用于验证业务逻辑的终端应用。',
    tags: ['documentation', 'prototyping', 'business-logic', 'skill']
  },
  '.claude/skills/prototype/SKILL.md': {
    summary: '原型开发技能的整体说明文档，提供快速构建丢弃式原型以验证设计的流程指引。',
    tags: ['documentation', 'prototyping', 'overview', 'skill']
  },
  '.claude/skills/prototype/UI.md': {
    summary: '原型开发中的用户界面实现指南，介绍如何快速搭建多种 UI 变体并进行对比。',
    tags: ['documentation', 'prototyping', 'ui-design', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/SKILL.md': {
    summary: 'Matt Pocock 技能的整体说明文档，描述相关技能工具的初始化与配置流程。',
    tags: ['documentation', 'setup', 'overview', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/domain.md': {
    summary: '领域模型相关的设置规范，指导如何定义和梳理业务领域知识。',
    tags: ['documentation', 'domain-driven-design', 'setup', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/issue-tracker-github.md': {
    summary: 'GitHub Issue Tracker 的集成设置规范，说明如何对接和管理 GitHub 上的开发任务。',
    tags: ['documentation', 'github', 'issue-tracking', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/issue-tracker-gitlab.md': {
    summary: 'GitLab Issue Tracker 的集成设置规范，说明如何对接和管理 GitLab 上的开发任务。',
    tags: ['documentation', 'gitlab', 'issue-tracking', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/issue-tracker-local.md': {
    summary: '本地 Issue Tracker 的设置规范，为离线或本地开发提供任务追踪方案。',
    tags: ['documentation', 'local-environment', 'issue-tracking', 'skill']
  },
  '.claude/skills/setup-matt-pocock-skills/triage-labels.md': {
    summary: '缺陷分流与标签管理规范，定义如何通过标签体系管理和分发工单。',
    tags: ['documentation', 'issue-triage', 'label-management', 'skill']
  }
};

function processBatch(batchIndex) {
  const extractResultsPath = "C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-" + batchIndex + ".json";
  if (!fs.existsSync(extractResultsPath)) {
    console.error("Extract results not found for batch " + batchIndex);
    return;
  }
  
  const extractResults = JSON.parse(fs.readFileSync(extractResultsPath, 'utf8'));
  
  const nodes = [];
  const edges = [];
  
  for (const fileResult of extractResults.results) {
    const filePath = fileResult.path;
    const name = filePath.split('/').pop();
    const info = summaries[filePath] || {
      summary: "关于 " + name + " 的说明文档。",
      tags: ['documentation', 'skill']
    };
    
    // File Node
    const fileNode = {
      id: "document:" + filePath,
      type: 'document',
      name: name,
      filePath: filePath,
      summary: info.summary,
      tags: info.tags,
      complexity: fileResult.totalLines > 200 ? 'complex' : (fileResult.totalLines > 50 ? 'moderate' : 'simple')
    };
    
    nodes.push(fileNode);
  }
  
  const outputJson = {
    nodes: nodes,
    edges: edges
  };
  
  const outputPath = "C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate/batch-" + batchIndex + ".json";
  fs.writeFileSync(outputPath, JSON.stringify(outputJson, null, 2), 'utf8');
  console.log("Wrote batch " + batchIndex + " with " + nodes.length + " nodes and " + edges.length + " edges");
}

[18, 19, 20, 21].forEach(processBatch);