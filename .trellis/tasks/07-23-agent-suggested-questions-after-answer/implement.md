# Implement: 回答后下一步建议问题

## Preconditions

- [x] `prd.md` decisions resolved
- [x] `design.md` written
- [ ] User reviews artifacts and approves `task.py start`
- [ ] **Do not implement before start**

## Ordered checklist

### 1. Model + config plumbing

1. Add `AgentApplication.follow_up_suggested_questions_enabled` (default `False`) + migration
2. Wire `build_publish_config` / `runtime_config`
3. Serializer field `followUpSuggestedQuestionsEnabled`
4. Device runtime agent payload exposes the flag
5. Tests: create/update/read + default false + publish snapshot contains flag

**Verify:** `python manage.py test apps.ai_models.tests.test_agent_application_api` (or targeted cases)

### 2. Shared generator service

1. Add `apps/ai_models/services/follow_up_suggested_questions.py`
2. Implement guards, history compact, built-in prompt, parse, cap 3
3. Use `llm_services.run_llm_chat_completion` only
4. Unit tests with mocked LLM：happy path / bad JSON / disabled / empty answer / exception → `[]`

**Verify:** new test module green

### 3. Web SSE channel

1. In `ChatConversationViewSet.send` platform-LLM success path only, after answer saved, before `[DONE]`, call generator and yield `followUpSuggestedQuestions` event
2. Skip annotation + third-party paths
3. Extend `web/src/api/modules/chat.ts` `sendMessageStream` callback
4. Application management preview: state for follow-ups; display priority follow-up → static; click sends

**Verify:** chat API test with mocked completion includes SSE line; frontend typecheck `npm run build` if touching types

### 4. Realtime WS channel

1. In platform LLM completion assembling `llm.done.payload`, attach `followUpSuggestedQuestions`
2. Only when enabled + platform backend + real LLM answer; skip command short-circuit / third-party / timeout-empty
3. **Do not** write suggestions into agent memory or TTS
4. Extend `backend/config/tests/test_realtime_websocket.py` (or closest) with mock

**Verify:** realtime tests green

### 5. HTTP voice-chat channel

1. `DeviceVoiceChatView` success payload always includes `followUpSuggestedQuestions` (array)
2. Generate only under same guards
3. Test in `test_device_authorization_api` or dedicated voice-chat tests with mock

**Verify:** voice-chat tests green

### 6. Quality gate

1. Full related tests:
   - `apps.ai_models.tests.test_agent_application_api`
   - `apps.ai_models.tests.test_chat_api` (extend)
   - follow-up service tests
   - realtime + device voice-chat related
2. Manual smoke checklist (post-implement):
   - switch off → no extra LLM, empty/fallback static
   - switch on + publish → web chips after answer
   - third-party agent → no follow-up call
   - confirm main history length unchanged after many turns with follow-up clicks

## Validation commands

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_application_api
docker compose exec backend python manage.py test apps.ai_models.tests.test_chat_api
docker compose exec backend python manage.py test apps.ai_models.tests.test_follow_up_suggested_questions
docker compose exec backend python manage.py test config.tests.test_realtime_websocket
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api
cd web && npm run build
```

(Adjust test module names if implementation renames files.)

## Risky files / rollback points

| File | Risk |
|------|------|
| `backend/apps/ai_models/views.py` (`send`) | Easy to accidentally fold into main messages — review diff carefully |
| `backend/config/realtime.py` | TTS/order regressions — only touch done payload assembly |
| `backend/apps/devices/views.py` (`DeviceVoiceChatView`) | Session/history side effects — only add response field + service call |
| `web/.../application-management/index.tsx` | Large file — surgical UI only |

Rollback: disable flag globally; revert channel hooks; leave migration if already applied.

## Out of order / do not

- Do not put follow-up instruction into system prompt of main chat
- Do not store follow-up as ChatMessage
- Do not enable by default
- Do not implement third-party path
- Do not git commit unless user asks in finish phase

## Review gate before `task.py start`

User must approve:

1. `prd.md` requirements + AC
2. `design.md` contracts (field names, SSE shape, `llm.done`, voice-chat)
3. This checklist

Then:

```bash
python ./.trellis/scripts/task.py start
```
