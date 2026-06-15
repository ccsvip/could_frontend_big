import json
import math
import os

def run():
    # Load batch input data
    with open(r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-analyzer-input-34.json", "r", encoding="utf-8") as f:
        input_data = json.load(f)
        
    batch_import_data = input_data.get("batchImportData", {})
    
    # Load extraction results
    with open(r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-extract-results-34.json", "r", encoding="utf-8") as f:
        ext_results = json.load(f)
        
    results = ext_results.get("results", [])
    
    file_info_map = {
        "backend/apps/accounts/migrations/0005_accountapplication_username.py": {
            "summary": "Django 数据迁移文件，为 AccountApplication 模型添加 username 字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0006_remove_accountapplication_email_and_more.py": {
            "summary": "Django 数据迁移文件，移除 AccountApplication 模型的 email 等字段，调整字段定义。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0007_accountuser.py": {
            "summary": "Django 数据迁移文件，新增 AccountUser 账户用户模型。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0008_accountapplication_tenant.py": {
            "summary": "Django 数据迁移文件，为 AccountApplication 添加多租户 tenant 关联字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0009_menu_audience.py": {
            "summary": "Django 数据迁移文件，为 Menu 菜单模型添加 audience 受众字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0010_seed_tenant_menus.py": {
            "summary": "Django 数据迁移文件，用于初始化（seed）租户的默认菜单数据。",
            "tags": ["migration", "database", "data-seed"]
        },
        "backend/apps/accounts/migrations/0011_role_is_template_role_tenant_alter_role_code_and_more.py": {
            "summary": "Django 数据迁移文件，为 Role 角色模型增加模板标识 is_template 和 tenant 字段，并修改角色代码字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/accounts/migrations/0012_seed_audit_logs_menu.py": {
            "summary": "Django 数据迁移文件，用于向系统中预置审计日志（audit logs）的菜单数据。",
            "tags": ["migration", "database", "data-seed"]
        },
        "backend/apps/accounts/services/__init__.py": {
            "summary": "账户服务模块的初始化文件（__init__.py），通常作为包入口。",
            "tags": ["entry-point", "service"]
        },
        "backend/apps/ai_models/__init__.py": {
            "summary": "AI 模型应用的初始化文件。",
            "tags": ["entry-point", "module"]
        },
        "backend/apps/ai_models/AGENTS.md": {
            "summary": "AI 模型应用的说明文档，包含应用设计、代理模型使用相关的上下文及架构信息。",
            "tags": ["documentation", "overview", "architecture"]
        },
        "backend/apps/ai_models/apps.py": {
            "summary": "Django 应用配置文件，定义 ai_models 应用的基础配置信息。",
            "tags": ["configuration", "app-config"]
        },
        "backend/apps/ai_models/migrations/__init__.py": {
            "summary": "AI 模型应用迁移模块的初始化文件。",
            "tags": ["entry-point", "migration"]
        },
        "backend/apps/ai_models/migrations/0001_initial.py": {
            "summary": "AI 模型应用的初始数据迁移文件，创建应用的基础数据库表结构。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0002_chatconversation_chatmessage.py": {
            "summary": "Django 数据迁移文件，创建 ChatConversation 会话和 ChatMessage 消息模型表。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0003_chatconversation_system_prompt.py": {
            "summary": "Django 数据迁移文件，为聊天会话模型增加 system_prompt 系统提示词字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0004_chatconversation_temperature_and_more.py": {
            "summary": "Django 数据迁移文件，为会话模型增加 temperature 等生成参数字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0005_chat_summary_message_feedback.py": {
            "summary": "Django 数据迁移文件，添加聊天总结以及消息反馈相关的字段或模型。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0006_chatconversation_tenant_llmprovider_tenant.py": {
            "summary": "Django 数据迁移文件，为会话和 LLM 提供商增加多租户 tenant 关联。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0007_asr_config.py": {
            "summary": "Django 数据迁移文件，新增语音识别 ASRConfig 配置模型。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0008_alter_asrconfig_options_alter_asrconfig_is_active_and_more.py": {
            "summary": "Django 数据迁移文件，修改 ASR 配置的选项及激活状态字段等属性。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0009_asr_replacement_rule.py": {
            "summary": "Django 数据迁移文件，新增 ASR 文本替换规则模型。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0010_remove_asr_replacement_sort_order.py": {
            "summary": "Django 数据迁移文件，移除 ASR 替换规则中的排序字段。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0011_agentapplication_chatconversation_application_and_more.py": {
            "summary": "Django 数据迁移文件，创建智能体应用 AgentApplication 模型，并将其与聊天会话建立关联。",
            "tags": ["migration", "database", "schema-definition"]
        },
        "backend/apps/ai_models/migrations/0012_seed_agent_application_tenant_access.py": {
            "summary": "Django 数据迁移文件，预置智能体应用针对不同租户的访问权限数据。",
            "tags": ["migration", "database", "data-seed"]
        }
    }
    
    nodes = []
    edges = []
    
    for res in results:
        path = res["path"]
        category = res["fileCategory"]
        lines = res.get("nonEmptyLines", 0)
        
        info = file_info_map.get(path, {
            "summary": "文件摘要未提供。",
            "tags": ["file"]
        })
        
        if lines < 50:
            complexity = "simple"
        elif lines <= 200:
            complexity = "moderate"
        else:
            complexity = "complex"
            
        # Determine node type
        if category == "docs":
            node_type = "document"
            node_id = f"document:{path}"
        elif category == "config":
            node_type = "config"
            node_id = f"config:{path}"
        else:
            node_type = "file"
            node_id = f"file:{path}"
            
        nodes.append({
            "id": node_id,
            "type": node_type,
            "name": os.path.basename(path),
            "filePath": path,
            "summary": info["summary"],
            "tags": info["tags"],
            "complexity": complexity
        })
        
        # Imports
        imports = batch_import_data.get(path, [])
        for imp in imports:
            edges.append({
                "source": node_id,
                "target": f"file:{imp}",
                "type": "imports",
                "direction": "forward",
                "weight": 0.7
            })
            
        # Functions and Classes (for code)
        if category == "code":
            exports = {e["name"]: e for e in res.get("exports", [])}
            
            for fn in res.get("functions", []):
                fn_name = fn["name"]
                is_exported = fn_name in exports
                fn_lines = fn["endLine"] - fn["startLine"] + 1
                
                if fn_lines >= 10 or is_exported:
                    fn_id = f"function:{path}:{fn_name}"
                    nodes.append({
                        "id": fn_id,
                        "type": "function",
                        "name": fn_name,
                        "filePath": path,
                        "lineRange": [fn["startLine"], fn["endLine"]],
                        "summary": f"实现 {fn_name} 逻辑的函数或方法。",
                        "tags": ["function", "logic", "handler"],
                        "complexity": "simple" if fn_lines < 20 else "moderate"
                    })
                    edges.append({
                        "source": node_id,
                        "target": fn_id,
                        "type": "contains",
                        "direction": "forward",
                        "weight": 1.0
                    })
                    if is_exported:
                        edges.append({
                            "source": node_id,
                            "target": fn_id,
                            "type": "exports",
                            "direction": "forward",
                            "weight": 0.8
                        })
                        
            for cls in res.get("classes", []):
                cls_name = cls["name"]
                is_exported = cls_name in exports
                cls_lines = cls["endLine"] - cls["startLine"] + 1
                methods_count = len(cls.get("methods", []))
                
                if cls_lines >= 20 or methods_count >= 2 or is_exported:
                    cls_id = f"class:{path}:{cls_name}"
                    nodes.append({
                        "id": cls_id,
                        "type": "class",
                        "name": cls_name,
                        "filePath": path,
                        "lineRange": [cls["startLine"], cls["endLine"]],
                        "summary": f"定义 {cls_name} 的类结构。",
                        "tags": ["class", "schema-definition", "data-model"] if "Migration" not in cls_name else ["class", "migration"],
                        "complexity": "simple" if cls_lines < 50 else "moderate"
                    })
                    edges.append({
                        "source": node_id,
                        "target": cls_id,
                        "type": "contains",
                        "direction": "forward",
                        "weight": 1.0
                    })
                    if is_exported:
                        edges.append({
                            "source": node_id,
                            "target": cls_id,
                            "type": "exports",
                            "direction": "forward",
                            "weight": 0.8
                        })
    
    # Validation logic
    node_count = len(nodes)
    edge_count = len(edges)
    
    if node_count <= 60 and edge_count <= 120:
        out_path = r"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\intermediate\batch-34.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f, ensure_ascii=False, indent=2)
        print(f"Wrote 1 part, nodes: {node_count}, edges: {edge_count}")
    else:
        parts = math.ceil(max(node_count / 60, edge_count / 120))
        # Sort nodes by filePath
        files = sorted(list(set([n.get("filePath", "") for n in nodes])))
        chunk_size = math.ceil(len(files) / parts)
        
        for k in range(parts):
            chunk_files = files[k*chunk_size : (k+1)*chunk_size]
            part_nodes = [n for n in nodes if n.get("filePath", "") in chunk_files]
            part_node_ids = set(n["id"] for n in part_nodes)
            part_edges = [e for e in edges if e["source"] in part_node_ids]
            
            out_path = fr"C:\SVN_CODE\branches\real\could_frontend\.understand-anything\intermediate\batch-34-part-{k+1}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"nodes": part_nodes, "edges": part_edges}, f, ensure_ascii=False, indent=2)
            print(f"Wrote part {k+1}, nodes: {len(part_nodes)}, edges: {len(part_edges)}")

if __name__ == "__main__":
    run()
