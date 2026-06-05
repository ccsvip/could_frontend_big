# Audit Log Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let company administrators view and permanently clear their own company's operation logs, while super administrators can view and clear all platform logs.

**Architecture:** Extend the existing `apps.audit` middleware and API instead of adding manual per-view logging. Store backend-generated operation details in `OperationLog.description`, gate reads and clearing with an audit-specific permission, and simplify the existing React log page to the four requested columns plus a destructive clear confirmation.

**Tech Stack:** Django 5.2, Django REST Framework, React 18, Vite, TypeScript, Ant Design, Docker Compose.

---

## File Structure

- Modify `backend/apps/audit/models.py`: add `description`.
- Create `backend/apps/audit/descriptions.py`: route-aware operation detail resolver.
- Modify `backend/apps/audit/middleware.py`: populate `description`.
- Modify `backend/apps/audit/serializers.py`: expose `description`.
- Modify `backend/apps/audit/views.py`: tenant-scoped list permissions and clear endpoint.
- Modify `backend/apps/accounts/permissions.py`: add audit permission class.
- Modify `backend/apps/accounts/services/permissions.py`: add `audit.logs.view` as an inherent company-admin permission.
- Create `backend/apps/accounts/migrations/0012_seed_audit_logs_menu.py`: seed `/logs` tenant-admin menu and `audit.logs.view`.
- Create `backend/apps/audit/migrations/0002_operationlog_description.py`: add database field.
- Modify `backend/apps/audit/tests/test_operation_log_api.py`: cover description, list scope, and clear behavior.
- Modify `backend/apps/tenants/tests/test_isolation_contract.py`: update audit exemption text if needed.
- Modify `web/src/api/modules/audit.ts`: add `description` and `clearOperationLogs`.
- Modify `web/src/router/index.tsx`: guard `/logs` with `audit.logs.view`.
- Modify `web/src/views/log-management/index.tsx`: columns, scope-aware filter, clear modal.
- Create or modify `web/scripts/test-audit-log-management-static.mjs`: static frontend assertions.
- Modify `web/package.json`: add script entry if the project keeps named static checks there.

## Task 1: Backend Description Field And Resolver

**Files:**
- Modify: `backend/apps/audit/models.py`
- Create: `backend/apps/audit/descriptions.py`
- Modify: `backend/apps/audit/middleware.py`
- Modify: `backend/apps/audit/serializers.py`
- Create: `backend/apps/audit/migrations/0002_operationlog_description.py`
- Test: `backend/apps/audit/tests/test_operation_log_api.py`

- [ ] **Step 1: Add failing tests for persisted operation details**

Add these assertions to `OperationLogMiddlewareTests.test_successful_write_creates_one_log`:

```python
self.assertTrue(log.description)
self.assertIn('公司', log.description)
```

Add a new test:

```python
def test_serializer_exposes_description(self):
    self.client.post('/api/v1/tenants/', {'name': '审计详情公司'}, format='json')

    resp = self.client.get('/api/v1/audit/logs/')

    self.assertEqual(resp.status_code, status.HTTP_200_OK)
    first = resp.data['results'][0]
    self.assertIn('description', first)
    self.assertIn('公司', first['description'])
```

- [ ] **Step 2: Run failing backend audit tests**

Run:

```bash
docker compose exec backend python manage.py test apps.audit.tests.test_operation_log_api
```

Expected: fails because `OperationLog` and serializer do not yet expose `description`.

- [ ] **Step 3: Add `description` to `OperationLog`**

In `backend/apps/audit/models.py`, add this field after `path`:

```python
description = models.CharField('操作说明', max_length=255, blank=True, default='')
```

Create `backend/apps/audit/migrations/0002_operationlog_description.py`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='operationlog',
            name='description',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='操作说明'),
        ),
    ]
```

- [ ] **Step 4: Add a focused operation description resolver**

Create `backend/apps/audit/descriptions.py`:

```python
from __future__ import annotations

import re
from typing import Any


ACTION_LABELS = {
    'create': '新增',
    'update': '修改',
    'delete': '删除',
}


