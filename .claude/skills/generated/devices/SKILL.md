---
name: devices
description: "Skill for the Devices area of could_frontend_big. 134 symbols across 19 files."
---

# Devices

134 symbols | 19 files | Cohesion: 78%

## When to Use

- Working with code in `backend/`
- Understanding how get_request_id, get_trace_id, bind_device_authorization work
- Modifying devices-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/devices/views.py` | _client_ip, post, _application_payload, _agent_application_payload, _log_activation (+61) |
| `backend/apps/devices/serializers.py` | to_representation, validate_voiceToneConfig, _encode_text, create, update (+12) |
| `backend/apps/devices/models.py` | _tenant_fk, DeviceGroup, DeviceApplication, Device, WakeWord (+3) |
| `backend/apps/devices/tts_voice_config.py` | public_device_tts_voice_config, _first, _bounded_float, _bounded_int, normalize_device_tts_voice_config (+2) |
| `backend/apps/devices/services/authorization.py` | bind_device_authorization, ignore_device_authorization_request, rename_authorization_device, revoke_device_authorization, publish_device_authorization_event |
| `backend/apps/devices/realtime.py` | publish_device_event_sync, resolve_device_event_subscription, _resolve_connection, _parse_positive_int, build_device_runtime_config_event |
| `backend/config/request_id.py` | _clean_header_value, __call__, get_request_id, get_trace_id |
| `backend/apps/devices/services/chat_sessions.py` | _device_chat_session_display, device_chat_session_groups, serialize_device_chat_session_groups, device_chat_session_logs |
| `backend/apps/ai_models/services/tts_runtime_events.py` | publish_tenant_tts_config_changed, publish_tts_provider_authorization_changed, publish_tts_voice_authorization_changed |
| `backend/apps/ai_models/views.py` | get, stats |

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
| `DevicePermissionMixin` | Class | `backend/apps/devices/views.py` | 172 |
| `DeviceViewSet` | Class | `backend/apps/devices/views.py` | 209 |
| `DeviceGroupViewSet` | Class | `backend/apps/devices/views.py` | 314 |
| `DeviceApplicationViewSet` | Class | `backend/apps/devices/views.py` | 319 |
| `DeviceAuthorizationCodeViewSet` | Class | `backend/apps/devices/views.py` | 376 |
| `WakeWordViewSet` | Class | `backend/apps/devices/views.py` | 644 |
| `DeviceRuntimeView` | Class | `backend/apps/devices/views.py` | 764 |
| `DeviceRuntimeConfigView` | Class | `backend/apps/devices/views.py` | 785 |
| `DeviceRuntimeResourcesView` | Class | `backend/apps/devices/views.py` | 1037 |
| `DeviceRuntimeHeartbeatView` | Class | `backend/apps/devices/views.py` | 1113 |
| `DeviceVoiceChatView` | Class | `backend/apps/devices/views.py` | 1153 |
| `DeviceSerializer` | Class | `backend/apps/devices/serializers.py` | 125 |
| `DeviceDetailSerializer` | Class | `backend/apps/devices/serializers.py` | 302 |
| `DeviceAuthorizationRequestSerializer` | Class | `backend/apps/devices/serializers.py` | 461 |
| `get_request_id` | Function | `backend/config/request_id.py` | 42 |

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
| Services | 7 calls |
| Resources | 4 calls |
| Tenants | 2 calls |
| Tests | 1 calls |
| Ai_models | 1 calls |

## How to Explore

1. `context({name: "get_request_id"})` — see callers and callees
2. `query({search_query: "devices"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
