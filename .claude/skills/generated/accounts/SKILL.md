---
name: accounts
description: "Skill for the Accounts area of could_frontend_big. 85 symbols across 9 files."
---

# Accounts

85 symbols | 9 files | Cohesion: 98%

## When to Use

- Working with code in `backend/`
- Understanding how generate_unique_tenant_code, provision_company, notify_account_application_created work
- Modifying accounts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/accounts/permissions.py` | HasPermissionCode, CanViewAccountApplications, CanReviewAccountApplications, CanManageTenants, CanManageEmployees (+66) |
| `backend/apps/accounts/serializers.py` | _get_access_context, get_role, get_permissions, get_menus |
| `backend/apps/accounts/models.py` | ensure_login_user, save, provision_company |
| `backend/apps/tenants/services.py` | generate_unique_tenant_code, provision_company |
| `backend/apps/tenants/serializers.py` | create |
| `backend/apps/accounts/services/notifications.py` | notify_account_application_created |
| `backend/apps/accounts/tasks.py` | notify_account_application |
| `backend/apps/accounts/tests.py` | test_notify_account_application_task_sends_feishu_message |
| `backend/apps/accounts/views.py` | create |

## Entry Points

Start here when exploring this area:

- **`generate_unique_tenant_code`** (Function) — `backend/apps/tenants/services.py:76`
- **`provision_company`** (Function) — `backend/apps/tenants/services.py:89`
- **`notify_account_application_created`** (Function) — `backend/apps/accounts/services/notifications.py:9`
- **`notify_account_application`** (Function) — `backend/apps/accounts/tasks.py:7`
- **`HasPermissionCode`** (Class) — `backend/apps/accounts/permissions.py:40`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `HasPermissionCode` | Class | `backend/apps/accounts/permissions.py` | 40 |
| `CanViewAccountApplications` | Class | `backend/apps/accounts/permissions.py` | 52 |
| `CanReviewAccountApplications` | Class | `backend/apps/accounts/permissions.py` | 56 |
| `CanManageTenants` | Class | `backend/apps/accounts/permissions.py` | 60 |
| `CanManageEmployees` | Class | `backend/apps/accounts/permissions.py` | 65 |
| `CanViewAuditLogs` | Class | `backend/apps/accounts/permissions.py` | 70 |
| `CanClearAuditLogs` | Class | `backend/apps/accounts/permissions.py` | 84 |
| `CanViewDevices` | Class | `backend/apps/accounts/permissions.py` | 91 |
| `CanCreateDevices` | Class | `backend/apps/accounts/permissions.py` | 95 |
| `CanUpdateDevices` | Class | `backend/apps/accounts/permissions.py` | 99 |
| `CanDeleteDevices` | Class | `backend/apps/accounts/permissions.py` | 103 |
| `CanViewImageResources` | Class | `backend/apps/accounts/permissions.py` | 107 |
| `CanCreateImageResources` | Class | `backend/apps/accounts/permissions.py` | 111 |
| `CanUpdateImageResources` | Class | `backend/apps/accounts/permissions.py` | 115 |
| `CanDeleteImageResources` | Class | `backend/apps/accounts/permissions.py` | 119 |
| `CanViewVideoResources` | Class | `backend/apps/accounts/permissions.py` | 123 |
| `CanCreateVideoResources` | Class | `backend/apps/accounts/permissions.py` | 127 |
| `CanUpdateVideoResources` | Class | `backend/apps/accounts/permissions.py` | 131 |
| `CanDeleteVideoResources` | Class | `backend/apps/accounts/permissions.py` | 135 |
| `CanViewScrollingTexts` | Class | `backend/apps/accounts/permissions.py` | 139 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 1 calls |
| Tests | 1 calls |
| Knowledge_base | 1 calls |

## How to Explore

1. `context({name: "generate_unique_tenant_code"})` — see callers and callees
2. `query({search_query: "accounts"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
