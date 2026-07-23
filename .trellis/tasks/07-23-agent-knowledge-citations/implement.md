# Implementation Plan — 智能体回答知识引用展示

## Ordered Checklist

### 1. Lock the shared reference/context seam

- [x] Refactor `agent_knowledge.py` so one bounded selection loop produces both the exact LLM context and selected chunks.
- [x] Add normalized snapshot/management serialization helpers with defensive validation.
- [x] Preserve existing media matching and recall-test behavior.
- [x] Add service tests proving chunks excluded by `max_chars` are not referenced.

Validation:

```powershell
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_knowledge_service --keepdb
```

### 2. Persist webpage chat references

- [x] Add `ChatMessage.knowledge_references` and migration.
- [x] Save selected snapshots with successful platform-LLM assistant messages in streaming and non-streaming branches.
- [x] Emit a terminal SSE `knowledgeReferences` event after persistence.
- [x] Add `knowledgeReferences` to `ChatMessageSerializer` history output.
- [x] Verify annotation, third-party, empty retrieval, failure, and regeneration paths remain empty/correct.

Validation:

```powershell
docker compose exec backend python manage.py test apps.ai_models.tests.test_chat_api --keepdb
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api --keepdb
```

### 3. Persist device runtime references without changing device contracts

- [x] Add `DeviceChatLog.knowledge_references` and migration.
- [x] Extend the HTTP internal answer-generation result with selected reference snapshots.
- [x] Carry WebSocket snapshots through private runtime session state and pass them only to `record_device_chat_log()`.
- [x] Keep the WebSocket done payload on an explicit public-field allowlist; never spread private session state.
- [x] Keep HTTP response and WebSocket event field sets unchanged.
- [x] Extend management device-log/session serializers with `knowledgeReferences` on assistant messages.
- [x] Verify annotation, third-party, direct-command, and no-retrieval logs store empty lists.

Validation:

```powershell
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb
docker compose exec backend python manage.py test apps.devices.tests.test_device_chat_session_api --keepdb
docker compose exec backend python manage.py test config.tests.test_realtime_websocket --keepdb
docker compose exec backend python manage.py test config.tests.test_realtime_command_dispatch --keepdb
```

### 4. Add shared management UI

- [x] Define `KnowledgeReference` in the owning frontend API module and reuse it from device types.
- [x] Extend SSE parsing with a typed reference callback.
- [x] Add streaming reference state and attach it to the temporary assistant message.
- [x] Build reusable `KnowledgeReferences` component with document grouping and responsive details.
- [x] Render it below assistant answers in live web debugging and device-session history.
- [x] Use only Tabler icons, `brand-*`, `text-fluid-*`, and responsive widths.

Validation:

```powershell
Set-Location "web"
npm run build
```

### 5. Cross-layer regression and contract checks

- [x] Assert web SSE references equal persisted history references.
- [x] Assert device HTTP response contains no `knowledgeReferences` while its management log does.
- [x] Assert WebSocket response contains no `knowledgeReferences` while its management log does.
- [x] Assert foreign-tenant conversation/log access remains denied or absent.
- [x] Assert old rows with default empty lists serialize and render normally.
- [x] Run the Tailwind token guard against changed TSX files.

Validation:

```powershell
node "scripts/check-tailwind-tokens.js"
git diff --check
```

## Expected File Touches

- `backend/apps/ai_models/services/agent_knowledge.py`
- `backend/apps/ai_models/models.py`
- `backend/apps/ai_models/serializers.py`
- `backend/apps/ai_models/views.py`
- `backend/apps/ai_models/migrations/0041_*.py`
- `backend/apps/ai_models/tests/test_agent_knowledge_service.py`
- `backend/apps/ai_models/tests/test_chat_api.py`
- `backend/apps/devices/models.py`
- `backend/apps/devices/services/chat_logs.py`
- `backend/apps/devices/services/chat_sessions.py`
- `backend/apps/devices/serializers.py`
- `backend/apps/devices/views.py`
- `backend/apps/devices/migrations/0024_*.py`
- `backend/apps/devices/tests/test_device_authorization_api.py`
- `backend/apps/devices/tests/test_device_chat_session_api.py`
- `backend/config/realtime.py`
- `backend/config/tests/test_realtime_websocket.py`
- `web/src/api/modules/chat.ts`
- `web/src/api/modules/devices.ts`
- `web/src/components/knowledge-references.tsx`
- `web/src/views/application-management/index.tsx`

Exact migration numbers must be generated from the live dependency graph rather than assumed if concurrent migrations appear.

## Risk Register

| Risk | Mitigation |
|---|---|
| Full recall result is accidentally persisted instead of bounded context chunks | One helper returns both context and selected snapshots; regression test forces truncation |
| Device protocol gains management-only fields | Contract tests assert absent fields on HTTP/WS responses and present fields only in management history |
| Streaming answer is saved but reference event is lost | History refresh remains authoritative; event is an immediate-display optimization |
| `_generate_answer()` result-shape change misses a caller | Search all callers and cover HTTP + WebSocket tests |
| WebSocket private session references leak into the done event | Pass references explicitly only to log persistence and assert the public event has no such key |
| JSON snapshot contains malformed/unserializable provider metadata | Build a strict primitive-only normalized DTO; never persist raw metadata |
| Large chunk snapshots increase row size | Bounded top-N and existing `max_chars` cap constrain total stored content |
| Huge application-management view gains more duplicated UI | Extract a stateless shared component; keep grouping/render logic outside the page |

## Review Gates Before Start

- [ ] User approves the final PRD, design, and implementation plan.
- [ ] `prd.md` has no unresolved open questions or duplicated temporary brainstorm notes.
- [ ] Device public contract compatibility is explicit in tests.
- [ ] Context-selection invariant has a named regression test.

## Rollback Points

1. After shared context selection: revert helper refactor if retrieval tests regress.
2. After backend persistence: keep additive columns, disable writes/serialization if necessary.
3. After UI: remove the shared component calls without affecting stored data or device runtime.
