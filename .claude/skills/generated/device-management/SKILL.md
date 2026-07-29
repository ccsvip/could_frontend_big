---
name: device-management
description: "Skill for the Device-management area of could_frontend_big. 24 symbols across 4 files."
---

# Device-management

24 symbols | 4 files | Cohesion: 69%

## When to Use

- Working with code in `web/`
- Understanding how fetchDeviceApplicationDeletionImpact, deleteWakeWord, handleApplicationDelete work
- Modifying device-management-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/device-management/index.tsx` | handleApplicationDelete, render, openApplicationConfig, openWakeWordModal, handleWakeWordDelete (+14) |
| `web/src/api/modules/devices.ts` | fetchDeviceApplicationDeletionImpact, deleteWakeWord |
| `web/src/api/realtime.ts` | buildDeviceEventsUnsubscribeCommand, parseRealtimeMessage |
| `web/src/views/device-management/device-expiration-display.ts` | resolveDeviceExpirationDisplay |

## Entry Points

Start here when exploring this area:

- **`fetchDeviceApplicationDeletionImpact`** (Function) — `web/src/api/modules/devices.ts:478`
- **`deleteWakeWord`** (Function) — `web/src/api/modules/devices.ts:505`
- **`handleApplicationDelete`** (Function) — `web/src/views/device-management/index.tsx:232`
- **`render`** (Function) — `web/src/views/device-management/index.tsx:264`
- **`openApplicationConfig`** (Function) — `web/src/views/device-management/index.tsx:592`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchDeviceApplicationDeletionImpact` | Function | `web/src/api/modules/devices.ts` | 478 |
| `deleteWakeWord` | Function | `web/src/api/modules/devices.ts` | 505 |
| `handleApplicationDelete` | Function | `web/src/views/device-management/index.tsx` | 232 |
| `render` | Function | `web/src/views/device-management/index.tsx` | 264 |
| `openApplicationConfig` | Function | `web/src/views/device-management/index.tsx` | 592 |
| `openWakeWordModal` | Function | `web/src/views/device-management/index.tsx` | 622 |
| `handleWakeWordDelete` | Function | `web/src/views/device-management/index.tsx` | 647 |
| `renderWakeWordsByDevice` | Function | `web/src/views/device-management/index.tsx` | 653 |
| `expandedRowRender` | Function | `web/src/views/device-management/index.tsx` | 683 |
| `buildDeviceEventsUnsubscribeCommand` | Function | `web/src/api/realtime.ts` | 60 |
| `resolveDeviceExpirationDisplay` | Function | `web/src/views/device-management/device-expiration-display.ts` | 13 |
| `DeviceManagementPage` | Function | `web/src/views/device-management/index.tsx` | 165 |
| `hasPermission` | Function | `web/src/views/device-management/index.tsx` | 202 |
| `runtimeDiagnosticCounts` | Function | `web/src/views/device-management/index.tsx` | 219 |
| `handleFilterChange` | Function | `web/src/views/device-management/index.tsx` | 535 |
| `parseRealtimeMessage` | Function | `web/src/api/realtime.ts` | 98 |
| `scheduleReload` | Function | `web/src/views/device-management/index.tsx` | 450 |
| `connect` | Function | `web/src/views/device-management/index.tsx` | 460 |
| `applicationOptions` | Function | `web/src/views/device-management/index.tsx` | 213 |
| `agentApplicationOptions` | Function | `web/src/views/device-management/index.tsx` | 215 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `DeviceManagementPage → ReadStoredJson` | cross_community | 4 |
| `DeviceManagementPage → ParseMenu` | cross_community | 4 |
| `DeviceManagementPage → ReadStoredRole` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Views | 5 calls |
| Modules | 4 calls |
| Application-management | 2 calls |
| Store | 1 calls |
| Router | 1 calls |
| Command-management | 1 calls |

## How to Explore

1. `context({name: "fetchDeviceApplicationDeletionImpact"})` — see callers and callees
2. `query({search_query: "device-management"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
