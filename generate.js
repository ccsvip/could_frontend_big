const fs = require('fs');

const expertData = {
    // Batch 9
    "backend/apps/audit/admin.py": {
        summary: "配置 Django Admin 以管理和查看 OperationLog 审计日志模型。",
        tags: ["configuration", "admin", "audit-log"],
    },
    "backend/apps/audit/descriptions.py": {
        summary: "提供辅助函数，根据请求的方法、路径和载荷生成易于理解的中文操作描述。",
        tags: ["utility", "audit-log", "formatting"],
        functions: {
            "describe_operation": {
                summary: "根据 HTTP 请求详情映射并生成特定的业务操作中文描述。",
                tags: ["utility", "formatting"]
            }
        }
    },
    "backend/apps/audit/models.py": {
        summary: "定义 OperationLog 数据库模型，用于记录用户的各类操作行为、IP 地址、租户信息及请求详情。",
        tags: ["data-model", "audit-log", "database"],
        classes: {
            "OperationLog": {
                summary: "记录用户操作详情的数据库模型，包含租户关联、执行用户及请求路径等元数据。",
                tags: ["data-model", "database"]
            }
        }
    },
    "backend/apps/audit/serializers.py": {
        summary: "提供 OperationLog 的 DRF 序列化器，用于在 API 响应中格式化审计日志并嵌套展示操作者信息。",
        tags: ["serialization", "audit-log", "api-handler"],
        classes: {
            "OperationLogSerializer": {
                summary: "将审计日志模型实例转换为 JSON 数据，包含关联的用户详情解析。",
                tags: ["serialization"]
            }
        }
    },
    "backend/apps/audit/tests/test_operation_log_api.py": {
        summary: "审计日志模块的集成测试用例，覆盖日志查询、权限控制、租户数据隔离及日志清空等核心功能。",
        tags: ["test", "audit-log", "api-handler"],
        classes: {
            "OperationLogAPITests": {
                summary: "验证审计日志 API 端点的核心测试套件，确保权限机制和数据过滤正确工作。",
                tags: ["test"]
            }
        }
    },
    "backend/apps/audit/urls.py": {
        summary: "注册并路由审计日志相关的 DRF ViewSet，提供 /audit-logs/ 访问端点。",
        tags: ["entry-point", "routing", "audit-log"]
    },
    "backend/apps/audit/views.py": {
        summary: "处理审计日志的 API 视图集，支持按租户查询日志及具备特定权限时清空日志的高级操作。",
        tags: ["api-handler", "audit-log", "controller"],
        classes: {
            "OperationLogViewSet": {
                summary: "提供只读的日志查询接口及清空功能的视图集，内置多租户数据隔离逻辑。",
                tags: ["api-handler", "controller"]
            }
        }
    },
    
    // Batch 10
    "backend/config/sentry.py": {
        summary: "Sentry SDK 的初始化和配置逻辑，包含忽略特定健康检查路径和静态资源的过滤机制。",
        tags: ["configuration", "monitoring", "error-tracking"],
        functions: {
            "filter_transactions": {
                summary: "过滤请求事务，防止静态文件和内部健康检查路径被错误上报到 Sentry。",
                tags: ["monitoring", "filtering"]
            },
            "init_sentry": {
                summary: "初始化 Sentry SDK 并应用忽略规则、环境信息及性能采样率配置。",
                tags: ["configuration", "monitoring"]
            }
        }
    },
    "backend/config/settings/base.py": {
        summary: "Django 项目的基础配置文件，定义了应用注册、中间件、数据库连接、缓存及日志配置。",
        tags: ["configuration", "django", "core-settings"]
    },
    "backend/config/settings/dev.py": {
        summary: "本地开发环境专用的 Django 配置，开启调试模式并配置开发工具。",
        tags: ["configuration", "development", "django"]
    },
    "backend/config/settings/prod.py": {
        summary: "生产环境专用的 Django 配置，关闭调试模式并应用安全相关的生产策略。",
        tags: ["configuration", "production", "django"]
    },
    "backend/config/test_sentry_filters.py": {
        summary: "针对 Sentry 事件与事务过滤逻辑的测试文件，确保无效的上报请求被正确拦截。",
        tags: ["test", "monitoring", "error-tracking"],
        classes: {
            "SentryFilterTests": {
                summary: "测试 filter_transactions 等方法是否按预期屏蔽特定路由的性能追踪。",
                tags: ["test"]
            }
        }
    },

    // Batch 11
    "backend/config/__init__.py": {
        summary: "项目配置包的初始化入口，确保在 Django 启动时预先加载并注册 Celery 实例。",
        tags: ["entry-point", "configuration", "django"]
    },
    "backend/config/celery.py": {
        summary: "Celery 应用实例化及配置，负责从 Django settings 加载异步任务队列的参数配置。",
        tags: ["configuration", "task-queue", "async"]
    },
    "backend/config/tasks.py": {
        summary: "存放跨模块或通用的 Celery 异步任务，例如简单的调试探测任务。",
        tags: ["task-queue", "utility", "background-job"],
        functions: {
            "debug_task": {
                summary: "打印当前请求信息的调试任务，用于验证 Celery worker 进程的联通性。",
                tags: ["task-queue", "utility"]
            }
        }
    },

    // Batch 12
    "web/src/api/modules/tts.ts": {
        summary: "封装与语音合成 (TTS) 相关的 HTTP 接口调用逻辑，提供清晰的前端 API 访问层。",
        tags: ["api-handler", "tts", "integration"]
    },
    "web/src/views/tts-management/index.tsx": {
        summary: "用于管理音色模型及相关资源的 React 视图页面组件。",
        tags: ["component", "view", "tts"]
    },
    "web/src/views/tts-settings/index.tsx": {
        summary: "提供全局或特定应用的语音合成参数设置页面，例如语速、音量及默认声音的调节。",
        tags: ["component", "view", "tts"]
    },

    // Batch 13
    "backend/Dockerfile": {
        summary: "构建包含 Django、DRF 和 Celery 运行环境的镜像，通过多阶段构建优化体积，并封装服务启动序列。",
        tags: ["containerization", "infrastructure", "django"],
        languageNotes: "容器内启动序列和健康检查由根目录的 docker-compose 编排，本 Dockerfile 主要固化 Python 系统依赖。"
    },

    // Batch 14
    "web/Dockerfile": {
        summary: "构建 React 开发环境的 Docker 镜像，用于在容器内通过 Node 运行 Vite 开发服务器以支持热更新。",
        tags: ["containerization", "infrastructure", "frontend"],
        languageNotes: "本镜像为开发态使用 (npm run dev) 设计，通过匿名数据卷挂载依赖以规避宿主 npm 安装的污染问题。"
    }
};

