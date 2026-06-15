import json
import math
import os

def create_nodes_and_edges(batch_idx, file_metadata):
    with open(f'.understand-anything/tmp/batch-input-6.json', 'r', encoding='utf-8') as f:
        batches = json.load(f)
    
    batch_data = next(b for b in batches if b['batchIndex'] == batch_idx)
    batch_import_data = batch_data.get('batchImportData', {})
    neighbor_map = batch_data.get('neighborMap', {})
    
    with open(f'.understand-anything/tmp/ua-file-extract-results-{batch_idx}.json', 'r', encoding='utf-8') as f:
        extract_data = json.load(f)
    
    results = extract_data.get('results', [])
    
    nodes = []
    edges = []
    
    for res in results:
        path = res['path']
        cat = res['fileCategory']
        meta = file_metadata.get(path, {})
        
        # File node
        node_type = 'file'
        if cat == 'config': node_type = 'config'
        elif cat == 'docs': node_type = 'document'
        elif cat == 'infra':
            if 'docker' in path.lower() or 'manifest' in path.lower(): node_type = 'service'
            elif 'workflow' in path.lower() or 'ci' in path.lower(): node_type = 'pipeline'
            else: node_type = 'resource'
        elif cat == 'data':
            if '.sql' in path.lower(): node_type = 'table'
            elif 'schema' in path.lower() or '.proto' in path.lower() or '.graphql' in path.lower(): node_type = 'schema'
            else: node_type = 'endpoint'
        elif cat == 'script': node_type = 'file'
        elif cat == 'markup': node_type = 'file'
            
        file_id = f"{node_type}:{path}"
        
        complexity = 'simple'
        nl = res.get('nonEmptyLines', 0)
        if nl > 200: complexity = 'complex'
        elif nl > 50: complexity = 'moderate'
        
        summary = meta.get('summary', f"实现了 {os.path.basename(path)} 的相关逻辑。")
        tags = meta.get('tags', ['utility', 'script'])
        language_notes = meta.get('languageNotes')
        
        node = {
            "id": file_id,
            "type": node_type,
            "name": os.path.basename(path),
            "filePath": path,
            "summary": summary,
            "tags": tags,
            "complexity": complexity
        }
        if language_notes:
            node["languageNotes"] = language_notes
            
        nodes.append(node)
        
        # Imports edges & tested_by
        is_test_file = 'test' in path.lower()
        imports = batch_import_data.get(path, [])
        for imp in imports:
            # 1:1 emission NO aggregation
            edges.append({
                "source": file_id,
                "target": f"file:{imp}",
                "type": "imports",
                "direction": "forward",
                "weight": 0.7
            })
            
            # tested_by (source=test, target=prod, merge script will flip to prod->test)
            if is_test_file and 'test' not in imp.lower():
                edges.append({
                    "source": file_id,
                    "target": f"file:{imp}",
                    "type": "tested_by",
                    "direction": "forward",
                    "weight": 0.5
                })
            
        # Functions and classes
        functions = res.get('functions', [])
        classes = res.get('classes', [])
        exports = {e['name'] for e in res.get('exports', [])}
        
        for func in functions:
            name = func['name']
            start = func.get('startLine', 0)
            end = func.get('endLine', 0)
            is_exported = name in exports
            if (end - start + 1 >= 10) or is_exported:
                func_id = f"function:{path}:{name}"
                nodes.append({
                    "id": func_id,
                    "type": "function",
                    "name": name,
                    "filePath": path,
                    "lineRange": [start, end],
                    "summary": f"提供 {name} 函数的实现。",
                    "tags": ["function", "logic", "utility"] + (["exported"] if is_exported else []),
                    "complexity": "moderate" if end - start > 50 else "simple"
                })
                edges.append({
                    "source": file_id,
                    "target": func_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0
                })
                if is_exported:
                    edges.append({
                        "source": file_id,
                        "target": func_id,
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8
                    })
                    
        for cls in classes:
            name = cls['name']
            start = cls.get('startLine', 0)
            end = cls.get('endLine', 0)
            methods = cls.get('methods', [])
            is_exported = name in exports
            if len(methods) >= 2 or (end - start + 1 >= 20) or is_exported:
                cls_id = f"class:{path}:{name}"
                nodes.append({
                    "id": cls_id,
                    "type": "class",
                    "name": name,
                    "filePath": path,
                    "lineRange": [start, end],
                    "summary": f"定义 {name} 类，提供相关数据模型或业务逻辑。",
                    "tags": ["class", "data-model"] + (["exported"] if is_exported else []),
                    "complexity": "complex" if end - start > 100 else ("moderate" if end - start > 30 else "simple")
                })
                edges.append({
                    "source": file_id,
                    "target": cls_id,
                    "type": "contains",
                    "direction": "forward",
                    "weight": 1.0
                })
                if is_exported:
                    edges.append({
                        "source": file_id,
                        "target": cls_id,
                        "type": "exports",
                        "direction": "forward",
                        "weight": 0.8
                    })

    # Writing out chunks
    node_count = len(nodes)
    edge_count = len(edges)
    
    parts = 1
    if node_count > 60 or edge_count > 120:
        parts = math.ceil(max(node_count / 60, edge_count / 120))
        
    print(f"Batch {batch_idx}: {node_count} nodes, {edge_count} edges -> {parts} parts")
    
    os.makedirs('.understand-anything/intermediate', exist_ok=True)
    
    if parts == 1:
        with open(f'.understand-anything/intermediate/batch-{batch_idx}.json', 'w', encoding='utf-8') as f:
            json.dump({"nodes": nodes, "edges": edges}, f, ensure_ascii=False, indent=2)
    else:
        # Sort files
        all_files = sorted(list(set(n.get('filePath') for n in nodes if n.get('filePath'))))
        chunk_size = math.ceil(len(all_files) / parts)
        
        for k in range(parts):
            chunk_files = set(all_files[k*chunk_size : (k+1)*chunk_size])
            part_nodes = [n for n in nodes if n.get('filePath') in chunk_files]
            part_node_ids = set(n['id'] for n in part_nodes)
            
            # Edges whose source is in this part's nodes
            part_edges = [e for e in edges if e['source'] in part_node_ids]
            
            out_file = f'.understand-anything/intermediate/batch-{batch_idx}-part-{k+1}.json'
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump({"nodes": part_nodes, "edges": part_edges}, f, ensure_ascii=False, indent=2)

