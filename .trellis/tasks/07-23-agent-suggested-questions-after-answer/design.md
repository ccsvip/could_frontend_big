# Design: 回答后下一步建议问题

## Overview

在**不改动主对话上下文组装**的前提下，增加统一旁路服务 `generate_follow_up_suggested_questions`，于平台 LLM 主回答成功落定后二次非流式调用同一主模型，产出最多 3 条建议，经三通道以 `followUpSuggestedQuestions` 交付。

```text
主链路（现有，禁止改语义）
  user → history/RAG/指令 → platform LLM → answer 落库/推送
                    │
                    ▼  only if enabled && platform LLM path && real LLM answer
  follow-up service（新）
    histories(最近少量纯文本) + 内置 instruction
    → run_llm_chat_completion (stream=false, low temperature)
    → parse JSON array → list[str] (<=3)
                    │
                    ▼
  旁路交付（不写 history）
    SSE event | llm.done.payload | HTTP JSON field
```

## Data model

### `AgentApplication` 新字段

| DB | API (camelCase) | 类型 | 默认 |
|----|-----------------|------|------|
| `follow_up_suggested_questions_enabled` | `followUpSuggestedQuestionsEnabled` | bool | `false` |

- 加入 `build_publish_config()` / `runtime_config()`
- 设备 runtime agent payload 同步下发（与 `openingMessageEnabled` 并列）
- 迁移：仅加字段 + default false；无数据回填

**不**新增：条数、prompt、专用模型字段（V1）。

## Shared service

建议路径：`backend/apps/ai_models/services/follow_up_suggested_questions.py`

### Public API

```python
def generate_follow_up_suggested_questions(
    *,
    model: LLMModel,
    history_messages: list[dict[str, str]],  # [{role, content}, ...] 纯文本轮次
    latest_answer: str,
    enabled: bool,
    timeout: int = 30,
) -> list[str]:
    """Never raises for business failures; returns [] on any soft failure."""
```

### Guard rails (in order)

1. `enabled` is False → `[]`
2. `model` missing / latest_answer blank → `[]`
3. Build compact history text: last **3** message turns (user/assistant only), hard trim if needed (~3000 chars safety, not full tokenizer)
4. Call `llm_services.run_llm_chat_completion` with:
   - `temperature=0.2`（或 0）
   - `max_tokens` 小（如 256）
   - `timeout` 短（如 20–30s），避免拖死 voice/WS
5. Parse model text:
   - extract first `[...]` span
   - `json.loads`；失败可尝试简易清理
   - keep only non-empty strings；strip；cap 3；单条过长可截断到 40 字级（中文友好，非硬 20 ASCII）
6. Any exception → log warning → `[]`

### Prompt (built-in, Chinese-friendly)

Instruction gist:

- 根据对话历史与助手最新回复，预测用户最可能继续问的 **3** 个问题
- 每条简短（建议 ≤20 个汉字）
- **输出语言与助手最新回复一致**
- **只输出 JSON 数组**：`["q1","q2","q3"]`，无其它文字

History 仅作为 user/system 文本输入给**这一次**请求的 `messages`，与主会话 `messages` 对象无关。

## Channel integration

### 1) Web debug SSE (`ChatConversationViewSet.send`)

**When:** platform LLM stream/non-stream path successfully produced assistant message (same place title/summary side effects run).  
**Not when:** annotation hit；third-party chatbot path；error paths.

**How:** after assistant content is finalized and before `data: [DONE]`，yield:

```json
{"followUpSuggestedQuestions": ["...", "...", "..."]}
```

Reuse existing pattern of auxiliary SSE JSON objects (`title`, `summary`).

**Frontend (`web/src/api/modules/chat.ts` + application-management):**

- extend `sendMessageStream` with `onFollowUpSuggestedQuestions?: (qs: string[]) => void`
- parse `parsed.followUpSuggestedQuestions`
- preview UI: after answer, chips = follow-up if length>0 else static `suggestedQuestions`
- click → existing send path

### 2) Realtime WS (`backend/config/realtime.py`)

**When:** platform LLM path finished with real `answer_text` and no command-only short-circuit that skipped LLM.  
**Where:** when building `llm.done` `done_payload` (near existing `answerText` / `commandDispatch`).

```json
{
  "type": "llm.done",
  "payload": {
    "answerText": "...",
    "followUpSuggestedQuestions": ["..."]
  }
}
```

- Generate **before** sending `llm.done` so client sees field with final answer; keep TTS pipeline independent (do not block TTS start longer than necessary — prefer: start TTS as today, run follow-up in parallel only if current architecture already allows; if not, sequential after answer text known but **before** or **with** `llm.done` is acceptable; **must not** insert follow-up into TTS text).
- Recommended simple V1: after full answer_text known, call sync generator via `sync_to_async` then include in `llm.done`; accept small added latency on that event only. Do **not** write into `_AGENT_MEMORY`.

**Not when:** third-party agent backend; effective_input_timeout; command short-circuit without LLM.

### 3) HTTP `DeviceVoiceChatView`

**When:** `_generate_answer` used platform LLM and returned normal answer (not third-party-only path if excluded; not command-only if that path skips LLM).  
**Where:** final `payload` dict alongside `answerText`:

```json
{
  "answerText": "...",
  "followUpSuggestedQuestions": []
}
```

Always include key when voice-chat succeeds (empty array if disabled/skipped) for client simplicity.

## Config / serializers / UI

| Layer | Change |
|-------|--------|
| Model + migration | new bool field default false |
| Agent serializers | read/write `followUpSuggestedQuestionsEnabled` |
| `build_publish_config` / `runtime_config` | include key |
| Device runtime agent payload | include key |
| Application management「对话设置」 | Switch 默认关；保存进现有 update payload |
| Tests | agent application API + service unit + one channel contract |

## Context isolation checklist (must pass review)

| Risk | Mitigation |
|------|------------|
| Pollute main `messages` | Separate service call only |
| Persist as ChatMessage | Never create message for follow-ups |
| Agent memory pollution | Do not call `_remember_agent_exchange` with suggestions |
| session_store pollution | Do not `append_turn` suggestions |
| TTS speaks suggestions | Never pass list into TTS |
| Change RAG/history window | Read-only copy of last turns for follow-up only |

## Compatibility

- Default off → zero behavior change for existing agents until enabled + published (follow existing publish semantics of conversation settings)
- Old clients ignore unknown JSON fields
- Static `suggestedQuestions` unchanged

## Trade-offs

| Choice | Trade-off |
|--------|-----------|
| Sync follow-up before `llm.done` | + simpler contract; − slightly later done event |
| Same main model | + consistent; − cost when enabled |
| Fixed 3 + built-in prompt | + YAGNI; − less customizable |
| Field rename `followUp*` | + no clash with static config; − longer name |

## Rollback

1. Force-disable: set all agents `follow_up_suggested_questions_enabled=false` or feature-skip in service
2. Code rollback: remove hooks; migration reverse only if needed (bool field harmless left in place)

## Non-goals (design)

- Streaming the follow-up generation
- Grounding to KB chunks
- Per-app custom prompt UI
