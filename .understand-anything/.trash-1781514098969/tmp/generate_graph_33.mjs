import fs from 'fs';

const extracted = JSON.parse(fs.readFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-extract-results-33.json', 'utf8'));
const input = JSON.parse(fs.readFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\tmp\\ua-file-analyzer-input-33.json', 'utf8'));

const nodes = [];
const edges = [];

extracted.results.forEach(res => {
    let type = 'file';
    let summary = '';
    let tags = [];
    let complexity = 'simple';

    if (res.fileCategory === 'docs') {
        type = 'document';
        summary = '提供关于 ' + res.path.split('/').pop() + ' 的文档和指南。';
        tags = ['documentation', 'guide'];
        if (res.path.includes('SKILL.md')) {
            summary = '定义 ' + res.path.split('/')[2] + ' 的 AI 技能指令和工作流。';
            tags = ['documentation', 'ai-skill', 'workflow'];
        } else if (res.path.includes('AGENTS.md')) {
            summary = '定义当前模块的 AI 代理行为规范和领域约束。';
            tags = ['documentation', 'agent-rules', 'guidelines'];
        }
    } else if (res.fileCategory === 'config') {
        type = 'config';
        summary = '项目级别的配置文件：' + res.path.split('/').pop();
        tags = ['configuration'];
        if (res.path.includes('domain-graph.json')) {
            summary = '由 Understand Anything 提取的领域知识图谱数据文件。';
            tags = ['configuration', 'knowledge-graph', 'domain-model'];
            complexity = 'complex';
        }
    } else if (res.fileCategory === 'code') {
        type = 'file';
        summary = '项目源代码文件：' + res.path.split('/').pop();
        tags = ['code'];
        if (res.path.includes('migrations/')) {
            summary = 'Django 数据库迁移文件，用于定义数据库表结构的变更。';
            tags = ['database', 'migration', 'django'];
        } else if (res.path.endsWith('__init__.py')) {
            summary = 'Python 包初始化文件，用于将目录标记为模块。';
            tags = ['entry-point', 'package-init'];
        } else if (res.path.endsWith('apps.py')) {
            summary = 'Django 应用程序配置，注册应用及其信号等初始化逻辑。';
            tags = ['configuration', 'django-app'];
        } else if (res.path.includes('.gitattributes')) {
            summary = 'Git 属性配置文件，用于设置特定文件路径的 Git 行为（如换行符处理）。';
            tags = ['configuration', 'git'];
        } else if (res.path.includes('.understandignore')) {
            summary = 'Understand Anything 工具的忽略列表配置。';
            tags = ['configuration', 'tool-config'];
        }
    }

    if (res.totalLines > 200) complexity = 'complex';
    else if (res.totalLines > 50) complexity = 'moderate';

    nodes.push({
        id: `${type}:${res.path}`,
        type: type,
        name: res.path.split('/').pop(),
        filePath: res.path,
        summary: summary,
        tags: tags,
        complexity: complexity
    });

    if (res.functions) {
        res.functions.forEach(fn => {
            if (fn.endLine - fn.startLine >= 9 || fn.name.startsWith('test')) {
                nodes.push({
                    id: `function:${res.path}:${fn.name}`,
                    type: 'function',
                    name: fn.name,
                    filePath: res.path,
                    lineRange: [fn.startLine, fn.endLine],
                    summary: `实现 ${fn.name} 的功能逻辑。`,
                    tags: ['function', 'logic'],
                    complexity: 'simple'
                });
                edges.push({
                    source: `${type}:${res.path}`,
                    target: `function:${res.path}:${fn.name}`,
                    type: 'contains',
                    direction: 'forward',
                    weight: 1.0
                });
            }
        });
    }

    if (res.classes) {
        res.classes.forEach(cls => {
            nodes.push({
                id: `class:${res.path}:${cls.name}`,
                type: 'class',
                name: cls.name,
                filePath: res.path,
                lineRange: [cls.startLine, cls.endLine],
                summary: `定义 ${cls.name} 类结构。`,
                tags: ['class', 'data-model'],
                complexity: (cls.endLine - cls.startLine > 50) ? 'moderate' : 'simple'
            });
            edges.push({
                source: `${type}:${res.path}`,
                target: `class:${res.path}:${cls.name}`,
                type: 'contains',
                direction: 'forward',
                weight: 1.0
            });
        });
    }

    if (input.batchImportData[res.path]) {
        input.batchImportData[res.path].forEach(imp => {
            edges.push({
                source: `${type}:${res.path}`,
                target: `file:${imp}`,
                type: 'imports',
                direction: 'forward',
                weight: 0.7
            });
        });
    }
});

fs.writeFileSync('C:\\SVN_CODE\\branches\\real\\could_frontend\\.understand-anything\\intermediate\\batch-33.json', JSON.stringify({ nodes, edges }, null, 2), 'utf8');
console.log(`Done! Nodes: ${nodes.length}, Edges: ${edges.length}`);
