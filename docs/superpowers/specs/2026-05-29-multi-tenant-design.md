# solin 多租户改造设计规格

**日期**：2026-05-29  
**来源设计稿**：`scripts/multi-tenant-design.html`  
**状态**：待用户最终审阅  
**目标项目**：`could_frontend`（React 18 + Vite + Django 5.2 + DRF + Celery）

## 1. 目标

将当前单租户后台管理平台改造成多租户系统。一个租户代表一家公司。公司间所有业务数据必须行级隔离，包括设备、素材、知识库、控制指令、点位、AI 供应商配置、API Key、聊天会话等。

本设计采用以下已确认选择：

- 数据隔离：行级隔离，单 PostgreSQL database / 单 schema。
- 登录识别：用户名全局唯一，登录后由后端从用户绑定关系反查租户。
- AI 供应商配置：每家公司自配，完全隔离，不做平台共享。
- 用户归属：不替换 Django `auth.User`，通过 `UserProfile` 一对一扩展表绑定租户。

非目标：

- 不做 schema-per-tenant 或 DB-per-tenant。
- 不做子域名或 `/t/:tenant` 路径前缀。
- 不做跨公司共享资源、邀请协作或跨公司任职。
- 不让公司管理员进入 Django admin；Django admin 仍只给 superuser / 平台运维使用。

## 2. 总体架构

新增后端 app：`backend/apps/tenants/`。

核心模型：

- `Tenant`：公司主体。
  - `name`：公司名。
  - `code`：全局唯一 slug，用于媒体路径和内部标识。
  - `admin_user`：公司管理员用户。
  - `is_active`：公司是否启用。
  - `is_legacy`：是否默认历史公司。
  - `created_at` / `updated_at`。
- `UserProfile`：用户租户扩展。
  - `user`：OneToOne 到 `settings.AUTH_USER_MODEL`。
  - `tenant`：FK 到 `Tenant`。
  - `must_change_password`：管理员创建员工后首次登录强制改密。

superuser 不要求绑定 `UserProfile`，仅通过 Django admin 跨租户维护。普通业务用户必须存在且只能存在一个 `UserProfile`。

## 3. 登录与租户识别

登录页保持现状：用户名 + 密码。

后端登录流程：

1. `LoginView` 按用户名认证用户。
2. 若用户是 superuser：允许登录，但业务前端默认不提供跨租户数据视图。
3. 若用户不是 superuser：读取 `user.tenant_profile.tenant`。
4. 若租户不存在或 `is_active=False`：拒绝登录。
5. JWT access token 写入 `tenant_id` claim。
6. `/auth/login/` 与 `/auth/me/` 返回统一用户上下文：

```json
{
  "username": "jack",
  "role": { "code": "tenant_admin", "name": "公司管理员" },
  "permissions": ["..."],
  "menus": [{ "key": "devices", "label": "设备管理" }],
  "tenant": { "id": 1, "name": "默认公司", "code": "default" },
  "mustChangePassword": false
}
```

前端不允许传入 `tenant_id`。所有租户身份都来自 JWT / 当前用户上下文。

## 4. 后端隔离防线

后端采用三道防线。

### 4.1 TenantMiddleware

`TenantMiddleware` 在认证后运行：

- 读取 `request.user`。
- superuser：`request.tenant = None`。
- 普通用户：`request.tenant = request.user.tenant_profile.tenant`。
- 对业务 API，普通用户无租户时直接拒绝。

### 4.2 TenantScopedViewSetMixin

所有租户业务 ViewSet 继承该 mixin：

- `get_queryset()`：自动 `filter(tenant=request.tenant)`。
- `perform_create()`：自动 `serializer.save(tenant=request.tenant)`。
- superuser 在业务 API 不默认跨租户；跨租户维护走 Django admin。

### 4.3 Serializer / Service 校验

所有跨模型引用必须校验同租户：

- `TaskCommandStep.control_command`、`point`、`resource` 必须同租户。
- `ChatConversation.llm_provider` 必须同租户。
- 知识库下载和批量下载必须二次校验文档属于当前租户。

前端请求体中的 `tenant` 字段应被忽略或直接拒绝。

## 5. 需要加 tenant 的业务模型

以下模型必须增加 `tenant = ForeignKey(Tenant, on_delete=CASCADE)`：

