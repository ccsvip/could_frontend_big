const fs = require('fs');

const data = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-4.json', 'utf8'));
const input = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-analyzer-input-4.json', 'utf8'));

const batchImportData = input.batchImportData || {};

const nodes = [];
const edges = [];

function getComplexity(lines) {
  if (lines < 50) return 'simple';
  if (lines < 200) return 'moderate';
  return 'complex';
}

function getSummaryAndTags(path) {
  let summary = '提供前端组件或页面视图，用于处理相关业务逻辑和用户交互。';
  let tags = ['frontend', 'react', 'view'];

  if (path.includes('asr-management')) {
    summary = '语音识别（ASR）管理页面，包含服务状态监控、实时测试和替换规则配置。';
    tags.push('asr', 'management', 'voice');
  } else if (path.includes('asr-settings')) {
    summary = '语音识别（ASR）系统设置页面，用于配置ASR服务的基础参数。';
    tags.push('asr', 'settings', 'configuration');
  } else if (path.includes('command-management/command-export-format')) {
    summary = '定义指令导出的格式标准和相关工具函数。';
    tags.push('command', 'export', 'utility');
  } else if (path.includes('command-management/command-export-state')) {
    summary = '管理指令导出的状态和进度信息。';
    tags.push('command', 'export', 'state');
  } else if (path.includes('command-management/export')) {
    summary = '指令管理模块的导出页面，支持选择不同格式导出指令数据。';
    tags.push('command', 'export', 'page');
  } else if (path.includes('command-management/groups')) {
    summary = '指令分组管理视图，用于维护和分类相关联的指令集合。';
    tags.push('command', 'group', 'management');
  } else if (path.includes('command-management/index')) {
    summary = '指令管理入口页面，集成各级指令、任务和分组的配置入口。';
    tags.push('command', 'entry-point', 'management');
  } else if (path.includes('command-management/points')) {
    summary = '埋点或关键点管理页面，用于配置指令执行路径中的关键位置点。';
    tags.push('command', 'points', 'management');
  } else if (path.includes('command-management/task-step-form-list')) {
    summary = '任务步骤表单列表组件，用于编辑和编排指令任务的具体执行步骤。';
    tags.push('command', 'task', 'form', 'component');
  } else if (path.includes('command-management/tasks')) {
    summary = '指令任务管理页面，用于创建和维护由多个指令步骤组成的执行任务。';
    tags.push('command', 'task', 'management');
  } else if (path.includes('command-management/workspace')) {
    summary = '指令管理的工作区视图，提供可视化的指令编排和配置环境。';
    tags.push('command', 'workspace', 'management');
  } else if (path.includes('device-authorization-center')) {
    summary = '设备授权中心页面，处理设备接入请求、授权审批和激活日志查询。';
    tags.push('device', 'authorization', 'security');
  } else if (path.includes('device-management')) {
    summary = '设备管理页面，用于查看、控制和维护已接入系统的数字人终端设备。';
    tags.push('device', 'management', 'hardware');
  } else if (path.includes('employee-management')) {
    summary = '员工或企业子用户管理页面，包括人员列表、角色分配和密码重置功能。';
    tags.push('employee', 'management', 'rbac');
  } else if (path.includes('force-password-change')) {
    summary = '强制密码修改页面，处理首次登录或密码过期时的重置逻辑。';
    tags.push('auth', 'password', 'security');
  } else if (path.includes('knowledge-base')) {
    summary = '知识库管理页面，提供知识文档的上传、解析状态查看和内容审核功能。';
    tags.push('knowledge-base', 'document', 'management');
  } else if (path.includes('llm-management')) {
    summary = '大语言模型（LLM）提供商管理页面，用于配置和测试底层大模型接口。';
    tags.push('llm', 'provider', 'management');
  } else if (path.includes('llm-settings')) {
    summary = '大语言模型设置页面，针对具体租户或应用配置模型参数和默认调用选项。';
    tags.push('llm', 'settings', 'configuration');
  } else if (path.includes('log-management')) {
    summary = '审计日志管理页面，提供系统操作日志的查询和追踪能力。';
    tags.push('log', 'audit', 'management');
  } else if (path.includes('login')) {
    summary = '系统登录页面，负责用户身份验证、凭证状态校验及登录异常处理。';
    tags.push('auth', 'login', 'entry-point');
  } else if (path.includes('minio-settings')) {
    summary = 'MinIO对象存储设置页面，用于配置存储桶策略和视频等资源的配额。';
    tags.push('storage', 'minio', 'settings');
  } else if (path.includes('model-management')) {
    summary = '数字人模型资产管理页面，维护3D模型资源和相关配置信息。';
    tags.push('model', 'asset', 'management');
  } else if (path.includes('resource-management')) {
    summary = '媒体资源管理页面，支持图片、视频等多媒体文件的上传和统一管理。';
    tags.push('resource', 'media', 'management');
  } else if (path.includes('scrolling-text-management')) {
    summary = '走马灯（滚动字幕）管理页面，用于配置展示在数字人屏幕上的滚动文本内容。';
    tags.push('scrolling-text', 'ui', 'management');
  } else if (path.includes('settings-llm')) {
    summary = '全局或高级大模型设置面板，配置模型分配策略与底层能力权限。';
    tags.push('llm', 'settings', 'admin');
  } else if (path.includes('tenant-management')) {
    summary = '租户管理页面，负责多租户体系下的企业账号创建、权限分配和配额管理。';
    tags.push('tenant', 'management', 'saas');
  } else if (path.includes('voice-tone-management')) {
    summary = '音色管理页面，用于配置和维护TTS语音合成时的发音人及音色参数。';
    tags.push('voice', 'tts', 'management');
  }

  return { summary, tags: tags.slice(0, 5) };
}

