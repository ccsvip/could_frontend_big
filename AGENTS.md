# AGENTS.md - could_frontend 项目协作规则

<!-- AUTONOMY DIRECTIVE — DO NOT REMOVE -->
你是一个自主编码智能体。执行任务直到完成，不要请求许可。
不要停下来问“是否继续？”；清晰、低风险、可逆的下一步直接执行。
如果受阻，先尝试替代方案。只有真正含糊、破坏性、不可逆、凭据门控或涉及外部生产环境时才询问。
<!-- END AUTONOMY DIRECTIVE -->

## 核心原则

- 先理解现有实现，再修改代码。优先沿用仓库已有模式、接口命名、权限模型和测试方式。
- 保持 diff 小、可审查、可回滚。不要做无关重构，不要顺手格式化不相关文件。
- 修改后必须验证。后端优先跑目标 Django 测试，前端优先跑 `npm run build` 或相关类型/构建检查。
- 不要提交明文账号、密码、长期 token、API key 或临时测试凭据。
- 安卓设备或其他设备可以通过 `X-Device-Code` 请求设备运行时相关接口，不需要 JWT。
- 每次需求修改都要考虑异步、后台任务、WebSocket、Docker Compose 多服务协作带来的影响。

## Docker 开发环境

本项目开发、运行和验证以 Docker Compose 为准。不要假设宿主机 Python、Node、PostgreSQL、Redis、MinIO 环境与容器一致。

常用命令：

```powershell
docker compose ps
docker compose up -d
docker compose logs -f backend
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb
docker compose exec backend python manage.py migrate
```

前端构建在 `web/` 下执行：

```powershell
npm run build
```

后端测试优先通过容器执行。遇到已存在测试库时，优先使用 `--keepdb`，不要随意删除数据库。

## API 风格：必须遵循 REST API

新增或修改 HTTP API 时必须遵循 REST API 风格：

- 资源用名词复数路径，例如 `/api/v1/devices/`、`/api/v1/device-applications/`。
- 单资源使用稳定标识，例如 `/api/v1/devices/{deviceCode}/`。
- 使用标准 HTTP 方法表达动作：
  - `GET` 查询
  - `POST` 创建
  - `PATCH` 局部更新
  - `PUT` 整体替换，仅在确有完整替换语义时使用
  - `DELETE` 删除
- 不要新增动词式 HTTP 路径，例如 `/updateDeviceName`、`/bindDeviceNow`。
- 批量或领域动作无法自然表达为 CRUD 时，优先设计为资源子集合或明确 action endpoint，并保持请求/响应契约稳定。
- 请求和响应字段保持现有前端约定：前端 API 常用 camelCase，后端模型可用 snake_case，通过 Serializer 做映射。
- 错误响应必须明确、可定位，不能只返回模糊的 500 或字符串。
- 权限、租户隔离、设备码认证必须集中处理，不要在业务函数中散落临时绕过。

### 实时能力例外

实时通信不通过新增多个业务 WebSocket URL 实现。第一方实时能力使用统一 WebSocket 入口，并通过明确的 `type` / command name / payload contract 路由。

HTTP API 仍必须保持 REST 风格；WebSocket 只用于实时事件、流式能力和订阅类场景。

## 设备与权限约定

- 设备运行时配置入口：`GET /api/v1/device-runtime/config/`。
- 后台设备管理入口：`/api/v1/devices/`，单设备 lookup 使用 `deviceCode`。
- 设备名称由后台维护。安卓首次登记可默认“待修改”，安卓上报不应覆盖后台维护的设备名称。
- 公司管理员和公司员工权限基本一致；员工看不到员工管理，其它功能一致。后续不要反复询问这个差异。
- 公司数据必须按 tenant 隔离。普通公司账号不得通过 query 参数越权访问其他公司数据。
- 平台管理员按公司浏览时，只能通过已有 tenant scope 机制访问业务列表。
- 只维护一个websocet 可以通过不通过type去实现不同功能。
- 不同公司数据要保证100%隔离

## 修改前后的最低检查

修改前：

- 用 `rg` 或 `codebase-memory-mcp` 找入口和影响面。
- 读真实源码确认图谱结论。
- 明确 REST 路径、Serializer 字段、权限、前端 API 类型和异步影响。

修改后：

- 后端改动：跑相关 Django 测试，优先容器内执行。
- 前端改动：至少跑 `npm run build`。
- API 改动：确认前端 API module、页面调用、文档/模拟器是否需要同步。
- 运行时/设备改动：确认 `X-Device-Code`、在线/离线状态、heartbeat、统一 WebSocket 事件不会被破坏。

## Git 与提交

- 只提交与当前任务相关的改动。
- 暂存区已有用户改动时，不要擅自撤销；先识别哪些是当前任务需要提交的内容。
- 提交信息优先使用中文，简洁描述业务结果。

## 前端图标规范

