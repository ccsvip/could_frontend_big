---
name: ai-models
description: "Skill for the Ai_models area of could_frontend_big. 286 symbols across 29 files."
---

# Ai_models

286 symbols | 29 files | Cohesion: 81%

## When to Use

- Working with code in `backend/`
- Understanding how get_llm_api_protocol, build_llm_api_url, build_llm_request_payload work
- Modifying ai_models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/views.py` | ASRReplacementRuleViewSet, PlatformLLMProviderViewSet, PlatformLLMModelViewSet, PlatformThirdPartyChatbotProviderViewSet, PlatformThirdPartyChatbotApplicationViewSet (+119) |
| `backend/apps/ai_models/serializers.py` | mask_knowledge_api_key, create, validate_fillerWords, _adapter, get_configSchemaKey (+25) |
| `backend/apps/ai_models/llm_services.py` | _normalize_api_protocol, get_llm_api_protocol, build_llm_api_url, _responses_input, _responses_tools (+22) |
| `backend/apps/ai_models/realtime_tts.py` | _stream_tts_audio, _forward_tts_upstream_audio, ensure_segment_started, finish_active_segment, _new_tts_stream_stats (+17) |
| `backend/apps/ai_models/models.py` | load, load, save, default_agent_opening_message, build_publish_config (+8) |
| `backend/apps/resources/views.py` | PermissionMappedModelViewSet, ModelAssetViewSet, CommandGroupViewSet, ControlCommandViewSet, TaskCommandViewSet (+4) |
| `backend/apps/ai_models/services/tts_adapters.py` | stream_realtime_text, stream_realtime_segments, get_tts_provider_adapter, get_adapter_for_voice, normalize_public_controls (+1) |
| `backend/apps/devices/views.py` | DeviceChatSessionCollectionView, DeviceChatSessionDetailView, perform_create, get_queryset, stats (+1) |
| `backend/apps/ai_models/realtime_asr.py` | load_asr_filler_words, is_filler_transcript_text, apply_asr_replacement_rules, is_final_transcript_event, is_filtered_filler_final_event (+1) |
| `backend/apps/tenants/mixins.py` | TenantScopedQuerysetMixin, tenant_create_kwargs, perform_create, superuser_tenant_filter, get_queryset |

## Entry Points

Start here when exploring this area:

- **`get_llm_api_protocol`** (Function) — `backend/apps/ai_models/llm_services.py:107`
- **`build_llm_api_url`** (Function) — `backend/apps/ai_models/llm_services.py:113`
- **`build_llm_request_payload`** (Function) — `backend/apps/ai_models/llm_services.py:164`
- **`run_llm_chat_completion`** (Function) — `backend/apps/ai_models/llm_services.py:207`
- **`stream_llm_chat_completion`** (Function) — `backend/apps/ai_models/llm_services.py:274`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ASRReplacementRuleViewSet` | Class | `backend/apps/ai_models/views.py` | 343 |
| `PlatformLLMProviderViewSet` | Class | `backend/apps/ai_models/views.py` | 852 |
| `PlatformLLMModelViewSet` | Class | `backend/apps/ai_models/views.py` | 913 |
| `PlatformThirdPartyChatbotProviderViewSet` | Class | `backend/apps/ai_models/views.py` | 949 |
| `PlatformThirdPartyChatbotApplicationViewSet` | Class | `backend/apps/ai_models/views.py` | 983 |
| `PlatformThirdPartyChatbotIntegrationViewSet` | Class | `backend/apps/ai_models/views.py` | 1030 |
| `AgentApplicationViewSet` | Class | `backend/apps/ai_models/views.py` | 1936 |
| `ChatConversationViewSet` | Class | `backend/apps/ai_models/views.py` | 2269 |
| `PointViewSet` | Class | `backend/apps/resources/point_views.py` | 81 |
| `PermissionMappedModelViewSet` | Class | `backend/apps/resources/views.py` | 84 |
| `ModelAssetViewSet` | Class | `backend/apps/resources/views.py` | 847 |
| `CommandGroupViewSet` | Class | `backend/apps/resources/views.py` | 891 |
| `ControlCommandViewSet` | Class | `backend/apps/resources/views.py` | 952 |
| `TaskCommandViewSet` | Class | `backend/apps/resources/views.py` | 1038 |
| `ASRFillerWordSetView` | Class | `backend/apps/ai_models/views.py` | 226 |
| `ASRRuntimeSettingsView` | Class | `backend/apps/ai_models/views.py` | 261 |
| `CompanyTTSOptionsView` | Class | `backend/apps/ai_models/views.py` | 659 |
| `CompanyTTSDefaultVoiceView` | Class | `backend/apps/ai_models/views.py` | 678 |
| `CompanyTTSTestView` | Class | `backend/apps/ai_models/views.py` | 757 |
| `CompanyLLMOptionsView` | Class | `backend/apps/ai_models/views.py` | 1699 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Perform_create → Get_user_membership` | cross_community | 10 |
| `Perform_create → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_create → Is_business_cache_enabled` | cross_community | 7 |
| `Perform_create → Get_business_cache_timeout` | cross_community | 7 |
| `Index → Load` | cross_community | 6 |
| `Delete → Superuser_tenant_filter` | cross_community | 6 |
| `Perform_update → Load` | cross_community | 6 |
| `Put → Load_aliyun` | cross_community | 5 |
| `Put → Load_aliyun` | cross_community | 5 |
| `Bulk_download → Superuser_tenant_filter` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 20 calls |
| Resources | 6 calls |
| Tests | 5 calls |
| Config | 2 calls |
| Devices | 1 calls |
| Knowledge_base | 1 calls |
| Tenants | 1 calls |

## How to Explore

1. `context({name: "get_llm_api_protocol"})` — see callers and callees
2. `query({search_query: "ai_models"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
