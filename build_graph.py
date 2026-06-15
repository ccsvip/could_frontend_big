import json
import math
import os

with open(r'C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-extract-results-1.json', 'r', encoding='utf-8') as f:
    extract_data = json.load(f)

with open(r'C:\SVN_CODE\branches\real\could_frontend\.understand-anything\tmp\ua-file-analyzer-input-1.json', 'r', encoding='utf-8') as f:
    input_data = json.load(f)

import_data = input_data.get('batchImportData', {})
neighbor_map = input_data.get('neighborMap', {})
batch_files = {item['path']: item for item in input_data.get('batchFiles', [])}

nodes = []
edges = []

file_summaries = {
    "backend/apps/ai_models/tests/test_asr_realtime.py": ("ASR实时语音识别接口测试用例，覆盖WebSocket连接建立、文本提取和替换规则。", ["test", "websocket", "asr", "realtime"]),
    "backend/apps/audit/middleware.py": ("全局操作审计中间件，记录用户在系统中的关键操作日志，支持租户级别的数据隔离。", ["middleware", "audit", "security", "logging"]),
    "backend/apps/devices/admin.py": ("设备模块的Django Admin配置，用于在后台管理面板管理设备和激活记录。", ["configuration", "admin", "device-management"]),
    "backend/apps/devices/management/commands/seed_devices.py": ("设备数据种子脚本，用于开发环境初始化设备数据，创建默认设备和租户关联。", ["script", "seed", "device", "initialization"]),
    "backend/apps/devices/models.py": ("设备模块的数据模型，定义了Device及激活记录表结构，处理设备鉴权与租户关联。", ["data-model", "device", "database", "tenant"]),
    "backend/apps/devices/realtime.py": ("设备实时通信模块，处理设备WebSocket连接认证、权限校验和心跳维护。", ["realtime", "websocket", "device", "authentication"]),
    "backend/apps/devices/serializers.py": ("设备模块的数据序列化器，用于在API中序列化设备信息、校验请求数据。", ["serialization", "device", "api", "validation"]),
    "backend/apps/devices/tests/test_device_authorization_api.py": ("设备授权API接口的单元测试，验证基于DeviceCode的免登录访问和跨租户隔离。", ["test", "device", "authorization", "api"]),
    "backend/apps/devices/tokens.py": ("设备令牌管理模块，用于签发和验证基于DeviceCode的短效访问令牌。", ["security", "token", "device", "authentication"]),
    "backend/apps/devices/urls.py": ("设备模块的路由配置文件，将设备相关API注册到路由系统。", ["configuration", "routing", "device", "api"]),
    "backend/apps/devices/views.py": ("设备模块的视图和API接口，提供设备的增删改查、鉴权以及状态管理功能。", ["api-handler", "device", "controller", "management"]),
    "backend/apps/devices/websocket.py": ("设备WebSocket核心逻辑，处理设备状态推送、流式下发指令及实时响应。", ["websocket", "realtime", "device", "communication"]),
    "backend/apps/resources/admin.py": ("资源模块的Django Admin配置，管理多媒体资源、模型资产、语音音色等。", ["configuration", "admin", "resource"]),
    "backend/apps/resources/models.py": ("资源模块的数据模型，包含多媒体、文字指令、任务流、视频配额等模型定义。", ["data-model", "resource", "database"]),
    "backend/apps/resources/point_models.py": ("点位数据模型，定义监控或巡检场景下的物理点位和关联资源。", ["data-model", "point", "database"]),
    "backend/apps/resources/point_runtime.py": ("点位运行时逻辑，构建设备端点位信息的下发数据结构。", ["utility", "point", "runtime", "data-structure"]),
    "backend/apps/resources/point_serializers.py": ("点位数据的序列化器，用于前端展示与API通信。", ["serialization", "point", "api"]),
    "backend/apps/resources/point_views.py": ("点位数据的API视图，提供增删改查及查询功能。", ["api-handler", "point", "controller"]),
    "backend/apps/resources/serializers.py": ("核心资源序列化器，包括任务流、资源下发、Minio配置、视频配额等序列化逻辑。", ["serialization", "resource", "api", "task-flow"]),
    "backend/apps/resources/services/aliyun_commands.py": ("阿里云IoT指令服务集成，封装与阿里云平台的命令下发通信和鉴权。", ["service", "aliyun", "iot", "integration"]),
    "backend/apps/resources/services/minio_client.py": ("Minio对象存储客户端服务，处理文件上传、预签名URL生成、视频容量控制。", ["service", "storage", "minio", "file-upload"]),
    "backend/apps/resources/tests/test_minio_client.py": ("Minio客户端服务测试用例，验证存储对象前缀、视频配额以及URL签名功能。", ["test", "storage", "minio", "unit-test"]),
    "backend/apps/resources/tests/test_minio_settings_api.py": ("Minio设置与视频配额相关的API接口测试。", ["test", "api", "storage", "configuration"]),
    "backend/apps/resources/urls.py": ("资源模块路由配置，映射各资源类型及指令相关的接口路由。", ["configuration", "routing", "resource"]),
    "backend/apps/resources/views.py": ("资源模块主视图集合，提供多类型资产及命令工作流的管理API。", ["api-handler", "resource", "controller", "workflow"]),
    "backend/apps/tenants/admin.py": ("多租户架构Django Admin配置，管理公司租户与人员归属记录。", ["configuration", "admin", "tenant"]),
    "backend/apps/tenants/managers.py": ("租户自定义查询管理器，用于在数据库层面自动附加租户隔离过滤条件。", ["utility", "database", "tenant", "query"]),
    "backend/apps/tenants/mixins.py": ("多租户Mixin扩展，为视图自动注入基于当前登录用户的租户过滤逻辑。", ["utility", "mixin", "tenant", "security"]),
    "backend/apps/tenants/models.py": ("多租户核心数据模型，定义公司(Tenant)和用户关联(Membership)表。", ["data-model", "tenant", "database"]),
    "backend/apps/tenants/services.py": ("多租户核心业务服务，处理基于上下文解析租户、构建数据隔离域等逻辑。", ["service", "tenant", "business-logic", "isolation"]),
    "backend/apps/tenants/tests/test_cross_tenant_isolation.py": ("跨租户数据隔离机制测试，验证API和数据模型层面的防越权控制。", ["test", "security", "tenant", "isolation"]),
    "backend/apps/tenants/tests/test_employee_management_api.py": ("员工管理相关API的测试用例，校验租户内人员增删改查的逻辑。", ["test", "api", "employee", "tenant"]),
    "backend/apps/tenants/tests/test_isolation_contract.py": ("租户数据契约测试，检查所有定义了tenant外键的模型是否都应用了隔离策略。", ["test", "security", "database", "contract"]),
    "backend/apps/tenants/tests/test_tenant_management_api.py": ("租户主体管理API测试用例。", ["test", "api", "tenant", "management"])
}