- `devices.Device`
- `resources.Resource`
- `resources.VoiceTone`
- `resources.ModelAsset`
- `resources.ScrollingText`
- `resources.CommandGroup`
- `resources.ControlCommand`
- `resources.TaskCommand`
- `resources.point_models.Point`
- `knowledge_base.KnowledgeDocument`
- `ai_models.LLMProvider`
- `ai_models.ChatConversation`

`ChatMessage` 不单独加 `tenant`，通过 `ChatConversation` 继承隔离边界。

## 6. 唯一约束调整

以下字段从全局唯一改为租户内唯一：

| 模型 | 当前字段 | 新约束 |
|---|---|---|
| `Device` | `code` | `(tenant, code)` |
| `VoiceTone` | `voice_code` | `(tenant, voice_code)` |
| `ModelAsset` | `name` | `(tenant, name)` |
| `ControlCommand` | `command_code` | `(tenant, command_code)` |
| `TaskCommand` | `command_code` | `(tenant, command_code)` |
| `Point` | `command` | `(tenant, command)` |
| `Role` | `code` | 平台模板全局唯一；租户角色 `(tenant, code)` 唯一 |

`Role` 采用两层结构：

- `tenant = null` 且 `is_template=True`：平台模板角色。
- `tenant != null`：公司派生角色。

初始模板至少包含：

- `tenant_admin`：公司管理员。
- `tenant_employee`：公司员工。

## 7. 账号申请与员工管理

账号申请通过后，后端在事务中完成：

1. 根据 `AccountApplication.enterprise_name` 创建 `Tenant`。
2. 创建或启用申请人 `auth.User`。
3. 创建 `UserProfile(user=申请人, tenant=新公司, must_change_password=False)`。
4. 设置 `Tenant.admin_user = 申请人`。
5. 绑定 `tenant_admin` 角色。
6. 回写 `AccountApplication.tenant`。

新增员工管理 API：

- 列表：只列当前租户员工。
- 创建：公司管理员创建本公司员工，并设置初始密码。
- 停用：只停用本公司员工。
- 重置密码：只重置本公司员工密码，并设置 `must_change_password=True`。

员工不能跨公司任职。

## 8. AI 供应商配置隔离

AI 大模型供应商配置全部租户内私有；后续接入 ASR / TTS Provider 时必须沿用同一隔离规则：

- `LLMProvider.tenant` 必填。
- 当前代码尚未实现 `ASRProvider` / `TTSProvider` 模型；新增这些模型时必须同步设计为 `tenant` 必填。
- API Key 只属于对应公司。
- 公司 A 无法查询、复用或引用公司 B 的 Provider。
- 聊天会话选择 Provider 时必须校验同租户。

不提供平台共享 Provider，避免破坏“全部资源隔离”的产品承诺。

## 9. 媒体文件隔离

新增上传路径规则：

```text
media/{tenant_code}/resources/...
media/{tenant_code}/knowledge-base/...
media/{tenant_code}/models/...
media/{tenant_code}/voice-tones/...
media/{tenant_code}/ai-models/...
```

所有上传对象保存前必须已经设置 `tenant`。下载接口不能只依赖文件 URL，需要通过数据库对象二次校验 `object.tenant == request.tenant`。

知识库下载和批量下载是最高风险点：

- 单文件下载：对象查询必须按 tenant 过滤。
- 批量下载：`id__in` 查询必须叠加 `tenant=request.tenant`。
- 无效、重复、跨租户 ID 统一按不可见处理。

## 10. 缓存与 Celery

业务缓存 key 必须包含 tenant：

- `device_stats` 改为 `tenant:{id}:device_stats`。
- `resources`、`knowledge_base` 等 business cache namespace 需要 tenant 维度。

Celery 任务没有 `request` 上下文。所有租户相关异步任务必须显式传入 `tenant_id`，任务内部按 `tenant_id` 查询对象，禁止裸 `Model.objects.get(pk=...)` 处理业务数据。

## 11. Docker 启动链路影响

当前 backend 启动链路：

```text
migrate → seed_operations_periodic_tasks → collectstatic → 创建 admin → seed_devices → uvicorn
```

要求：

- 创建 admin superuser 时不绑定租户，保持 `tenant_profile` 可不存在。
- `seed_devices` 在多租户后必须写入默认公司；如果默认公司不存在则以非零退出并提示先执行迁移，避免创建无租户设备。
- 默认公司由数据迁移创建，必须发生在 `seed_devices` 前。

## 12. 历史数据迁移

采用默认公司收容历史数据：

