const fs = require('fs');
const path = require('path');

const extractData = JSON.parse(fs.readFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-extract-results-3.json', 'utf8'));
const batchInput = JSON.parse(fs.readFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\batch-input-3.json', 'utf8'))[0];
const batchImportData = batchInput.batchImportData || {};

const nodes = [];
const edges = [];

function getComplexity(metrics) {
    if (!metrics) return 'moderate';
    const lines = metrics.nonEmptyLines || 0;
    if (lines < 50) return 'simple';
    if (lines > 200) return 'complex';
    return 'moderate';
}

function getZhSummary(filePath, type = 'file', name = '') {
    const map = {
        'asr-management': '语音识别(ASR)管理',
        'asr-settings': '语音识别(ASR)设置',
        'command-management': '指令管理',
        'device-authorization-center': '设备授权中心',
        'device-management': '设备管理',
        'employee-management': '员工管理',
        'force-password-change': '强制密码修改',
        'knowledge-base': '知识库管理',
        'llm-management': '大语言模型(LLM)管理',
        'llm-settings': '大语言模型(LLM)配置',
        'log-management': '日志管理',
        'login': '用户登录与认证',
        'minio-settings': 'MinIO对象存储配置',
        'model-management': '3D模型资产管理',
        'resource-management': '图片/视频资源管理',
        'scrolling-text-management': '滚动字幕管理',
        'settings-llm': 'LLM参数与授权设置',
        'tenant-management': '租户(公司)管理',
        'voice-tone-management': '音色与语音合成管理'
    };
    
    let domain = '通用功能';
    for (const [key, val] of Object.entries(map)) {
        if (filePath.includes(key)) {
            domain = val;
            break;
        }
    }

    if (type === 'file') {
        if (filePath.includes('index.tsx')) return `提供${domain}页面的主视图入口、路由挂载和顶级状态管理。`;
        if (filePath.endsWith('.tsx')) return `提供${domain}模块中的【${name || path.basename(filePath, '.tsx')}】UI组件及视图逻辑。`;
        if (filePath.endsWith('.ts')) return `提供${domain}模块的类型定义、常量或工具函数。`;
        return `${domain}的源文件。`;
    } else if (type === 'function') {
        if (name.includes('Page') || name === 'Index' || name === 'App') return `${domain}页面的顶级React组件。`;
        if (name.startsWith('use')) return `为${domain}提供特定的React Hook状态逻辑。`;
        if (name.startsWith('handle')) return `处理${domain}视图中的特定事件交互。`;
        if (name.match(/^[A-Z]/)) return `${domain}的子视图React组件。`;
        return `实现${domain}相关的一项业务或辅助逻辑。`;
    } else if (type === 'class') {
        return `封装${domain}相关业务状态与行为的类对象。`;
    }
    return '未定义';
}

function getTags(filePath, type = 'file', name = '') {
    const tags = ['frontend-view'];
    if (filePath.includes('index.tsx')) tags.push('entry-point');
    if (filePath.endsWith('.tsx')) tags.push('react-component', 'ui');
    if (filePath.includes('management')) tags.push('admin-management');
    if (filePath.includes('settings')) tags.push('configuration');
    
    if (type === 'function') {
        if (name.match(/^[A-Z]/)) tags.push('component');
        if (name.startsWith('use')) tags.push('hook', 'state-management');
        if (name.startsWith('handle')) tags.push('event-handler');
    }
    
    return tags.slice(0, 4);
}

extractData.results.forEach(res => {
    const fPath = res.path;
    const fileId = `file:${fPath}`;
    const complexity = getComplexity({ nonEmptyLines: res.nonEmptyLines });
    
    nodes.push({
        id: fileId,
        type: 'file',
        name: path.basename(fPath),
        filePath: fPath,
        summary: getZhSummary(fPath, 'file', ''),
        tags: getTags(fPath, 'file', ''),
        complexity: complexity,
        languageNotes: fPath.endsWith('.tsx') ? "使用React Hooks与函数式组件构成的视图层。" : ""
    });

    if (batchImportData[fPath]) {
        batchImportData[fPath].forEach(imp => {
            edges.push({
                source: fileId,
                target: `file:${imp}`,
                type: 'imports',
                direction: 'forward',
                weight: 0.7
            });
        });
    }

    const exportedNames = new Set((res.exports || []).map(e => e.name));
    const processedFuncs = new Set();

    (res.functions || []).forEach(fn => {
        const lines = fn.endLine - fn.startLine + 1;
        const isExported = exportedNames.has(fn.name);
        
        if (lines >= 10 || isExported) {
            const fnId = `function:${fPath}:${fn.name}`;
            processedFuncs.add(fn.name);
            nodes.push({
                id: fnId,
                type: 'function',
                name: fn.name,
                filePath: fPath,
                lineRange: [fn.startLine, fn.endLine],
                summary: getZhSummary(fPath, 'function', fn.name),
                tags: getTags(fPath, 'function', fn.name),
                complexity: lines > 100 ? 'complex' : (lines > 30 ? 'moderate' : 'simple')
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

    (res.classes || []).forEach(cls => {
        const lines = cls.endLine - cls.startLine + 1;
        const isExported = exportedNames.has(cls.name);
        
        if (cls.methods?.length >= 2 || lines >= 20 || isExported) {
            const clsId = `class:${fPath}:${cls.name}`;
            nodes.push({
                id: clsId,
                type: 'class',
                name: cls.name,
                filePath: fPath,
                lineRange: [cls.startLine, cls.endLine],
                summary: getZhSummary(fPath, 'class', cls.name),
                tags: getTags(fPath, 'class', cls.name),
                complexity: lines > 100 ? 'complex' : (lines > 30 ? 'moderate' : 'simple')
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

    if (res.callGraph) {
        res.callGraph.forEach(call => {
            if (processedFuncs.has(call.caller) && processedFuncs.has(call.callee)) {
                edges.push({
                    source: `function:${fPath}:${call.caller}`,
                    target: `function:${fPath}:${call.callee}`,
                    type: 'calls',
                    direction: 'forward',
                    weight: 0.8
                });
            }
        });
    }
});

const batchIndex = 3;
const nodeCount = nodes.length;
const edgeCount = edges.length;
const parts = Math.ceil(Math.max(nodeCount / 60, edgeCount / 120));

console.log(`Nodes: ${nodeCount}, Edges: ${edgeCount}, Parts: ${parts}`);

const allFiles = Array.from(new Set(nodes.map(n => n.filePath).filter(Boolean))).sort();

for (let k = 1; k <= parts; k++) {
    const startIdx = Math.floor((k - 1) * allFiles.length / parts);
    const endIdx = Math.floor(k * allFiles.length / parts);
    const partFiles = new Set(allFiles.slice(startIdx, endIdx));
    
    const partNodes = nodes.filter(n => partFiles.has(n.filePath));
    const partNodeIds = new Set(partNodes.map(n => n.id));
    
    const partEdges = edges.filter(e => partNodeIds.has(e.source));
    
    const outPath = parts === 1 
        ? `C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batch-${batchIndex}.json`
        : `C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batch-${batchIndex}-part-${k}.json`;
        
    fs.writeFileSync(outPath, JSON.stringify({ nodes: partNodes, edges: partEdges }, null, 2), 'utf8');
    console.log(`Wrote ${outPath} with ${partNodes.length} nodes and ${partEdges.length} edges`);
}
