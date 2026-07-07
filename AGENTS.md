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

## 第三方机器人上下文集成

- 接入或排查第三方 LLM / chatbot 多轮上下文前，先阅读 `wiki/第三方机器人上下文集成指南.md`。
- 发给第三方的上游会话 ID 必须来自第三方 API 响应，并按该厂商配置的字段/路径保存和复用；不要把安卓、HTTP 语音、WebSocket 的本地 `sessionId` 当成第三方 `chat_id` / `sessionId` 发送。
- 方案 A（先创建会话再发消息）必须配置响应 `extract` 和创建会话步骤的 `skipWhenVariableExists`，避免每轮重新打开第三方会话。
- 方案 B（单个 chat 接口自动创建/续接）必须用请求体模板回传第三方返回的 `sessionId`，首轮需要 JSON `null` 时使用 `nullWhenMissingVariables`，不要长期写死 `sessionId: null`。
- 新增第三方集成时至少补一个两轮回归测试：首轮模拟第三方返回上游会话 ID，第二轮断言请求第三方时复用同一个 ID。

## 修改前后的最低检查

修改前：

- 用 `rg` / `rg --files` 找入口和影响面。
- 读真实源码确认调用关系、数据流和边界条件。
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

## 前端设计 token 与响应式规范

设计系统已存在：antd theme（`web/src/main.tsx`，`colorPrimary=#0f766e`、`borderRadius=10/12/14`）+ Tailwind `brand` 色阶（`web/tailwind.config.ts`，`brand-700=#0f766e`）+ 全局类（`web/src/styles/index.css` 的 `.page-hero` / `.page-section-title`）。新增/修改前端时必须遵守：

### 颜色与 token

- 用 `brand-*` 色阶（如 `text-brand-700`、`bg-brand-50`），**不要**用 Tailwind 默认 `teal-*`，**不要**在组件里硬写 `#0f766e` 字面量。
- 主色 `#0f766e` 只允许出现在 `main.tsx`（antd token）和 `styles/index.css`（全局类）这两个"token 源"文件；业务页面一律走 `brand-*` 或 antd 组件默认。
- 优先让 antd 组件用自己的 token 渲染（`<Button type="primary">` 即是主色），不要再用 `!bg-teal-600` 之类硬覆盖。

### `!important` 覆盖纪律

- 严禁用 Tailwind `!` 前缀（`!p-0`、`!bg-teal-600`、`!rounded-xl`）去打 antd 默认值。这是历史遗留问题，是当前 UI 不一致的根因。
- 确需覆盖 antd 内部样式时，用 `styles/index.css` 里带作用域的全局类（如 `.app-sidebar-menu`、`.custom-scrollbar`），不要在页面 className 里堆 `!`。
- 卡片统一用 `rounded-xl` / `shadow-card`（已在 tailwind config 定义），不要每页各写一组 `!rounded-xl !shadow-[...]`。

### 响应式（必做，不是可选）

- 任何固定宽度（`w-64`、`w-80`、`min-w-[260px]`、`style={{width}}`）都必须配响应式变体，或改用 `w-full sm:w-52` 这类 mobile-first 写法。手机端横向滚动是缺陷，不是"小屏将就"。
- 尺寸单位用 `clamp(min, preferred, max)` 或 Tailwind 响应式前缀；**不要**用裸 `vw`/`vh`（在不同分辨率下不可控）。`styles/index.css` 的 `.page-hero` 已改为 `clamp()` 示范。
- 复用页面骨架：顶部 hero 用 `.page-hero`，区块标题用 `.page-section-title`，内容容器用 Tailwind `container`（已配置 center + 断点 padding），不要每页各写一套 `!px-[2%]`。

### 移动端

- `DashboardLayout` 已用 `useBreakpoint()` + `Drawer` 处理侧栏折叠；内容页不要假设侧栏宽度恒定，不要写死 `SIDEBAR_WIDTH` 相关的负 margin。
- 表格在 `<lg` 用 `scroll={{ x: ... }}` 允许横向滚动，不要让列宽撑爆容器。

### Pre-commit 设计 token 守卫（强制执行）

上述颜色/`!`/响应式规则不是仅靠自觉——`scripts/check-tailwind-tokens.js` + `.githooks/pre-commit` 会在提交时自动拦截**净增量**违规：

- 对每个暂存的 `*.tsx`，对比 HEAD 与暂存版的 `!`-前缀类计数和 `teal-*` 计数；计数上升才拦截（存量不触发，避免误伤重构）。
- 拦截条件：`!`-前缀类计数上升，或 `teal-*` 计数上升。
- 重构（如图标迁移、teal→brand 改名）只要不让计数上升就放行；纯新增 `!p-0`/`teal-600` 会被挡。
- 紧急跳过：`git commit --no-verify`，但请在 PR/commit message 说明原因。

**首次启用**（每个 clone 一次）：

```bash
git config core.hooksPath .githooks
# unix 还需：chmod +x .githooks/pre-commit
```

未配置 `core.hooksPath` 时守卫不生效，新 clone 必须执行一次。CI 若要强制，可在流水线里直接跑 `node scripts/check-tailwind-tokens.js`（对全量 `*.tsx` 做 HEAD vs 工作区对比）。

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature-slug>/` (local markdown, not GitHub Issues). See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles map 1:1 to default strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as the `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## 代码查询工具使用规则

按"先快后深、按需升级"的原则路由：日常导航先用 `rg` 和真实源码；只有需要跨模块语义判断、架构分析、复杂度/耦合度评估时，才升级到 CodeGraph agentic 工具。

### 第一优先级：源码搜索与阅读

**触发条件**（默认使用）：

- 查询目标明确，能通过文件名、符号名、路由、组件名、接口路径或错误文本定位
- 需要确认调用点、字段映射、权限判断、测试覆盖或真实实现细节
- 修改前评估影响面，修改后核对 diff 是否局限

**常用方式**：

- `rg --files`：按路径快速定位文件
- `rg "<pattern>"`：按符号、接口路径、文案、错误码、类型名搜索
- `Get-Content` / 分段读取真实源码：确认上下文，不只依赖搜索结果摘要
- `git diff -- <path>`：核对本次改动范围

### 第二优先级：CodeGraph agentic 工具

**触发条件**（满足任一才用，不要默认走这层）：

- 已用 `rg` 和源码阅读定位入口，但需要跨多个维度综合判断
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

1. 用 `rg --files` / `rg` 定位候选文件、符号和调用点。
2. 读取真实源码，确认数据流、权限、异步任务、WebSocket、Docker Compose 服务边界。
3. 若结果已足够回答或修改，直接执行，不再调用 agentic 工具。
4. 若仍需要跨模块综合判断，再升级到对应的 CodeGraph agentic 工具，并把前序源码结论写进 focus。

### 索引维护

- 只在需要 CodeGraph agentic 工具时维护 CodeGraph 索引。
- 若 agentic 查询返回空结果或明显过期，先确认相关文件是否被排除；必要时执行 `codegraph index . --index-tier balanced` 后重试。
- 修改函数签名、类结构、导入关系、新建/删除文件后，如果后续还要使用 CodeGraph agentic 工具，先重新索引。
- 仅修改函数内部实现且不再使用 agentic 工具时，不需要索引。

### 成本控制

- 用户明确要求节省 token 时，全程使用 `rg` 和源码阅读，跳过 agentic 工具。
- 能通过精确搜索和小范围源码阅读解决的问题，不升级到 agentic 工具。
