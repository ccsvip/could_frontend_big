---
name: ai-models
description: "Skill for the Ai_models area of could_frontend_big. 277 symbols across 29 files."
---

# Ai_models

277 symbols | 29 files | Cohesion: 78%

## When to Use

- Working with code in `backend/`
- Understanding how text_to_blocks, blocks_to_text, normalize_reply_blocks work
- Modifying ai_models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/views.py` | _build_chat_completions_url, create, send, annotation_event_stream, _save_third_party_assistant_message (+113) |
| `backend/apps/ai_models/serializers.py` | validate, to_representation, validate, get_contentBlocks, mask_knowledge_api_key (+27) |
| `backend/apps/ai_models/realtime_tts.py` | _stream_tts_audio, _forward_tts_upstream_audio, ensure_segment_started, finish_active_segment, _new_tts_stream_stats (+14) |
| `backend/apps/ai_models/llm_services.py` | get_effective_llm_model_for_tenant, get_tenant_llm_settings, mask_api_key, get_effective_llm_models_for_tenant, is_llm_model_effective_for_tenant (+13) |
| `backend/apps/devices/views.py` | _generate_answer, _resolve_third_party_conversation, _runtime_conversation_user, DeviceChatSessionCollectionView, DeviceChatSessionDetailView (+9) |
| `backend/apps/ai_models/models.py` | save, default_agent_opening_message, build_publish_config, publish, runtime_config (+8) |
| `backend/apps/ai_models/services/reply_blocks.py` | text_to_blocks, blocks_to_text, normalize_reply_blocks, serialize_reply_blocks, serialize_published_annotation_blocks (+3) |
| `backend/apps/resources/views.py` | PermissionMappedModelViewSet, ModelAssetViewSet, CommandGroupViewSet, ControlCommandViewSet, TaskCommandViewSet (+1) |
| `backend/apps/ai_models/realtime_asr.py` | load_asr_filler_words, is_filler_transcript_text, apply_asr_replacement_rules, is_final_transcript_event, is_filtered_filler_final_event (+1) |
| `backend/apps/ai_models/tests/test_llm_model_usage.py` | test_llm_test_settings_load_uses_singleton_row, test_tenant_settings_service_creates_company_settings_once, test_mask_api_key_keeps_only_safe_edges, test_llm_model_effective_service_returns_boolean, test_validate_llm_test_settings_values_rejects_out_of_range_values |

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
| `ASRFillerWordSetView` | Class | `backend/apps/ai_models/views.py` | 215 |
| `ASRRuntimeSettingsView` | Class | `backend/apps/ai_models/views.py` | 250 |
| `CompanyTTSOptionsView` | Class | `backend/apps/ai_models/views.py` | 512 |
| `CompanyTTSDefaultVoiceView` | Class | `backend/apps/ai_models/views.py` | 531 |
| `CompanyTTSTestView` | Class | `backend/apps/ai_models/views.py` | 551 |
| `CompanyLLMOptionsView` | Class | `backend/apps/ai_models/views.py` | 1353 |
| `CompanyThirdPartyChatbotOptionsView` | Class | `backend/apps/ai_models/views.py` | 1360 |
| `CompanyLLMDefaultModelView` | Class | `backend/apps/ai_models/views.py` | 1367 |
| `CompanyLLMModelTestView` | Class | `backend/apps/ai_models/views.py` | 1389 |
| `DeviceChatSessionCollectionView` | Class | `backend/apps/devices/views.py` | 108 |
| `DeviceChatSessionDetailView` | Class | `backend/apps/devices/views.py` | 139 |
| `DevicePermissionMixin` | Class | `backend/apps/devices/views.py` | 170 |
| `DeviceViewSet` | Class | `backend/apps/devices/views.py` | 207 |
| `DeviceGroupViewSet` | Class | `backend/apps/devices/views.py` | 312 |
| `DeviceApplicationViewSet` | Class | `backend/apps/devices/views.py` | 317 |
| `DeviceAuthorizationCodeViewSet` | Class | `backend/apps/devices/views.py` | 374 |
| `WakeWordViewSet` | Class | `backend/apps/devices/views.py` | 642 |
| `TenantScopedQuerysetMixin` | Class | `backend/apps/tenants/mixins.py` | 3 |
| `ASRReplacementRuleViewSet` | Class | `backend/apps/ai_models/views.py` | 332 |
| `PlatformLLMProviderViewSet` | Class | `backend/apps/ai_models/views.py` | 611 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get → Load` | cross_community | 7 |
| `Get → _strip` | cross_community | 7 |
| `Send → Load` | cross_community | 6 |
| `Send → _strip` | cross_community | 6 |
| `Send → _int_from_env` | cross_community | 6 |
| `Send → _bool_from_env` | cross_community | 6 |
| `Get → _resource_map` | cross_community | 6 |
| `Index → Load` | cross_community | 6 |
| `Delete → Superuser_tenant_filter` | cross_community | 6 |
| `Perform_update → Load` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 20 calls |
| Resources | 4 calls |
| Devices | 4 calls |
| Tests | 4 calls |
| Config | 4 calls |
| Knowledge_base | 1 calls |
| Tenants | 1 calls |

## How to Explore

1. `context({name: "text_to_blocks"})` — see callers and callees
2. `query({search_query: "ai_models"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
