const fs = require('fs');
const path = require('path');

const outDir = 'C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate';

const batch26 = {
  nodes: [
    {
      id: 'document:backend/AGENTS.md',
      type: 'document',
      name: 'AGENTS.md',
      filePath: 'backend/AGENTS.md',
      summary: '后端模块的开发协作规范与架构指南，包含核心约定和模块拆分说明。',
      tags: ['documentation', 'development', 'architecture'],
      complexity: 'moderate'
    },
    {
      id: 'document:backend/CLAUDE.md',
      type: 'document',
      name: 'CLAUDE.md',
      filePath: 'backend/CLAUDE.md',
      summary: '为 AI 辅助开发提供的后端模块专属指南，记录常见问题解答与变更日志。',
      tags: ['documentation', 'development', 'ai-guide'],
      complexity: 'moderate'
    },
    {
      id: 'config:backend/requirements.txt',
      type: 'config',
      name: 'requirements.txt',
      filePath: 'backend/requirements.txt',
      summary: 'Python 后端服务的依赖清单，列出所有必要的 Pip 包及版本要求。',
      tags: ['configuration', 'dependency', 'python'],
      complexity: 'simple'
    }
  ],
  edges: []
};

const batch27 = {
  nodes: [
    {
      id: 'document:docs/superpowers/plans/2026-06-04-minio-settings.md',
      type: 'document',
      name: '2026-06-04-minio-settings.md',
      filePath: 'docs/superpowers/plans/2026-06-04-minio-settings.md',
      summary: 'MinIO 对象存储相关配置项的开发与调整计划文档。',
      tags: ['documentation', 'planning', 'storage'],
      complexity: 'moderate'
    },
    {
      id: 'document:docs/superpowers/plans/2026-06-05-asr-settings.md',
      type: 'document',
      name: '2026-06-05-asr-settings.md',
      filePath: 'docs/superpowers/plans/2026-06-05-asr-settings.md',
      summary: '语音识别 (ASR) 配置管理模块的开发计划及实现细节。',
      tags: ['documentation', 'planning', 'speech-recognition'],
      complexity: 'complex'
    },
    {
      id: 'document:docs/superpowers/plans/2026-06-05-audit-log-management.md',
      type: 'document',
      name: '2026-06-05-audit-log-management.md',
      filePath: 'docs/superpowers/plans/2026-06-05-audit-log-management.md',
      summary: '系统审计日志管理功能的详细规划文档，涵盖记录策略与展示方案。',
      tags: ['documentation', 'planning', 'audit', 'security'],
      complexity: 'complex'
    },
    {
      id: 'document:docs/superpowers/plans/2026-06-06-login-command-center.md',
      type: 'document',
      name: '2026-06-06-login-command-center.md',
      filePath: 'docs/superpowers/plans/2026-06-06-login-command-center.md',
      summary: '登录中枢系统与命令中心的开发演进计划。',
      tags: ['documentation', 'planning', 'authentication', 'entry-point'],
      complexity: 'complex'
    },
    {
      id: 'document:docs/superpowers/plans/2026-06-10-llm-settings.md',
      type: 'document',
      name: '2026-06-10-llm-settings.md',
      filePath: 'docs/superpowers/plans/2026-06-10-llm-settings.md',
      summary: '大型语言模型 (LLM) 服务集成与参数配置的综合开发计划文档。',
      tags: ['documentation', 'planning', 'llm', 'configuration'],
      complexity: 'complex'
    },
    {
      id: 'document:docs/superpowers/plans/2026-06-15-tts-settings.md',
      type: 'document',
      name: '2026-06-15-tts-settings.md',
      filePath: 'docs/superpowers/plans/2026-06-15-tts-settings.md',
      summary: '语音合成 (TTS) 相关配置的系统开发与接入计划说明。',
      tags: ['documentation', 'planning', 'text-to-speech'],
      complexity: 'complex'
    }
  ],
  edges: []
};

