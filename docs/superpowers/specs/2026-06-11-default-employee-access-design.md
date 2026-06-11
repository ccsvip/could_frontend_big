# 公司员工默认全权限设计

## 背景

当前公司管理员创建员工后，员工可能能看到侧边栏菜单，但进入页面后看不到内容。诊断结果显示：菜单来自公司授权的 `Tenant.menus`，而页面和接口访问依赖权限点 `permissions`。普通员工当前需要 `UserRole` 才能获得权限；若创建员工时没有绑定角色，就会出现有菜单但权限为空的状态。

## 目标

公司管理员创建员工时，员工默认拥有该公司已被平台授权范围内的全部业务菜单和全部业务权限。唯一例外是员工管理能力：普通员工不能看到员工管理菜单，也不能拥有员工管理相关操作权限。

## 非目标

- 不引入公司内自定义角色体系。
- 不让普通员工越过平台超管对公司的授权范围。
- 不开放员工管理菜单或 `tenant.employees.manage` 给普通员工。
- 不改变平台超管和公司管理员的权限语义。

## 权限规则

### 公司管理员

公司管理员继续保留当前行为：

- 菜单包含公司被分配的业务菜单，以及公司管理员专属菜单 `/employees`。
- 权限包含公司被分配的权限点，以及 `tenant.employees.manage`。

### 普通员工

普通员工不再依赖 `UserRole` 才能获得默认权限。员工访问上下文应直接从所属公司派生：

- 菜单 = `Tenant.menus` 中启用且可分配给公司的业务菜单。
- 权限 = `Tenant.permission_points` 中启用的权限点。
- 排除员工管理菜单 `/employees`。
- 排除员工管理权限 `tenant.employees.manage`。

如果平台超管调整某公司的菜单或权限点，普通员工的默认菜单和权限应自动跟随变化。

## 数据流

1. 公司管理员通过员工管理创建员工。
2. 后端创建 `auth.User` 和 `Membership`，`Membership.is_tenant_admin=False`。
3. 登录或刷新 `/auth/me/` 时，`UserSerializer` 调用 `build_user_access_context()`。
4. `build_user_access_context()` 对普通员工从 `membership.tenant` 读取公司授权，生成菜单和权限。
5. 前端继续使用 `/auth/me/` 返回的 `menus` 渲染侧边栏，用 `permissions` 执行路由和按钮守卫。

## 现有数据处理

规则改为从 `Membership.tenant` 动态派生后，已创建且没有 `UserRole` 的员工会自动恢复默认权限，不需要补建角色。已有 `UserRole` 不应再影响默认员工权限；如保留数据库记录，也只是历史残留，不参与默认员工 access-context 计算。

## 测试要求

- 公司管理员创建的新员工登录后，除 `/employees` 外能看到公司已授权业务菜单。
- 新员工拥有公司已授权业务权限点，访问 `/devices/` 等业务接口不再因权限为空返回 403。
- 新员工不拥有 `tenant.employees.manage`，访问 `/employees/` 和 `/roles/` 仍返回 403。
- 平台超管修改公司授权后，员工 `/auth/me/` 返回的菜单和权限自动变化。
- 已存在的无角色员工在新规则下获得同样的默认业务权限。

## 推荐实现

优先修改 `backend/apps/accounts/services/permissions.py` 的普通员工分支：取消对 `user.role_binding` 的强依赖，直接用 `membership.tenant` 派生菜单和权限。员工创建接口可以继续保存 `role_name` 作为展示字段，但不再要求或依赖 `roleId`。
