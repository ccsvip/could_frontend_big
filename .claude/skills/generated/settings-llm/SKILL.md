---
name: settings-llm
description: "Skill for the Settings-llm area of could_frontend_big. 21 symbols across 2 files."
---

# Settings-llm

21 symbols | 2 files | Cohesion: 94%

## When to Use

- Working with code in `web/`
- Understanding how createPlatformLLMModel, updatePlatformLLMModel, updatePlatformLLMTestSettings work
- Modifying settings-llm-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/settings-llm/index.tsx` | LlmSettingsAdminPage, loadAuthorization, submitModel, updateGrant, saveAuthorization (+8) |
| `web/src/api/modules/llm-settings.ts` | createPlatformLLMModel, updatePlatformLLMModel, updatePlatformLLMTestSettings, fetchTenantLLMAuthorization, updateTenantLLMAuthorization (+3) |

## Entry Points

Start here when exploring this area:

- **`createPlatformLLMModel`** (Function) — `web/src/api/modules/llm-settings.ts:398`
- **`updatePlatformLLMModel`** (Function) — `web/src/api/modules/llm-settings.ts:403`
- **`updatePlatformLLMTestSettings`** (Function) — `web/src/api/modules/llm-settings.ts:417`
- **`fetchTenantLLMAuthorization`** (Function) — `web/src/api/modules/llm-settings.ts:422`
- **`updateTenantLLMAuthorization`** (Function) — `web/src/api/modules/llm-settings.ts:427`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `createPlatformLLMModel` | Function | `web/src/api/modules/llm-settings.ts` | 398 |
| `updatePlatformLLMModel` | Function | `web/src/api/modules/llm-settings.ts` | 403 |
| `updatePlatformLLMTestSettings` | Function | `web/src/api/modules/llm-settings.ts` | 417 |
| `fetchTenantLLMAuthorization` | Function | `web/src/api/modules/llm-settings.ts` | 422 |
| `updateTenantLLMAuthorization` | Function | `web/src/api/modules/llm-settings.ts` | 427 |
| `LlmSettingsAdminPage` | Function | `web/src/views/settings-llm/index.tsx` | 76 |
| `loadAuthorization` | Function | `web/src/views/settings-llm/index.tsx` | 129 |
| `submitModel` | Function | `web/src/views/settings-llm/index.tsx` | 208 |
| `updateGrant` | Function | `web/src/views/settings-llm/index.tsx` | 236 |
| `saveAuthorization` | Function | `web/src/views/settings-llm/index.tsx` | 250 |
| `saveTestSettings` | Function | `web/src/views/settings-llm/index.tsx` | 267 |
| `deletePlatformLLMProvider` | Function | `web/src/api/modules/llm-settings.ts` | 389 |
| `deletePlatformLLMModel` | Function | `web/src/api/modules/llm-settings.ts` | 408 |
| `testPlatformLLMModel` | Function | `web/src/api/modules/llm-settings.ts` | 438 |
| `openEditProvider` | Function | `web/src/views/settings-llm/index.tsx` | 159 |
| `openCreateModel` | Function | `web/src/views/settings-llm/index.tsx` | 189 |
| `openEditModel` | Function | `web/src/views/settings-llm/index.tsx` | 196 |
| `handleTestModel` | Function | `web/src/views/settings-llm/index.tsx` | 222 |
| `render` | Function | `web/src/views/settings-llm/index.tsx` | 277 |
| `activeGrantIds` | Function | `web/src/views/settings-llm/index.tsx` | 103 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `LlmSettingsAdminPage → FetchTenantLLMAuthorization` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Modules | 3 calls |

## How to Explore

1. `context({name: "createPlatformLLMModel"})` — see callers and callees
2. `query({search_query: "settings-llm"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