file_metadata_7 = {
    "backend/apps/ai_models/admin.py": {
        "summary": "Django admin 配置文件，用于管理 AI 模型和相关资源的后台界面。",
        "tags": ["admin", "configuration", "data-model"]
    },
    "backend/apps/ai_models/llm_services.py": {
        "summary": "大语言模型（LLM）服务封装层，提供与多种底层大模型平台的统一交互接口。",
        "tags": ["service", "llm", "api-wrapper"]
    },
    "backend/apps/ai_models/models.py": {
        "summary": "定义 AI 模型的数据库结构，包括模型配置、租户隔离等核心业务表。",
        "tags": ["data-model", "database", "schema-definition"]
    },
    "backend/apps/ai_models/realtime_asr.py": {
        "summary": "处理实时语音识别（ASR）的逻辑，包含音频流接收与转写服务对接。",
        "tags": ["api-handler", "audio-processing", "service"]
    },
    "backend/apps/ai_models/serializers.py": {
        "summary": "DRF 序列化器，用于在 AI 模型相关的 API 请求与响应中进行数据转换与校验。",
        "tags": ["serialization", "validation", "api"]
    },
    "backend/apps/ai_models/services/__init__.py": {
        "summary": "AI 模型服务模块的导出点（Barrel file）。",
        "tags": ["entry-point", "barrel"]
    },
    "backend/apps/ai_models/services/asr.py": {
        "summary": "语音识别（ASR）具体服务实现，负责对接外部 ASR 提供商 API 并处理业务逻辑。",
        "tags": ["service", "audio-processing", "integration"]
    },
    "backend/apps/ai_models/services/tts.py": {
        "summary": "文本转语音（TTS）服务实现，调用外部合成接口以生成音频流或文件。",
        "tags": ["service", "audio-processing", "integration"]
    },
    "backend/apps/ai_models/tests/test_asr_api.py": {
        "summary": "针对语音识别（ASR）API 的自动化测试用例，覆盖不同请求场景及权限验证。",
        "tags": ["test", "api-test", "quality-assurance"]
    },
    "backend/apps/ai_models/tests/test_chat_api.py": {
        "summary": "针对对话大模型（Chat）API 的自动化测试用例，包含多轮对话和上下文验证。",
        "tags": ["test", "api-test", "quality-assurance"]
    },
    "backend/apps/ai_models/tests/test_llm_model_usage.py": {
        "summary": "验证 LLM 模型用量统计与限流规则的测试用例。",
        "tags": ["test", "metrics", "quality-assurance"]
    },
    "backend/apps/ai_models/tests/test_llm_platform_settings_api.py": {
        "summary": "针对底层 LLM 平台配置与管理 API 的测试集。",
        "tags": ["test", "api-test", "quality-assurance"]
    },
    "backend/apps/ai_models/tests/test_tts_api.py": {
        "summary": "针对文本转语音（TTS）API 的测试用例。",
        "tags": ["test", "api-test", "quality-assurance"]
    },
    "backend/apps/ai_models/urls.py": {
        "summary": "定义 AI 模型相关功能的 URL 路由映射。",
        "tags": ["router", "api", "configuration"]
    },
    "backend/apps/ai_models/views.py": {
        "summary": "DRF 视图层，处理与 AI 模型（含 LLM、ASR、TTS）有关的所有 HTTP 接口请求。",
        "tags": ["api-handler", "controller", "endpoint"]
    },
    "backend/apps/tenants/tests/test_llm_isolation.py": {
        "summary": "测试多租户环境下 LLM 模型数据与调用的隔离性。",
        "tags": ["test", "security", "multi-tenant"]
    }
}

