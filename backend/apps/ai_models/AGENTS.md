[backend](../../AGENTS.md) > apps > **ai_models**

# apps/ai_models AGENTS.md

## OVERVIEW

AI 三件套（ASR / LLM / TTS）+ 聊天会话。`views.py` ~40KB（仓库最大 Python 文件），核心是聊天 SSE 流式：`httpx.AsyncClient` + `async def` + `StreamingHttpResponse` 异步生成器。

## STRUCTURE

```
ai_models/
├── models.py        # ASRProvider / LLMProvider / TTSProvider / ChatConversation / ChatMessage
├── serializers.py
├── views.py         # 40KB —— 供应商 CRUD + chat conversations + SSE 流式 + 标题自动生成
├── urls.py          # /ai-models/{asr,llm,tts}/providers/*  /ai-models/chat/conversations/*
├── admin.py         # SimpleUI 后台
└── (无 tasks.py)    # 当前没有 Celery 任务
```

## CONVENTIONS

- **流式必须异步**：`/conversations/<id>/send/` 必须 `async def` + `httpx.AsyncClient` + `async generator` + `StreamingHttpResponse`。同步 generator 在 ASGI 下会被整段消费。
- **ASR 安卓设备身份**：安卓端不登录后台、不拿后台 JWT。ASR 运行时必须通过设备号解析公司上下文：安卓 WebSocket 用 `X-Device-Code` 请求头；`scripts/asr-replacement-test.html` 先用 `X-Device-Code` 调 `/ai-models/asr/device-status/` 验证公司，再用 `deviceCode` 查询参数打开浏览器 WebSocket（浏览器原生 WebSocket 不能自定义请求头）。
- **SSE 兼容**：解析上游事件行**必须**同时匹配 `data:{...}` 与 `data: {...}`（冒号后 0/1 个空格）。LongCat 用前者。
- **API URL 规范化**：`api_base_url` 用户可能填 `https://api.x.com/openai`、`https://api.x.com/openai/v1` 或完整 `.../chat/completions`。`views.py` 内有规范化函数统一归一到 chat completions 端点。**不要**在调用处再做拼接。
- **OpenAI 兼容兜底**：`stream=true` 时上游若返回 200 + 普通 JSON，回退读 `choices[0].message.content` 转单条 SSE 片段下发。
- **system_prompt 注入**：`ChatConversation.system_prompt` 在每次 `send` 时被注入到 `messages` 历史最前面，作为 `system` 角色。
- **temperature / max_tokens**：从 `ChatConversation` 字段读取，真实进入上游请求体。
- **重生成**：`send` 端点支持 `regenerateMessageId`，**只允许**最后一条助手消息；后端会删该助手消息并复用前一条用户消息重请求。
- **自动标题**：会话标题为默认值 `新对话` 时，首轮回复成功后用同一模型轻量请求生成短标题，回写 `title`。
- **日志规范**：聊天链路打 `chat.send.*` / `chat.conversation.config_updated`；**不**打印 API key、**不**打印完整用户消息正文，只打 `conversation_id` / `provider_id` / `model_name` / `api_url` / `status_code` / `content_type` / `completed_*` / `timeout` / `exception`。

## ANTI-PATTERNS

- ❌ 用 `requests` 替代 `httpx.AsyncClient`：会同步阻塞 ASGI worker。
- ❌ 在 ASR 安卓链路或替换词测试页里用 `admin / admin123456`、后台登录接口或后台 JWT：这会绕开设备到公司的解析，和安卓端真实行为不一致。
- ❌ 用 `Response.iter_content` 替代 `httpx.aiter_lines` 异步迭代。
- ❌ 在 SSE 解析里只识别 `data: `（带空格）：丢 LongCat。
- ❌ 在日志里打 `api_key` / 完整 prompt / 完整用户消息正文。
- ❌ 让 `regenerateMessageId` 命中非最后一条助手消息：会破坏会话线性结构。
- ❌ 把规范化逻辑泄到 serializer：URL 规范化只在 `views.py` 调用上游前那一刻做。

## NOTES

- `views.py` 40KB / 836 行，没有拆分意图：所有聊天与供应商相关都在一处便于看上下文；改一个端点要先定位区段。
- LLM 供应商当前以 OpenAI 兼容协议为主（自定义 base_url + key + model_name）；非兼容协议（Anthropic 原生等）暂未接入。
- 聊天测试覆盖了模型切换、SSE 兼容（`data:{...}`）、200 + 普通 JSON 兜底场景。
