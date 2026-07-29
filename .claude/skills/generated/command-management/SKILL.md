---
name: command-management
description: "Skill for the Command-management area of could_frontend_big. 126 symbols across 13 files."
---

# Command-management

126 symbols | 13 files | Cohesion: 77%

## When to Use

- Working with code in `web/`
- Understanding how createControlCommand, updateControlCommand, deleteControlCommand work
- Modifying command-management-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/command-management/workspace.tsx` | invalidateTaskLookupCache, closeControlModal, saveControl, removeControl, closeGroupModal (+33) |
| `web/src/api/modules/commands.ts` | createControlCommand, updateControlCommand, deleteControlCommand, exportAllCommands, buildActiveParam (+13) |
| `web/src/views/command-management/tasks.tsx` | getStepSummary, loadData, openEditModal, handleDelete, render (+5) |
| `web/src/views/command-management/task-step-form-list.tsx` | stripInlineWhitespace, getDragScrollContainer, TaskStepFormList, stopDragAutoScroll, updateDragAutoScroll (+5) |
| `web/src/views/command-management/index.tsx` | ControlCommandManagementPage, hasPermission, loadData, loadGroups, openEditModal (+4) |
| `web/src/views/command-management/points.tsx` | PointManagementPage, hasPermission, loadData, openEditModal, closeFormModal (+4) |
| `web/src/views/command-management/export.tsx` | downloadJson, handleDownloadCommands, handleDownloadGroupCommands, render, fetchExportManagementGroups (+3) |
| `web/src/views/command-management/groups.tsx` | CommandGroupManagementPage, hasPermission, loadData, closeFormModal, handleSubmit (+3) |
| `web/src/views/command-management/control-command-recognition-policy.tsx` | toThreshold, ControlCommandRecognitionPolicyPanel, loadPolicy, saveFixedReply, savePolicy (+1) |
| `web/src/views/command-management/command-export-format.ts` | getGroupCommands, buildCommandGroupExportPayload, buildCommandGroupExportCollectionPayload, buildCommandGroupExportFilename |

## Entry Points

Start here when exploring this area:

- **`createControlCommand`** (Function) — `web/src/api/modules/commands.ts:197`
- **`updateControlCommand`** (Function) — `web/src/api/modules/commands.ts:202`
- **`deleteControlCommand`** (Function) — `web/src/api/modules/commands.ts:207`
- **`normalizeControlCommandReplyPreferences`** (Function) — `web/src/views/command-management/control-command-reply-preferences.ts:12`
- **`ControlCommandManagementPage`** (Function) — `web/src/views/command-management/index.tsx:69`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `createControlCommand` | Function | `web/src/api/modules/commands.ts` | 197 |
| `updateControlCommand` | Function | `web/src/api/modules/commands.ts` | 202 |
| `deleteControlCommand` | Function | `web/src/api/modules/commands.ts` | 207 |
| `normalizeControlCommandReplyPreferences` | Function | `web/src/views/command-management/control-command-reply-preferences.ts` | 12 |
| `ControlCommandManagementPage` | Function | `web/src/views/command-management/index.tsx` | 69 |
| `hasPermission` | Function | `web/src/views/command-management/index.tsx` | 70 |
| `loadData` | Function | `web/src/views/command-management/index.tsx` | 95 |
| `loadGroups` | Function | `web/src/views/command-management/index.tsx` | 108 |
| `openEditModal` | Function | `web/src/views/command-management/index.tsx` | 140 |
| `closeFormModal` | Function | `web/src/views/command-management/index.tsx` | 157 |
| `handleSubmit` | Function | `web/src/views/command-management/index.tsx` | 176 |
| `handleDelete` | Function | `web/src/views/command-management/index.tsx` | 210 |
| `render` | Function | `web/src/views/command-management/index.tsx` | 230 |
| `closeControlModal` | Function | `web/src/views/command-management/workspace.tsx` | 471 |
| `saveControl` | Function | `web/src/views/command-management/workspace.tsx` | 477 |
| `removeControl` | Function | `web/src/views/command-management/workspace.tsx` | 511 |
| `createPoint` | Function | `web/src/api/modules/point-management.ts` | 57 |
| `updatePoint` | Function | `web/src/api/modules/point-management.ts` | 62 |
| `deletePoint` | Function | `web/src/api/modules/point-management.ts` | 67 |
| `PointManagementPage` | Function | `web/src/views/command-management/points.tsx` | 31 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `CommandWorkspacePage → BuildActiveParam` | cross_community | 5 |
| `TaskCommandManagementPage → BuildActiveParam` | cross_community | 5 |
| `TaskCommandManagementPage → BuildActiveParam` | cross_community | 5 |
| `CommandWorkspacePage → ReadStoredJson` | cross_community | 4 |
| `CommandWorkspacePage → ParseMenu` | cross_community | 4 |
| `TaskCommandManagementPage → ReadStoredJson` | cross_community | 4 |
| `TaskCommandManagementPage → ParseMenu` | cross_community | 4 |
| `ImportCurrentGroupCommands → BuildActiveParam` | cross_community | 4 |
| `CommandWorkspacePage → ReadStoredRole` | cross_community | 3 |
| `CommandWorkspacePage → CollectPages` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Modules | 9 calls |
| Store | 6 calls |

## How to Explore

1. `context({name: "createControlCommand"})` — see callers and callees
2. `query({search_query: "command-management"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
