[根目录](../../../CLAUDE.md) > [backend](../../CLAUDE.md) > **apps/tenants**

# tenants 模块 AGENTS

## 模块职责

`apps/tenants` 是多租户隔离的**地基**。负责：

- 公司（`Tenant`）与成员归属（`Membership`）数据模型。
- 行级隔离的三道防线工具：`TenantManager`、`TenantScopedQuerysetMixin`、租户解析 services。
- 平台超管 API（公司 CRUD + 给公司分配菜单/权限点）。
- 公司管理员 API（员工 CRUD、租户级角色 CRUD、首登改密标志）。
- 审批通过自动开通公司（`provision_company`，被 `accounts.AccountApplication.save` 调用）。

## 三道防线（任一层都能挡跨租户读取）

1. **Manager**：tenant-scoped 模型 `objects = TenantManager()`，业务路径走 `.for_tenant(t)`；`for_tenant(None)` 返回空集（fail-closed）。
2. **ViewSet 基类** `TenantScopedQuerysetMixin`：`get_queryset()` 自动 `.for_tenant(request_tenant)`，`perform_create()` 强制注入 `tenant`（前端伪造无效）。已有自定义 `get_queryset` 的视图改为 `return self.apply_tenant_scope(qs)`；自定义 `perform_create` 改为 `serializer.save(**self.tenant_create_kwargs())`。
3. **缓存键**：`config/business_cache.py` 的响应缓存键、`DeviceViewSet.stats` 的统计键都并入 `tenant_id`。

> 护栏：`tests/test_isolation_contract.py` 会在「带 tenant 外键但没挂 TenantManager」时 CI 报红。新增 tenant-scoped 模型时务必挂 manager，或在该文件的 `KNOWN_NON_SCOPED_EXEMPTIONS` 登记豁免并写理由。

## 租户解析（关键：为什么不用 middleware）

DRF 的 JWT 鉴权在 **view 层**，Django middleware 阶段 `request.user` 还是匿名，所以**没有** TenantMiddleware。租户一律由 `services.get_request_tenant(request)` 从 `request.user.membership` 解析：

- superuser → `None`（平台运维，业务查询对其放行 `.all()`，跨租户维护走 Django admin）。
- 普通用户无 membership → `None` → `for_tenant(None)` 空集（防御）。
- JWT 里的 `tenant_id` claim 仅作辅助，**权威永远是 DB 的 Membership**（避免重新归属后旧 token 串租户）。

公开运行时端点（数字人设备，无登录态）走 `?tenant=<code>`：见 `services.scope_queryset_member_or_public` / `resolve_member_or_public_tenant`，用于 `resources` 的 Point / ScrollingText content / 指令查询。

## 三级菜单（在 accounts，不在本模块）

菜单分级派发的中枢是 `apps/accounts/services/permissions.py` 的 `build_user_access_context`，配合 `Menu.audience` 字段（`all` / `platform` / `tenant_admin`）：

- 超管：`audience in (all, platform)` 全部菜单（含租户管理），不含 `tenant_admin`。
- 公司管理员（`Membership.is_tenant_admin`）：`Tenant.menus`（all 类）+ 所有 `tenant_admin` 类菜单（员工管理）；权限 = `Tenant.permission_points` + `tenant.employees.manage`。
- 员工：`Role.menus ∩ Tenant.menus`；权限 = `Role.permission_points ∩ Tenant.permission_points`。

## 对外接口

平台超管（`CanManageTenants`，仅 superuser access-context 含 `tenant.management.view`）：
- `GET/POST/PATCH/PUT /api/v1/tenants/`
- `GET/PUT /api/v1/tenants/<id>/menus/`（读/写该公司被分配的 menuIds + permissionPointIds）
- `GET /api/v1/menus/catalog/`（可分配菜单目录 + 权限点）

公司管理员（`CanManageEmployees`，tenant_admin access-context 固有 `tenant.employees.manage`）：
- `GET/POST/PATCH /api/v1/employees/` + `POST /api/v1/employees/<id>/reset-password/`
- `GET/POST/PATCH/DELETE /api/v1/roles/`（菜单/权限点服务端钳制在本公司被授权范围内）
- `GET /api/v1/my-tenant/catalog/`（本公司视角的可分配目录）