- 图标库统一使用 **@tabler/icons-react**，不再使用 `@ant-design/icons` 或 `lucide-react`。
- Tabler Icons 命名统一以 `Icon` 前缀（如 `IconDatabase`、IconArrowLeft`）。
- 图标大小通过 `size` 属性控制，不依赖 Tailwind `text-*` 类缩放 SVG。
- 每个文件只从 `@tabler/icons-react` 统一导入一次，不混用多套图标库。

## 代码查询工具使用规则

你有两套代码图谱工具，按"先快后深、按需升级"的原则路由。

### 第一优先级：codebase-memory-mcp（零成本 · 亚毫秒级）

**触发条件**（满足任一即用）：
- 查询目标明确，答案可直接从图结构提取，无需多步推理
- 需要精确的调用链、依赖关系、源码片段
- 高频日常导航（每次会话中反复出现的查询）

**工具映射**：

| 意图 | 工具 |
|---|---|
| 谁调用 / 被调用了 X | `trace_path`（direction: inbound/outbound） |
| 按名称/文件/度数找节点 | `search_graph`（name_pattern、file_pattern、degree 过滤） |
| 自定义图遍历查询 | `query_graph`（openCypher 读子集） |
| 读取函数源码 | `get_code_snippet`（需先用 search_graph 获取限定名） |
| 项目架构概览 | `get_architecture` |
| git diff 影响了哪些符号 | `detect_changes` |
| 全文搜索代码 | `search_code` |
| 死代码检测 | `query_graph` 查零入度节点 |
| 图的 schema 和统计 | `get_graph_schema`（首次查询前先跑一次） |

**注意**：`trace_path` 返回空时，先用 `search_graph(name_pattern=".*PartialName.*")` 找到精确节点名再重试。

### 第二优先级：CodeGraph agentic 工具（消耗 token · 多步推理）

**触发条件**（满足任一才用，不要默认走这层）：
- 第一优先级的结构查询已执行，但结果需要跨多个维度综合判断
- 问题本身是开放式的（"什么会崩""架构有什么问题""重构优先级"）
- 需要语义搜索（自然语言描述意图，而非精确符号名）
- 需要耦合度、复杂度等质量度量

**工具映射**：

| 意图 | 工具 | focus 参数 |
|---|---|---|
| 语义搜索 / 上下文构建 / 自然语言问答 | `agentic_context` | "search" / "builder" / "question" |
| 重构影响评估、变更爆炸半径 | `agentic_impact` | "dependencies" / "call_chain" |
| 系统结构、API 边界、架构模式 | `agentic_architecture` | "structure" / "api_surface" |
| 复杂度热点、耦合度量、重构优先级 | `agentic_quality` | "complexity" / "coupling" / "hotspots" |

### 升级路径

不要一上来就调 agentic 工具。按以下顺序推进：

1. `get_graph_schema` → 了解图结构
2. `search_graph` / `trace_path` → 快速定位目标节点和直接关系
3. 若结果已足够回答 → 直接输出，停止
4. 若需要跨维度综合判断 → 升级到对应的 agentic 工具，把前序查询结果作为 focus 参数传入

### 边界情况

- **语言覆盖**：codebase-memory-mcp 支持 158 种语言，CodeGraph 仅支持 14 种（Rust/Python/TS/JS/Go/Java/C++/C/Swift/Kotlin/C#/Ruby/PHP/Dart）。项目含 CodeGraph 不支持的语言时，该部分只能用 codebase-memory-mcp。
- **未索引项目**：两个工具都需要先索引。若查询返回空且项目未索引，先调用 `index_repository`（codebase-memory-mcp）和 `codegraph index`（CodeGraph）。
- **成本敏感场景**：若用户明确要求节省 token，全程只用第一优先级，跳过 agentic 工具。

### 索引自动维护规则

索引新鲜度直接影响查询准确性。按以下规则主动维护，不要完全依赖后台 watcher。

#### 会话启动时

- 首次查询前，先调用 `index_status`（codebase-memory-mcp）确认项目已索引
- 若返回未索引或状态异常 → 立即调用 `index_repository` 完成首次索引
- 若项目含 CodeGraph 支持的语言且本次会话可能用到 agentic 工具 → 确认 CodeGraph 索引也存在

#### 代码变更后

当你（代理自身）对代码做了以下操作后，主动触发增量索引，再继续后续查询：

| 变更类型 | 触发动作 |
|---|---|
| 新建 / 删除文件 | 两个工具都需要重新索引该文件影响范围 |
| 修改函数签名、类结构、导入关系 | codebase-memory-mcp 的 `index_repository` 会自动增量同步；CodeGraph 需 `codegraph index . --index-tier balanced` |
| 仅修改函数内部实现（签名不变） | 结构图谱不受影响，无需重新索引；但若后续要用 `agentic_context` 做语义搜索，嵌入可能过期，需重新索引 |

**执行时机**：在完成编辑操作（如 Edit/Write 工具调用）之后、下一次图谱查询之前，插入一次索引同步。不要在编辑中途触发，避免索引到半成品状态。

#### 查询异常时

若查询返回空结果或结果明显过期（比如你刚创建的函数查不到），按以下顺序排查：

1. 先调用 `index_status` 确认索引时间戳是否早于你的最后一次编辑
2. 若索引过期 → 调用 `index_repository` 增量同步 → 重新查询
3. 若索引是最新的但仍查不到 → 用 `search_graph(name_pattern=".*PartialName.*")` 做模糊匹配，确认节点是否因命名差异未命中
4. 若以上都无效 → 可能是解析失败，检查文件是否在 `.gitignore` 或 `.cbmignore` 中被排除

#### 成本控制

- 增量索引本身零 LLM 成本，可以放心触发
- 但避免无意义的频繁索引：同一文件在 30 秒内多次编辑，只需在最后一次编辑后索引一次
- 若用户明确表示"只是浏览代码不做修改"，跳过索引维护，直接查询即可
