const fs = require('fs');

const inputData = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-analyzer-input-3.json', 'utf8'));
const extractData = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-3.json', 'utf8'));

const batchImportData = inputData.batchImportData || {};
const results = extractData.results || [];

let nodes = [];
let edges = [];

results.forEach(fileData => {
    const filePath = fileData.path;
    const category = fileData.fileCategory;
    
    let type = 'file';
    let summary = '提供特定功能的业务模块。';
    let tags = ['module'];
    let complexity = 'simple';
    
    if (fileData.nonEmptyLines > 200) complexity = 'complex';
    else if (fileData.nonEmptyLines >= 50) complexity = 'moderate';
    
    if (filePath.includes('api/client.ts')) {
        summary = '提供基础 HTTP 请求封装与响应拦截，处理授权与统一错误处理。';
        tags = ['api-client', 'http', 'interceptor'];
    } else if (filePath.includes('api/modules/')) {
        summary = '封装对应业务领域的 API 请求方法集合，供业务层调用。';
        tags = ['api-module', '接口封装', 'business-data'];
    } else if (filePath.includes('components/')) {
        summary = '提供可复用的基础 UI 组件或业务组件。';
        tags = ['component', 'ui', 'reusable'];
    } else if (filePath.includes('layouts/')) {
        summary = '页面基础布局组件，负责全局导航与侧边栏渲染。';
        tags = ['layout', 'navigation', 'structure'];
    } else if (filePath.includes('main.tsx')) {
        summary = '前端应用的主入口文件，负责挂载 React 根节点与全局提供者。';
        tags = ['entry-point', 'mounting', 'bootstrap'];
    } else if (filePath.includes('router/')) {
        summary = '定义前端路由表，包含页面级路由和路由守卫逻辑。';
        tags = ['router', 'routing', 'guard'];
    } else if (filePath.includes('store/')) {
        summary = '全局状态管理模块，维护跨组件共享的业务状态。';
        tags = ['store', '状态管理', 'global-state'];
    } else if (filePath.includes('views/')) {
        summary = '业务页面组件，负责展示数据、处理用户交互和编排子组件。';
        tags = ['view', 'page', 'business-view'];
    }
    
    nodes.push({
        id: `file:${filePath}`,
        type: type,
        name: filePath.split('/').pop(),
        filePath: filePath,
        summary: summary,
        tags: tags,
        complexity: complexity
    });
    
    // Import edges
    const imports = batchImportData[filePath] || [];
    imports.forEach(targetPath => {
        edges.push({
            source: `file:${filePath}`,
            target: `file:${targetPath}`,
            type: 'imports',
            direction: 'forward',
            weight: 0.7
        });
    });
    
    // Functions
    if (fileData.functions) {
        fileData.functions.forEach(fn => {
            const lines = fn.endLine - fn.startLine + 1;
            const isExported = (fileData.exports || []).some(e => e.name === fn.name);
            if (lines >= 10 || isExported) {
                const fnId = `function:${filePath}:${fn.name}`;
                nodes.push({
                    id: fnId,
                    type: 'function',
                    name: fn.name,
                    filePath: filePath,
                    lineRange: [fn.startLine, fn.endLine],
                    summary: `实现 ${fn.name} 的核心逻辑处理。`,
                    tags: ['function', 'logic'],
                    complexity: lines > 50 ? 'complex' : (lines > 20 ? 'moderate' : 'simple')
                });
                
                edges.push({
                    source: `file:${filePath}`,
                    target: fnId,
                    type: 'contains',
                    direction: 'forward',
                    weight: 1.0
                });
                
                if (isExported) {
                    edges.push({
                        source: `file:${filePath}`,
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
    if (fileData.classes) {
        fileData.classes.forEach(cls => {
            const lines = cls.endLine - cls.startLine + 1;
            const isExported = (fileData.exports || []).some(e => e.name === cls.name);
            if (lines >= 20 || (cls.methods && cls.methods.length >= 2) || isExported) {
                const clsId = `class:${filePath}:${cls.name}`;
                nodes.push({
                    id: clsId,
                    type: 'class',
                    name: cls.name,
                    filePath: filePath,
                    lineRange: [cls.startLine, cls.endLine],
                    summary: `定义 ${cls.name} 类结构与相关方法。`,
                    tags: ['class', 'oop'],
                    complexity: lines > 100 ? 'complex' : (lines > 50 ? 'moderate' : 'simple')
                });
                
                edges.push({
                    source: `file:${filePath}`,
                    target: clsId,
                    type: 'contains',
                    direction: 'forward',
                    weight: 1.0
                });
                
                if (isExported) {
                    edges.push({
                        source: `file:${filePath}`,
                        target: clsId,
                        type: 'exports',
                        direction: 'forward',
                        weight: 0.8
                    });
                }
            }
        });
    }
    
    // Call edges
    if (fileData.callGraph) {
        // internal calls
        fileData.callGraph.forEach(call => {
            const callerId = `function:${filePath}:${call.caller}`;
            const calleeFn = (fileData.functions || []).find(f => f.name === call.callee);
            if (calleeFn) {
                const calleeId = `function:${filePath}:${call.callee}`;
                const callerExists = nodes.some(n => n.id === callerId);
                const calleeExists = nodes.some(n => n.id === calleeId);
                if (callerExists && calleeExists) {
                    const edgeExists = edges.some(e => e.source === callerId && e.target === calleeId && e.type === 'calls');
                    if (!edgeExists) {
                        edges.push({
                            source: callerId,
                            target: calleeId,
                            type: 'calls',
                            direction: 'forward',
                            weight: 0.8
                        });
                    }
                }
            }
        });
    }
});

const MAX_NODES = 60;
const MAX_EDGES = 120;

const files = Array.from(new Set(nodes.filter(n => n.type === 'file').map(n => n.filePath))).sort();

let parts = [];
let currentNodes = [];
let currentEdges = [];
let currentFiles = [];

files.forEach(file => {
    const fileNodes = nodes.filter(n => n.filePath === file);
    const fileNodeIds = new Set(fileNodes.map(n => n.id));
    const fileEdges = edges.filter(e => fileNodeIds.has(e.source));
    
    if (currentNodes.length + fileNodes.length > MAX_NODES || currentEdges.length + fileEdges.length > MAX_EDGES) {
        if (currentNodes.length > 0) {
            parts.push({nodes: currentNodes, edges: currentEdges});
        }
        currentNodes = [...fileNodes];
        currentEdges = [...fileEdges];
        currentFiles = [file];
    } else {
        currentNodes = currentNodes.concat(fileNodes);
        currentEdges = currentEdges.concat(fileEdges);
        currentFiles.push(file);
    }
});
if (currentNodes.length > 0) {
    parts.push({nodes: currentNodes, edges: currentEdges});
}

parts.forEach((part, index) => {
    const k = index + 1;
    fs.writeFileSync(`C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate/batch-3-part-${k}.json`, JSON.stringify(part, null, 2));
    console.log(`Written part ${k} with ${part.nodes.length} nodes and ${part.edges.length} edges.`);
});
