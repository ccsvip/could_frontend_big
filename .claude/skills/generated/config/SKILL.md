---
name: config
description: "Skill for the Config area of could_frontend_big. 162 symbols across 19 files."
---

# Config

162 symbols | 19 files | Cohesion: 87%

## When to Use

- Working with code in `backend/`
- Understanding how publish_device_event, add_device_event_subscriber, remove_device_event_subscriber work
- Modifying config-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/config/realtime.py` | _log_agent_voice_pipeline, _close_asr_upstream_context, _close_asr_upstream_context_later, close, close_device_events (+90) |
| `backend/config/business_cache.py` | register_business_cache_key, clear_business_cache_namespace, clear_all_business_cache, make_registry_key, validate_business_cache_namespace (+9) |
| `backend/config/sentry.py` | before_send, _coerce_text, _event_message, _event_exception_text, _argv (+4) |
| `backend/config/tests/test_realtime_websocket.py` | send, test_unexpected_asgi_send_after_close_is_not_suppressed, test_client_connection_reset_error_is_treated_as_client_disconnect, run_task, stale_agent_task (+2) |
| `backend/apps/devices/realtime.py` | publish_device_event, add_device_event_subscriber, remove_device_event_subscriber, _event_targets_device, _invalidate_device_stats (+1) |
| `backend/apps/devices/tests/test_device_authorization_api.py` | run_websocket, test_runtime_device_lookup_rejects_unbound_company, test_realtime_agent_memory_key_changes_only_after_publish, test_realtime_llm_session_uses_published_agent_prompt, run_llm |
| `backend/config/tests/test_sentry_before_send.py` | test_manage_py_test_argv_is_dropped, test_manage_py_test_with_full_path_is_dropped, test_uvicorn_argv_is_kept, test_celery_argv_is_kept, test_missing_argv_is_kept |
| `backend/apps/devices/services/runtime.py` | runtime_device_error, get_runtime_device, validate_runtime_application_active, get_ready_runtime_device |
| `backend/config/test_sentry_filters.py` | test_drops_celery_worker_redis_reconnect_during_restart, test_drops_celery_beat_database_shutdown_during_restart, test_keeps_same_messages_outside_celery_processes, test_keeps_unrelated_celery_errors |
| `backend/config/request_id.py` | make_request_id, clean_trace_value |

## Entry Points

Start here when exploring this area:

- **`publish_device_event`** (Function) — `backend/apps/devices/realtime.py:27`
- **`add_device_event_subscriber`** (Function) — `backend/apps/devices/realtime.py:77`
- **`remove_device_event_subscriber`** (Function) — `backend/apps/devices/realtime.py:89`
- **`run_websocket`** (Function) — `backend/apps/devices/tests/test_device_authorization_api.py:921`
- **`has_device_tts_voice_config`** (Function) — `backend/apps/devices/tts_voice_config.py:65`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `publish_device_event` | Function | `backend/apps/devices/realtime.py` | 27 |
| `add_device_event_subscriber` | Function | `backend/apps/devices/realtime.py` | 77 |
| `remove_device_event_subscriber` | Function | `backend/apps/devices/realtime.py` | 89 |
| `run_websocket` | Function | `backend/apps/devices/tests/test_device_authorization_api.py` | 921 |
| `has_device_tts_voice_config` | Function | `backend/apps/devices/tts_voice_config.py` | 65 |
| `application` | Function | `backend/config/asgi.py` | 9 |
| `realtime_websocket_application` | Function | `backend/config/realtime.py` | 381 |
| `on_delta` | Function | `backend/config/realtime.py` | 961 |
| `send_with_command_id` | Function | `backend/config/realtime.py` | 2536 |
| `make_request_id` | Function | `backend/config/request_id.py` | 10 |
| `clean_trace_value` | Function | `backend/config/request_id.py` | 14 |
| `run_task` | Function | `backend/config/tests/test_realtime_websocket.py` | 262 |
| `stale_agent_task` | Function | `backend/config/tests/test_realtime_websocket.py` | 321 |
| `run_start` | Function | `backend/config/tests/test_realtime_websocket.py` | 1161 |
| `run_cases` | Function | `backend/config/tests/test_realtime_websocket.py` | 1186 |
| `resolve_runtime_config_event_subscription` | Function | `backend/apps/devices/realtime.py` | 51 |
| `runtime_device_error` | Function | `backend/apps/devices/services/runtime.py` | 48 |
| `get_runtime_device` | Function | `backend/apps/devices/services/runtime.py` | 56 |
| `validate_runtime_application_active` | Function | `backend/apps/devices/services/runtime.py` | 94 |
| `get_ready_runtime_device` | Function | `backend/apps/devices/services/runtime.py` | 100 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Documents → Get_user_membership` | cross_community | 10 |
| `Media_assets → Get_user_membership` | cross_community | 10 |
| `Perform_create → Get_user_membership` | cross_community | 10 |
| `Bulk → Get_user_membership` | cross_community | 10 |
| `Perform_update → Get_user_membership` | cross_community | 10 |
| `Documents → Validate_business_cache_namespace` | cross_community | 9 |
| `Bulk_download → Get_user_membership` | cross_community | 9 |
| `Media_assets → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_create → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_create → Validate_business_cache_namespace` | cross_community | 9 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 8 calls |
| Services | 7 calls |
| Devices | 3 calls |
| Error_codes | 2 calls |
| Ai_models | 2 calls |
| Audit | 1 calls |
| Knowledge_base | 1 calls |

## How to Explore

1. `context({name: "publish_device_event"})` — see callers and callees
2. `query({search_query: "config"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
