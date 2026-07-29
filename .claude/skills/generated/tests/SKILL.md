---
name: tests
description: "Skill for the Tests area of could_frontend_big. 585 symbols across 61 files."
---

# Tests

585 symbols | 61 files | Cohesion: 88%

## When to Use

- Working with code in `backend/`
- Understanding how try_dispatch_command, llm_model_has_usage, llm_model_has_active_company_authorization work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/tests/test_agent_application_api.py` | setUp, AgentApplicationApiTests, grant_permissions, agent_application_model, test_create_annotation_from_assistant_message (+39) |
| `backend/apps/knowledge_base/tests/test_api.py` | setUp, KnowledgeBaseApiTests, grant_permissions, create_document, test_create_knowledge_base_returns_index_config (+23) |
| `backend/config/tests/test_realtime_websocket.py` | setUp, grant_permissions, setUp, RealtimeDeviceEventsTests, RealtimeDeviceStatusTests (+22) |
| `backend/apps/ai_models/tests/test_third_party_chatbot_api.py` | setUp, ThirdPartyChatbotApiTests, provider_model, grant_permissions, create_chatbot (+21) |
| `backend/apps/ai_models/tests/test_llm_model_usage.py` | LLMModelUsageTests, setUp, provider_model, llm_model_model, tenant_grant_model (+21) |
| `backend/apps/ai_models/tests/test_llm_company_settings_api.py` | LLMCompanySettingsApiTests, setUp, provider_model, tenant_grant_model, tenant_settings_model (+19) |
| `backend/apps/ai_models/tests/test_asr_api.py` | setUp, ASRApiTests, grant_permissions, test_non_superuser_cannot_update_asr_settings, test_user_with_asr_view_can_read_status_without_secret (+15) |
| `backend/apps/resources/tests/test_command_dispatch.py` | _run, test_returns_none_when_no_commands, test_low_score_control_text_returns_ordinary_conversation_diagnostics, test_limited_tool_selection_uses_control_command_custom_reply_without_second_generation, test_tool_selection_sends_only_matching_company_candidates (+15) |
| `backend/apps/app_updates/tests/test_app_update_api.py` | _consume_stream, make_release, test_threshold_confirm_compares_against_latest_uploaded_release, test_release_only_allows_active_patch_and_no_delete, test_model_rejects_file_replacement_and_invalid_filename (+15) |
| `backend/apps/resources/tests/test_resource_api.py` | setUp, ResourceApiTests, grant_permissions, test_create_video_resource_allows_cloud_url_without_file, test_create_video_resource_rejects_empty_cloud_url_and_empty_file (+14) |

## Entry Points

Start here when exploring this area:

- **`try_dispatch_command`** (Function) — `backend/apps/resources/services/command_dispatch.py:145`
- **`llm_model_has_usage`** (Function) — `backend/apps/ai_models/llm_services.py:56`
- **`llm_model_has_active_company_authorization`** (Function) — `backend/apps/ai_models/llm_services.py:67`
- **`llm_provider_has_active_company_authorization`** (Function) — `backend/apps/ai_models/llm_services.py:73`
- **`llm_provider_has_usage`** (Function) — `backend/apps/ai_models/llm_services.py:79`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `AgentApplicationApiTests` | Class | `backend/apps/ai_models/tests/test_agent_application_api.py` | 155 |
| `AgentKnowledgeRetrievalTests` | Class | `backend/apps/ai_models/tests/test_agent_knowledge_service.py` | 196 |
| `ASRApiTests` | Class | `backend/apps/ai_models/tests/test_asr_api.py` | 17 |
| `ASRRealtimeTests` | Class | `backend/apps/ai_models/tests/test_asr_realtime.py` | 43 |
| `ChatApiTests` | Class | `backend/apps/ai_models/tests/test_chat_api.py` | 192 |
| `KnowledgeModelSettingsApiTests` | Class | `backend/apps/ai_models/tests/test_knowledge_model_settings_api.py` | 13 |
| `LLMCompanySettingsApiTests` | Class | `backend/apps/ai_models/tests/test_llm_company_settings_api.py` | 14 |
| `LLMModelUsageTests` | Class | `backend/apps/ai_models/tests/test_llm_model_usage.py` | 63 |
| `LLMPlatformSettingsApiTests` | Class | `backend/apps/ai_models/tests/test_llm_platform_settings_api.py` | 12 |
| `ThirdPartyChatbotApiTests` | Class | `backend/apps/ai_models/tests/test_third_party_chatbot_api.py` | 80 |
| `TTSRealtimeTests` | Class | `backend/apps/ai_models/tests/test_tts_api.py` | 107 |
| `TTSApiTests` | Class | `backend/apps/ai_models/tests/test_tts_api.py` | 325 |
| `DeviceApplicationDeletionApiTests` | Class | `backend/apps/devices/tests/test_device_application_deletion_api.py` | 16 |
| `DeviceAuthorizationApiTests` | Class | `backend/apps/devices/tests/test_device_authorization_api.py` | 36 |
| `DeviceChatSessionApiTests` | Class | `backend/apps/devices/tests/test_device_chat_session_api.py` | 15 |
| `KnowledgeBaseApiTests` | Class | `backend/apps/knowledge_base/tests/test_api.py` | 29 |
| `KnowledgeDocumentChunkApiTests` | Class | `backend/apps/knowledge_base/tests/test_chunks_api.py` | 21 |
| `ManagedRagTests` | Class | `backend/apps/knowledge_base/tests/test_managed_rag.py` | 23 |
| `BackendManagementFlowApiTests` | Class | `backend/apps/resources/tests/test_backend_management_flow_api.py` | 23 |
| `BusinessMetadataCacheApiTests` | Class | `backend/apps/resources/tests/test_business_metadata_cache_api.py` | 28 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Post → Get_tenant_video_usage_bytes` | cross_community | 6 |
| `Post → Tenant_object_prefix` | cross_community | 6 |
| `Put → Load_aliyun` | cross_community | 5 |
| `Put → Load_aliyun` | cross_community | 5 |
| `Stream_chatbot_message → Normalize_chatbot_api_key` | cross_community | 5 |
| `Post → Get_user_membership` | cross_community | 5 |
| `Post → Load` | cross_community | 5 |
| `Post → _strip` | cross_community | 5 |
| `Post → _int_from_env` | cross_community | 5 |
| `Post → _bool_from_env` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 23 calls |
| Ai_models | 9 calls |
| Config | 4 calls |
| Devices | 1 calls |
| Resources | 1 calls |
| Tenants | 1 calls |

## How to Explore

1. `context({name: "try_dispatch_command"})` — see callers and callees
2. `query({search_query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
