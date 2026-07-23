# Technical Design — 智能体回答知识引用展示

## 1. Architecture

```text
retrieve_knowledge_chunks
  -> select_context_chunks(max_chars)
       -> knowledge context string sent to LLM
       -> immutable knowledge reference snapshots

Web debugging chat
  -> ChatMessage.knowledge_references
  -> final SSE event + conversation history serializer
  -> KnowledgeReferences (shared React component)

Device HTTP
  -> DeviceVoiceChatView._generate_answer internal result
  -> record_device_chat_log
Device unified WebSocket
  -> private runtime session state
  -> record_device_chat_log
  -> DeviceChatLog.knowledge_references
  -> management device-session history serializer
  -> KnowledgeReferences (same React component)
```

The feature changes only management-facing data. Device HTTP response payloads and unified WebSocket events remain byte-for-byte compatible with respect to their field set.

## 2. Domain Semantics

A knowledge reference is an immutable snapshot of one retrieval chunk that was actually included in the system context sent to the platform LLM for a specific answer.

It proves that the model received the chunk, not that every sentence in the answer was derived from it. UI copy therefore uses “知识引用” / “检索来源” and does not render inline `[1]` attribution.

References are empty for:

- annotation answers;
- third-party chatbot answers;
- direct control-command execution;
- retrieval skipped, disabled, empty, failed, or fully excluded by the context size limit.

## 3. Shared Contract

Backend storage uses snake_case JSON keys; the management API serializer emits camelCase.

```text
StoredKnowledgeReference
  position: int                  # 1-based order in model context
  knowledge_base_id: int
  knowledge_base_name: str
  document_id: int
  document_name: str
  chunk_id: str                  # remote chunk identifier when available; otherwise stable empty string
  chunk_index: int | null
  content: str                   # immutable retrieval-time snapshot
  score: float | null

KnowledgeReference (management DTO)
  position: number
  knowledgeBaseId: number
  knowledgeBaseName: string
  documentId: number
  documentName: string
  chunkId: string
  chunkIndex: number | null
  content: string
  score: number | null
```

No Workspace ID, Index ID, File ID, provider credential, or tenant ID is stored in the public snapshot.

### Normalization owner

Add one backend helper module in `apps.ai_models.services` that owns:

- selecting the exact chunks included under `max_chars`;
- formatting those chunks into the LLM context;
- converting selected chunks to normalized storage snapshots;
- serializing stored snapshots into the management DTO defensively.

All web/device paths consume this owner. Views and React components must not independently reinterpret raw retrieval payloads.

## 4. Context Selection Invariant

Current `_format_context_from_recall_result()` stops before the first chunk that would exceed `max_chars`, while `retrieve_knowledge_context_with_recall()` returns the untrimmed recall result. Saving `recall_result['chunks']` directly would create false references.

Refactor the formatting seam to return both values from the same loop:

```python
context, selected_chunks = format_context_with_selected_chunks(recall_result, max_chars=3000)
references = build_knowledge_reference_snapshots(selected_chunks)
```

The following invariant must be tested:

```text
reference chunks == chunks represented in the exact knowledge context sent to the LLM
```

Media assets remain answer blocks and are outside the knowledge-reference DTO for this MVP.

## 5. Persistence

### Models

Add independent JSON fields with `default=list`:

- `ChatMessage.knowledge_references`
- `DeviceChatLog.knowledge_references`

JSON snapshots are preferred over a new relational citation table for this MVP because:

- the bounded retrieval count is small;
- references are immutable and always read with their parent message/log;
- no citation-level filtering, editing, deletion, or analytics is required;
- parent deletion already supplies the desired lifecycle;
- it avoids joins and cross-app polymorphic ownership.

This is intentionally not stored in `content_blocks` / `answer_blocks`; those fields are rendered and spoken as answer content.

### Migrations

Create one migration in each owning app:

- `ai_models` depends on its current latest migration and adds the chat-message field;
- `devices` depends on its current latest migration and adds the device-log field.

Defaults make all historical rows backward compatible without a data migration.

## 6. Web Debugging Flow

