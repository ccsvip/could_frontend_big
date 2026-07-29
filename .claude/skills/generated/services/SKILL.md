---
name: services
description: "Skill for the Services area of could_frontend_big. 281 symbols across 34 files."
---

# Services

281 symbols | 34 files | Cohesion: 76%

## When to Use

- Working with code in `backend/`
- Understanding how is_admin_user, get_role_payload, serialize_menu_tree work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/services/agent_knowledge.py` | _chunk_knowledge_base_id, _chunk_knowledge_base_name, _knowledge_base_min_score, _chunk_retrieval_min_score, _retrieved_chunk_from_stored_chunk (+56) |
| `backend/apps/ai_models/services/third_party_chatbots.py` | default_scheme_a_config, default_scheme_b_config, default_config_for_scheme, supports_streaming, normalize_integration_config (+38) |
| `backend/apps/ai_models/services/tts.py` | get_aliyun_tts_provider, get_tts_model_profile_voice_codes, is_tts_voice_supported_by_model_code, get_tenant_tts_settings, get_available_tts_voices (+25) |
| `backend/apps/resources/services/minio_client.py` | _require_complete, _normalize_endpoint, _build_client, _build_r2_client, _ensure_bucket (+15) |
| `backend/apps/resources/services/feishu.py` | _build_signature, _append_server_ip, send_feishu_text, send_feishu_card, _format_beijing_now (+9) |
| `backend/apps/resources/services/command_dispatch.py` | _execute_control, _dispatch_control_command, _execute_task, _load_control_command, _load_task_command (+6) |
| `backend/apps/ai_models/services/asr.py` | create_connection, build_asr_ws_url, is_asr_configured, transcribe_pcm_audio, _missing_config_message (+5) |
| `backend/apps/resources/services/command_tools.py` | build_task_command_tools, build_task_command_tool, build_command_tools, find_tool_by_name, command_index_map (+5) |
| `backend/apps/resources/tests/test_command_tools.py` | test_build_command_tools_combines_control_and_task, test_find_tool_by_name_returns_match, test_command_index_map, test_build_tools_for_none_tenant_returns_empty, test_build_control_command_tool_uses_openai_format (+4) |
| `backend/apps/accounts/services/permissions.py` | is_admin_user, get_role_payload, _get_membership, _collect_with_ancestors, serialize_menu_tree (+3) |

## Entry Points

Start here when exploring this area:

- **`is_admin_user`** (Function) — `backend/apps/accounts/services/permissions.py:19`
- **`get_role_payload`** (Function) — `backend/apps/accounts/services/permissions.py:23`
- **`serialize_menu_tree`** (Function) — `backend/apps/accounts/services/permissions.py:67`
- **`get_active_menus_for_user`** (Function) — `backend/apps/accounts/services/permissions.py:94`
- **`get_active_permission_codes_for_user`** (Function) — `backend/apps/accounts/services/permissions.py:133`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `is_admin_user` | Function | `backend/apps/accounts/services/permissions.py` | 19 |
| `get_role_payload` | Function | `backend/apps/accounts/services/permissions.py` | 23 |
| `serialize_menu_tree` | Function | `backend/apps/accounts/services/permissions.py` | 67 |
| `get_active_menus_for_user` | Function | `backend/apps/accounts/services/permissions.py` | 94 |
| `get_active_permission_codes_for_user` | Function | `backend/apps/accounts/services/permissions.py` | 133 |
| `get_user_membership` | Function | `backend/apps/tenants/services.py` | 8 |
| `build_asr_ws_url` | Function | `backend/apps/ai_models/services/asr.py` | 59 |
| `is_asr_configured` | Function | `backend/apps/ai_models/services/asr.py` | 93 |
| `transcribe_pcm_audio` | Function | `backend/apps/ai_models/services/asr.py` | 97 |
| `test_asr_connection` | Function | `backend/apps/ai_models/services/asr.py` | 227 |
| `get_tenant_video_usage_bytes` | Function | `backend/apps/resources/services/minio_client.py` | 255 |
| `get_tenant_video_quota_summary` | Function | `backend/apps/resources/services/minio_client.py` | 269 |
| `presign_resource_put_url` | Function | `backend/apps/resources/services/minio_client.py` | 331 |
| `delete_object` | Function | `backend/apps/resources/services/minio_client.py` | 417 |
| `iter_object_chunks` | Function | `backend/apps/resources/services/minio_client.py` | 436 |
| `resolve_tts_voice` | Function | `backend/apps/ai_models/realtime_tts.py` | 87 |
| `resolve_tts_provider` | Function | `backend/apps/ai_models/realtime_tts.py` | 127 |
| `get_aliyun_tts_provider` | Function | `backend/apps/ai_models/services/tts.py` | 111 |
| `get_tts_model_profile_voice_codes` | Function | `backend/apps/ai_models/services/tts.py` | 171 |
| `is_tts_voice_supported_by_model_code` | Function | `backend/apps/ai_models/services/tts.py` | 178 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Documents → Get_user_membership` | cross_community | 10 |
| `Media_assets → Get_user_membership` | cross_community | 10 |
| `Perform_create → Get_user_membership` | cross_community | 10 |
| `Bulk → Get_user_membership` | cross_community | 10 |
| `Perform_update → Get_user_membership` | cross_community | 10 |
| `Bulk_download → Get_user_membership` | cross_community | 9 |
| `Get → Load` | cross_community | 7 |
| `Get → _strip` | cross_community | 7 |
| `Perform_update → _param` | cross_community | 7 |
| `Send → Load` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 14 calls |
| Ai_models | 10 calls |
| Resources | 5 calls |
| Knowledge_base | 2 calls |

## How to Explore

1. `context({name: "is_admin_user"})` — see callers and callees
2. `query({search_query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
