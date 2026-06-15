import json
import sys

# Output format needs to be identical to what's expected
output = {
    "nodes": [],
    "edges": []
}

files_meta = {
    "backend/apps/resources/tests/test_admin_model_asset.py": {
        "type": "file",
        "summary": "包含 ResourceAdmin 的测试用例，验证模型资产管理在 Django Admin 中的呈现。",
        "tags": ["test", "admin", "model-asset"],
        "complexity": "moderate"
    },
    "backend/apps/tenants/__init__.py": {
        "type": "file",
        "summary": "租户模块的初始化文件。",
        "tags": ["entry-point", "tenants"],
        "complexity": "simple"
    },
    "backend/apps/tenants/AGENTS.md": {
        "type": "document",
        "summary": "租户模块的系统提示文档，描述了租户隔离机制、模型结构和开发约束。",
        "tags": ["documentation", "tenants", "architecture"],
        "complexity": "moderate"
    },
    "backend/apps/tenants/apps.py": {
        "type": "file",
        "summary": "租户应用的 Django 应用程序配置，注册 tenants 模块。",
        "tags": ["configuration", "django-app"],
        "complexity": "simple"
    },
    "backend/apps/tenants/migrations/__init__.py": {
        "type": "file",
        "summary": "数据库迁移目录的初始化文件。",
        "tags": ["initialization", "migration"],
        "complexity": "simple"
    },
    "backend/apps/tenants/migrations/0001_initial.py": {
        "type": "file",
        "summary": "租户应用的初始数据库表结构迁移文件。",
        "tags": ["migration", "database"],
        "complexity": "moderate"
    },
    "backend/apps/tenants/migrations/0002_default_company.py": {
        "type": "file",
        "summary": "创建默认租户公司实体的数据库迁移脚本。",
        "tags": ["migration", "database"],
        "complexity": "moderate"
    },
    "backend/apps/tenants/migrations/0003_backfill_business_tenants.py": {
        "type": "file",
        "summary": "回填历史业务数据的租户字段，实现租户隔离的平滑过渡。",
        "tags": ["migration", "database"],
        "complexity": "moderate"
    },
    "backend/apps/tenants/migrations/0004_membership_role_name.py": {
        "type": "file",
        "summary": "更新 Membership 模型中的角色名称的迁移文件。",
        "tags": ["migration", "database"],
        "complexity": "simple"
    },
    "backend/apps/tenants/tests/__init__.py": {
        "type": "file",
        "summary": "租户模块测试用例的初始化文件。",
        "tags": ["test", "initialization"],
        "complexity": "simple"
    },
    "backend/config/AGENTS.md": {
        "type": "document",
        "summary": "系统配置模块的 AI 代理指南，定义了全局配置、入口和底层依赖的约定。",
        "tags": ["documentation", "configuration", "guidelines"],
        "complexity": "simple"
    },
    "backend/config/asgi.py": {
        "type": "file",
        "summary": "ASGI 应用程序入口点，用于处理 WebSocket 和异步 HTTP 请求，集成 Django 与实时流式接口。",
        "tags": ["entry-point", "asgi", "websocket"],
        "complexity": "simple"
    },
    "backend/config/exceptions.py": {
        "type": "file",
        "summary": "全局异常处理程序，自定义 DRF 错误响应格式以统一 API 的错误结构。",
        "tags": ["exception-handling", "api-handler", "middleware"],
        "complexity": "moderate"
    },
    "backend/config/pagination.py": {
        "type": "file",
        "summary": "全局分页配置类，定义了标准 API 的分页大小和返回格式。",
        "tags": ["configuration", "pagination", "api"],
        "complexity": "simple"
    },
    "backend/config/settings/__init__.py": {
        "type": "file",
        "summary": "配置模块初始化文件，用于组织不同环境的 Django settings。",
        "tags": ["entry-point", "configuration"],
        "complexity": "simple"
    },
    "backend/config/tests/__init__.py": {
        "type": "file",
        "summary": "全局配置测试用例的初始化文件。",
        "tags": ["test", "initialization"],
        "complexity": "simple"
    },
    "backend/config/tests/test_cache_settings.py": {
        "type": "file",
        "summary": "缓存配置的测试文件，验证默认缓存后端正确连接到了 Redis。",
        "tags": ["test", "cache", "redis"],
        "complexity": "simple"
    },
    "backend/config/urls.py": {
        "type": "file",
        "summary": "Django 主路由配置，注册所有 API 版本入口，并包含自定义 404 处理视图。",
        "tags": ["entry-point", "routing", "api"],
        "complexity": "moderate"
    },
    "backend/config/wsgi.py": {
        "type": "file",
        "summary": "WSGI 应用程序入口，用于传统的同步 Django 部署。",
        "tags": ["entry-point", "wsgi", "deployment"],
        "complexity": "simple"
    },
    "backend/manage.py": {
        "type": "file",
        "summary": "Django 项目的命令行管理工具入口，用于启动服务和执行管理命令。",
        "tags": ["entry-point", "cli", "management"],
        "complexity": "simple"
    },
    "backend/templates/404.html": {
        "type": "file",
        "summary": "自定义 404 错误页面模板。",
        "tags": ["markup", "template", "error-page"],
        "complexity": "complex"
    },
    "flow-web/index.html": {
        "type": "file",
        "summary": "工作流 Web 应用的前端主入口 HTML 文件。",
        "tags": ["entry-point", "markup", "frontend"],
        "complexity": "complex"
    },
    "flow-web/my-video/renders/my-video_2026-05-31_00-51-48.meta.json": {
        "type": "config",
        "summary": "视频渲染过程的元数据配置文件，包含渲染状态与时长。",
        "tags": ["configuration", "metadata", "video-rendering"],
        "complexity": "simple"
    },
    "flow-web/TERMINAL-ENCODING.md": {
        "type": "document",
        "summary": "终端编码修复指南，解决 Windows 环境下的中文乱码、换行符等常见问题。",
        "tags": ["documentation", "encoding", "troubleshooting"],
        "complexity": "moderate"
    },
    "scripts/asr-replacement-test.html": {
        "type": "file",
        "summary": "语音识别 (ASR) 替换功能的测试工具页面。",
        "tags": ["test", "markup", "asr", "tool"],
        "complexity": "complex"
    }
}