1. Build model messages and retrieve knowledge once.
2. Select context chunks and build reference snapshots before dispatch.
3. Save snapshots on the created assistant `ChatMessage` after a successful answer.
4. Emit `knowledgeReferences` in a final SSE JSON event after message persistence and before `[DONE]`.
5. Extend `ChatMessageSerializer` to return `knowledgeReferences` for history.
6. The SSE client invokes a typed `onKnowledgeReferences` callback.
7. The temporary streaming message holds references; the existing post-finish refresh replaces it with the persisted message.

Annotation and third-party branches require no retrieval and persist the default empty list.

Regeneration already deletes the previous assistant message. Its embedded JSON references are deleted with it, and the new answer receives only its new snapshots.

## 7. Device Runtime Flow

### Internal state only

The HTTP and unified WebSocket paths currently share retrieval services but have separate orchestration seams. Carry normalized snapshots only through their private internal state; this is not a public API contract.

- annotation / third-party paths use an empty list;
- the HTTP platform-LLM path extends `_generate_answer()`'s internal result with the exact selected references;
- the unified WebSocket platform-LLM setup stores exact selected references in a private session key alongside `messages` and `knowledgeMediaBlocks`;
- HTTP and WebSocket logging calls pass snapshots only to `record_device_chat_log()`;
- the WebSocket done payload is built from an explicit public-field allowlist and never spreads private session state;
- neither path adds snapshots to its device-facing response/event.

Extend `record_device_chat_log()` with an optional `knowledge_references` argument and persist it defensively as a list.

Extend both management read shapes:

- flat `DeviceChatLogSerializer`, if still consumed by management screens;
- `serialize_device_chat_session()` assistant-message projection used by application conversation history.

## 8. Management UI

Create a focused reusable component, for example:

```text
web/src/components/knowledge-references.tsx
```

Responsibilities:

- render nothing for an empty list;
- group references by `documentId` (fallback to stable document name only for malformed legacy data);
- render a compact “知识引用 · N 个文档” trigger below the answer;
- show document chips/names at the first level;
- open an Ant Design Popover or Drawer with responsive width;
- list each chunk’s order, knowledge-base/document names, score, and pre-wrapped content snapshot.

The component receives already typed `KnowledgeReference[]`; it does not fetch data or inspect raw API payloads. Both live-chat messages and device-history messages render it under assistant reply blocks.

Use `@tabler/icons-react`, `brand-*`, `text-fluid-*`, mobile-first widths, and existing Ant Design tokens. Do not add hardcoded pixel text classes, `teal-*`, or Tailwind `!` overrides.

## 9. Failure Handling

- Retrieval failure already degrades to no context; references are empty.
- Snapshot normalization ignores malformed chunks individually and logs a warning without failing the answer.
- Persistence uses normalized plain JSON only.
- Management serialization treats non-list legacy/corrupt values as empty and filters invalid entries.
- SSE reference-event serialization failure must not suppress `[DONE]`; log and omit the event.
- Device log persistence remains inside its existing non-fatal logging boundary.

## 10. Tenant Isolation and Security

- References originate only from `retrieve_knowledge_chunks()`, which resolves remote results back to locally authorized tenant documents and discards unmapped hits.
- History endpoints retain their existing tenant-scoped parent querysets.
- The client cannot submit or query arbitrary reference IDs.
- Snapshotted chunk content is exposed only wherever the owning conversation/log is already readable.
- Remote provider IDs and credentials are never serialized.

## 11. Compatibility

- Database: additive nullable-by-default JSON behavior (`default=list`), no backfill.
- Web API: additive `knowledgeReferences` on management message DTOs.
- Web SSE: additive event consumed by the updated management client.
- Device HTTP/WebSocket: unchanged public fields.
- Existing messages/logs: render normally with empty references.

## 12. Trade-offs

- A JSON snapshot duplicates chunk text, but guarantees historical stability and keeps reads local to the parent record.
- Showing only selected context is more semantically honest than showing all candidates, but omits useful retrieval-debug candidates rejected by `max_chars`; recall-test remains the tool for full candidate inspection.
- Exact sentence-to-source attribution is deferred because current LLM output has no trustworthy alignment signal.

## 13. Rollback

- UI and serializer additions can be reverted independently; stored JSON remains harmless.
- Internal result propagation and persistence can be reverted while leaving additive columns in place.
- Database columns should not be removed during an emergency rollback because migrations are additive and empty defaults are inert.