def get_complexity(lines):
    if lines < 50: return "simple"
    if lines < 200: return "moderate"
    return "complex"

created_node_ids = set()

for file_result in extract_data.get('results', []):
    path = file_result['path']
    f_cat = batch_files.get(path, {}).get('fileCategory', 'code')
    size_lines = file_result.get('nonEmptyLines', 0)
    
    summary, tags = file_summaries.get(path, ("提供后端系统业务或测试逻辑支持。", ["backend", "module"]))
    complexity = get_complexity(size_lines)
    
    node_type = "file"
    if f_cat == "config": node_type = "config"
    elif "tests" in path: node_type = "file"
    
    file_node_id = f"{node_type}:{path}"
    
    nodes.append({
        "id": file_node_id,
        "type": node_type,
        "name": path.split('/')[-1],
        "filePath": path,
        "summary": summary,
        "tags": tags,
        "complexity": complexity
    })
    created_node_ids.add(file_node_id)
    
    # functions
    for f_node in file_result.get('functions', []):
        lines = f_node.get('endLine', 0) - f_node.get('startLine', 0) + 1
        is_exported = any(e.get('name') == f_node['name'] for e in file_result.get('exports', []))
        if lines >= 10 or is_exported:
            func_id = f"function:{path}:{f_node['name']}"
            nodes.append({
                "id": func_id,
                "type": "function",
                "name": f_node['name'],
                "filePath": path,
                "lineRange": [f_node.get('startLine', 0), f_node.get('endLine', 0)],
                "summary": f"{f_node['name']} 方法的实现，提供具体的数据处理或业务计算。",
                "tags": ["function", "implementation"],
                "complexity": get_complexity(lines)
            })
            created_node_ids.add(func_id)
            edges.append({
                "source": file_node_id,
                "target": func_id,
                "type": "contains",
                "direction": "forward",
                "weight": 1.0
            })
            if is_exported:
                edges.append({
                    "source": file_node_id,
                    "target": func_id,
                    "type": "exports",
                    "direction": "forward",
                    "weight": 0.8
                })
                
    # classes
    for c_node in file_result.get('classes', []):
        lines = c_node.get('endLine', 0) - c_node.get('startLine', 0) + 1
        is_exported = any(e.get('name') == c_node['name'] for e in file_result.get('exports', []))
        methods = len(c_node.get('methods', []))
        if lines >= 20 or methods >= 2 or is_exported:
            class_id = f"class:{path}:{c_node['name']}"
            
            c_sum = f"{c_node['name']} 类的实现"
            if "View" in c_node['name'] or "ViewSet" in c_node['name']:
                c_sum += "，处理API请求和视图逻辑。"
                c_tag = ["api-handler", "controller"]
            elif "Serializer" in c_node['name']:
                c_sum += "，负责数据序列化与校验。"
                c_tag = ["serialization", "data-validation"]
            elif "Model" in c_node['name'] or path.endswith("models.py"):
                c_sum += "，定义数据库表结构和实体关系。"
                c_tag = ["data-model", "database"]
            elif "Test" in c_node['name']:
                c_sum += "，定义相关模块的自动化测试套件。"
                c_tag = ["test", "unit-test"]
            else:
                c_sum += "，封装相关的数据模型或业务功能。"
                c_tag = ["class", "component"]
                
            nodes.append({
                "id": class_id,
                "type": "class",
                "name": c_node['name'],
                "filePath": path,
                "lineRange": [c_node.get('startLine', 0), c_node.get('endLine', 0)],
                "summary": c_sum,
                "tags": c_tag,
                "complexity": get_complexity(lines)
            })
            created_node_ids.add(class_id)
            edges.append({
                "source": file_node_id,
                "target": class_id,
                "type": "contains",
                "direction": "forward",
                "weight": 1.0
            })
            if is_exported:
                edges.append({
                    "source": file_node_id,
                    "target": class_id,
                    "type": "exports",
                    "direction": "forward",
                    "weight": 0.8
                })

    # Add import edges
    imports = import_data.get(path, [])
    for imp in imports:
        edges.append({
            "source": file_node_id,
            "target": f"file:{imp}",
            "type": "imports",
            "direction": "forward",
            "weight": 0.7
        })

    # Add tested_by edges if applicable
    if "tests" in path:
        for imp in imports:
            if "tests" not in imp:
                edges.append({
                    "source": f"file:{imp}",
                    "target": file_node_id,
                    "type": "tested_by",
                    "direction": "forward",
                    "weight": 0.5
                })

