[backend](../../AGENTS.md) > apps > **accounts**

# apps/accounts AGENTS.md

## OVERVIEW

认证、账号申请、JWT 登录、菜单/权限/RBAC 的中心 app。前端菜单、权限、角色的唯一事实来源是 `/auth/me/`。

## STRUCTURE

```
accounts/
├── models.py                 # AccountApplication / AccountUser proxy / Menu / PermissionPoint / Role / UserRole
├── serializers.py            # Login / ChangePassword / UserSerializer / account application payloads
├── views.py                  # login / me / change-password / account application review
├── permissions.py            # 全项目权限类注册表（HasPermissionCode 子类）
├── admin.py                  # SimpleUI 账号管理分组 + proxy User admin
├── tasks.py                  # 账号申请飞书通知 Celery task
├── services/
│   ├── permissions.py        # role / menus / permission codes 聚合
│   └── notifications.py      # 飞书通知
└── migrations/               # 菜单/权限种子 + 账号申请字段演进
```

## WHERE TO LOOK

| 任务 | 位置 | 注意 |
|------|------|------|
| 改登录返回体 | `views.py` + `serializers.py` | `LoginView` 和 `MeView` 都要保持同一 user context 形状 |
| 加权限码 | `permissions.py` + access-data migration | 新类继承 `HasPermissionCode`，`required_permission='module.action'` |
| 改菜单/权限聚合 | `services/permissions.py` | 前端直接信任 `/auth/me/` 的 `menus/permissions/role` |
| 改账号申请审核 | `models.py:AccountApplication.save()` | 审核状态变化有副作用 |
| 改 admin 用户入口 | `admin.py:AccountUserAdmin` | proxy model，不是新表 |

## CONVENTIONS

- **AccountUser 是 proxy**：只为把 `auth.User` 挂进 accounts 分组；不要在这里加真实字段。
- **申请密码已是 hash**：`ensure_login_user()` 复制 `application.password` 到 `user.password`；不要再 `set_password()`。
- **审核副作用在 model 层**：`AccountApplication.save()` 审核通过会建/启用用户；拒绝或撤回会停用已存在用户。
- **权限类集中注册**：所有 app 的 DRF permission class 都放 `permissions.py`；新增业务权限也走这里，保持前端 permission 字符串可追踪。
- **菜单/权限只后端生成**：`UserSerializer` 通过 `build_user_access_context()` 注入 `role/permissions/menus`；前端不硬编码菜单。
- **通知兜底**：异步 `.delay()` 可能遇到 Celery/Redis 不可用；调用方应像 `AccountApplicationCreateView` 一样捕获 `OperationalError` 并同步通知。

## ANTI-PATTERNS

- ❌ 对已 hash 的申请密码调用 `set_password()`：会双重哈希，用户无法登录。
- ❌ `unregister` 默认 `auth.User` admin：`UserRoleAdmin.autocomplete_fields=('user',)` 依赖默认注册。
- ❌ 在前端新增菜单/权限常量绕过 `/auth/me/`：会和 RBAC 数据源分叉。
- ❌ 把 `is_staff/is_superuser` 当普通角色写进 `UserRole`：superuser 分支由 `services/permissions.is_admin_user()` 处理。
- ❌ 在 permission class 里做租户过滤：租户隔离应在 queryset / manager 层，权限类只判断操作权限码。

## NOTES

- `Role.code` 当前全局唯一；若做多租户角色派生，需要改成平台模板 + tenant role 的组合约束。
- `AccountApplication.enterprise_name` 已存在，适合作为审核通过后创建 Tenant 的公司名来源。
- `AccountApplication.login_username` 优先 `username`，兼容历史 phone 登录数据。
