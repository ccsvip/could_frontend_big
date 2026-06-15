const fs = require('fs');

const extractResultsPath = 'C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-5.json';
const batchInputPath = 'C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/batch-input-4.json';

const extractResults = JSON.parse(fs.readFileSync(extractResultsPath));
const batchInput = JSON.parse(fs.readFileSync(batchInputPath))[0];
const batchIndex = batchInput.batchIndex;

const nodes = [];
const edges = [];

const fileCategoryMap = {
  'code': 'file',
  'config': 'config',
  'docs': 'document',
  'infra': 'service',
  'data': 'table',
  'script': 'file',
  'markup': 'file'
};

const getSummaryAndTags = (path, type, name) => {
  if (path.endsWith('models.py')) return { summary: '该文件定义了应用的核心数据模型与相关数据库表结构，包含字段定义与关联关系。', tags: ['data-model', 'database', 'schema-definition'] };
  if (path.endsWith('views.py')) return { summary: '该文件包含了处理前端请求的API视图和业务逻辑接口，负责参数校验与响应。', tags: ['api-handler', 'controller', 'web-endpoint'] };
  if (path.endsWith('admin.py')) return { summary: '该文件配置了Django的后台管理界面视图，提供数据模型的可视化管理。', tags: ['admin-panel', 'configuration', 'management-ui'] };
  if (path.endsWith('serializers.py')) return { summary: '该文件定义了数据序列化器，用于在模型与API之间转换与验证数据。', tags: ['serialization', 'data-model', 'data-validation'] };
  if (path.endsWith('urls.py')) return { summary: '该文件配置了应用的URL路由映射，关联请求路径与对应的视图函数。', tags: ['routing', 'configuration', 'entry-point'] };
  if (path.endsWith('tests.py') || path.includes('/tests/')) return { summary: '该文件包含用于验证业务逻辑的自动化测试用例，确保系统稳定性。', tags: ['test', 'quality-assurance', 'unit-testing'] };
  if (path.endsWith('services.py')) return { summary: '该文件封装了应用的核心业务逻辑和服务层方法，分离控制器与业务实现。', tags: ['service', 'business-logic', 'core-implementation'] };
  if (path.endsWith('permissions.py')) return { summary: '该文件定义了系统访问权限与授权规则，保护数据和接口的安全。', tags: ['security', 'authorization', 'access-control'] };
  if (path.endsWith('tasks.py')) return { summary: '该文件包含后台异步执行的Celery任务，处理耗时计算与定时操作。', tags: ['background-task', 'async', 'job-queue'] };
  if (path.endsWith('test_utils.py')) return { summary: '该文件提供了用于辅助单元测试和集成测试的工具函数与基类。', tags: ['test', 'utility', 'testing-helpers'] };
  if (path.endsWith('managers.py')) return { summary: '该文件定义了Django模型的自定义Manager类，封装常用的查询逻辑。', tags: ['database', 'data-model', 'query-builder'] };
  if (path.endsWith('realtime.py')) return { summary: '该文件包含了处理实时WebSocket连接与消息广播的逻辑，用于设备的双向通信。', tags: ['websocket', 'realtime', 'event-handler'] };
  if (path.endsWith('business_cache.py')) return { summary: '该文件实现了针对业务数据的缓存机制与相关工具，以提高系统响应速度。', tags: ['cache', 'optimization', 'performance'] };
  if (path.endsWith('feishu.py')) return { summary: '该文件封装了与飞书（Feishu）API集成的相关服务接口，处理外部平台的交互。', tags: ['integration', 'third-party', 'external-api'] };

  if (type === 'function') {
    if (name && name.startsWith('test_')) return { summary: '测试用例函数，验证系统特定模块或功能是否正常运行。', tags: ['test', 'quality-assurance', 'test-case'] };
    if (name && name.startsWith('get_')) return { summary: '数据获取或查询函数，用于从数据库或缓存中检索信息。', tags: ['getter', 'utility', 'data-retrieval'] };
    return { summary: '提供特定的业务处理功能或辅助计算，作为模块内部的工具方法。', tags: ['utility', 'function', 'helper-method'] };
  }
  if (type === 'class') {
    if (name && name.endsWith('Admin')) return { summary: 'Django Admin后台管理界面的配置类，定义模型在后台的展示与操作。', tags: ['admin', 'configuration', 'ui-config'] };
    if (name && name.endsWith('Serializer')) return { summary: '定义数据结构和序列化逻辑的类，支持反序列化与字段验证。', tags: ['serialization', 'schema', 'data-mapping'] };
    if (name && name.endsWith('ViewSet') || name.endsWith('View')) return { summary: '处理特定资源HTTP请求的视图类，封装了增删改查等RESTful操作。', tags: ['api-handler', 'view', 'endpoint'] };
    if (name && name.endsWith('Test') || name.endsWith('Tests')) return { summary: '分组的自动化测试用例类，包含测试环境的初始化与资源清理。', tags: ['test', 'quality-assurance', 'test-suite'] };
    if (name && name.endsWith('Permission')) return { summary: '定义请求级别的访问权限控制类，实现细粒度的安全拦截。', tags: ['security', 'authorization', 'permission-check'] };
    return { summary: '封装了特定的数据结构或业务流程，作为面向对象设计的核心组件。', tags: ['class', 'component', 'business-object'] };
  }
  
  return { summary: '该文件包含了支持系统运行的基础代码或配置，提供通用的支撑能力。', tags: ['file', 'module', 'system-base'] };
};

