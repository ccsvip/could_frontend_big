---
name: resources
description: "Skill for the Resources area of could_frontend_big. 122 symbols across 18 files."
---

# Resources

122 symbols | 18 files | Cohesion: 78%

## When to Use

- Working with code in `backend/`
- Understanding how build_absolute_file_url, build_public_object_url, enqueue_command_notification work
- Modifying resources-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/apps/resources/views.py` | _publish_runtime_config_changed, perform_create, perform_update, perform_destroy, perform_create (+45) |
| `backend/apps/resources/serializers.py` | build_absolute_file_url, get_fileUrl, get_iconUrl, get_audioUrl, get_thumbnailUrl (+23) |
| `backend/apps/resources/models.py` | _tenant_fk, Resource, ScrollingText, CommandGroup, VoiceTone (+4) |
| `backend/config/business_cache.py` | perform_create, perform_update, perform_destroy, clear_cached_business_responses, CachedBusinessResponseMixin |
| `backend/apps/knowledge_base/views.py` | perform_destroy, PermissionMappedViewSet, KnowledgeBaseViewSet, KnowledgeDocumentViewSet |
| `backend/apps/resources/tasks.py` | _resolve_notification_user, _resolve_notification_company, enqueue_command_notification, enqueue_command_change_notification |
| `backend/apps/resources/services/minio_client.py` | build_public_object_url, get_video_upload_config, get_resource_upload_config |
| `backend/apps/resources/tests/test_minio_client.py` | test_r2_public_url_uses_public_base_url, test_iter_object_chunks_releases_response, test_r2_presign_uses_r2_client_for_images |
| `backend/apps/resources/services/image_hashes.py` | normalize_sha256, calculate_sha256, find_duplicate_image |
| `backend/apps/tenants/services.py` | get_tenant_from_code_param, scope_queryset_member_or_public, resolve_member_or_public_tenant |

## Entry Points

Start here when exploring this area:

- **`build_absolute_file_url`** (Function) — `backend/apps/resources/serializers.py:41`
- **`build_public_object_url`** (Function) — `backend/apps/resources/services/minio_client.py:237`
- **`enqueue_command_notification`** (Function) — `backend/apps/resources/tasks.py:61`
- **`enqueue_command_change_notification`** (Function) — `backend/apps/resources/tasks.py:107`
- **`build_point_runtime_lookup_response`** (Function) — `backend/apps/resources/point_runtime.py:7`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `PermissionMappedViewSet` | Class | `backend/apps/knowledge_base/views.py` | 59 |
| `KnowledgeBaseViewSet` | Class | `backend/apps/knowledge_base/views.py` | 158 |
| `KnowledgeDocumentViewSet` | Class | `backend/apps/knowledge_base/views.py` | 406 |
| `BaseResourceViewSet` | Class | `backend/apps/resources/views.py` | 148 |
| `ImageResourceViewSet` | Class | `backend/apps/resources/views.py` | 226 |
| `VideoResourceViewSet` | Class | `backend/apps/resources/views.py` | 328 |
| `ScrollingTextViewSet` | Class | `backend/apps/resources/views.py` | 676 |
| `VoiceToneViewSet` | Class | `backend/apps/resources/views.py` | 798 |
| `CachedBusinessResponseMixin` | Class | `backend/config/business_cache.py` | 136 |
| `Resource` | Class | `backend/apps/resources/models.py` | 19 |
| `ScrollingText` | Class | `backend/apps/resources/models.py` | 78 |
| `CommandGroup` | Class | `backend/apps/resources/models.py` | 127 |
| `VoiceTone` | Class | `backend/apps/resources/models.py` | 154 |
| `ModelAsset` | Class | `backend/apps/resources/models.py` | 188 |
| `ControlCommand` | Class | `backend/apps/resources/models.py` | 247 |
| `TaskCommand` | Class | `backend/apps/resources/models.py` | 347 |
| `build_absolute_file_url` | Function | `backend/apps/resources/serializers.py` | 41 |
| `build_public_object_url` | Function | `backend/apps/resources/services/minio_client.py` | 237 |
| `enqueue_command_notification` | Function | `backend/apps/resources/tasks.py` | 61 |
| `enqueue_command_change_notification` | Function | `backend/apps/resources/tasks.py` | 107 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Documents → Get_user_membership` | cross_community | 10 |
| `Media_assets → Get_user_membership` | cross_community | 10 |
| `Perform_create → Get_user_membership` | cross_community | 10 |
| `Bulk → Get_user_membership` | cross_community | 10 |
| `Perform_update → Get_user_membership` | cross_community | 10 |
| `Documents → Validate_business_cache_namespace` | cross_community | 9 |
| `Media_assets → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_create → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_create → Validate_business_cache_namespace` | cross_community | 9 |
| `Perform_destroy → Validate_business_cache_namespace` | cross_community | 9 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 15 calls |
| Config | 4 calls |
| Tenants | 2 calls |
| Audit | 2 calls |
| Ai_models | 1 calls |
| Devices | 1 calls |

## How to Explore

1. `context({name: "build_absolute_file_url"})` — see callers and callees
2. `query({search_query: "resources"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