node_functions_classes = [
    {
        "id": "class:backend/apps/resources/tests/test_admin_model_asset.py:ResourceAdminEntryTests",
        "type": "class",
        "name": "ResourceAdminEntryTests",
        "filePath": "backend/apps/resources/tests/test_admin_model_asset.py",
        "lineRange": [9, 36],
        "summary": "测试模型资产在 Django 管理后台的注册及展示逻辑。",
        "tags": ["test", "class", "admin"],
        "complexity": "moderate"
    },
    {
        "id": "class:backend/apps/tenants/apps.py:TenantsConfig",
        "type": "class",
        "name": "TenantsConfig",
        "filePath": "backend/apps/tenants/apps.py",
        "lineRange": [4, 7],
        "summary": "租户模块应用配置，定义应用名称。 ",
        "tags": ["configuration", "class", "django-app"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/apps/tenants/migrations/0001_initial.py:Migration",
        "type": "class",
        "name": "Migration",
        "filePath": "backend/apps/tenants/migrations/0001_initial.py",
        "lineRange": [8, 54],
        "summary": "定义初始租户和成员资格模型结构的迁移类。",
        "tags": ["migration", "class", "database"],
        "complexity": "moderate"
    },
    {
        "id": "function:backend/apps/tenants/migrations/0002_default_company.py:create_default_company",
        "type": "function",
        "name": "create_default_company",
        "filePath": "backend/apps/tenants/migrations/0002_default_company.py",
        "lineRange": [8, 29],
        "summary": "生成并初始化默认租户，分配管理员权限。 ",
        "tags": ["migration", "function", "initialization"],
        "complexity": "moderate"
    },
    {
        "id": "function:backend/apps/tenants/migrations/0002_default_company.py:remove_default_company",
        "type": "function",
        "name": "remove_default_company",
        "filePath": "backend/apps/tenants/migrations/0002_default_company.py",
        "lineRange": [32, 40],
        "summary": "回滚删除系统默认租户及其关联数据。 ",
        "tags": ["migration", "function", "rollback"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/apps/tenants/migrations/0002_default_company.py:Migration",
        "type": "class",
        "name": "Migration",
        "filePath": "backend/apps/tenants/migrations/0002_default_company.py",
        "lineRange": [43, 58],
        "summary": "管理默认租户数据的 Django 迁移类。 ",
        "tags": ["migration", "class", "database"],
        "complexity": "simple"
    },
    {
        "id": "function:backend/apps/tenants/migrations/0003_backfill_business_tenants.py:backfill_default_tenant",
        "type": "function",
        "name": "backfill_default_tenant",
        "filePath": "backend/apps/tenants/migrations/0003_backfill_business_tenants.py",
        "lineRange": [21, 30],
        "summary": "将遗留业务数据与默认租户关联的填充函数。",
        "tags": ["migration", "function", "data-backfill"],
        "complexity": "simple"
    },
    {
        "id": "function:backend/apps/tenants/migrations/0003_backfill_business_tenants.py:clear_default_tenant",
        "type": "function",
        "name": "clear_default_tenant",
        "filePath": "backend/apps/tenants/migrations/0003_backfill_business_tenants.py",
        "lineRange": [33, 41],
        "summary": "回滚并清空业务数据中租户关联的操作。 ",
        "tags": ["migration", "function", "rollback"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/apps/tenants/migrations/0003_backfill_business_tenants.py:Migration",
        "type": "class",
        "name": "Migration",
        "filePath": "backend/apps/tenants/migrations/0003_backfill_business_tenants.py",
        "lineRange": [44, 56],
        "summary": "处理租户数据回填的数据库迁移类。",
        "tags": ["migration", "class", "database"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/apps/tenants/migrations/0004_membership_role_name.py:Migration",
        "type": "class",
        "name": "Migration",
        "filePath": "backend/apps/tenants/migrations/0004_membership_role_name.py",
        "lineRange": [6, 18],
        "summary": "调整成员角色名称字段参数的迁移类。",
        "tags": ["migration", "class", "database"],
        "complexity": "simple"
    },
    {
        "id": "function:backend/config/asgi.py:application",
        "type": "function",
        "name": "application",
        "filePath": "backend/config/asgi.py",
        "lineRange": [10, 27],
        "summary": "异步应用入口，根据协议类型分发至对应的 HTTP 或 WebSocket 处理器。",
        "tags": ["asgi", "function", "routing"],
        "complexity": "moderate"
    },
    {
        "id": "function:backend/config/exceptions.py:custom_exception_handler",
        "type": "function",
        "name": "custom_exception_handler",
        "filePath": "backend/config/exceptions.py",
        "lineRange": [9, 99],
        "summary": "拦截 DRF 异常，将错误提示统一转换为自定义的结构化响应。",
        "tags": ["exception-handling", "function", "middleware"],
        "complexity": "complex"
    },
    {
        "id": "class:backend/config/pagination.py:StandardPageNumberPagination",
        "type": "class",
        "name": "StandardPageNumberPagination",
        "filePath": "backend/config/pagination.py",
        "lineRange": [4, 15],
        "summary": "标准的分页类，限制了页大小和参数。",
        "tags": ["pagination", "class", "configuration"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/config/tests/test_cache_settings.py:CacheSettingsTests",
        "type": "class",
        "name": "CacheSettingsTests",
        "filePath": "backend/config/tests/test_cache_settings.py",
        "lineRange": [7, 15],
        "summary": "确认缓存机制优先使用环境变量配置的 Redis。",
        "tags": ["test", "class", "cache"],
        "complexity": "simple"
    },
    {
        "id": "function:backend/config/urls.py:backend_not_found_view",
        "type": "function",
        "name": "backend_not_found_view",
        "filePath": "backend/config/urls.py",
        "lineRange": [14, 15],
        "summary": "渲染自定义错误页面的视图。",
        "tags": ["routing", "function", "error-page"],
        "complexity": "simple"
    },
    {
        "id": "class:backend/config/urls.py:ApiV1RootView",
        "type": "class",
        "name": "ApiV1RootView",
        "filePath": "backend/config/urls.py",
        "lineRange": [18, 67],
        "summary": "生成并响应当前 API V1 所有可用接口路由的自描述页面。",
        "tags": ["api", "class", "routing"],
        "complexity": "moderate"
    },
    {
        "id": "function:backend/manage.py:main",
        "type": "function",
        "name": "main",
        "filePath": "backend/manage.py",
        "lineRange": [6, 10],
        "summary": "配置环境变量并启动 Django 命令行应用。",
        "tags": ["cli", "function", "entry-point"],
        "complexity": "simple"
    }
]

for fp, meta in files_meta.items():
    node = {
        "id": f"{meta['type']}:{fp}",
        "type": meta["type"],
        "name": fp.split("/")[-1],
        "filePath": fp,
        "summary": meta["summary"],
        "tags": meta["tags"],
        "complexity": meta["complexity"]
    }
    output["nodes"].append(node)

for n in node_functions_classes:
    output["nodes"].append(n)
    
    edge = {
        "source": f"file:{n['filePath']}",
        "target": n['id'],
        "type": "contains",
        "direction": "forward",
        "weight": 1.0
    }
    output["edges"].append(edge)

# Document -> Code relationships
doc_edges = [
    {
        "source": "document:backend/apps/tenants/AGENTS.md",
        "target": "file:backend/apps/tenants/apps.py",
        "type": "documents",
        "direction": "forward",
        "weight": 0.5
    },
    {
        "source": "document:backend/apps/tenants/AGENTS.md",
        "target": "file:backend/apps/tenants/migrations/0001_initial.py",
        "type": "documents",
        "direction": "forward",
        "weight": 0.5
    },
    {
        "source": "document:backend/config/AGENTS.md",
        "target": "file:backend/config/asgi.py",
        "type": "documents",
        "direction": "forward",
        "weight": 0.5
    },
    {
        "source": "document:backend/config/AGENTS.md",
        "target": "file:backend/config/wsgi.py",
        "type": "documents",
        "direction": "forward",
        "weight": 0.5
    },
    {
        "source": "document:backend/config/AGENTS.md",
        "target": "file:backend/config/settings/__init__.py",
        "type": "documents",
        "direction": "forward",
        "weight": 0.5
    }
]

output["edges"].extend(doc_edges)

with open(r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\intermediate\batch-38.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Generated {len(output['nodes'])} nodes and {len(output['edges'])} edges for batch 38")