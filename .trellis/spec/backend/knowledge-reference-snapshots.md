# Knowledge Reference Snapshots

## 1. Scope / Trigger

Apply this contract when an agent answer can use knowledge retrieval and the management UI needs to show its retrieval sources. References describe chunks included in the model context; they do not prove sentence-level attribution.

## 2. Signatures

- `ChatMessage.knowledge_references`: `JSONField(default=list)`
- `DeviceChatLog.knowledge_references`: `JSONField(default=list)`
- `retrieve_knowledge_context_with_media_and_references(...) -> tuple[str, list[dict], list[dict]]`
- `record_device_chat_log(..., knowledge_references: list[dict] | None = None)`

Stored entries use snake_case keys. Management serializers expose camelCase keys.

## 3. Contracts

Each stored snapshot contains `position`, local `knowledge_base_id`, local `document_id`, their names, `chunk_id`, `chunk_index`, `content`, and `score`. Do not store provider workspace, index, file identifiers, credentials, or tenant IDs in the public snapshot.

The selected chunk list and the exact LLM context must come from the same bounded loop. A candidate excluded by `max_chars` must not become a reference.

Web chat may add `knowledgeReferences` to its terminal management SSE event. Device HTTP responses and unified WebSocket events must not expose this field. Device references travel only through private server state into `DeviceChatLog`, then appear in management history APIs.

## 4. Validation & Error Matrix

| Condition | Behavior |
|---|---|
| Retrieval is skipped, disabled, empty, or fails | Continue the answer with `[]` references |
| Snapshot item lacks valid local knowledge-base/document IDs or content | Drop that item and continue |
| Score or chunk index is malformed | Serialize it as `null` |
| Annotation, third-party chatbot, or direct command handles the answer | Persist `[]` references |
| Command routing returns `hit=False` and normal LLM chat continues | Preserve the platform LLM references |
| Historical JSON is missing or malformed | Management serializer returns `[]` |

## 5. Good / Base / Bad Cases

- Good: two selected chunks from one document are stored, grouped as one document in the UI, and both remain visible after refresh.
- Base: a platform LLM answer without retrieval stores and renders an empty list.
- Bad: persisting all recall candidates, adding references to device `llm.done`, or clearing references merely because command routing returned a non-null `hit=False` outcome.

## 6. Tests Required

- Unit: assert chunks excluded by `max_chars` are absent from snapshots.
- Web chat: assert terminal SSE references equal the persisted assistant message references.
- Device HTTP: assert response has no `knowledgeReferences` and its `DeviceChatLog` has the snapshots.
- Unified WebSocket: assert `llm.done.payload` has no `knowledgeReferences` and its `DeviceChatLog` has the snapshots.
- Command routing: assert `hit=False` preserves references and `hit=True` clears them.
- History: assert user messages omit references and assistant messages return camelCase snapshots.

## 7. Wrong vs Correct

Wrong:

```python
references = build_knowledge_reference_snapshots(recall_result['chunks'])
done_payload['knowledgeReferences'] = references
```

Correct:

```python
context, selected_chunks = _format_context_from_recall_result(recall_result, max_chars=3000)
references = build_knowledge_reference_snapshots(selected_chunks)
record_device_chat_log(..., knowledge_references=references)
```