ROUTE_LABEL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'^/api/v1/tenants/(?:\d+/)?$'), '公司'),
    (re.compile(r'^/api/v1/tenants/\d+/menus/$'), '公司菜单'),
    (re.compile(r'^/api/v1/account-applications/\d+/approve/$'), '账号申请'),
    (re.compile(r'^/api/v1/account-applications/\d+/reject/$'), '账号申请'),
    (re.compile(r'^/api/v1/devices/[^/]+/$'), '设备'),
    (re.compile(r'^/api/v1/device-groups/(?:\d+/)?$'), '设备分组'),
    (re.compile(r'^/api/v1/device-applications/(?:\d+/)?$'), '设备应用'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/bind/$'), '设备授权'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/ignore/$'), '设备授权请求'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/authorize/$'), '设备授权'),
    (re.compile(r'^/api/v1/device-authorization-requests/[^/]+/revoke/$'), '设备授权'),
    (re.compile(r'^/api/v1/resources/images/(?:\d+/)?$'), '图片资源'),
    (re.compile(r'^/api/v1/resources/videos/(?:\d+/)?$'), '视频资源'),
    (re.compile(r'^/api/v1/resources/scrolling-texts/(?:\d+/)?$'), '滚动文字'),
    (re.compile(r'^/api/v1/resources/voice-tones/(?:\d+/)?$'), '音色'),
    (re.compile(r'^/api/v1/resources/models/(?:\d+/)?$'), '模型资源'),
    (re.compile(r'^/api/v1/knowledge-base/(?:\d+/)?$'), '知识库文档'),
    (re.compile(r'^/api/v1/ai-models/llm-providers/(?:\d+/)?$'), 'LLM 模型'),
    (re.compile(r'^/api/v1/commands/groups/(?:\d+/)?$'), '指令分组'),
    (re.compile(r'^/api/v1/commands/control/(?:\d+/)?$'), '控制指令'),
    (re.compile(r'^/api/v1/commands/tasks/(?:\d+/)?$'), '任务指令'),
    (re.compile(r'^/api/v1/commands/points/(?:\d+/)?$'), '点位'),
    (re.compile(r'^/api/v1/settings/minio/'), 'MinIO 设置'),
]


NAME_KEYS = (
    'name',
    'title',
    'displayName',
    'display_name',
    'nickname',
    'modelName',
    'model_name',
    'providerName',
    'provider_name',
    'filename',
    'fileName',
)


def _response_data(response) -> Any:
    return getattr(response, 'data', None)


def _extract_name(data: Any) -> str:
    if isinstance(data, dict):
        for key in NAME_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = data.get('data') or data.get('result')
        if nested is not data:
            return _extract_name(nested)
    return ''


def _route_label(path: str) -> str:
    for pattern, label in ROUTE_LABEL_RULES:
        if pattern.match(path):
            return label
    return '数据'


def describe_operation(*, request, response, action: str, method: str, path: str) -> str:
    action_label = ACTION_LABELS.get(action, action)
    route_label = _route_label(path)
    name = _extract_name(_response_data(response))

    if path.endswith('/approve/'):
        return f'通过{route_label}{f" {name}" if name else ""}'[:255]
    if path.endswith('/reject/'):
        return f'拒绝{route_label}{f" {name}" if name else ""}'[:255]
    if path.endswith('/bind/'):
        return f'绑定{route_label}{f" {name}" if name else ""}'[:255]
    if path.endswith('/ignore/'):
        return f'忽略{route_label}{f" {name}" if name else ""}'[:255]
    if path.endswith('/authorize/'):
        return f'授权{route_label}{f" {name}" if name else ""}'[:255]
    if path.endswith('/revoke/'):
        return f'撤销{route_label}{f" {name}" if name else ""}'[:255]

    return f'{action_label}{route_label}{f" {name}" if name else ""}'[:255]
