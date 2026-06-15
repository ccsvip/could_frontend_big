import json
import os

input_path = r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-extract-results-35.json"
input_batch_path = r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-analyzer-input-35.json"
out_dir = r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\intermediate"

with open(input_path, "r", encoding="utf-8") as f:
    extract_data = json.load(f)

with open(input_batch_path, "r", encoding="utf-8") as f:
    batch_data = json.load(f)

batch_import_data = batch_data.get("batchImportData", {})

nodes = []
edges = []

expert_knowledge = {
    "backend/apps/ai_models/migrations/0013_platform_llm_settings.py": {
        "summary": "AI模型应用的数据库迁移文件，负责清理旧的LLM模型绑定数据。",
        "tags": ["migration", "database", "ai-models"]
    },
    "backend/apps/ai_models/migrations/0014_remove_standalone_chat_room_menu.py": {
        "summary": "数据库迁移文件，用于从系统中移除独立的聊天室菜单项。",
        "tags": ["migration", "database", "menu-config"]
    },
    "backend/apps/ai_models/migrations/0015_tts_settings.py": {
        "summary": "TTS（文本转语音）设置的数据迁移文件，包含了从JSON文件加载并初始化默认语音数据的逻辑。",
        "tags": ["migration", "database", "tts", "data-seeding"]
    },
    "backend/apps/ai_models/tests/__init__.py": {
        "summary": "AI模型测试模块的初始化包文件。",
        "tags": ["test", "entry-point"]
    },
    "backend/apps/ai_models/tests/test_llm_provider_api.py": {
        "summary": "LLM提供商API的单元测试，主要验证已废弃的旧版接口是否被正确移除。",
        "tags": ["test", "api", "quality-assurance"]
    },
    "backend/apps/audit/__init__.py": {
        "summary": "审计日志(Audit)应用的初始化文件。",
        "tags": ["entry-point", "audit"]
    },
    "backend/apps/audit/apps.py": {
        "summary": "审计(Audit)应用的Django应用配置入口，定义了应用的元数据。",
        "tags": ["configuration", "django-app"]
    },
    "backend/apps/audit/migrations/__init__.py": {
        "summary": "审计模块迁移文件的包初始化文件。",
        "tags": ["entry-point", "migration"]
    },
    "backend/apps/audit/migrations/0001_initial.py": {
        "summary": "审计日志操作(OperationLog)数据表的初始创建迁移脚本。",
        "tags": ["migration", "database", "audit"]
    },
    "backend/apps/audit/migrations/0002_operationlog_description.py": {
        "summary": "审计日志数据表迁移文件，为操作日志新增描述(description)字段。",
        "tags": ["migration", "database", "audit"]
    },
    "backend/apps/audit/migrations/0003_operationlog_actor_role_name.py": {
        "summary": "审计日志数据表迁移文件，添加操作者角色名称字段以便更好地追踪行为。",
        "tags": ["migration", "database", "audit"]
    },
    "backend/apps/audit/migrations/0004_operationlog_actor_display_name.py": {
        "summary": "审计日志数据表迁移文件，添加操作者显示名称字段。",
        "tags": ["migration", "database", "audit"]
    },
    "backend/apps/audit/migrations/0005_detach_superuser_logs_and_fix_review_descriptions.py": {
        "summary": "审计日志数据修正迁移文件，分离超级管理员的日志记录，并修复知识库审核日志的描述文本。",
        "tags": ["migration", "database", "data-fix"]
    },
    "backend/apps/audit/tests/__init__.py": {
        "summary": "审计应用测试模块的初始化包文件。",
        "tags": ["test", "entry-point"]
    },
    "backend/apps/devices/__init__.py": {
        "summary": "设备管理(Devices)应用的初始化文件。",
        "tags": ["entry-point", "devices"]
    },
    "backend/apps/devices/AGENTS.md": {
        "summary": "设备管理模块的开发指南文档，详细记录了设备接入、鉴权流程及API设计规范。",
        "tags": ["documentation", "development", "architecture"]
    },
    "backend/apps/devices/apps.py": {
        "summary": "设备管理(Devices)应用的Django应用配置文件。",
        "tags": ["configuration", "django-app"]
    },
    "backend/apps/devices/management/__init__.py": {
        "summary": "设备管理应用的自定义命令模块初始化文件。",
        "tags": ["entry-point", "management"]
    },
    "backend/apps/devices/management/commands/__init__.py": {
        "summary": "设备管理自定义命令脚本的包初始化文件。",
        "tags": ["entry-point", "commands"]
    },
    "backend/apps/devices/management/commands/seed_operations_periodic_tasks.py": {
        "summary": "自定义Django管理命令，用于在系统中播种（初始化）设备运营相关的Celery周期性任务。",
        "tags": ["script", "utility", "celery", "data-seeding"]
    },
    "backend/apps/devices/migrations/__init__.py": {
        "summary": "设备管理迁移模块的初始化包文件。",
        "tags": ["entry-point", "migration"]
    },
    "backend/apps/devices/migrations/0001_initial.py": {
        "summary": "设备数据表的初始创建迁移脚本。",
        "tags": ["migration", "database", "devices"]
    },
    "backend/apps/devices/migrations/0002_device_tenant_alter_device_code_and_more.py": {
        "summary": "设备数据表迁移文件，为设备添加租户(tenant)关联并修改设备编码等字段属性。",
        "tags": ["migration", "database", "devices"]
    },
    "backend/apps/devices/migrations/0003_device_authorization_type_device_device_info_and_more.py": {
        "summary": "设备数据表的大型迁移文件，添加设备授权类型、设备详细信息JSON字段等多项属性，支持安卓等设备的免密登录体系。",
        "tags": ["migration", "database", "devices"]
    },
    "backend/apps/devices/migrations/0004_device_status_online_offline_only.py": {
        "summary": "设备数据表迁移文件，将设备状态精简为仅包含在线(online)与离线(offline)两种状态。",
        "tags": ["migration", "database", "devices"]
    }
}

