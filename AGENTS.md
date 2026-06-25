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

## 代码库探索规则：

1. 日常理解代码、定位实现、追踪调用链时，优先使用 CodeGraph。
2. 修改代码前，先用 CodeGraph 获取相关源码和影响范围。
3. 如果需要架构统计、图查询、ADR、跨模块关系分析，再使用 codebase-memory-mcp。
4. 如果两个工具结果不一致，以当前代码文件内容为准，并重新同步索引。
5. 不要在 CodeGraph 已经返回足够上下文时重复全仓库 grep。
