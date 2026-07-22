# Aliyun Bailian Managed RAG

## 1. Scope / Trigger

This contract applies to document knowledge bases. Supported documents are uploaded to Aliyun Bailian, which owns parsing, chunking, embedding, indexing, and retrieval. Local files remain only for download and retry. Image/video media matching remains an independent local capability.

## 2. Signatures

- Upload pipeline: `ApplyFileUploadLease -> PUT -> AddFile -> DescribeFile -> CreateIndex/SubmitIndexJob or SubmitIndexAddDocumentsJob`.
- Retrieval boundary: `bailian.retrieve(index_id, query, top_n, min_score) -> list[RetrievalNode]`.
- Each local `KnowledgeBase` maps to one `bailian_index_id`; each `KnowledgeDocument` maps to one `bailian_file_id`.
- Platform config: `BailianKnowledgeConfig`; tenant grant and remote category mapping: `TenantKnowledgeModelSettings`.
- Tenant category interface: `ensure_tenant_category(tenant_id) -> category_id`.

## 3. Contracts

- Official document formats: `doc/docx/wps/ppt/pptx/xls/xlsx/md/txt/pdf/epub/mobi`.
- Parser values: `AUTO_SELECT`, `DOCMIND`, `DOCMIND_DIGITAL`, `DOCMIND_LLM_VERSION`.
- Platform-only fields: AccessKey ID/Secret, Workspace ID, endpoint, active flag. Category ID is not accepted from an operator.
- AccessKey Secret is encrypted at rest and never returned. An empty secret on update preserves the stored value.
- Enabling managed RAG provisions a deterministic `solin_t{tenant_id}` category through `ListCategory/AddCategory`; first upload repeats the check as a recovery path.
- `TenantKnowledgeModelSettings` persists `bailian_category_id`, `bailian_category_workspace_id`, and a bounded `bailian_category_error`. Company-facing APIs never expose the remote ID.
- Upload lease and `AddFile` must receive the category ID returned by `ensure_tenant_category`; they must not read a shared global category.
- Tenant APIs never accept or return arbitrary Workspace, index, or file IDs.
- Recall keeps the existing `mode/chunks/mediaAssets` shape and uses `mode=bailian` for managed retrieval.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Tenant grant disabled | Reject upload/reindex; recall returns no document chunks |
| Platform config incomplete/inactive | Reject upload/reindex with a locatable validation error |
| Tenant category mapping exists for the active Workspace | Reuse it without a remote lookup or create call |
| Mapping is missing but deterministic remote category exists | Recover and persist its ID; do not create a duplicate |
| Category lookup/create fails | Persist a bounded tenant provisioning error and reject authorization/upload |
| Unsupported extension | Reject before any remote request |
| Remote parse/index failure | Persist `failed` plus the bounded error summary |
| Retrieve failure | Log tenant/base identifiers, return empty document recall, never query local pgvector |
| Remote delete failure | Keep the local record/file and return an explicit API error |
| Remote metadata references an unmapped file | Drop the node; never infer a cross-tenant document |

## 5. Good / Base / Bad Cases

- Good: enabling a tenant grant automatically provisions its category; each local base then supplies its stored `index_id`, and Bailian nodes map only to ready local documents.
- Base: Bailian returns no nodes or is temporarily unavailable; the LLM conversation continues without knowledge context.
- Bad: an operator enters one shared Category ID, or code calls `_embed_texts`, `build_document_index`, or `KnowledgeDocumentChunk` from the active document upload/recall path.

## 6. Tests Required

- Mock end-to-end upload for PDF, DOCX, and XLSX; assert final local status is ready and the index model is `bailian-managed-rag`.
- Mock parse/index failure, idempotent retry, force rebuild, and remote delete failure.
- Assert Retrieve results map only through tenant-scoped local file IDs and merge by score across bases.
- Patch local embedding/index helpers and assert they are never called by managed retrieval.
- Assert company responses contain only `managedRagEnabled`, never platform credentials or Workspace IDs.
- Assert two tenants receive different Category IDs, retries reuse the persisted mapping, and an existing deterministic remote category is recovered after an interrupted local save.

## 7. Wrong vs Correct

### Wrong

```python
lease = bailian.apply_upload_lease(config.category_id, file_name, content_md5, file_size)
```

### Correct

```python
category_id = ensure_tenant_category(document.tenant_id)
lease = bailian.apply_upload_lease(
    category_id=category_id,
    file_name=document.file_name,
    content_md5=content_md5,
    file_size=document.file_size,
)
```
