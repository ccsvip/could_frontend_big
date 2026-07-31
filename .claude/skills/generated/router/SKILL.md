---
name: router
description: "Skill for the Router area of could_frontend_big. 51 symbols across 3 files."
---

# Router

51 symbols | 3 files | Cohesion: 81%

## When to Use

- Working with code in `web/`
- Understanding how fetchCurrentUser, AppRouter, setUserContext work
- Modifying router-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/router/index.tsx` | LoginPage, DeviceManagementPage, DeviceAuthorizationCenterPage, AccountApplicationsPage, ModelManagementPage (+44) |
| `web/src/api/modules/auth.ts` | fetchCurrentUser |
| `web/src/store/tenant-scope.ts` | useTenantScopeStore |

## Entry Points

Start here when exploring this area:

- **`fetchCurrentUser`** (Function) — `web/src/api/modules/auth.ts:77`
- **`AppRouter`** (Function) — `web/src/router/index.tsx:290`
- **`setUserContext`** (Function) — `web/src/router/index.tsx:292`
- **`setAuthSyncStatus`** (Function) — `web/src/router/index.tsx:293`
- **`syncPromise`** (Function) — `web/src/router/index.tsx:309`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchCurrentUser` | Function | `web/src/api/modules/auth.ts` | 77 |
| `AppRouter` | Function | `web/src/router/index.tsx` | 290 |
| `setUserContext` | Function | `web/src/router/index.tsx` | 292 |
| `setAuthSyncStatus` | Function | `web/src/router/index.tsx` | 293 |
| `syncPromise` | Function | `web/src/router/index.tsx` | 309 |
| `useTenantScopeStore` | Function | `web/src/store/tenant-scope.ts` | 13 |
| `LoginPage` | Function | `web/src/router/index.tsx` | 8 |
| `DeviceManagementPage` | Function | `web/src/router/index.tsx` | 9 |
| `DeviceAuthorizationCenterPage` | Function | `web/src/router/index.tsx` | 12 |
| `AccountApplicationsPage` | Function | `web/src/router/index.tsx` | 17 |
| `ModelManagementPage` | Function | `web/src/router/index.tsx` | 20 |
| `ResourceManagementPage` | Function | `web/src/router/index.tsx` | 23 |
| `ScrollingTextManagementPage` | Function | `web/src/router/index.tsx` | 26 |
| `KnowledgeBasePage` | Function | `web/src/router/index.tsx` | 31 |
| `AsrManagementPage` | Function | `web/src/router/index.tsx` | 34 |
| `LlmManagementPage` | Function | `web/src/router/index.tsx` | 37 |
| `TtsManagementPage` | Function | `web/src/router/index.tsx` | 40 |
| `ApplicationManagementPage` | Function | `web/src/router/index.tsx` | 43 |
| `TenantManagementPage` | Function | `web/src/router/index.tsx` | 46 |
| `EmployeeManagementPage` | Function | `web/src/router/index.tsx` | 49 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `AppRouter → ReadStoredJson` | cross_community | 4 |
| `AppRouter → ParseMenu` | cross_community | 4 |
| `AppRouter → ReadStoredRole` | cross_community | 3 |
| `ApplicationManagementPage → UseTenantScopeStore` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Store | 7 calls |
| Layouts | 1 calls |

## How to Explore

1. `context({name: "fetchCurrentUser"})` — see callers and callees
2. `query({search_query: "router"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