const batch28 = {
  nodes: [
    {
      id: 'document:docs/superpowers/specs/2026-06-05-asr-settings-design.md',
      type: 'document',
      name: '2026-06-05-asr-settings-design.md',
      filePath: 'docs/superpowers/specs/2026-06-05-asr-settings-design.md',
      summary: '语音识别 (ASR) 配置模块的系统设计与规范说明。',
      tags: ['documentation', 'specification', 'speech-recognition'],
      complexity: 'moderate'
    },
    {
      id: 'document:docs/superpowers/specs/2026-06-05-audit-log-management-design.md',
      type: 'document',
      name: '2026-06-05-audit-log-management-design.md',
      filePath: 'docs/superpowers/specs/2026-06-05-audit-log-management-design.md',
      summary: '系统审计日志管理功能的设计规范及架构文档。',
      tags: ['documentation', 'specification', 'audit', 'security'],
      complexity: 'moderate'
    },
    {
      id: 'document:docs/superpowers/specs/2026-06-06-login-command-center-design.md',
      type: 'document',
      name: '2026-06-06-login-command-center-design.md',
      filePath: 'docs/superpowers/specs/2026-06-06-login-command-center-design.md',
      summary: '统一登录入口与指挥中心的设计说明及交互规范。',
      tags: ['documentation', 'specification', 'authentication', 'entry-point'],
      complexity: 'moderate'
    },
    {
      id: 'document:docs/superpowers/specs/2026-06-11-default-employee-access-design.md',
      type: 'document',
      name: '2026-06-11-default-employee-access-design.md',
      filePath: 'docs/superpowers/specs/2026-06-11-default-employee-access-design.md',
      summary: '员工默认权限分配机制的设计与安全访问控制规范。',
      tags: ['documentation', 'specification', 'authorization', 'security'],
      complexity: 'simple'
    }
  ],
  edges: []
};

