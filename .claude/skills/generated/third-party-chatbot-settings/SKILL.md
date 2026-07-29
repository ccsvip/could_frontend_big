---
name: third-party-chatbot-settings
description: "Skill for the Third-party-chatbot-settings area of could_frontend_big. 22 symbols across 2 files."
---

# Third-party-chatbot-settings

22 symbols | 2 files | Cohesion: 94%

## When to Use

- Working with code in `web/`
- Understanding how fetchPlatformThirdPartyChatbotIntegrations, createPlatformThirdPartyChatbotIntegration, updatePlatformThirdPartyChatbotIntegration work
- Modifying third-party-chatbot-settings-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/third-party-chatbot-settings/index.tsx` | createDefaultStep, parseJsonBody, parseEquals, normalizePayload, ThirdPartyChatbotSettingsPage (+12) |
| `web/src/api/modules/llm-settings.ts` | fetchPlatformThirdPartyChatbotIntegrations, createPlatformThirdPartyChatbotIntegration, updatePlatformThirdPartyChatbotIntegration, testPlatformThirdPartyChatbotIntegrationDraft, deletePlatformThirdPartyChatbotIntegration |

## Entry Points

Start here when exploring this area:

- **`fetchPlatformThirdPartyChatbotIntegrations`** (Function) — `web/src/api/modules/llm-settings.ts:521`
- **`createPlatformThirdPartyChatbotIntegration`** (Function) — `web/src/api/modules/llm-settings.ts:528`
- **`updatePlatformThirdPartyChatbotIntegration`** (Function) — `web/src/api/modules/llm-settings.ts:536`
- **`testPlatformThirdPartyChatbotIntegrationDraft`** (Function) — `web/src/api/modules/llm-settings.ts:551`
- **`ThirdPartyChatbotSettingsPage`** (Function) — `web/src/views/third-party-chatbot-settings/index.tsx:363`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchPlatformThirdPartyChatbotIntegrations` | Function | `web/src/api/modules/llm-settings.ts` | 521 |
| `createPlatformThirdPartyChatbotIntegration` | Function | `web/src/api/modules/llm-settings.ts` | 528 |
| `updatePlatformThirdPartyChatbotIntegration` | Function | `web/src/api/modules/llm-settings.ts` | 536 |
| `testPlatformThirdPartyChatbotIntegrationDraft` | Function | `web/src/api/modules/llm-settings.ts` | 551 |
| `ThirdPartyChatbotSettingsPage` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 363 |
| `loadData` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 381 |
| `openCreateSchemeEditor` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 405 |
| `submitIntegration` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 420 |
| `runDraftTest` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 449 |
| `stepItems` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 543 |
| `validator` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 621 |
| `deletePlatformThirdPartyChatbotIntegration` | Function | `web/src/api/modules/llm-settings.ts` | 547 |
| `openEdit` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 412 |
| `removeIntegration` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 443 |
| `render` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 485 |
| `createDefaultStep` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 116 |
| `parseJsonBody` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 243 |
| `parseEquals` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 259 |
| `normalizePayload` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 305 |
| `jsonText` | Function | `web/src/views/third-party-chatbot-settings/index.tsx` | 241 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ThirdPartyChatbotSettingsPage → ParseJsonBody` | intra_community | 4 |
| `ThirdPartyChatbotSettingsPage → ParseEquals` | intra_community | 4 |
| `ThirdPartyChatbotSettingsPage → FetchPlatformThirdPartyChatbotIntegrations` | intra_community | 4 |
| `ThirdPartyChatbotSettingsPage → FetchTenants` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Knowledge-base-settings | 1 calls |

## How to Explore

1. `context({name: "fetchPlatformThirdPartyChatbotIntegrations"})` — see callers and callees
2. `query({search_query: "third-party-chatbot-settings"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
