# Aliyun Bailian Managed RAG

## 1. Scope / Trigger

This contract applies to document knowledge bases. Supported documents are uploaded to Aliyun Bailian, which owns parsing, chunking, embedding, indexing, and retrieval. Local files remain only for download and retry. Image/video media matching remains an independent local capability.

## 2. Signatures

- Upload pipeline: `ApplyFileUploadLease -> PUT -> AddFile -> DescribeFile -> CreateIndex/SubmitIndexJob or SubmitIndexAddDocumentsJob`.
- Retrieval boundary: `bailian.retrieve(index_id, query, top_n, min_score) -> list[RetrievalNode]`.
- Each local `KnowledgeBase` maps to one `bailian_index_id`; each `KnowledgeDocument` maps to one `bailian_file_id`.
- Platform config: `BailianKnowledgeConfig`; tenant grant: `TenantKnowledgeModelSettings.managed_rag_enabled`.

## 3. Contracts

- Official document formats: `doc/docx/wps/ppt/pptx/xls/xlsx/md/txt/pdf/epub/mobi`.
- Parser values: `AUTO_SELECT`, `DOCMIND`, `DOCMIND_DIGITAL`, `DOCMIND_LLM_VERSION`.
- Platform-only fields: AccessKey ID/Secret, Workspace ID, Category ID, endpoint, active flag.
- AccessKey Secret is encrypted at rest and never returned. An empty secret on update preserves the stored value.
- Tenant APIs never accept or return arbitrary Workspace, index, or file IDs.
- Recall keeps the existing `mode/chunks/mediaAssets` shape and uses `mode=bailian` for managed retrieval.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Tenant grant disabled | Reject upload/reindex; recall returns no document chunks |
| Platform config incomplete/inactive | Reject upload/reindex with a locatable validation error |
| Unsupported extension | Reject before any remote request |
| Remote parse/index failure | Persist `failed` plus the bounded error summary |
| Retrieve failure | Log tenant/base identifiers, return empty document recall, never query local pgvector |
| Remote delete failure | Keep the local record/file and return an explicit API error |
| Remote metadata references an unmapped file | Drop the node; never infer a cross-tenant document |

## 5. Good / Base / Bad Cases

- Good: a tenant-scoped local base supplies its stored `index_id`; Bailian returns a node whose `file_id` maps to a ready local document.
- Base: Bailian returns no nodes or is temporarily unavailable; the LLM conversation continues without knowledge context.
- Bad: code calls `_embed_texts`, `build_document_index`, or `KnowledgeDocumentChunk` from the active document upload/recall path.

## 6. Tests Required

- Mock end-to-end upload for PDF, DOCX, and XLSX; assert final local status is ready and the index model is `bailian-managed-rag`.
- Mock parse/index failure, idempotent retry, force rebuild, and remote delete failure.
- Assert Retrieve results map only through tenant-scoped local file IDs and merge by score across bases.
- Patch local embedding/index helpers and assert they are never called by managed retrieval.
- Assert company responses contain only `managedRagEnabled`, never platform credentials or Workspace IDs.

## 7. Wrong vs Correct

### Wrong

```python
query_embedding = _embed_texts(client, model, [query])[0]
chunks = KnowledgeDocumentChunk.objects.filter(document__tenant=tenant)
```

### Correct

```python
nodes = bailian.retrieve(
    index_id=tenant_scoped_base.bailian_index_id,
    query=query,
    top_n=top_n,
    min_score=tenant_scoped_base.retrieval_min_score,
)
```