const batch29 = {
  nodes: [
    {
      id: 'document:flow-web/my-video/AGENTS.md',
      type: 'document',
      name: 'AGENTS.md',
      filePath: 'flow-web/my-video/AGENTS.md',
      summary: '视频流处理相关前端模块的开发与协同规范文档。',
      tags: ['documentation', 'development', 'architecture'],
      complexity: 'simple'
    },
    {
      id: 'document:flow-web/my-video/CLAUDE.md',
      type: 'document',
      name: 'CLAUDE.md',
      filePath: 'flow-web/my-video/CLAUDE.md',
      summary: '视频流模块的 AI 开发指南及项目背景说明文档。',
      tags: ['documentation', 'development', 'ai-guide'],
      complexity: 'simple'
    },
    {
      id: 'config:flow-web/my-video/hyperframes.json',
      type: 'config',
      name: 'hyperframes.json',
      filePath: 'flow-web/my-video/hyperframes.json',
      summary: '视频超帧或关键帧处理相关的元数据配置文件。',
      tags: ['configuration', 'video', 'metadata'],
      complexity: 'simple'
    },
    {
      id: 'file:flow-web/my-video/index.html',
      type: 'file',
      name: 'index.html',
      filePath: 'flow-web/my-video/index.html',
      summary: '视频流展示模块的主页入口文件，包含播放器结构与必要脚本。',
      tags: ['entry-point', 'markup', 'video-player'],
      complexity: 'complex'
    },
    {
      id: 'config:flow-web/my-video/meta.json',
      type: 'config',
      name: 'meta.json',
      filePath: 'flow-web/my-video/meta.json',
      summary: '视频工程项目的核心元数据描述文件。',
      tags: ['configuration', 'metadata', 'video'],
      complexity: 'simple'
    },
    {
      id: 'config:flow-web/my-video/package.json',
      type: 'config',
      name: 'package.json',
      filePath: 'flow-web/my-video/package.json',
      summary: '视频流模块的 Node.js 依赖配置与脚本执行入口。',
      tags: ['configuration', 'dependency', 'build-system'],
      complexity: 'simple'
    }
  ],
  edges: [
    {
      source: 'config:flow-web/my-video/package.json',
      target: 'file:flow-web/my-video/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    },
    {
      source: 'config:flow-web/my-video/meta.json',
      target: 'file:flow-web/my-video/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    },
    {
      source: 'config:flow-web/my-video/hyperframes.json',
      target: 'file:flow-web/my-video/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    }
  ]
};

const batch30 = {
  nodes: [
    {
      id: 'document:web/AGENTS.md',
      type: 'document',
      name: 'AGENTS.md',
      filePath: 'web/AGENTS.md',
      summary: '前端 React 项目的核心协作约定、目录结构及开发准则。',
      tags: ['documentation', 'development', 'frontend'],
      complexity: 'moderate'
    },
    {
      id: 'document:web/CLAUDE.md',
      type: 'document',
      name: 'CLAUDE.md',
      filePath: 'web/CLAUDE.md',
      summary: '前端项目专属 AI 辅助开发指南与常见问题收录。',
      tags: ['documentation', 'development', 'ai-guide'],
      complexity: 'moderate'
    },
    {
      id: 'file:web/asr-replacement-test.html',
      type: 'file',
      name: 'asr-replacement-test.html',
      filePath: 'web/asr-replacement-test.html',
      summary: '用于测试语音识别 (ASR) 替换方案的独立 HTML 测试页面，包含丰富的交互与数据展示。',
      tags: ['test', 'markup', 'speech-recognition'],
      complexity: 'complex'
    },
    {
      id: 'file:web/index.html',
      type: 'file',
      name: 'index.html',
      filePath: 'web/index.html',
      summary: '前端单页应用 (SPA) 的 HTML 骨架与应用挂载点。',
      tags: ['entry-point', 'markup', 'frontend'],
      complexity: 'simple'
    },
    {
      id: 'file:web/multi-tenant-design.html',
      type: 'file',
      name: 'multi-tenant-design.html',
      filePath: 'web/multi-tenant-design.html',
      summary: '多租户架构设计原型的静态展示或说明页面。',
      tags: ['markup', 'design-prototype', 'architecture'],
      complexity: 'complex'
    },
    {
      id: 'config:web/package.json',
      type: 'config',
      name: 'package.json',
      filePath: 'web/package.json',
      summary: '前端工程依赖配置中心，定义项目元数据、启动脚本与第三方库。',
      tags: ['configuration', 'dependency', 'build-system'],
      complexity: 'simple'
    },
    {
      id: 'config:web/tsconfig.app.json',
      type: 'config',
      name: 'tsconfig.app.json',
      filePath: 'web/tsconfig.app.json',
      summary: '应用层专属 TypeScript 编译选项配置，确保业务代码的类型校验。',
      tags: ['configuration', 'typescript', 'frontend'],
      complexity: 'simple'
    },
    {
      id: 'config:web/tsconfig.json',
      type: 'config',
      name: 'tsconfig.json',
      filePath: 'web/tsconfig.json',
      summary: 'TypeScript 主配置文件，继承并组织其他子模块编译设定。',
      tags: ['configuration', 'typescript', 'build-system'],
      complexity: 'simple'
    },
    {
      id: 'config:web/tsconfig.node.json',
      type: 'config',
      name: 'tsconfig.node.json',
      filePath: 'web/tsconfig.node.json',
      summary: 'Node 环境下构建脚本专属 TypeScript 编译选项配置文件。',
      tags: ['configuration', 'typescript', 'build-system'],
      complexity: 'simple'
    }
  ],
  edges: [
    {
      source: 'config:web/package.json',
      target: 'file:web/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    },
    {
      source: 'config:web/tsconfig.json',
      target: 'file:web/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    },
    {
      source: 'config:web/tsconfig.app.json',
      target: 'file:web/index.html',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    },
    {
      source: 'config:web/tsconfig.node.json',
      target: 'config:web/package.json',
      type: 'configures',
      direction: 'forward',
      weight: 0.6
    }
  ]
};

const writeBatch = (i, data) => {
  fs.writeFileSync(path.join(outDir, 'batch-' + i + '.json'), JSON.stringify(data, null, 2));
};

writeBatch(26, batch26);
writeBatch(27, batch27);
writeBatch(28, batch28);
writeBatch(29, batch29);
writeBatch(30, batch30);
console.log('Successfully wrote batches 26, 27, 28, 29, 30.');