# Add calls edges for confident internal refs
for file_result in extract_data.get('results', []):
    path = file_result['path']
    for call in file_result.get('callGraph', []):
        caller = f"function:{path}:{call['caller']}"
        callee = f"function:{path}:{call['callee']}"
        if caller in created_node_ids and callee in created_node_ids:
            edges.append({
                "source": caller,
                "target": callee,
                "type": "calls",
                "direction": "forward",
                "weight": 0.8
            })

node_count = len(nodes)
edge_count = len(edges)

if node_count <= 60 and edge_count <= 120:
    parts = 1
else:
    parts = math.ceil(max(node_count / 60.0, edge_count / 120.0))

file_paths = sorted(list(batch_files.keys()))
chunk_size = math.ceil(len(file_paths) / parts)

def get_part_for_file(p):
    if not p: return 1
    idx = file_paths.index(p) if p in file_paths else 0
    return (idx // chunk_size) + 1

for k in range(1, parts + 1):
    part_nodes = []
    part_edges = []
    
    for n in nodes:
        fp = n.get('filePath')
        if fp and get_part_for_file(fp) == k:
            part_nodes.append(n)
            
    part_node_ids = {n['id'] for n in part_nodes}
    for e in edges:
        source_id = e['source']
        if source_id in part_node_ids:
            part_edges.append(e)
            
    out_name = f'batch-1.json' if parts == 1 else f'batch-1-part-{k}.json'
    out_path = fr'C:\SVN_CODE\branches\real\could_frontend\.understand-anything\intermediate\{out_name}'
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'nodes': part_nodes, 'edges': part_edges}, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_name} with {len(part_nodes)} nodes and {len(part_edges)} edges")

