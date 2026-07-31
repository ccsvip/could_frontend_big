---
name: services
description: "Skill for the Services area of could_frontend_big. 378 symbols across 41 files."
---

# Services

378 symbols | 41 files | Cohesion: 76%

## When to Use

- Working with code in `backend/`
- Understanding how text_to_blocks, blocks_to_text, normalize_reply_blocks work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/services/agent_knowledge.py` | _chunk_knowledge_base_id, _chunk_knowledge_base_name, _knowledge_base_min_score, _chunk_retrieval_min_score, _retrieved_chunk_from_stored_chunk (+56) |
| `backend/apps/ai_models/services/third_party_chatbots.py` | default_scheme_a_config, default_scheme_b_config, default_config_for_scheme, supports_streaming, normalize_integration_config (+38) |
| `backend/apps/ai_models/services/tts.py` | mask_api_key, get_aliyun_tts_provider, get_effective_tts_config, get_tts_model_profile_voice_codes, is_tts_voice_supported_by_model_code (+33) |
| `backend/apps/ai_models/services/tts_adapters.py` | effective_config, effective_config, _coerce_controls, _qwen_provider, ensure_voice_supported (+18) |
| `backend/apps/resources/services/minio_client.py` | _require_complete, _normalize_endpoint, _build_client, _build_r2_client, _ensure_bucket (+15) |
| `backend/apps/ai_models/serializers.py` | validate, to_representation, validate, get_contentBlocks, get_configured (+11) |
| `backend/apps/ai_models/services/cosyvoice.py` | _is_valid_cosyvoice_workspace_endpoint, is_valid_cosyvoice_websocket_url, is_valid_cosyvoice_customization_url, get_cosyvoice_settings, get_effective_cosyvoice_tts_config (+9) |
| `backend/apps/ai_models/services/tts_authorization.py` | get_effective_tts_voices_for_tenant, _apply_model_code_filter, get_effective_tts_voice_for_tenant, is_tts_voice_effective_for_tenant, ensure_tts_voice_authorized_for_tenant (+9) |
| `backend/apps/resources/services/feishu.py` | _build_signature, _append_server_ip, send_feishu_text, send_feishu_card, _format_beijing_now (+9) |
| `backend/apps/ai_models/services/cosyvoice_realtime.py` | _run_task_message, _continue_task_message, _finish_task_message, stream_cosyvoice_realtime_segments, _send_json (+8) |

## Entry Points

Start here when exploring this area:

- **`text_to_blocks`** (Function) — `backend/apps/ai_models/services/reply_blocks.py:16`
- **`blocks_to_text`** (Function) — `backend/apps/ai_models/services/reply_blocks.py:21`
- **`normalize_reply_blocks`** (Function) — `backend/apps/ai_models/services/reply_blocks.py:26`
- **`serialize_reply_blocks`** (Function) — `backend/apps/ai_models/services/reply_blocks.py:59`
- **`serialize_published_annotation_blocks`** (Function) — `backend/apps/ai_models/services/reply_blocks.py:96`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `BaseTTSAdapter` | Class | `backend/apps/ai_models/services/tts_adapters.py` | 64 |
| `AliyunQwenTTSAdapter` | Class | `backend/apps/ai_models/services/tts_adapters.py` | 169 |
| `CosyVoiceTTSAdapter` | Class | `backend/apps/ai_models/services/tts_adapters.py` | 250 |
| `text_to_blocks` | Function | `backend/apps/ai_models/services/reply_blocks.py` | 16 |
| `blocks_to_text` | Function | `backend/apps/ai_models/services/reply_blocks.py` | 21 |
| `normalize_reply_blocks` | Function | `backend/apps/ai_models/services/reply_blocks.py` | 26 |
| `serialize_reply_blocks` | Function | `backend/apps/ai_models/services/reply_blocks.py` | 59 |
| `serialize_published_annotation_blocks` | Function | `backend/apps/ai_models/services/reply_blocks.py` | 96 |
| `annotation_event_stream` | Function | `backend/apps/ai_models/views.py` | 2550 |
| `third_party_event_stream` | Function | `backend/apps/ai_models/views.py` | 2594 |
| `serialize_device_chat_session` | Function | `backend/apps/devices/services/chat_sessions.py` | 113 |
| `is_admin_user` | Function | `backend/apps/accounts/services/permissions.py` | 19 |
| `get_role_payload` | Function | `backend/apps/accounts/services/permissions.py` | 23 |
| `serialize_menu_tree` | Function | `backend/apps/accounts/services/permissions.py` | 67 |
| `get_active_menus_for_user` | Function | `backend/apps/accounts/services/permissions.py` | 94 |
| `get_active_permission_codes_for_user` | Function | `backend/apps/accounts/services/permissions.py` | 133 |
| `get_user_membership` | Function | `backend/apps/tenants/services.py` | 8 |
| `is_valid_cosyvoice_websocket_url` | Function | `backend/apps/ai_models/services/cosyvoice.py` | 42 |
| `is_valid_cosyvoice_customization_url` | Function | `backend/apps/ai_models/services/cosyvoice.py` | 50 |
| `get_cosyvoice_settings` | Function | `backend/apps/ai_models/services/cosyvoice.py` | 58 |

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
| Ai_models | 18 calls |
| Tests | 14 calls |
| Resources | 7 calls |
| Knowledge_base | 2 calls |
| Devices | 2 calls |

## How to Explore

1. `context({name: "text_to_blocks"})` — see callers and callees
2. `query({search_query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
