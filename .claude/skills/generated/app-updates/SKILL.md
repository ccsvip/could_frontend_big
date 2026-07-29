---
name: app-updates
description: "Skill for the App_updates area of could_frontend_big. 22 symbols across 5 files."
---

# App_updates

22 symbols | 5 files | Cohesion: 93%

## When to Use

- Working with code in `backend/`
- Understanding how sign_release, SuperuserOnlyAdminMixin, AppReleaseAdmin work
- Modifying app_updates-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/app_updates/views.py` | _trace_payload, _error_response, _runtime_device, create, post (+7) |
| `backend/apps/app_updates/models.py` | _populate_file_metadata, _validate_immutable, save |
| `backend/apps/app_updates/admin.py` | SuperuserOnlyAdminMixin, AppReleaseAdmin, AppUpdateEventAdmin |
| `backend/apps/app_updates/serializers.py` | create_event, create |
| `backend/apps/app_updates/signing.py` | _load_private_key, sign_release |

## Entry Points

Start here when exploring this area:

- **`sign_release`** (Function) — `backend/apps/app_updates/signing.py:67`
- **`SuperuserOnlyAdminMixin`** (Class) — `backend/apps/app_updates/admin.py:6`
- **`AppReleaseAdmin`** (Class) — `backend/apps/app_updates/admin.py:21`
- **`AppUpdateEventAdmin`** (Class) — `backend/apps/app_updates/admin.py:49`
- **`create_event`** (Method) — `backend/apps/app_updates/serializers.py:117`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SuperuserOnlyAdminMixin` | Class | `backend/apps/app_updates/admin.py` | 6 |
| `AppReleaseAdmin` | Class | `backend/apps/app_updates/admin.py` | 21 |
| `AppUpdateEventAdmin` | Class | `backend/apps/app_updates/admin.py` | 49 |
| `sign_release` | Function | `backend/apps/app_updates/signing.py` | 67 |
| `create_event` | Method | `backend/apps/app_updates/serializers.py` | 117 |
| `create` | Method | `backend/apps/app_updates/views.py` | 48 |
| `post` | Method | `backend/apps/app_updates/views.py` | 67 |
| `post` | Method | `backend/apps/app_updates/views.py` | 127 |
| `get` | Method | `backend/apps/app_updates/views.py` | 220 |
| `patch` | Method | `backend/apps/app_updates/views.py` | 227 |
| `save` | Method | `backend/apps/app_updates/models.py` | 112 |
| `create` | Method | `backend/apps/app_updates/serializers.py` | 76 |
| `get` | Method | `backend/apps/app_updates/views.py` | 162 |
| `_load_private_key` | Function | `backend/apps/app_updates/signing.py` | 50 |
| `_trace_payload` | Function | `backend/apps/app_updates/views.py` | 23 |
| `_error_response` | Function | `backend/apps/app_updates/views.py` | 27 |
| `_runtime_device` | Function | `backend/apps/app_updates/views.py` | 34 |
| `_latest_uploaded_release` | Function | `backend/apps/app_updates/views.py` | 211 |
| `_file_chunks` | Function | `backend/apps/app_updates/views.py` | 142 |
| `_populate_file_metadata` | Method | `backend/apps/app_updates/models.py` | 91 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Post → Clean_trace_value` | cross_community | 7 |
| `Post → Clean_trace_value` | cross_community | 7 |
| `Patch → Clean_trace_value` | cross_community | 7 |
| `Post → Runtime_device_error` | cross_community | 4 |
| `Post → Runtime_device_error` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Devices | 3 calls |
| Config | 1 calls |
| Tests | 1 calls |

## How to Explore

1. `context({name: "sign_release"})` — see callers and callees
2. `query({search_query: "app_updates"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
