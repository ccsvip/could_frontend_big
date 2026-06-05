# Audit Log Management Design

Date: 2026-06-05

## Goal

Add an operation log viewer for company administrators while keeping tenant isolation strict.

Company administrators can view and permanently clear operation logs for their own company only. Platform super administrators keep the existing global log management capability and can permanently clear all platform logs.

The visible log fields are:

- Actor
- Action
- Operation detail
- Time

Read-only actions such as list/search/detail `GET` requests are not logged.

## Current Context

The project already has `apps.audit`:

- `OperationLogMiddleware` records successful write requests under `/api/v1/`.
- It only records `POST`, `PUT`, `PATCH`, and `DELETE`.
- It skips audit endpoints and authentication endpoints.
- `OperationLogViewSet` is currently read-only and superuser-only.
- The frontend already has `web/src/views/log-management/index.tsx`, but it derives operation detail from request paths in the browser.

The project also has a three-tier access model:

- Platform super administrators use `tenant.management.view`.
- Company administrators have `Membership.is_tenant_admin=True` and receive `tenant.employees.manage`.
- Employees receive only role and tenant-granted menu/permission intersections.

## Recommended Approach

Extend the existing audit system instead of introducing per-view manual logging.

The audit middleware remains the single point that captures successful write operations. The audit app adds a small description resolver that turns method/path/response metadata into stable operation detail text such as `新增公司 Acme`, `删除图片资源 Banner`, or `修改 LLM 模型 qwen-plus`.

This keeps the change focused and avoids scattering audit writes through every business ViewSet. If a resource name cannot be resolved, the resolver falls back to a generic detail such as `删除资源`.

## Data Model

Add one field to `OperationLog`:

- `description`: short text, blank allowed, stores the human-readable operation detail.

Existing fields remain:

- `actor`
- `actor_username`
- `tenant`
- `action`
- `method`
- `path`
- `status_code`
- `created_at`

The serializer exposes `description` as `description`.

## Backend Behavior

### Logging

`OperationLogMiddleware` continues to log only successful write requests:

- `POST` -> `create`
- `PUT` / `PATCH` -> `update`
- `DELETE` -> `delete`

It does not log:

- `GET` requests
- failed writes with status code `>= 400`
- `/api/v1/audit/`
- `/api/v1/auth/login/`
- `/api/v1/auth/refresh/`

The middleware resolves tenant as it does today:

- Company users use their membership tenant.
- Super administrators can be associated with `?tenant=<id>` when operating in a tenant-scoped route.
- Otherwise platform-level super administrator actions have no tenant.

### Operation Detail

Add an audit helper, for example `apps.audit.descriptions`, that receives request, response, action, method, and path. It returns a short description.

Initial rules cover the existing management surfaces:

- Tenants
- Account application approve/reject
- Device authorization actions
- Devices and device groups
- Image/video resources
- Scrolling text
- Voice tones
- Model assets
- Knowledge base documents
- AI model providers
- Command groups, control commands, task commands, and points
- MinIO settings where applicable

The resolver prefers object names from the response payload for creates/updates. For deletes, it may inspect the target object before the response completes when safe, or fall back to route-level text. It must never store request or response bodies wholesale.

### Listing Permissions

Replace the superuser-only audit permission with an audit-specific access rule:

- Platform super administrators can list all logs and may filter by `?tenant=<id>`.
- Company administrators can list only logs where `tenant` is their own company.
- Employees are not part of the requested surface. If `audit.logs.view` is ever assigned to an employee, backend tenant filtering still prevents cross-company reads.
- Users without a tenant and without superuser status are forbidden.

Add `audit.logs.view` as the frontend route and API permission code. Company administrators receive it by default, like `tenant.employees.manage`. Super administrators receive it through the existing "all active permission points" behavior.

### Clearing Logs

Add a custom endpoint:

`DELETE /api/v1/audit/logs/clear/`

Behavior:

- Super administrator: permanently delete all `OperationLog` rows.
- Company administrator: permanently delete only rows where `tenant` is their own company.
- Other users: forbidden.

The endpoint returns the number of deleted rows.

The clear endpoint remains under `/api/v1/audit/`, so the middleware skip list prevents the clear operation from creating a fresh log after deletion.

## Frontend Behavior

Reuse `web/src/views/log-management/index.tsx`.

Columns:

- 操作人
- 动作
- 操作具体做了什么
- 时间

Hide request method, request path, status code, and company columns from the main table. Super administrators may still use a company filter above the table. Company administrators do not see that filter.

Add a dangerous "清空日志" button in the page actions. Clicking it opens a destructive confirmation modal:

- It states that logs will be permanently deleted.
- It states the deletion cannot be recovered.
- For company administrators, it says the scope is the current company.
- For super administrators, it says the scope is the whole platform.

After successful clearing, show a success message and reload page 1.

## Routing And Menu

Keep route path `/logs`.

Change the route guard from `tenant.management.view` to `audit.logs.view`.

Seed or migrate a `/logs` menu item with an appropriate audience:

- Platform users already see platform menus through the super-admin sidebar builder.
- Company administrators should see `/logs` as an administrator-only menu entry.

The cleanest fit with the current menu model is to add `/logs` as `audience='tenant_admin'` and add `audit.logs.view` as an inherent company administrator permission. Employees do not see the menu by default.

## Tests

Backend tests:

- Successful writes create logs with `description`.
- `GET` requests do not create logs.
- Failed writes do not create logs.
- Super administrators can list all logs.
- Super administrators can filter by tenant.
- Company administrators can list only their company logs.
- Company administrators cannot read logs from another tenant by passing `?tenant=`.
- Company administrators can clear only their company logs.
- Super administrators can clear all logs.
- Staff non-superusers without tenant membership remain forbidden.

Frontend checks:

- Log route uses `audit.logs.view`.
- API module exposes `clearOperationLogs`.
- Log table renders the requested columns.
- Destructive clear modal text includes the irreversible warning.

Verification commands must use Docker Compose, for example:

```bash
docker compose exec backend python manage.py test apps.audit apps.tenants.tests.test_three_tier_access
docker compose exec web npm run lint
```

## Out Of Scope

- Logging read/search actions.
- Field-level before/after diffs.
- Storing request body or response body.
- Soft-deleting audit logs.
- Exporting audit logs.