```

- [ ] **Step 5: Store and serialize descriptions**

In `backend/apps/audit/middleware.py`, import lazily inside `_maybe_log`:

```python
from .descriptions import describe_operation
```

Before `OperationLog.objects.create(...)`, add:

```python
description = describe_operation(
    request=request,
    response=response,
    action=action,
    method=method,
    path=path,
)
```

Pass it to `OperationLog.objects.create`:

```python
description=description,
```

In `backend/apps/audit/serializers.py`, add `'description'` to `fields` after `'path'`.

- [ ] **Step 6: Run backend audit tests**

Run:

```bash
docker compose exec backend python manage.py test apps.audit.tests.test_operation_log_api
```

Expected: tests from Task 1 pass or reveal only permission-related failures handled in Task 2.

## Task 2: Backend Audit Permissions, Tenant Scope, And Clear Endpoint

**Files:**
- Modify: `backend/apps/accounts/permissions.py`
- Modify: `backend/apps/accounts/services/permissions.py`
- Create: `backend/apps/accounts/migrations/0012_seed_audit_logs_menu.py`
- Modify: `backend/apps/audit/views.py`
- Modify: `backend/apps/audit/tests/test_operation_log_api.py`
- Modify: `backend/apps/tenants/tests/test_isolation_contract.py`

- [ ] **Step 1: Add failing tests for company-admin list scope and clearing**

Replace `test_audit_logs_endpoint_forbidden_for_tenant_admin` with:

```python
def test_tenant_admin_lists_only_own_tenant_logs(self):
    tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
    tenant_b = Tenant.objects.create(name='公司B', code='comp-b')
    admin_a = User.objects.create_user('admin-a', password='pw12345678')
    Membership.objects.create(user=admin_a, tenant=tenant_a, is_tenant_admin=True)
    OperationLog.objects.create(actor_username='a1', tenant=tenant_a, action='create', method='POST', path='/api/v1/resources/images/', status_code=201, description='新增图片资源 A')
    OperationLog.objects.create(actor_username='b1', tenant=tenant_b, action='delete', method='DELETE', path='/api/v1/resources/images/1/', status_code=204, description='删除图片资源 B')

    self.client.force_authenticate(admin_a)
    resp = self.client.get(f'/api/v1/audit/logs/?tenant={tenant_b.id}')

    self.assertEqual(resp.status_code, status.HTTP_200_OK)
    self.assertEqual(resp.data['count'], 1)
    self.assertEqual(resp.data['results'][0]['tenant'], tenant_a.id)
```

Add:

```python
def test_tenant_admin_clears_only_own_tenant_logs(self):
    tenant_a = Tenant.objects.create(name='公司A', code='clear-a')
    tenant_b = Tenant.objects.create(name='公司B', code='clear-b')
    admin_a = User.objects.create_user('clear-admin-a', password='pw12345678')
    Membership.objects.create(user=admin_a, tenant=tenant_a, is_tenant_admin=True)
    OperationLog.objects.create(actor_username='a1', tenant=tenant_a, action='create', method='POST', path='/api/v1/resources/images/', status_code=201, description='新增图片资源 A')
    OperationLog.objects.create(actor_username='b1', tenant=tenant_b, action='delete', method='DELETE', path='/api/v1/resources/images/1/', status_code=204, description='删除图片资源 B')

    self.client.force_authenticate(admin_a)
    resp = self.client.delete('/api/v1/audit/logs/clear/')

    self.assertEqual(resp.status_code, status.HTTP_200_OK)
    self.assertEqual(resp.data['deleted'], 1)
    self.assertFalse(OperationLog.objects.filter(tenant=tenant_a).exists())
    self.assertTrue(OperationLog.objects.filter(tenant=tenant_b).exists())
```

Add:

```python
def test_superuser_clears_all_logs(self):
    tenant = Tenant.objects.create(name='公司C', code='clear-c')
    OperationLog.objects.create(actor_username='root', tenant=None, action='create', method='POST', path='/api/v1/tenants/', status_code=201, description='新增公司')
    OperationLog.objects.create(actor_username='admin', tenant=tenant, action='create', method='POST', path='/api/v1/resources/images/', status_code=201, description='新增图片资源')

    self.client.force_authenticate(self.superuser)
    resp = self.client.delete('/api/v1/audit/logs/clear/')

    self.assertEqual(resp.status_code, status.HTTP_200_OK)
    self.assertEqual(resp.data['deleted'], 2)
    self.assertEqual(OperationLog.objects.count(), 0)
