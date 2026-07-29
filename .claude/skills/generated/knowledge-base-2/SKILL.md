---
name: knowledge-base-2
description: "Skill for the Knowledge-base area of could_frontend_big. 38 symbols across 2 files."
---

# Knowledge-base

38 symbols | 2 files | Cohesion: 72%

## When to Use

- Working with code in `web/`
- Understanding how fetchKnowledgeDocuments, fetchKnowledgeBaseDocuments, uploadKnowledgeDocument work
- Modifying knowledge-base-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/knowledge-base/index.tsx` | formatFileSize, loadBases, loadDocuments, startUpload, handleSingleDownload (+18) |
| `web/src/api/modules/knowledge-base.ts` | buildListParams, buildUploadFormData, fetchKnowledgeDocuments, fetchKnowledgeBaseDocuments, uploadKnowledgeDocument (+10) |

## Entry Points

Start here when exploring this area:

- **`fetchKnowledgeDocuments`** (Function) — `web/src/api/modules/knowledge-base.ts:308`
- **`fetchKnowledgeBaseDocuments`** (Function) — `web/src/api/modules/knowledge-base.ts:339`
- **`uploadKnowledgeDocument`** (Function) — `web/src/api/modules/knowledge-base.ts:346`
- **`uploadKnowledgeBaseDocument`** (Function) — `web/src/api/modules/knowledge-base.ts:368`
- **`indexKnowledgeBase`** (Function) — `web/src/api/modules/knowledge-base.ts:425`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchKnowledgeDocuments` | Function | `web/src/api/modules/knowledge-base.ts` | 308 |
| `fetchKnowledgeBaseDocuments` | Function | `web/src/api/modules/knowledge-base.ts` | 339 |
| `uploadKnowledgeDocument` | Function | `web/src/api/modules/knowledge-base.ts` | 346 |
| `uploadKnowledgeBaseDocument` | Function | `web/src/api/modules/knowledge-base.ts` | 368 |
| `indexKnowledgeBase` | Function | `web/src/api/modules/knowledge-base.ts` | 425 |
| `indexKnowledgeDocument` | Function | `web/src/api/modules/knowledge-base.ts` | 432 |
| `deleteKnowledgeDocument` | Function | `web/src/api/modules/knowledge-base.ts` | 469 |
| `loadBases` | Function | `web/src/views/knowledge-base/index.tsx` | 266 |
| `loadDocuments` | Function | `web/src/views/knowledge-base/index.tsx` | 281 |
| `startUpload` | Function | `web/src/views/knowledge-base/index.tsx` | 362 |
| `handleSingleDownload` | Function | `web/src/views/knowledge-base/index.tsx` | 475 |
| `handleBulkDelete` | Function | `web/src/views/knowledge-base/index.tsx` | 496 |
| `handleDeleteDocument` | Function | `web/src/views/knowledge-base/index.tsx` | 517 |
| `handleIndexDocument` | Function | `web/src/views/knowledge-base/index.tsx` | 545 |
| `handleIndexBase` | Function | `web/src/views/knowledge-base/index.tsx` | 557 |
| `render` | Function | `web/src/views/knowledge-base/index.tsx` | 757 |
| `createKnowledgeBase` | Function | `web/src/api/modules/knowledge-base.ts` | 325 |
| `updateKnowledgeBase` | Function | `web/src/api/modules/knowledge-base.ts` | 330 |
| `deleteKnowledgeBase` | Function | `web/src/api/modules/knowledge-base.ts` | 335 |
| `recallTestKnowledgeBase` | Function | `web/src/api/modules/knowledge-base.ts` | 391 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `KnowledgeBasePage → ReadStoredJson` | cross_community | 4 |
| `KnowledgeBasePage → ParseMenu` | cross_community | 4 |
| `KnowledgeBasePage → BuildListParams` | cross_community | 4 |
| `KnowledgeBasePage → ReadStoredRole` | cross_community | 3 |
| `KnowledgeBasePage → FetchKnowledgeBases` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Modules | 8 calls |
| Store | 1 calls |
| Application-management | 1 calls |

## How to Explore

1. `context({name: "fetchKnowledgeDocuments"})` — see callers and callees
2. `query({search_query: "knowledge-base"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