data.results.forEach(fileResult => {
  const fileId = `file:${fileResult.path}`;
  const complexity = getComplexity(fileResult.nonEmptyLines);
  const { summary, tags } = getSummaryAndTags(fileResult.path);
  
  nodes.push({
    id: fileId,
    type: 'file',
    name: fileResult.path.split('/').pop(),
    filePath: fileResult.path,
    summary,
    tags,
    complexity
  });

  // Export check
  const exportedNames = new Set((fileResult.exports || []).map(e => e.name));

  // Functions
  if (fileResult.functions) {
    fileResult.functions.forEach(fn => {
      const lineCount = fn.endLine - fn.startLine + 1;
      const isExported = exportedNames.has(fn.name);
      
      // Significance filter
      if (lineCount >= 10 || isExported) {
        const fnId = `function:${fileResult.path}:${fn.name}`;
        nodes.push({
          id: fnId,
          type: 'function',
          name: fn.name,
          filePath: fileResult.path,
          lineRange: [fn.startLine, fn.endLine],
          summary: `函数 ${fn.name}，负责处理特定逻辑或组件渲染。`,
          tags: ['function', 'logic', isExported ? 'exported' : 'internal'],
          complexity: getComplexity(lineCount)
        });

        edges.push({
          source: fileId,
          target: fnId,
          type: 'contains',
          direction: 'forward',
          weight: 1.0
        });

        if (isExported) {
          edges.push({
            source: fileId,
            target: fnId,
            type: 'exports',
            direction: 'forward',
            weight: 0.8
          });
        }
      }
    });
  }

  // Classes
  if (fileResult.classes) {
    fileResult.classes.forEach(cls => {
      const lineCount = cls.endLine - cls.startLine + 1;
      const isExported = exportedNames.has(cls.name);
      const methodCount = (cls.methods || []).length;
      
      if (lineCount >= 20 || methodCount >= 2 || isExported) {
        const clsId = `class:${fileResult.path}:${cls.name}`;
        nodes.push({
          id: clsId,
          type: 'class',
          name: cls.name,
          filePath: fileResult.path,
          lineRange: [cls.startLine, cls.endLine],
          summary: `类 ${cls.name}，封装了相关的状态和行为逻辑。`,
          tags: ['class', 'component', isExported ? 'exported' : 'internal'],
          complexity: getComplexity(lineCount)
        });

        edges.push({
          source: fileId,
          target: clsId,
          type: 'contains',
          direction: 'forward',
          weight: 1.0
        });

        if (isExported) {
          edges.push({
            source: fileId,
            target: clsId,
            type: 'exports',
            direction: 'forward',
            weight: 0.8
          });
        }
      }
    });
  }

  // Import Edges
  const imports = batchImportData[fileResult.path] || [];
  imports.forEach(targetPath => {
    edges.push({
      source: fileId,
      target: `file:${targetPath}`,
      type: 'imports',
      direction: 'forward',
      weight: 0.7
    });
  });
});

// Extra neighborMap checks for cross-batch edges (e.g., calls) can be added here if desired.

// Output handling
const outDir = 'C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate';
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

// Split logic based on Step B
const BATCH_INDEX = 4;
const maxNodes = 60;
const maxEdges = 120;
const nodeCount = nodes.length;
const edgeCount = edges.length;

if (nodeCount <= maxNodes && edgeCount <= maxEdges) {
  fs.writeFileSync(`${outDir}/batch-${BATCH_INDEX}.json`, JSON.stringify({ nodes, edges }, null, 2));
  console.log(`Wrote 1 part. Total nodes: ${nodeCount}, edges: ${edgeCount}`);
} else {
  const parts = Math.ceil(Math.max(nodeCount / maxNodes, edgeCount / maxEdges));
  const files = data.results.map(r => r.path).sort();
  
  for (let i = 0; i < parts; i++) {
    const startIdx = Math.floor((i * files.length) / parts);
    const endIdx = Math.floor(((i + 1) * files.length) / parts);
    const partFiles = new Set(files.slice(startIdx, endIdx));
    
    const partNodes = nodes.filter(n => {
      // Find the file path from the node id (e.g. file:web/src... or function:web/src...)
      // Because we split by files and node ID has the file path
      let np = n.id.replace(/^(file|function|class):/, '');
      np = np.split(':')[0]; // get the path part
      return partFiles.has(np);
    });
    
    const partNodeIds = new Set(partNodes.map(n => n.id));
    const partEdges = edges.filter(e => partNodeIds.has(e.source));
    
    fs.writeFileSync(`${outDir}/batch-${BATCH_INDEX}-part-${i + 1}.json`, JSON.stringify({ nodes: partNodes, edges: partEdges }, null, 2));
    console.log(`Wrote part ${i + 1}. Nodes: ${partNodes.length}, Edges: ${partEdges.length}`);
  }
}