const getComplexity = (lines) => {
  if (lines < 50) return 'simple';
  if (lines <= 200) return 'moderate';
  return 'complex';
};

extractResults.results.forEach(file => {
  const fileNodeType = fileCategoryMap[file.fileCategory] || 'file';
  const fileNodeId = `${fileNodeType}:${file.path}`;
  const { summary, tags } = getSummaryAndTags(file.path, fileNodeType, file.path.split('/').pop());
  
  nodes.push({
    id: fileNodeId,
    type: fileNodeType,
    name: file.path.split('/').pop(),
    filePath: file.path,
    summary,
    tags,
    complexity: getComplexity(file.nonEmptyLines || file.totalLines)
  });

  // Functions
  if (file.functions) {
    file.functions.forEach(func => {
      if ((func.endLine - func.startLine + 1) >= 10 || (file.exports && file.exports.some(e => e.name === func.name))) {
        const funcId = `function:${file.path}:${func.name}`;
        const fMeta = getSummaryAndTags(file.path, 'function', func.name);
        nodes.push({
          id: funcId,
          type: 'function',
          name: func.name,
          filePath: file.path,
          lineRange: [func.startLine, func.endLine],
          summary: fMeta.summary,
          tags: fMeta.tags,
          complexity: getComplexity(func.endLine - func.startLine + 1)
        });
        
        edges.push({
          source: fileNodeId,
          target: funcId,
          type: 'contains',
          direction: 'forward',
          weight: 1.0
        });
      }
    });
  }

  // Classes
  if (file.classes) {
    file.classes.forEach(cls => {
      if ((cls.endLine - cls.startLine + 1) >= 20 || (cls.methods && cls.methods.length >= 2) || (file.exports && file.exports.some(e => e.name === cls.name))) {
        const clsId = `class:${file.path}:${cls.name}`;
        const cMeta = getSummaryAndTags(file.path, 'class', cls.name);
        nodes.push({
          id: clsId,
          type: 'class',
          name: cls.name,
          filePath: file.path,
          lineRange: [cls.startLine, cls.endLine],
          summary: cMeta.summary,
          tags: cMeta.tags,
          complexity: getComplexity(cls.endLine - cls.startLine + 1)
        });
        
        edges.push({
          source: fileNodeId,
          target: clsId,
          type: 'contains',
          direction: 'forward',
          weight: 1.0
        });
      }
    });
  }
});

// Import edges from batchImportData
if (batchInput.batchImportData) {
  Object.keys(batchInput.batchImportData).forEach(filePath => {
    // Make sure we only emit for files in our batch
    if (extractResults.results.some(r => r.path === filePath)) {
      const imports = batchInput.batchImportData[filePath];
      imports.forEach(targetPath => {
        edges.push({
          source: `file:${filePath}`,
          target: `file:${targetPath}`,
          type: 'imports',
          direction: 'forward',
          weight: 0.7
        });
      });
    }
  });
}

extractResults.results.forEach(file => {
  if (file.callGraph) {
    file.callGraph.forEach(call => {
      const callerId = `function:${file.path}:${call.caller}`;
      const calleeId = `function:${file.path}:${call.callee}`;
      if (nodes.some(n => n.id === callerId) && nodes.some(n => n.id === calleeId)) {
        edges.push({
          source: callerId,
          target: calleeId,
          type: 'calls',
          direction: 'forward',
          weight: 0.8
        });
      }
    });
  }
});

const nodeCount = nodes.length;
const edgeCount = edges.length;

if (nodeCount <= 60 && edgeCount <= 120) {
  fs.writeFileSync(`C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate/batch-${batchIndex}.json`, JSON.stringify({ nodes, edges }, null, 2));
  console.log(`Wrote 1 part, nodes: ${nodeCount}, edges: ${edgeCount}`);
} else {
  const parts = Math.ceil(Math.max(nodeCount / 60, edgeCount / 120));
  
  // Sort files
  const files = extractResults.results.map(r => r.path).sort();
  const chunkSize = Math.ceil(files.length / parts);
  
  for (let k = 1; k <= parts; k++) {
    const partFiles = files.slice((k - 1) * chunkSize, k * chunkSize);
    const partNodes = nodes.filter(n => partFiles.includes(n.filePath));
    const partNodeIds = new Set(partNodes.map(n => n.id));
    const partEdges = edges.filter(e => partNodeIds.has(e.source));
    
    fs.writeFileSync(`C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate/batch-${batchIndex}-part-${k}.json`, JSON.stringify({ nodes: partNodes, edges: partEdges }, null, 2));
  }
  console.log(`Wrote ${parts} parts, total nodes: ${nodeCount}, total edges: ${edgeCount}`);
}