## 数据模型

- `Tenant(name, code[unique slug], is_active, is_legacy, menus M2M→accounts.Menu, permission_points M2M→accounts.PermissionPoint)`
- `Membership(user OneToOne→auth.User, tenant FK, is_tenant_admin, must_change_password)`
- 关联改动（在各自 app）：12 张业务表加 nullable `tenant` FK + 按租户唯一约束；`accounts.Role` 加 `tenant`/`is_template`；`accounts.Menu` 加 `audience`；`accounts.AccountApplication` 加 `tenant`。

> 为什么用 `Membership` 一对一表而不是给 User 加字段：`AUTH_USER_MODEL` 是原生 `auth.User`，中途替换 user model 风险极高，故用独立表挂租户。

## 测试与质量

`docker compose exec backend python manage.py test apps.tenants`，覆盖：
- `test_cross_tenant_isolation`：跨租户列表/详情 404、perform_create 注入、superuser 旁路、公开端点 ?tenant 隔离。
- `test_approval_provisioning`：审批建公司、幂等、登录返回 tenant。
- `test_three_tier_access`：三级菜单/权限派发边界。
- `test_tenant_management_api`：超管菜单分配、不可分配 platform/tenant_admin 菜单、公司管理员无权访问平台端点。
- `test_employee_management_api`：员工 CRUD、用户名全局唯一、首登改密、角色菜单钳制、角色 code 租户内唯一。
- `test_llm_isolation`：LLM 供应商按公司隔离、聊天不跨租户兜底。
- `test_isolation_contract`：隔离契约护栏（防回归）。

测试辅助 `test_utils.TenantTestMixin.setup_tenant`：给「单租户时代」旧测试补 Membership + 全量授权（镜像默认公司）。旧测试在测试体内惰性建权限点时，需同步 `tenant.permission_points.add(...)`，否则 `role ∩ tenant` 交集为空导致 403。

## 常见问题 (FAQ)

- Q: 新加一个业务模型要隔离，怎么做？
  - A: ① 模型加 `tenant = ForeignKey('tenants.Tenant', ...)` + `objects = TenantManager()`；② ViewSet 继承 `TenantScopedQuerysetMixin`（放在 Cached mixin 之后、PermissionMapped 之前）；③ 加「跨租户 404」测试。漏挂 manager 时 `test_isolation_contract` 会报红。
- Q: superuser 在前端业务页看到的是哪家公司的数据？
  - A: 全部（mixin 检测到 `is_superuser` 直接 `.all()`）。跨租户维护建议走 `/admin/`。生产前端通常不让 superuser 当业务账号用。
- Q: 公司管理员能把超管没分配给他公司的菜单分给员工吗？
  - A: 不能。`/roles/` 的 serializer 服务端校验菜单必须在 `request.tenant.menus` 内，越界返回 400。
- Q: 员工首次登录为什么被拦在改密页？怎么解除？
  - A: `Membership.must_change_password=True`（建号/重置密码时置位）。前端 `AuthGuard` 拦截；员工走 `/auth/change-password/` 成功后后端清标志。
- Q: 数字人设备调公开接口（点位/指令/滚动文本）怎么带公司？
  - A: 加 `?tenant=<公司 code>` 查询参数。无参数 + 无登录态 → 空集（不泄漏任何公司数据）。

## 相关文件清单

- `models.py` / `managers.py` / `mixins.py` / `services.py` / `admin.py`
- `serializers.py` / `views.py`（平台超管）、`employee_serializers.py` / `employee_views.py`（公司管理员）、`urls.py`
- `migrations/0001_initial.py`、`0002_default_company.py`、`0003_backfill_business_tenants.py`
- `apps/accounts/services/permissions.py`（三级 access-context 中枢）
- `apps/accounts/migrations/0009_menu_audience.py`、`0010_seed_tenant_menus.py`、`0011_*`（Role.tenant）
- `test_utils.py` + `tests/*`

## 变更记录 (Changelog)

- 2026-05-31：初始化。多租户改造 PR-1~PR-6 落地：行级隔离三道防线、审批建公司、三级菜单分配、员工管理+租户级角色+首登改密、每公司 LLM 供应商。21 项真实栈端到端冒烟全通过。