```

- [ ] **Step 2: Run failing permission tests**

Run:

```bash
docker compose exec backend python manage.py test apps.audit.tests.test_operation_log_api
```

Expected: company administrator tests fail with 403 or missing clear route.

- [ ] **Step 3: Add audit permission classes**

In `backend/apps/accounts/permissions.py`, add:

```python
class CanViewAuditLogs(HasPermissionCode):
    required_permission = 'audit.logs.view'


class CanClearAuditLogs(HasPermissionCode):
    required_permission = 'audit.logs.view'
```

- [ ] **Step 4: Make `audit.logs.view` inherent for company administrators**

In `backend/apps/accounts/services/permissions.py`, add:

```python
AUDIT_LOGS_VIEW_CODE = 'audit.logs.view'
```

In the `membership.is_tenant_admin` branch of `get_active_permission_codes_for_user`, add:

```python
codes.add(AUDIT_LOGS_VIEW_CODE)
```

- [ ] **Step 5: Seed audit menu and permission**

Create `backend/apps/accounts/migrations/0012_seed_audit_logs_menu.py`:

```python
from django.db import migrations


def seed_audit_logs_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')

    Menu.objects.update_or_create(
        key='/logs',
        defaults={
            'name': '日志管理',
            'path': '/logs',
            'icon': 'FileSearchOutlined',
            'audience': 'tenant_admin',
            'sort_order': 99,
            'is_active': True,
        },
    )
    PermissionPoint.objects.update_or_create(
        code='audit.logs.view',
        defaults={
            'name': '日志查看',
            'module': 'audit',
            'description': '允许查看和清空授权范围内的操作日志',
            'is_active': True,
        },
    )


def unseed_audit_logs_menu(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Menu.objects.filter(key='/logs').delete()
    PermissionPoint.objects.filter(code='audit.logs.view').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_role_is_template_role_tenant_alter_role_code_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_audit_logs_menu, unseed_audit_logs_menu),
    ]
```

- [ ] **Step 6: Implement scoped list and clear endpoint**

In `backend/apps/audit/views.py`, replace `IsSuperUser` with `CanClearAuditLogs` and `CanViewAuditLogs`, and add imports:

```python
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanClearAuditLogs, CanViewAuditLogs
from apps.tenants.services import get_user_tenant
```

Set:

```python
permission_classes = [CanViewAuditLogs]
```

Add:

```python
def get_queryset(self):
    queryset = super().get_queryset()
    user = self.request.user
    if user.is_superuser:
        raw_tenant = (self.request.query_params.get('tenant') or '').strip()
        if raw_tenant.isdigit():
            queryset = queryset.filter(tenant_id=int(raw_tenant))
        return queryset

    tenant = get_user_tenant(user)
    if tenant is None:
        return queryset.none()
    return queryset.filter(tenant=tenant)


@action(detail=False, methods=['delete'], url_path='clear', permission_classes=[CanClearAuditLogs])
def clear(self, request):
    user = request.user
    queryset = OperationLog.objects.all()
    if not user.is_superuser:
        tenant = get_user_tenant(user)
        if tenant is None:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(tenant=tenant)

    deleted, _ = queryset.delete()
    return Response({'deleted': deleted})
```

- [ ] **Step 7: Update audit isolation exemption text**

In `backend/apps/tenants/tests/test_isolation_contract.py`, change the `('audit', 'OperationLog')` exemption text to:

```python
'跨租户审计日志，经审计接口按 superuser/tenant_admin 访问范围过滤，不参与业务租户隔离'
```

- [ ] **Step 8: Run backend tests**

Run:

```bash
docker compose exec backend python manage.py test apps.audit apps.tenants.tests.test_three_tier_access apps.tenants.tests.test_isolation_contract
```

Expected: all selected backend tests pass.

## Task 3: Frontend API, Route Guard, And Static Test

**Files:**
- Modify: `web/src/api/modules/audit.ts`
- Modify: `web/src/router/index.tsx`
- Create: `web/scripts/test-audit-log-management-static.mjs`
- Modify: `web/package.json` if scripts are centrally listed

- [ ] **Step 1: Add frontend static test**

Create `web/scripts/test-audit-log-management-static.mjs`:

```javascript
import assert from 'node:assert/strict';
import fs from 'node:fs';

