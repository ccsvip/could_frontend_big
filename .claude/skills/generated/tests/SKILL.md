---
name: tests
description: "Skill for the Tests area of could_frontend_big. 713 symbols across 66 files."
---

# Tests

713 symbols | 66 files | Cohesion: 88%

## When to Use

- Working with code in `backend/`
- Understanding how try_dispatch_command, llm_model_has_usage, llm_model_has_active_company_authorization work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/ai_models/tests/test_agent_application_api.py` | setUp, AgentApplicationApiTests, grant_permissions, agent_application_model, test_create_annotation_from_assistant_message (+39) |
| `backend/apps/ai_models/tests/test_company_tts_options_api.py` | setUp, grant_permissions, setUp, setUp, CompanyTTSProviderNeutralOptionsTests (+25) |
| `backend/apps/devices/tests/test_device_tts_authorization.py` | setUp, grant_permissions, setUp, setUp, DeviceTTSAuthorizationTests (+24) |
| `backend/config/tests/test_realtime_websocket.py` | setUp, setUp, grant_permissions, setUp, RealtimeTTSVoiceRoutingTests (+24) |
| `backend/apps/knowledge_base/tests/test_api.py` | setUp, KnowledgeBaseApiTests, grant_permissions, create_document, test_create_knowledge_base_returns_index_config (+23) |
| `backend/apps/ai_models/tests/test_llm_model_usage.py` | LLMModelUsageTests, setUp, provider_model, llm_model_model, tenant_grant_model (+22) |
| `backend/apps/ai_models/tests/test_third_party_chatbot_api.py` | setUp, ThirdPartyChatbotApiTests, provider_model, grant_permissions, create_chatbot (+21) |
| `backend/apps/ai_models/tests/test_tts_api.py` | setUp, setUp, TTSRealtimeTests, TTSApiTests, authenticate_superuser (+20) |
| `backend/apps/ai_models/tests/test_llm_company_settings_api.py` | LLMCompanySettingsApiTests, setUp, provider_model, tenant_grant_model, tenant_settings_model (+19) |
| `backend/apps/ai_models/tests/test_tts_authorization.py` | grant, test_multiple_cards_are_unioned_and_ordered_by_card, test_default_voice_is_used_when_still_authorized, test_unauthorized_default_falls_back_inside_authorization, test_ensure_authorized_rejects_unauthorized_voice_id (+18) |

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
| `CompanyTTSProviderNeutralOptionsTests` | Class | `backend/apps/ai_models/tests/test_company_tts_options_api.py` | 22 |
| `CompanyTTSDefaultVoiceAuthorizationTests` | Class | `backend/apps/ai_models/tests/test_company_tts_options_api.py` | 183 |
| `CompanyTTSTestAuthorizationTests` | Class | `backend/apps/ai_models/tests/test_company_tts_options_api.py` | 298 |
| `KnowledgeModelSettingsApiTests` | Class | `backend/apps/ai_models/tests/test_knowledge_model_settings_api.py` | 13 |
| `LLMCompanySettingsApiTests` | Class | `backend/apps/ai_models/tests/test_llm_company_settings_api.py` | 14 |
| `LLMModelUsageTests` | Class | `backend/apps/ai_models/tests/test_llm_model_usage.py` | 64 |
| `LLMPlatformSettingsApiTests` | Class | `backend/apps/ai_models/tests/test_llm_platform_settings_api.py` | 12 |
| `ThirdPartyChatbotApiTests` | Class | `backend/apps/ai_models/tests/test_third_party_chatbot_api.py` | 80 |
| `TTSRealtimeTests` | Class | `backend/apps/ai_models/tests/test_tts_api.py` | 250 |
| `TTSApiTests` | Class | `backend/apps/ai_models/tests/test_tts_api.py` | 474 |
| `DeviceApplicationDeletionApiTests` | Class | `backend/apps/devices/tests/test_device_application_deletion_api.py` | 16 |
| `DeviceAuthorizationApiTests` | Class | `backend/apps/devices/tests/test_device_authorization_api.py` | 36 |
| `DeviceChatSessionApiTests` | Class | `backend/apps/devices/tests/test_device_chat_session_api.py` | 15 |
| `DeviceTTSAuthorizationTests` | Class | `backend/apps/devices/tests/test_device_tts_authorization.py` | 26 |
| `DeviceHTTPRuntimeTTSAuthorizationTests` | Class | `backend/apps/devices/tests/test_device_tts_authorization.py` | 275 |

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
| Services | 22 calls |
| Ai_models | 10 calls |
| Config | 4 calls |
| Devices | 1 calls |
| Resources | 1 calls |
| Tenants | 1 calls |
| Knowledge_base | 1 calls |

## How to Explore

1. `context({name: "try_dispatch_command"})` — see callers and callees
2. `query({search_query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
