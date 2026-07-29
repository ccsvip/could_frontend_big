---
name: asr-management
description: "Skill for the Asr-management area of could_frontend_big. 33 symbols across 2 files."
---

# Asr-management

33 symbols | 2 files | Cohesion: 81%

## When to Use

- Working with code in `web/`
- Understanding how updateAsrRuntimeConfig, fetchAsrFillerWords, updateAsrFillerWords work
- Modifying asr-management-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/asr-management/index.tsx` | downsampleBuffer, encodePCM16, AsrManagementPage, loadFillerWords, loadRuntimeSettings (+19) |
| `web/src/api/modules/asr.ts` | updateAsrRuntimeConfig, fetchAsrFillerWords, updateAsrFillerWords, fetchAsrRuntimeSettings, updateAsrRuntimeSettings (+4) |

## Entry Points

Start here when exploring this area:

- **`updateAsrRuntimeConfig`** (Function) — `web/src/api/modules/asr.ts:85`
- **`fetchAsrFillerWords`** (Function) — `web/src/api/modules/asr.ts:97`
- **`updateAsrFillerWords`** (Function) — `web/src/api/modules/asr.ts:102`
- **`fetchAsrRuntimeSettings`** (Function) — `web/src/api/modules/asr.ts:107`
- **`updateAsrRuntimeSettings`** (Function) — `web/src/api/modules/asr.ts:112`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `updateAsrRuntimeConfig` | Function | `web/src/api/modules/asr.ts` | 85 |
| `fetchAsrFillerWords` | Function | `web/src/api/modules/asr.ts` | 97 |
| `updateAsrFillerWords` | Function | `web/src/api/modules/asr.ts` | 102 |
| `fetchAsrRuntimeSettings` | Function | `web/src/api/modules/asr.ts` | 107 |
| `updateAsrRuntimeSettings` | Function | `web/src/api/modules/asr.ts` | 112 |
| `AsrManagementPage` | Function | `web/src/views/asr-management/index.tsx` | 211 |
| `loadFillerWords` | Function | `web/src/views/asr-management/index.tsx` | 278 |
| `loadRuntimeSettings` | Function | `web/src/views/asr-management/index.tsx` | 288 |
| `stopAudio` | Function | `web/src/views/asr-management/index.tsx` | 317 |
| `closeSocket` | Function | `web/src/views/asr-management/index.tsx` | 331 |
| `resetTest` | Function | `web/src/views/asr-management/index.tsx` | 336 |
| `handleVadSave` | Function | `web/src/views/asr-management/index.tsx` | 405 |
| `handleFillerWordsSave` | Function | `web/src/views/asr-management/index.tsx` | 422 |
| `handleRuntimeSettingsSave` | Function | `web/src/views/asr-management/index.tsx` | 434 |
| `handleRuntimeSettingsRestore` | Function | `web/src/views/asr-management/index.tsx` | 449 |
| `setupAudioStreaming` | Function | `web/src/views/asr-management/index.tsx` | 463 |
| `handleSocketMessage` | Function | `web/src/views/asr-management/index.tsx` | 514 |
| `startTest` | Function | `web/src/views/asr-management/index.tsx` | 555 |
| `fetchAsrReplacementRules` | Function | `web/src/api/modules/asr.ts` | 119 |
| `deleteAsrReplacementRule` | Function | `web/src/api/modules/asr.ts` | 136 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `AsrManagementPage → ReadStoredJson` | cross_community | 4 |
| `AsrManagementPage → ParseMenu` | cross_community | 4 |
| `AsrManagementPage → ReadStoredRole` | cross_community | 3 |
| `AsrManagementPage → FetchAsrStatus` | cross_community | 3 |
| `AsrManagementPage → FetchAsrReplacementRules` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Views | 6 calls |
| Store | 1 calls |
| Router | 1 calls |
| Modules | 1 calls |

## How to Explore

1. `context({name: "updateAsrRuntimeConfig"})` — see callers and callees
2. `query({search_query: "asr-management"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