const inputData = JSON.parse(fs.readFileSync('.understand-anything/tmp/batch-input-7.json', 'utf8'));

[9, 10, 11, 12, 13, 14].forEach(batchIndex => {
    const input = inputData.find(b => b.batchIndex === batchIndex);
    const extracted = JSON.parse(fs.readFileSync('.understand-anything/tmp/ua-file-extract-results-' + batchIndex + '.json', 'utf8'));
    
    let nodes = [];
    let edges = [];

    extracted.results.forEach(file => {
        const ed = expertData[file.path] || { summary: "自动生成的文件节点。", tags: ["file"] };
        
        let nodeType = 'file';
        if (file.fileCategory === 'config') nodeType = 'config';
        if (file.fileCategory === 'infra') nodeType = file.path.includes('Dockerfile') ? 'service' : 'pipeline';
        if (file.fileCategory === 'data' && file.path.endsWith('.sql')) nodeType = 'table';
        
        nodes.push({
            id: `${nodeType}:${file.path}`,
            type: nodeType,
            name: file.path.split('/').pop(),
            filePath: file.path,
            summary: ed.summary,
            tags: ed.tags,
            complexity: file.totalLines > 200 ? 'complex' : (file.totalLines > 50 ? 'moderate' : 'simple'),
            languageNotes: ed.languageNotes || undefined
        });

        // Functions
        if (file.functions) {
            file.functions.forEach(fn => {
                let isExported = file.exports?.find(e => e.name === fn.name);
                if (fn.endLine - fn.startLine >= 10 || isExported) {
                    let fnNodeId = `function:${file.path}:${fn.name}`;
                    let fnEd = ed.functions && ed.functions[fn.name] ? ed.functions[fn.name] : {summary: `${fn.name} 的具体实现代码。`, tags: ["function"]};
                    nodes.push({
                        id: fnNodeId,
                        type: 'function',
                        name: fn.name,
                        filePath: file.path,
                        lineRange: [fn.startLine, fn.endLine],
                        summary: fnEd.summary,
                        tags: fnEd.tags,
                        complexity: (fn.endLine - fn.startLine) > 50 ? 'complex' : 'simple'
                    });
                    edges.push({
                        source: `${nodeType}:${file.path}`,
                        target: fnNodeId,
                        type: 'contains',
                        direction: 'forward',
                        weight: 1.0
                    });
                    if (isExported) {
                        edges.push({
                            source: `${nodeType}:${file.path}`,
                            target: fnNodeId,
                            type: 'exports',
                            direction: 'forward',
                            weight: 0.8
                        });
                    }
                }
            });
        }

        // Classes
        if (file.classes) {
            file.classes.forEach(cls => {
                let isExported = file.exports?.find(e => e.name === cls.name);
                if (cls.endLine - cls.startLine >= 20 || (cls.methods && cls.methods.length >= 2) || isExported) {
                    let clsNodeId = `class:${file.path}:${cls.name}`;
                    let clsEd = ed.classes && ed.classes[cls.name] ? ed.classes[cls.name] : {summary: `${cls.name} 的类定义。`, tags: ["class"]};
                    nodes.push({
                        id: clsNodeId,
                        type: 'class',
                        name: cls.name,
                        filePath: file.path,
                        lineRange: [cls.startLine, cls.endLine],
                        summary: clsEd.summary,
                        tags: clsEd.tags,
                        complexity: (cls.endLine - cls.startLine) > 100 ? 'complex' : 'moderate'
                    });
                    edges.push({
                        source: `${nodeType}:${file.path}`,
                        target: clsNodeId,
                        type: 'contains',
                        direction: 'forward',
                        weight: 1.0
                    });
                    if (isExported) {
                        edges.push({
                            source: `${nodeType}:${file.path}`,
                            target: clsNodeId,
                            type: 'exports',
                            direction: 'forward',
                            weight: 0.8
                        });
                    }
                }
            });
        }
        
        // Imports
        const imports = input.batchImportData[file.path] || [];
        imports.forEach(imp => {
            edges.push({
                source: `${nodeType}:${file.path}`,
                target: `file:${imp}`, // imports generally point to files unless infra
                type: 'imports',
                direction: 'forward',
                weight: 0.7
            });
        });
        
        // Extra edges from expertData
        if (ed.extraEdges) {
            edges.push(...ed.extraEdges.map(e => ({...e, source: `${nodeType}:${file.path}`})));
        }

        // Handle specific non-code relationships
        if (file.fileCategory === 'infra' && file.path.includes('Dockerfile')) {
            if (file.path.startsWith('backend/')) {
                edges.push({
                    source: `${nodeType}:${file.path}`,
                    target: `file:backend/config/settings/base.py`,
                    type: 'deploys',
                    direction: 'forward',
                    weight: 0.7
                });
            } else if (file.path.startsWith('web/')) {
                edges.push({
                    source: `${nodeType}:${file.path}`,
                    target: `file:web/package.json`, // though not strictly in batch, it represents the app
                    type: 'deploys',
                    direction: 'forward',
                    weight: 0.7
                });
            }
        }
    });

    fs.writeFileSync(`.understand-anything/intermediate/batch-${batchIndex}.json`, JSON.stringify({nodes, edges}, null, 2), 'utf8');
    console.log(`Wrote batch-${batchIndex}.json with ${nodes.length} nodes and ${edges.length} edges.`);
});