const auditApi = fs.readFileSync('src/api/modules/audit.ts', 'utf8');
const router = fs.readFileSync('src/router/index.tsx', 'utf8');
const page = fs.readFileSync('src/views/log-management/index.tsx', 'utf8');

assert(auditApi.includes('description: string;'), 'OperationLogRecord should expose description');
assert(auditApi.includes('clearOperationLogs'), 'audit API should expose clearOperationLogs');
assert(router.includes('permission="audit.logs.view"'), 'logs route should use audit.logs.view guard');
assert(page.includes('操作具体做了什么'), 'log table should show operation detail column');
assert(page.includes('无法恢复'), 'clear modal should warn that deletion cannot be recovered');
assert(!page.includes(\"title: '请求路径'\"), 'log table should not expose request path as a main column');

console.log('audit log management static checks passed');
```

- [ ] **Step 2: Run failing frontend static test**

Run:

```bash
docker compose exec web node scripts/test-audit-log-management-static.mjs
```

Expected: fails because API, route guard, and page are not updated yet.

- [ ] **Step 3: Update audit API module**

In `web/src/api/modules/audit.ts`, add to `OperationLogRecord`:

```ts
description: string;
```

Add:

```ts
export const clearOperationLogs = async () => {
  const response = await httpClient.delete<{ deleted: number }>('/audit/logs/clear/');
  return response.data;
};
```

- [ ] **Step 4: Update route guard**

In `web/src/router/index.tsx`, change the `/logs` route guard:

```tsx
<PermissionGuard permission="audit.logs.view">
  <LogManagementPage />
</PermissionGuard>
```

- [ ] **Step 5: Run static test again**

Run:

```bash
docker compose exec web node scripts/test-audit-log-management-static.mjs
```

Expected: still fails until Task 4 updates the page.

## Task 4: Frontend Log Page UI

**Files:**
- Modify: `web/src/views/log-management/index.tsx`
- Test: `web/scripts/test-audit-log-management-static.mjs`

- [ ] **Step 1: Import clear API, auth store, and modal controls**

Update imports in `web/src/views/log-management/index.tsx`:

```tsx
import { DeleteOutlined, FileSearchOutlined } from '@ant-design/icons';
import { Button, Card, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import {
  clearOperationLogs,
  fetchOperationLogs,
  type OperationLogAction,
  type OperationLogRecord,
} from '../../api/modules/audit';
import { useAuthStore } from '../../store/auth';
```

- [ ] **Step 2: Remove frontend path-description rules**

Delete `methodColorMap`, `statusColor`, `fallbackActionText`, `pathDescriptionRules`, and `describeOperationPath`. The table must use `record.description` from the backend.

- [ ] **Step 3: Add scope awareness and clear handler**

Inside `LogManagementPage`, add:

```tsx
const hasPermission = useAuthStore((state) => state.hasPermission);
const tenant = useAuthStore((state) => state.tenant);
const isPlatformAdmin = hasPermission('tenant.management.view') || !tenant;
const [clearing, setClearing] = useState(false);
```

Add:

```tsx
const handleClearLogs = () => {
  Modal.confirm({
    title: '清空日志',
    content: isPlatformAdmin
      ? '将真实删除全平台全部操作日志，无法恢复。'
      : '将真实删除当前公司全部操作日志，无法恢复。',
    okText: '确认清空',
    okButtonProps: { danger: true, loading: clearing },
    cancelText: '取消',
    async onOk() {
      setClearing(true);
      try {
        const data = await clearOperationLogs();
        message.success(`已清空 ${data.deleted} 条日志`);
        setTenantFilter(undefined);
        setPage(1);
        await loadLogs(1, undefined);
      } finally {
        setClearing(false);
      }
    },
  });
};
```

- [ ] **Step 4: Load tenants only for platform administrators**

Change the tenant loading effect:

```tsx
useEffect(() => {
  if (!isPlatformAdmin || hasLoadedTenantsRef.current) {
    return;
  }
  hasLoadedTenantsRef.current = true;
  void (async () => {
    try {
      const data = await fetchTenants({ page_size: 100 });
      setTenants(data.results);
    } catch {
      // 错误已在拦截器中处理
    }
  })();
}, [isPlatformAdmin]);
```

- [ ] **Step 5: Replace columns with requested fields**

Use these table columns:

```tsx
const columns: ColumnsType<OperationLogRecord> = useMemo(
  () => [
    {
      title: '操作人',
      dataIndex: 'actorUsername',
      key: 'actorUsername',
      width: '20%',
      render: (value: string) => value || <span className="text-slate-400">匿名</span>,
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: '14%',
      render: (action: OperationLogAction) => {
        const meta = actionMap[action];
        return <Tag color={meta?.color}>{meta?.text ?? action}</Tag>;
      },
    },
    {
      title: '操作具体做了什么',
      dataIndex: 'description',
      key: 'description',
      width: '46%',
      ellipsis: true,
      render: (value: string) => value || <span className="text-slate-400">-</span>,
    },
    {
      title: '时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: '20%',
    },
  ],
  [],
);
```

- [ ] **Step 6: Render scope-aware actions**

In the page hero right side, render:

```tsx
<Space className="!w-full justify-end md:!w-auto">
  {isPlatformAdmin ? (
    <Select
      allowClear
      placeholder="按公司筛选"
      className="!w-60"
      value={tenantFilter}
      onChange={(value) => {
        setTenantFilter(value);
        setPage(1);
      }}
      options={tenants.map((tenantItem) => ({ value: tenantItem.id, label: tenantItem.name }))}
    />
  ) : null}
  <Button danger icon={<DeleteOutlined />} loading={clearing} onClick={handleClearLogs}>
    清空日志
  </Button>
</Space>
```

- [ ] **Step 7: Run frontend static test**

Run:

```bash
docker compose exec web node scripts/test-audit-log-management-static.mjs
```

Expected: `audit log management static checks passed`.

## Task 5: Final Docker Verification

**Files:**
- No new files unless verification reveals a defect.

- [ ] **Step 1: Run backend audit and tenant tests**

Run:

```bash
docker compose exec backend python manage.py test apps.audit apps.tenants.tests.test_three_tier_access apps.tenants.tests.test_isolation_contract
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend lint**

Run:

```bash
docker compose exec web npm run lint
```

Expected: lint passes. If the project has pre-existing lint failures unrelated to this work, capture the exact output and run the narrower static check from Task 4.

- [ ] **Step 3: Run frontend audit static check**

Run:

```bash
docker compose exec web node scripts/test-audit-log-management-static.mjs
```

Expected: `audit log management static checks passed`.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git diff --stat
git diff -- backend/apps/audit backend/apps/accounts backend/apps/tenants/tests/test_isolation_contract.py web/src/api/modules/audit.ts web/src/router/index.tsx web/src/views/log-management/index.tsx web/scripts/test-audit-log-management-static.mjs
```

Expected: diff contains only audit log management changes described in this plan.

## Self-Review

Spec coverage:

- Company-admin own-company viewing is covered by Task 2.
- Company-admin own-company clearing is covered by Task 2 and Task 4.
- Super-admin global viewing and clearing are covered by Task 2.
- Operation detail is covered by Task 1 and surfaced by Task 4.
- Frontend four-column display is covered by Task 4.
- Irreversible warning is covered by Task 4.
- Docker-only verification is covered by Task 5.

Vague-marker scan:

- This plan intentionally avoids unfinished markers and provides concrete code or commands for every implementation step.

Type consistency:

- Backend serializer field is `description`.
- Frontend type field is `description`.
- Clear API function is `clearOperationLogs`.
- Route permission is `audit.logs.view`.
