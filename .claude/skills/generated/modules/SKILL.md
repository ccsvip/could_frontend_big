---
name: modules
description: "Skill for the Modules area of could_frontend_big. 146 symbols across 39 files."
---

# Modules

146 symbols | 39 files | Cohesion: 83%

## When to Use

- Working with code in `web/`
- Understanding how fetchAgentApplications, fetchDevices, fetchDeviceStats work
- Modifying modules-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/api/modules/devices.ts` | normalizeList, buildDeviceParams, fetchDevices, fetchDeviceStats, fetchDeviceGroups (+13) |
| `web/src/api/modules/knowledge-base.ts` | readBlobErrorMessage, extractFileName, saveBlob, authorizedDownloadRequest, downloadKnowledgeDocument (+6) |
| `web/src/views/device-management/index.tsx` | loadData, handleSearch, handleDevicePageChange, handleWakeWordSave, refreshVoiceToneOptions (+5) |
| `web/src/api/modules/llm-settings.ts` | fetchCompanyLLMOptions, fetchCompanyThirdPartyChatbotOptions, buildProviderFormData, createPlatformLLMProvider, updatePlatformLLMProvider (+4) |
| `web/src/api/modules/resources.ts` | buildListParams, fetchImageResources, fetchVideoResources, buildFormData, createImageResource (+3) |
| `web/src/views/knowledge-base/index.tsx` | openBindMediaModal, handleBulkDownload, loadMediaAssets, handleBindMediaAssets, handleSaveMediaAsset (+1) |
| `web/src/api/modules/tts.ts` | fetchCompanyTtsOptions, ttsSettingsPath, fetchTtsSettings, updateTtsSettings, ttsSettingsTestPath (+1) |
| `web/src/api/modules/models.ts` | buildFormData, createModelAsset, updateModelAsset, buildListParams, fetchModelAssets (+1) |
| `web/src/views/application-management/index.tsx` | loadConversationServiceStatus, loadLogConversations, handleDeleteLogConversation, fetchAllKnowledgeBases, loadOptions |
| `web/src/api/modules/voice-tones.ts` | buildFormData, createVoiceTone, updateVoiceTone, buildListParams, fetchVoiceTones |

## Entry Points

Start here when exploring this area:

- **`fetchAgentApplications`** (Function) — `web/src/api/modules/applications.ts:104`
- **`fetchDevices`** (Function) — `web/src/api/modules/devices.ts:298`
- **`fetchDeviceStats`** (Function) — `web/src/api/modules/devices.ts:303`
- **`fetchDeviceGroups`** (Function) — `web/src/api/modules/devices.ts:439`
- **`fetchDeviceApplications`** (Function) — `web/src/api/modules/devices.ts:460`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchAgentApplications` | Function | `web/src/api/modules/applications.ts` | 104 |
| `fetchDevices` | Function | `web/src/api/modules/devices.ts` | 298 |
| `fetchDeviceStats` | Function | `web/src/api/modules/devices.ts` | 303 |
| `fetchDeviceGroups` | Function | `web/src/api/modules/devices.ts` | 439 |
| `fetchDeviceApplications` | Function | `web/src/api/modules/devices.ts` | 460 |
| `fetchWakeWords` | Function | `web/src/api/modules/devices.ts` | 488 |
| `createWakeWord` | Function | `web/src/api/modules/devices.ts` | 495 |
| `updateWakeWord` | Function | `web/src/api/modules/devices.ts` | 500 |
| `loadData` | Function | `web/src/views/device-management/index.tsx` | 391 |
| `handleSearch` | Function | `web/src/views/device-management/index.tsx` | 538 |
| `handleDevicePageChange` | Function | `web/src/views/device-management/index.tsx` | 548 |
| `handleWakeWordSave` | Function | `web/src/views/device-management/index.tsx` | 641 |
| `fetchControlCommands` | Function | `web/src/api/modules/commands.ts` | 190 |
| `fetchPoints` | Function | `web/src/api/modules/point-management.ts` | 50 |
| `fetchImageResources` | Function | `web/src/api/modules/resources.ts` | 130 |
| `fetchVideoResources` | Function | `web/src/api/modules/resources.ts` | 135 |
| `loadLookups` | Function | `web/src/views/command-management/tasks.tsx` | 129 |
| `buildCurrentGroupExport` | Function | `web/src/views/command-management/workspace.tsx` | 632 |
| `openBindMediaModal` | Function | `web/src/views/knowledge-base/index.tsx` | 644 |
| `handleUnauthorizedResponse` | Function | `web/src/api/client.ts` | 136 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `TaskCommandManagementPage → BuildActiveParam` | cross_community | 5 |
| `ModelManagementPage → BuildListParams` | cross_community | 4 |
| `TtsManagementPage → NormalizeTtsSessionConfig` | cross_community | 4 |
| `TtsSettingsPage → TtsSettingsPath` | cross_community | 4 |
| `ImportCurrentGroupCommands → BuildActiveParam` | cross_community | 4 |
| `KnowledgeBasePage → FetchKnowledgeBases` | cross_community | 3 |
| `CommandWorkspacePage → CollectPages` | cross_community | 3 |
| `AsrManagementPage → FetchAsrStatus` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Device-authorization-center | 3 calls |
| Command-management | 3 calls |
| Tts-settings | 2 calls |
| Tts-management | 1 calls |
| Tenant-management | 1 calls |
| Knowledge-base | 1 calls |
| Application-management | 1 calls |

## How to Explore

1. `context({name: "fetchAgentApplications"})` — see callers and callees
2. `query({search_query: "modules"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