file_metadata_8 = {
    ".claude/skills/impeccable/scripts/detector/cli/main.mjs": {
        "summary": "反模式检测工具的命令行入口，负责解析参数并启动相应的检测引擎。",
        "tags": ["entry-point", "cli", "script"]
    },
    ".claude/skills/impeccable/scripts/detector/detect-antipatterns.mjs": {
        "summary": "反模式检测的核心协调逻辑，根据目标类型分发至对应的规则检测引擎。",
        "tags": ["controller", "logic", "orchestration"]
    },
    ".claude/skills/impeccable/scripts/detector/engines/browser/detect-url.mjs": {
        "summary": "浏览器环境下的检测引擎，通过加载 URL 并进行动态 DOM 分析来识别问题。",
        "tags": ["engine", "browser-automation", "analysis"]
    },
    ".claude/skills/impeccable/scripts/detector/engines/regex/detect-text.mjs": {
        "summary": "基于正则表达式的文本级反模式检测引擎，用于快速扫描源代码或静态内容。",
        "tags": ["engine", "regex", "static-analysis"]
    },
    ".claude/skills/impeccable/scripts/detector/engines/static-html/css-cascade.mjs": {
        "summary": "解析并检测静态 HTML 中 CSS 层叠与特异性问题的逻辑。",
        "tags": ["engine", "css-analysis", "static-analysis"]
    },
    ".claude/skills/impeccable/scripts/detector/engines/static-html/detect-html.mjs": {
        "summary": "静态 HTML 反模式检测引擎，分析结构与标签使用是否符合最佳实践。",
        "tags": ["engine", "html-analysis", "static-analysis"]
    },
    ".claude/skills/impeccable/scripts/detector/engines/visual/screenshot-contrast.mjs": {
        "summary": "视觉层面的检测引擎，通过截图分析界面元素的色彩对比度是否达标。",
        "tags": ["engine", "visual-analysis", "accessibility"]
    },
    ".claude/skills/impeccable/scripts/detector/findings.mjs": {
        "summary": "定义检测结果与问题的标准数据结构，以及报告汇总逻辑。",
        "tags": ["data-model", "reporting", "utility"]
    },
    ".claude/skills/impeccable/scripts/detector/node/file-system.mjs": {
        "summary": "提供针对 Node.js 文件系统的操作封装，以支持检测引擎加载目标文件。",
        "tags": ["utility", "file-io", "system"]
    },
    ".claude/skills/impeccable/scripts/detector/profile/profiler.mjs": {
        "summary": "检测过程的性能分析器，记录各项检测规则的耗时与执行效率。",
        "tags": ["utility", "profiling", "metrics"]
    },
    ".claude/skills/impeccable/scripts/detector/registry/antipatterns.mjs": {
        "summary": "预定义的反模式注册表，列举了所有受支持的检测规则及其元数据。",
        "tags": ["registry", "configuration", "ruleset"]
    },
    ".claude/skills/impeccable/scripts/detector/rules/checks.mjs": {
        "summary": "包含具体反模式检测规则的实现逻辑集合，如颜色空间、布局嵌套等检查。",
        "tags": ["rules", "logic", "validation"]
    },
    ".claude/skills/impeccable/scripts/detector/shared/color.mjs": {
        "summary": "通用的颜色操作与转换工具函数，辅助进行视觉与对比度检测。",
        "tags": ["utility", "color", "shared"]
    },
    ".claude/skills/impeccable/scripts/detector/shared/constants.mjs": {
        "summary": "定义检测系统全局共享的常量，如错误码、默认阈值等。",
        "tags": ["constants", "configuration", "shared"]
    },
    ".claude/skills/impeccable/scripts/detector/shared/page.mjs": {
        "summary": "页面相关的基础操作与常量，提供给不同引擎统一的上下文支持。",
        "tags": ["utility", "page-context", "shared"]
    }
}

create_nodes_and_edges(7, file_metadata_7)
create_nodes_and_edges(8, file_metadata_8)