for res in extract_data.get("results", []):
    path = res["path"]
    cat = res["fileCategory"]
    lines = res["nonEmptyLines"]
    
    node_type = "file"
    if cat == "infra":
        node_type = "service"
    elif cat == "data":
        node_type = "table"
    elif cat == "docs":
        node_type = "document"
    elif cat == "config":
        node_type = "config"
        
    name = os.path.basename(path)
    
    complexity = "simple"
    if lines > 200:
        complexity = "complex"
    elif lines >= 50:
        complexity = "moderate"
        
    knowledge = expert_knowledge.get(path, {})
    summary = knowledge.get("summary", "基础文件实现。")
    tags = knowledge.get("tags", ["utility"])
    
    lang_notes = None
    if "migration" in path.lower():
        lang_notes = "Django database migration module."
    
    nodes.append({
        "id": f"{node_type}:{path}",
        "type": node_type,
        "name": name,
        "filePath": path,
        "summary": summary,
        "tags": tags[:5],
        "complexity": complexity,
        "languageNotes": lang_notes
    })
    
    if "functions" in res:
        for fn in res["functions"]:
            fn_lines = fn.get("endLine", 0) - fn.get("startLine", 0) + 1
            is_exported = any(e["name"] == fn["name"] for e in res.get("exports", []))
            if fn_lines >= 10 or is_exported:
                fn_id = f"function:{path}:{fn['name']}"
                nodes.append({
                    "id": fn_id,
                    "type": "function",
                    "name": fn["name"],
                    "filePath": path,
                    "lineRange": [fn.get("startLine", 0), fn.get("endLine", 0)],
                    "summary": f"{fn['name']} 的具体业务逻辑实现。",
                    "tags": ["function", "utility"],
                    "complexity": "simple" if fn_lines < 20 else ("moderate" if fn_lines < 50 else "complex")
                })
                edges.append({
                    "source": f"{node_type}:{path}",
                    "target": fn_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0
                })
                if is_exported:
                    edges.append({
                        "source": f"{node_type}:{path}",
                        "target": fn_id,
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8
                    })
                    
    if "classes" in res:
        for cls in res["classes"]:
            cls_lines = cls.get("endLine", 0) - cls.get("startLine", 0) + 1
            methods_count = len(cls.get("methods", []))
            is_exported = any(e["name"] == cls["name"] for e in res.get("exports", []))
            if cls_lines >= 20 or methods_count >= 2 or is_exported:
                cls_id = f"class:{path}:{cls['name']}"
                nodes.append({
                    "id": cls_id,
                    "type": "class",
                    "name": cls["name"],
                    "filePath": path,
                    "lineRange": [cls.get("startLine", 0), cls.get("endLine", 0)],
                    "summary": f"定义 {cls['name']} 类的数据结构或行为实现。",
                    "tags": ["class", "data-model"] if "Migration" not in cls["name"] else ["class", "migration"],
                    "complexity": "simple" if cls_lines < 50 else ("moderate" if cls_lines < 150 else "complex")
                })
                edges.append({
                    "source": f"{node_type}:{path}",
                    "target": cls_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0
                })
                if is_exported:
                    edges.append({
                        "source": f"{node_type}:{path}",
                        "target": cls_id,
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8
                    })
                    
    imports = batch_import_data.get(path, [])
    for imp in imports:
        edges.append({
            "source": f"{node_type}:{path}",
            "target": f"file:{imp}",
            "type": "imports",
            "direction": "forward",
            "weight": 0.7
        })

print(f"Total Nodes: {len(nodes)}, Total Edges: {len(edges)}")

out_file = os.path.join(out_dir, "batch-35.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({"nodes": nodes, "edges": edges}, f, ensure_ascii=False, indent=2)
