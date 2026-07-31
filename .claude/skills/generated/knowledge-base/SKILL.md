---
name: knowledge-base
description: "Skill for the Knowledge_base area of could_frontend_big. 86 symbols across 13 files."
---

# Knowledge_base

86 symbols | 13 files | Cohesion: 80%

## When to Use

- Working with code in `backend/`
- Understanding how find_category_by_name, create_category, apply_upload_lease work
- Modifying knowledge_base-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/knowledge_base/bailian.py` | _client, _data, find_category_by_name, create_category, apply_upload_lease (+17) |
| `backend/apps/knowledge_base/views.py` | enqueue_document_index, assert_managed_rag_available, resolve_document_chunk_remote, enqueue_media_asset_index, get_serializer_context (+17) |
| `backend/apps/knowledge_base/media_indexing.py` | _setting, _dashscope_api_key, _headers, _resource_public_url, _first_embedding (+5) |
| `backend/apps/knowledge_base/managed_indexing.py` | _remote_index_name, _assert_tenant_authorized, _file_md5, _update_document, _wait_for_parse (+4) |
| `backend/apps/knowledge_base/tests/test_managed_rag.py` | test_remote_index_name_is_stable_unique_and_within_bailian_limit, test_official_document_formats_use_managed_indexing, test_long_knowledge_base_name_uses_valid_remote_index_name, test_tenant_category_is_created_once_and_reused, test_tenant_category_recovers_existing_remote_mapping (+1) |
| `backend/apps/knowledge_base/services.py` | _document_display_name, _document_company_name, notify_knowledge_document_event, notify_knowledge_document_deleted, notify_knowledge_bulk_download |
| `backend/apps/ai_models/services/agent_knowledge.py` | match_media_assets_for_chunks, serialize_media_assets, _serialize_recall_result |
| `backend/apps/resources/services/feishu.py` | notify_command_event, notify_control_command_event, notify_business_event_card |
| `backend/apps/knowledge_base/tenant_provisioning.py` | tenant_category_name, ensure_tenant_category |
| `backend/apps/knowledge_base/tasks.py` | build_knowledge_media_asset_index |

## Entry Points

Start here when exploring this area:

- **`find_category_by_name`** (Function) — `backend/apps/knowledge_base/bailian.py:63`
- **`create_category`** (Function) — `backend/apps/knowledge_base/bailian.py:77`
- **`apply_upload_lease`** (Function) — `backend/apps/knowledge_base/bailian.py:89`
- **`add_file`** (Function) — `backend/apps/knowledge_base/bailian.py:128`
- **`describe_file`** (Function) — `backend/apps/knowledge_base/bailian.py:141`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `find_category_by_name` | Function | `backend/apps/knowledge_base/bailian.py` | 63 |
| `create_category` | Function | `backend/apps/knowledge_base/bailian.py` | 77 |
| `apply_upload_lease` | Function | `backend/apps/knowledge_base/bailian.py` | 89 |
| `add_file` | Function | `backend/apps/knowledge_base/bailian.py` | 128 |
| `describe_file` | Function | `backend/apps/knowledge_base/bailian.py` | 141 |
| `create_index` | Function | `backend/apps/knowledge_base/bailian.py` | 151 |
| `submit_index` | Function | `backend/apps/knowledge_base/bailian.py` | 169 |
| `add_document_to_index` | Function | `backend/apps/knowledge_base/bailian.py` | 178 |
| `get_index_job_status` | Function | `backend/apps/knowledge_base/bailian.py` | 191 |
| `retrieve` | Function | `backend/apps/knowledge_base/bailian.py` | 197 |
| `list_chunks` | Function | `backend/apps/knowledge_base/bailian.py` | 292 |
| `update_chunk` | Function | `backend/apps/knowledge_base/bailian.py` | 328 |
| `match_media_assets_for_chunks` | Function | `backend/apps/ai_models/services/agent_knowledge.py` | 860 |
| `serialize_media_assets` | Function | `backend/apps/ai_models/services/agent_knowledge.py` | 920 |
| `embed_media_query` | Function | `backend/apps/knowledge_base/media_indexing.py` | 144 |
| `build_media_asset_index` | Function | `backend/apps/knowledge_base/media_indexing.py` | 159 |
| `build_knowledge_media_asset_index` | Function | `backend/apps/knowledge_base/tasks.py` | 16 |
| `enqueue_document_index` | Function | `backend/apps/knowledge_base/views.py` | 85 |
| `assert_managed_rag_available` | Function | `backend/apps/knowledge_base/views.py` | 105 |
| `resolve_document_chunk_remote` | Function | `backend/apps/knowledge_base/views.py` | 119 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Documents → Get_user_membership` | cross_community | 10 |
| `Media_assets → Get_user_membership` | cross_community | 10 |
| `Documents → Validate_business_cache_namespace` | cross_community | 9 |
| `Bulk_download → Get_user_membership` | cross_community | 9 |
| `Media_assets → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_destroy → Validate_business_cache_namespace` | cross_community | 9 |
| `Bulk_download → Validate_business_cache_namespace` | cross_community | 8 |
| `Media_asset_detail → Validate_business_cache_namespace` | cross_community | 8 |
| `Index → Validate_business_cache_namespace` | cross_community | 8 |
| `Perform_update → Validate_business_cache_namespace` | cross_community | 8 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Resources | 10 calls |
| Ai_models | 6 calls |
| Config | 6 calls |
| Services | 5 calls |
| Tests | 2 calls |

## How to Explore

1. `context({name: "find_category_by_name"})` — see callers and callees
2. `query({search_query: "knowledge_base"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
