---
name: application-management
description: "Skill for the Application-management area of could_frontend_big. 120 symbols across 10 files."
---

# Application-management

120 symbols | 10 files | Cohesion: 74%

## When to Use

- Working with code in `web/`
- Understanding how fetchAgentApplication, publishAgentApplication, updateConversationConfig work
- Modifying application-management-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/application-management/index.tsx` | normalizeTtsFilterExcludePatterns, applyApplicationState, getApplicationSaveMismatch, stringValue, isDirty (+68) |
| `web/src/views/application-management/use-agent-audio.ts` | playQueuedStreamSegments, enqueueStreamPlaybackText, appendStreamPlaybackText, finishStreamPlayback, normalizeTtsExcludePatterns (+8) |
| `web/src/api/modules/applications.ts` | fetchAgentApplication, publishAgentApplication, createAgentApplicationConversation, fetchAgentAnnotations, createAgentAnnotation (+7) |
| `web/src/views/application-management/monitor-dashboard.tsx` | fmt, fmtPct, TrendChart, AccentCard, SourceBadge (+2) |
| `web/src/api/modules/chat.ts` | updateConversationConfig, parseSseDataLine, sendMessageStream, processStream, clearApplicationWebConversationHistory (+1) |
| `web/src/views/application-management/playback-request-guard.ts` | createPlaybackRequestGuard, isCurrent, complete |
| `web/src/api/modules/devices.ts` | clearDeviceChatSessions, fetchDeviceChatSession |
| `web/src/views/tts-realtime-playback.ts` | sanitizeTtsText, stripMarkdownForTts |
| `web/src/components/status-tag.test.tsx` | testStatusTagInterface |
| `web/src/components/status-tag.tsx` | StatusTag |

## Entry Points

Start here when exploring this area:

- **`fetchAgentApplication`** (Function) — `web/src/api/modules/applications.ts:111`
- **`publishAgentApplication`** (Function) — `web/src/api/modules/applications.ts:126`
- **`updateConversationConfig`** (Function) — `web/src/api/modules/chat.ts:72`
- **`applyApplicationState`** (Function) — `web/src/views/application-management/index.tsx:475`
- **`getApplicationSaveMismatch`** (Function) — `web/src/views/application-management/index.tsx:502`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchAgentApplication` | Function | `web/src/api/modules/applications.ts` | 111 |
| `publishAgentApplication` | Function | `web/src/api/modules/applications.ts` | 126 |
| `updateConversationConfig` | Function | `web/src/api/modules/chat.ts` | 72 |
| `applyApplicationState` | Function | `web/src/views/application-management/index.tsx` | 475 |
| `getApplicationSaveMismatch` | Function | `web/src/views/application-management/index.tsx` | 502 |
| `stringValue` | Function | `web/src/views/application-management/index.tsx` | 503 |
| `isDirty` | Function | `web/src/views/application-management/index.tsx` | 551 |
| `loadSelectedApplication` | Function | `web/src/views/application-management/index.tsx` | 675 |
| `handleSaveConfig` | Function | `web/src/views/application-management/index.tsx` | 1132 |
| `handlePublish` | Function | `web/src/views/application-management/index.tsx` | 1230 |
| `handleKeyDown` | Function | `web/src/views/application-management/index.tsx` | 1251 |
| `addTtsFilterExcludePattern` | Function | `web/src/views/application-management/index.tsx` | 1412 |
| `createAgentApplicationConversation` | Function | `web/src/api/modules/applications.ts` | 135 |
| `sendMessageStream` | Function | `web/src/api/modules/chat.ts` | 87 |
| `processStream` | Function | `web/src/api/modules/chat.ts` | 140 |
| `ensureConversation` | Function | `web/src/views/application-management/index.tsx` | 1295 |
| `startNewConversation` | Function | `web/src/views/application-management/index.tsx` | 1309 |
| `sendChatContent` | Function | `web/src/views/application-management/index.tsx` | 1330 |
| `handleSend` | Function | `web/src/views/application-management/index.tsx` | 1404 |
| `sendSuggestedQuestion` | Function | `web/src/views/application-management/index.tsx` | 1477 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ApplicationManagementPage → ReadStoredJson` | cross_community | 4 |
| `ApplicationManagementPage → ParseMenu` | cross_community | 4 |
| `ApplicationManagementPage → ReadStoredRole` | cross_community | 4 |
| `ApplicationManagementPage → EncodeRealtimeCommand` | cross_community | 4 |
| `ApplicationManagementPage → BuildAsrSessionCancelCommand` | cross_community | 4 |
| `ApplicationManagementPage → CreateRealtimeCommandId` | cross_community | 4 |
| `ApplicationManagementPage → BuildAsrSessionFinishCommand` | cross_community | 4 |
| `ApplicationManagementPage → UseTenantScopeStore` | cross_community | 3 |
| `ApplicationManagementPage → CreatePlaybackRequestGuard` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Modules | 5 calls |
| Components | 5 calls |
| Views | 3 calls |
| Store | 2 calls |
| Router | 1 calls |

## How to Explore

1. `context({name: "fetchAgentApplication"})` — see callers and callees
2. `query({search_query: "application-management"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
