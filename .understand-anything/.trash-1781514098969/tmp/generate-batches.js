const fs = require('fs');
const path = require('path');

const projectRoot = 'C:\\SVN_CODE\\branches\\real\\could_frontend';
const intermediateDir = path.join(projectRoot, '.understand-anything', 'intermediate');

if (!fs.existsSync(intermediateDir)) {
  fs.mkdirSync(intermediateDir, { recursive: true });
}

// Batch 15
const batch15Nodes = [
  {
    "id": "document:.claude/skills/grill-with-docs/ADR-FORMAT.md",
    "type": "document",
    "name": "ADR-FORMAT.md",
    "filePath": ".claude/skills/grill-with-docs/ADR-FORMAT.md",
    "summary": "规定了架构决策记录（ADR）的标准格式、模板结构、编号规则以及何时应当引入新的ADR。",
    "tags": ["documentation", "architecture", "guidelines"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/grill-with-docs/CONTEXT-FORMAT.md",
    "type": "document",
    "name": "CONTEXT-FORMAT.md",
    "filePath": ".claude/skills/grill-with-docs/CONTEXT-FORMAT.md",
    "summary": "定义了项目上下文文档（CONTEXT.md）的维护规范、内容结构、排版规则及其在单体与多模块仓库中的使用方式。",
    "tags": ["documentation", "context", "guidelines"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/grill-with-docs/SKILL.md",
    "type": "document",
    "name": "SKILL.md",
    "filePath": ".claude/skills/grill-with-docs/SKILL.md",
    "summary": "定义了 grill-with-docs 技能的核心指令，指导AI如何在对话中利用领域术语挑战用户方案，并在讨论过程中内联更新上下文和产出ADR。",
    "tags": ["documentation", "skill", "guidelines"],
    "complexity": "moderate"
  }
];

fs.writeFileSync(
  path.join(intermediateDir, 'batch-15.json'),
  JSON.stringify({ nodes: batch15Nodes, edges: [] }, null, 2)
);

// Batch 16
const batch16Nodes = [
  {
    "id": "config:.claude/skills/impeccable/agents/impeccable_asset_producer.toml",
    "type": "config",
    "name": "impeccable_asset_producer.toml",
    "filePath": ".claude/skills/impeccable/agents/impeccable_asset_producer.toml",
    "summary": "impeccable 技能中负责生成资产文件的智能体配置，定义了提示词和相关行为约束。",
    "tags": ["configuration", "agent", "skill"],
    "complexity": "moderate"
  },
  {
    "id": "config:.claude/skills/impeccable/agents/impeccable_manual_edit_applier.toml",
    "type": "config",
    "name": "impeccable_manual_edit_applier.toml",
    "filePath": ".claude/skills/impeccable/agents/impeccable_manual_edit_applier.toml",
    "summary": "impeccable 技能中负责应用手动代码修改的智能体配置，包含差异解析和文件更新规则。",
    "tags": ["configuration", "agent", "skill"],
    "complexity": "moderate"
  },
  {
    "id": "config:.claude/skills/impeccable/agents/openai.yaml",
    "type": "config",
    "name": "openai.yaml",
    "filePath": ".claude/skills/impeccable/agents/openai.yaml",
    "summary": "OpenAI 接口调用的配置文件，声明了与大语言模型交互时的参数及接口映射。",
    "tags": ["configuration", "llm", "skill"],
    "complexity": "simple"
  }
];

fs.writeFileSync(
  path.join(intermediateDir, 'batch-16.json'),
  JSON.stringify({ nodes: batch16Nodes, edges: [] }, null, 2)
);

// Batch 17
const batch17Nodes = [
  {
    "id": "document:.claude/skills/impeccable/reference/adapt.md",
    "type": "document",
    "name": "adapt.md",
    "filePath": ".claude/skills/impeccable/reference/adapt.md",
    "summary": "提供了前端界面适配的参考指南，涵盖响应式设计、跨平台兼容性及多终端布局策略。",
    "tags": ["documentation", "design", "responsive"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/animate.md",
    "type": "document",
    "name": "animate.md",
    "filePath": ".claude/skills/impeccable/reference/animate.md",
    "summary": "记录了界面动画与过渡效果的设计原则，指导如何通过动效提升用户体验与视觉反馈。",
    "tags": ["documentation", "design", "animation"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/audit.md",
    "type": "document",
    "name": "audit.md",
    "filePath": ".claude/skills/impeccable/reference/audit.md",
    "summary": "定义了UI/UX设计的审查标准与流程，包括可用性评估、无障碍检查及视觉一致性核验。",
    "tags": ["documentation", "audit", "ui-ux"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/bolder.md",
    "type": "document",
    "name": "bolder.md",
    "filePath": ".claude/skills/impeccable/reference/bolder.md",
    "summary": "介绍如何通过强化排版、色彩对比与视觉层级，使平淡的界面设计变得更具视觉冲击力和现代感。",
    "tags": ["documentation", "design", "visual"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/brand.md",
    "type": "document",
    "name": "brand.md",
    "filePath": ".claude/skills/impeccable/reference/brand.md",
    "summary": "阐述了如何在界面实现中融入品牌调性，确保排版、色彩和组件风格与品牌视觉规范对齐。",
    "tags": ["documentation", "design", "branding"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/clarify.md",
    "type": "document",
    "name": "clarify.md",
    "filePath": ".claude/skills/impeccable/reference/clarify.md",
    "summary": "指导如何简化复杂界面，通过优化信息架构、减轻认知负荷与改善布局来提升用户清晰度。",
    "tags": ["documentation", "design", "usability"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/codex.md",
    "type": "document",
    "name": "codex.md",
    "filePath": ".claude/skills/impeccable/reference/codex.md",
    "summary": "设计系统的核心规范文件，整理了组件库、设计令牌及前端视觉标准的基础原则。",
    "tags": ["documentation", "design-system", "guidelines"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/colorize.md",
    "type": "document",
    "name": "colorize.md",
    "filePath": ".claude/skills/impeccable/reference/colorize.md",
    "summary": "提供了色彩应用的深入指南，涵盖调色板生成、深色模式适配、对比度要求及色彩心理学。",
    "tags": ["documentation", "design", "color"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/craft.md",
    "type": "document",
    "name": "craft.md",
    "filePath": ".claude/skills/impeccable/reference/craft.md",
    "summary": "强调界面设计中的细节打磨，指导如何通过精确的间距、阴影和微小对齐提升整体专业感。",
    "tags": ["documentation", "design", "polish"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/critique.md",
    "type": "document",
    "name": "critique.md",
    "filePath": ".claude/skills/impeccable/reference/critique.md",
    "summary": "极其详尽的设计评审指南，提供从布局、排版到交互行为的全方位批评与改进方法论。",
    "tags": ["documentation", "design", "review"],
    "complexity": "complex"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/delight.md",
    "type": "document",
    "name": "delight.md",
    "filePath": ".claude/skills/impeccable/reference/delight.md",
    "summary": "介绍如何通过巧妙的微交互、空状态设计与彩蛋等手段增加产品的使用趣味性与用户愉悦感。",
    "tags": ["documentation", "design", "ux"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/distill.md",
    "type": "document",
    "name": "distill.md",
    "filePath": ".claude/skills/impeccable/reference/distill.md",
    "summary": "指导如何对冗长或复杂的UI组件与文案进行提炼与精简，保留最核心的用户价值。",
    "tags": ["documentation", "design", "simplification"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/document.md",
    "type": "document",
    "name": "document.md",
    "filePath": ".claude/skills/impeccable/reference/document.md",
    "summary": "说明了如何规范地编写设计决策、组件文档及使用场景，保障团队内外对界面的理解一致。",
    "tags": ["documentation", "design", "guidelines"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/extract.md",
    "type": "document",
    "name": "extract.md",
    "filePath": ".claude/skills/impeccable/reference/extract.md",
    "summary": "描述了从现有页面中提取通用组件与设计模式的最佳实践，以提升代码与设计的复用率。",
    "tags": ["documentation", "design", "refactoring"],
    "complexity": "simple"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/harden.md",
    "type": "document",
    "name": "harden.md",
    "filePath": ".claude/skills/impeccable/reference/harden.md",
    "summary": "关注前端界面的健壮性与边界情况处理，涵盖长文本截断、加载状态、错误提示及防御性样式设计。",
    "tags": ["documentation", "design", "robustness"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/init.md",
    "type": "document",
    "name": "init.md",
    "filePath": ".claude/skills/impeccable/reference/init.md",
    "summary": "界面设计项目的初始化指南，指导如何从零构建视觉骨架、确立基础设计令牌及结构。",
    "tags": ["documentation", "design", "setup"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/interaction-design.md",
    "type": "document",
    "name": "interaction-design.md",
    "filePath": ".claude/skills/impeccable/reference/interaction-design.md",
    "summary": "探讨核心交互设计原则，包括状态流转、用户输入反馈及表单处理的最佳实践。",
    "tags": ["documentation", "design", "interaction"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/layout.md",
    "type": "document",
    "name": "layout.md",
    "filePath": ".claude/skills/impeccable/reference/layout.md",
    "summary": "深入剖析界面布局策略，涵盖网格系统、留白运用及各种经典排版范式。",
    "tags": ["documentation", "design", "layout"],
    "complexity": "moderate"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/live.md",
    "type": "document",
    "name": "live.md",
    "filePath": ".claude/skills/impeccable/reference/live.md",
    "summary": "详细记录了浏览器内实时设计与调整（Live）的工作流，包括元素抓取、状态注入及实时变体生成机制。",
    "tags": ["documentation", "design", "workflow"],
    "complexity": "complex"
  },
  {
    "id": "document:.claude/skills/impeccable/reference/onboard.md",
    "type": "document",
    "name": "onboard.md",
    "filePath": ".claude/skills/impeccable/reference/onboard.md",
    "summary": "用户引导体验与空状态设计指南，指导如何降低新用户上手门槛并促进核心功能发现。",
    "tags": ["documentation", "design", "onboarding"],
    "complexity": "moderate"
  }
];

fs.writeFileSync(
  path.join(intermediateDir, 'batch-17.json'),
  JSON.stringify({ nodes: batch17Nodes, edges: [] }, null, 2)
);

console.log('Successfully wrote batch-15.json, batch-16.json, and batch-17.json');