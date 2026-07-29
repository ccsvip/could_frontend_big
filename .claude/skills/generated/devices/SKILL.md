---
name: devices
description: "Skill for the Devices area of could_frontend_big. 123 symbols across 17 files."
---

# Devices

123 symbols | 17 files | Cohesion: 81%

## When to Use

- Working with code in `backend/`
- Understanding how get_request_id, get_trace_id, bind_device_authorization work
- Modifying devices-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/devices/views.py` | _client_ip, post, _application_payload, _agent_application_payload, _log_activation (+55) |
| `backend/apps/devices/serializers.py` | _tenant_from_context, get_queryset, validate, _encode_text, create (+11) |
| `backend/apps/devices/models.py` | _tenant_fk, DeviceGroup, DeviceApplication, Device, WakeWord (+3) |
| `backend/apps/devices/tts_voice_config.py` | public_device_tts_voice_config, _first, _bounded_float, _bounded_int, normalize_device_tts_voice_config (+2) |
| `backend/apps/devices/services/authorization.py` | bind_device_authorization, ignore_device_authorization_request, rename_authorization_device, revoke_device_authorization, publish_device_authorization_event |
| `backend/apps/devices/realtime.py` | publish_device_event_sync, resolve_device_event_subscription, _resolve_connection, _parse_positive_int, build_device_runtime_config_event |
| `backend/config/request_id.py` | _clean_header_value, __call__, get_request_id, get_trace_id |
| `backend/apps/devices/services/chat_sessions.py` | _device_chat_session_display, device_chat_session_groups, serialize_device_chat_session_groups, device_chat_session_logs |
| `backend/apps/ai_models/views.py` | get, stats |
| `backend/apps/devices/services/voice_pipeline_logging.py` | log_voice_pipeline, _redact_value |

## Entry Points

Start here when exploring this area:

- **`get_request_id`** (Function) — `backend/config/request_id.py:42`
- **`get_trace_id`** (Function) — `backend/config/request_id.py:46`
- **`bind_device_authorization`** (Function) — `backend/apps/devices/services/authorization.py:8`
- **`ignore_device_authorization_request`** (Function) — `backend/apps/devices/services/authorization.py:12`
- **`rename_authorization_device`** (Function) — `backend/apps/devices/services/authorization.py:18`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `DeviceGroup` | Class | `backend/apps/devices/models.py` | 17 |
| `DeviceApplication` | Class | `backend/apps/devices/models.py` | 38 |
| `Device` | Class | `backend/apps/devices/models.py` | 105 |
| `WakeWord` | Class | `backend/apps/devices/models.py` | 200 |
| `DeviceAuthorizationCode` | Class | `backend/apps/devices/models.py` | 239 |
| `DeviceRuntimeView` | Class | `backend/apps/devices/views.py` | 762 |
| `DeviceRuntimeConfigView` | Class | `backend/apps/devices/views.py` | 783 |
| `DeviceRuntimeResourcesView` | Class | `backend/apps/devices/views.py` | 1035 |
| `DeviceRuntimeHeartbeatView` | Class | `backend/apps/devices/views.py` | 1111 |
| `DeviceVoiceChatView` | Class | `backend/apps/devices/views.py` | 1151 |
| `DeviceSerializer` | Class | `backend/apps/devices/serializers.py` | 111 |
| `DeviceDetailSerializer` | Class | `backend/apps/devices/serializers.py` | 288 |
| `DeviceAuthorizationRequestSerializer` | Class | `backend/apps/devices/serializers.py` | 447 |
| `get_request_id` | Function | `backend/config/request_id.py` | 42 |
| `get_trace_id` | Function | `backend/config/request_id.py` | 46 |
| `bind_device_authorization` | Function | `backend/apps/devices/services/authorization.py` | 8 |
| `ignore_device_authorization_request` | Function | `backend/apps/devices/services/authorization.py` | 12 |
| `rename_authorization_device` | Function | `backend/apps/devices/services/authorization.py` | 18 |
| `revoke_device_authorization` | Function | `backend/apps/devices/services/authorization.py` | 24 |
| `publish_device_authorization_event` | Function | `backend/apps/devices/services/authorization.py` | 64 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Post → Clean_trace_value` | cross_community | 7 |
| `Post → Clean_trace_value` | cross_community | 7 |
| `Patch → Clean_trace_value` | cross_community | 7 |
| `Get → Load` | cross_community | 7 |
| `Get → _strip` | cross_community | 7 |
| `Perform_update → _param` | cross_community | 7 |
| `Post → Load` | cross_community | 6 |
| `Post → _strip` | cross_community | 6 |
| `Get → _bounded_float` | cross_community | 6 |
| `Get → _resource_map` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Config | 10 calls |
| Resources | 5 calls |
| Services | 4 calls |
| Ai_models | 3 calls |
| Tenants | 2 calls |
| Tests | 1 calls |

## How to Explore

1. `context({name: "get_request_id"})` — see callers and callees
2. `query({search_query: "devices"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
