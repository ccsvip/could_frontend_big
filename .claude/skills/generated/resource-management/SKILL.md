---
name: resource-management
description: "Skill for the Resource-management area of could_frontend_big. 45 symbols across 2 files."
---

# Resource-management

45 symbols | 2 files | Cohesion: 93%

## When to Use

- Working with code in `web/`
- Understanding how bulkDeleteImageResources, fetchResourceUploadConfig, ResourceManagementPage work
- Modifying resource-management-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/resource-management/index.tsx` | formatFileMB, getResourceSourceUrl, hasResourceSource, ResourceManagementPage, hasPermission (+33) |
| `web/src/api/modules/resources.ts` | bulkDeleteImageResources, fetchResourceUploadConfig, batchCreateImageResources, presignResourceUpload, isDuplicateImageError (+2) |

## Entry Points

Start here when exploring this area:

- **`bulkDeleteImageResources`** (Function) — `web/src/api/modules/resources.ts:166`
- **`fetchResourceUploadConfig`** (Function) — `web/src/api/modules/resources.ts:228`
- **`ResourceManagementPage`** (Function) — `web/src/views/resource-management/index.tsx:515`
- **`hasPermission`** (Function) — `web/src/views/resource-management/index.tsx:517`
- **`loadData`** (Function) — `web/src/views/resource-management/index.tsx:567`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `bulkDeleteImageResources` | Function | `web/src/api/modules/resources.ts` | 166 |
| `fetchResourceUploadConfig` | Function | `web/src/api/modules/resources.ts` | 228 |
| `ResourceManagementPage` | Function | `web/src/views/resource-management/index.tsx` | 515 |
| `hasPermission` | Function | `web/src/views/resource-management/index.tsx` | 517 |
| `loadData` | Function | `web/src/views/resource-management/index.tsx` | 567 |
| `updatePageSize` | Function | `web/src/views/resource-management/index.tsx` | 594 |
| `openEditModal` | Function | `web/src/views/resource-management/index.tsx` | 637 |
| `handleDelete` | Function | `web/src/views/resource-management/index.tsx` | 676 |
| `toggleResourceSelection` | Function | `web/src/views/resource-management/index.tsx` | 696 |
| `toggleCurrentPageSelection` | Function | `web/src/views/resource-management/index.tsx` | 702 |
| `handleBulkDelete` | Function | `web/src/views/resource-management/index.tsx` | 706 |
| `batchCreateImageResources` | Function | `web/src/api/modules/resources.ts` | 145 |
| `presignResourceUpload` | Function | `web/src/api/modules/resources.ts` | 233 |
| `isDuplicateImageError` | Function | `web/src/api/modules/resources.ts` | 244 |
| `getDuplicateImageLocation` | Function | `web/src/api/modules/resources.ts` | 246 |
| `uploadFileToPresignedUrl` | Function | `web/src/api/modules/resources.ts` | 270 |
| `closeBatchModal` | Function | `web/src/views/resource-management/index.tsx` | 662 |
| `closeFormModal` | Function | `web/src/views/resource-management/index.tsx` | 667 |
| `uploadResourceToObjectStorage` | Function | `web/src/views/resource-management/index.tsx` | 748 |
| `handleSubmit` | Function | `web/src/views/resource-management/index.tsx` | 820 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ResourceManagementPage → ReadStoredJson` | cross_community | 4 |
| `ResourceManagementPage → ParseMenu` | cross_community | 4 |
| `ResourceManagementPage → ReadStoredRole` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Store | 1 calls |
| Modules | 1 calls |

## How to Explore

1. `context({name: "bulkDeleteImageResources"})` — see callers and callees
2. `query({search_query: "resource-management"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