1. 创建 `Tenant(name='默认公司', code='default', is_legacy=True)`。
2. 所有非 superuser 用户创建 `UserProfile(tenant=默认公司)`。
3. 所有现有业务数据回填 `tenant=默认公司`。
4. 保持 superuser 无租户归属。

本仓库当前未发现设计稿中提到的 `company_name` / `password_hash` 孤儿列；`AccountApplication.password` 是合法字段。

## 13. 前端改造

前端不做 URL 租户前缀，不传租户字段。

需要修改：

- `web/src/store/auth.ts`
  - 新增 `tenant` 类型和 localStorage 持久化。
  - `login()` / `setUserContext()` / `clearAuth()` 同步处理 tenant。
- `web/src/api/modules/auth.ts`
  - `LoginResponse` / `CurrentUser` 增加 `tenant` 和 `mustChangePassword`。
- `web/src/layouts/dashboard-layout.tsx`
  - 顶栏显示当前公司名。
- `web/src/views/login/index.tsx`
  - 登录后处理 `mustChangePassword`。
- 新增 `web/src/api/modules/employees.ts`。
- 新增 `web/src/views/employees/index.tsx`。
- `web/src/router/index.tsx`
  - 新增 `/employees` 路由，权限为 `tenant.employees.manage`。

现有业务页面继续调用原 API，由后端按 JWT 自动隔离。

## 14. 测试策略

后端必须补充租户测试工厂：

- `make_tenant()`。
- `make_user(tenant=...)`。
- `make_tenant_admin(tenant=...)`。

每类租户资源至少覆盖：

- 同租户列表/详情/创建/修改/删除成功。
- 跨租户详情/修改/删除返回 404 或 403。
- 前端传入伪造 tenant 被忽略或拒绝。
- 唯一字段允许不同租户重复，不允许同租户重复。
- 知识库下载和批量下载无法通过 ID 获取其他租户文件。
- AI Provider 和 ChatConversation 不能跨租户引用。

前端验证：

- 登录后 tenant 写入 store/localStorage。
- `/auth/me` 刷新后 tenant 同步更新。
- 顶栏显示公司名。
- 员工管理路由受 `tenant.employees.manage` 权限保护。

## 15. 分阶段实施建议

### PR-1：租户基础设施

- 新增 `apps/tenants`。
- 新增 `Tenant` / `UserProfile`。
- 默认公司数据迁移。
- JWT claim 增加 `tenant_id`。
- `/auth/login/` 和 `/auth/me` 返回 tenant。
- `TenantMiddleware`。

### PR-2：业务表 tenant 化

- 给所有业务模型加 `tenant`。
- 回填历史数据到默认公司。
- 调整唯一约束。
- 接入 `TenantScopedViewSetMixin`。
- 修正媒体路径和下载校验。

### PR-3：账号申请创建公司

- 审核通过自动创建 Tenant。
- 绑定申请人为公司管理员。
- 创建 tenant role。

### PR-4：员工管理

- 后端员工 CRUD / 停用 / 重置密码。
- 前端 `/employees` 页面。
- 首次登录强制改密。

### PR-5：角色模板与公司派生角色

- 平台模板角色。
- 公司角色派生。
- 权限与菜单在租户角色内配置。

## 16. 风险与防护

| 风险 | 防护 |
|---|---|
| ViewSet 忘记租户过滤 | 所有业务 ViewSet 必须继承 `TenantScopedViewSetMixin`；测试跨租户 404 |
| Celery 任务越权 | 任务参数显式带 `tenant_id` |
| 媒体 URL 可猜 | tenant 路径分区 + 下载接口二次校验 |
| 唯一约束仍全局 | PR-2 同步改为租户内唯一 |
| superuser 前端跨租户语义混乱 | 前端不提供跨租户；跨租户维护仅 Django admin |
| 中途替换 `AUTH_USER_MODEL` 风险 | 使用 `UserProfile`，不替换 auth.User |

## 17. 验收标准

- 公司 A 无法通过 API 读取、修改、删除公司 B 的任何业务资源。
- 公司 A 无法看到公司 B 的 AI Provider/API Key。
- 公司 A 无法通过知识库文件 ID 或批量下载拿到公司 B 文件。
- 公司 A 可以使用与公司 B 相同的设备编号、模型名、音色编码、控制指令编码，但同公司内仍唯一。
- 账号申请通过会创建新公司和公司管理员。
- 公司管理员只能管理员工，不能进入 Django admin。
- superuser 可在 Django admin 查看全部租户数据。
- 现有历史数据全部归入默认公司。
