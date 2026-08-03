[backend](../../AGENTS.md) > apps > **ai_models**

# apps/ai_models AGENTS.md

## OVERVIEW

AI 三件套（ASR / LLM / TTS）+ 聊天会话。`views.py` ~40KB（仓库最大 Python 文件），核心是聊天 SSE 流式：`httpx.AsyncClient` + `async def` + `StreamingHttpResponse` 异步生成器。

## STRUCTURE

```
ai_models/
├── models.py        # ASRProvider / LLMProvider / TTSProvider / TenantTTSProviderGrant / TenantTTSVoiceGrant / ChatConversation / ChatMessage
├── serializers.py
├── views.py         # 40KB —— 供应商 CRUD + chat conversations + SSE 流式 + 标题自动生成
├── urls.py          # /ai-models/{asr,llm,tts}/providers/*  /ai-models/chat/conversations/*
├── admin.py         # SimpleUI 后台
├── services/
│   ├── tts_authorization.py   # 公司 TTS 授权唯一入口（派生有效音色）
│   ├── tts_adapters.py        # 供应商差异 seam（Qwen / CosyVoice）
│   ├── cosyvoice_realtime.py  # run-task / continue-task / finish-task 桥接
│   └── tts_runtime_events.py  # 授权变更后推送完整 runtime config
└── (无 tasks.py)    # 当前没有 Celery 任务
```

## CONVENTIONS

- **流式必须异步**：`/conversations/<id>/send/` 必须 `async def` + `httpx.AsyncClient` + `async generator` + `StreamingHttpResponse`。同步 generator 在 ASGI 下会被整段消费。
- **ASR 安卓设备身份**：安卓端不登录后台、不拿后台 JWT。ASR 运行时必须通过设备号解析公司上下文：统一实时通信命令 `asr.session.start` 的载荷携带 `deviceCode`；`scripts/asr-replacement-test.html` 先用 `X-Device-Code` 调 `/ai-models/asr/device-status/` 验证公司，再连接 `/ws/realtime/` 并发送 `asr.session.start`。
- **SSE 兼容**：解析上游事件行**必须**同时匹配 `data:{...}` 与 `data: {...}`（冒号后 0/1 个空格）。LongCat 用前者。
- **API URL 规范化**：`api_base_url` 用户可能填 `https://api.x.com/openai`、`https://api.x.com/openai/v1` 或完整 `.../chat/completions`。`views.py` 内有规范化函数统一归一到 chat completions 端点。**不要**在调用处再做拼接。
- **OpenAI 兼容兜底**：`stream=true` 时上游若返回 200 + 普通 JSON，回退读 `choices[0].message.content` 转单条 SSE 片段下发。
- **system_prompt 注入**：`ChatConversation.system_prompt` 在每次 `send` 时被注入到 `messages` 历史最前面，作为 `system` 角色。
- **temperature / max_tokens**：从 `ChatConversation` 字段读取，真实进入上游请求体。
- **重生成**：`send` 端点支持 `regenerateMessageId`，**只允许**最后一条助手消息；后端会删该助手消息并复用前一条用户消息重请求。
- **自动标题**：会话标题为默认值 `新对话` 时，首轮回复成功后用同一模型轻量请求生成短标题，回写 `title`。
- **日志规范**：聊天链路打 `chat.send.*` / `chat.conversation.config_updated`；**不**打印 API key、**不**打印完整用户消息正文，只打 `conversation_id` / `provider_id` / `model_name` / `api_url` / `status_code` / `content_type` / `completed_*` / `timeout` / `exception`。
- **公司 TTS 授权唯一入口**：任何"这家公司能用哪个音色"的判断都必须走 `services/tts_authorization.py`，不得用请求里的 `voiceId` 直查 `TTSVoice.objects`。授权是**两级**的：卡片级 `TenantTTSProviderGrant`（`grant_mode` = `all` / `selected`）+ 音色级 `TenantTTSVoiceGrant`，再叠加 `TTSVoice.owner_tenant`（复刻音色归属公司，`NULL` 表示平台公有）。有效音色由 `active grant + active card + active/visible voice + owner_tenant 归属 + (all 模式 或 已勾选)` 派生，不落库。
- **`is_visible` 是平台上架，不是公司可见**：它是全局开关（`verbose_name='平台上架'`），下架即对所有公司不可用。要按公司收窄只能用 `grant_mode` + `TenantTTSVoiceGrant` + `owner_tenant`。
- **派生条件必须写在同一个 `.filter()` 里**：拆成两次 `.filter()` 时两个条件会分别匹配不同的关联行，`selected` 卡片可能被别家公司的授权行悄悄放宽。
- **默认音色按"保存后"校验**：授权 PUT 里 `defaultVoiceId` 要对 `_voice_ids_after_save` 派生集合校验，不能读库（读库读到的是保存前的状态），否则同一次请求可以既取消勾选某音色又把它设成默认。
- **TTS 供应商差异只在 adapter 内**：用 `get_adapter_for_voice(voice)` 按已解析音色所属卡片派发；每张卡片的公共配置存在自己的 `TenantTTSProviderGrant.public_config`，按各自 `publicConfigSchema` 白名单校验。
- **realtime 路由键是音色**：`voiceId` / 设备绑定 / 公司默认决定卡片；客户端 `providerCode` 只做一致性校验，不一致返回 `tts.error` 1025。旧客户端不传该字段必须照常工作。
- **CosyVoice 复刻音色归属**：复刻接口可选传 `ownerTenantId`，落到 `TTSVoice.owner_tenant`（serializer 用 `source='owner_tenant'`，view 侧 `**serializer.validated_data` 直接透传）；不传则为平台公有音色。
- 完整契约见 `.trellis/spec/backend/tts-tenant-card-authorization.md`。

## ANTI-PATTERNS

- ❌ 用 `requests` 替代 `httpx.AsyncClient`：会同步阻塞 ASGI worker。
- ❌ 在 ASR 安卓链路或替换词测试页里用 `admin / admin123456`、后台登录接口或后台 JWT：这会绕开设备到公司的解析，和安卓端真实行为不一致。
- ❌ 为 ASR / TTS 新增或恢复 `/ws/asr/test/`、`/ws/tts/test/` 等功能专用 WebSocket：第一方实时通信只走 `/ws/realtime/` 命令协议。
- ❌ 用 `Response.iter_content` 替代 `httpx.aiter_lines` 异步迭代。
- ❌ 在 SSE 解析里只识别 `data: `（带空格）：丢 LongCat。
- ❌ 在日志里打 `api_key` / 完整 prompt / 完整用户消息正文。
- ❌ 让 `regenerateMessageId` 命中非最后一条助手消息：会破坏会话线性结构。
- ❌ 把规范化逻辑泄到 serializer：URL 规范化只在 `views.py` 调用上游前那一刻做。
- ❌ 用请求里的 `providerCode` 决定真实上游协议：这让公司能跳到未授权卡片。
- ❌ 把新供应商字段并进共享的 `tts_session_config`：Qwen 与 CosyVoice 配置会互相覆盖。
- ❌ 用 `model_code` 过滤全部卡片的音色：它是 Qwen 播报档位概念，会把其它卡片音色全部误杀。
- ❌ 用 `is_visible` 实现"只对某家公司隐藏"：它是平台级上架开关，一改全公司都看不到。
- ❌ 在 `all` 模式下清空 `TenantTTSVoiceGrant` 勾选：超管切回 `selected` 时会丢掉他看不见的历史选择。
- ❌ 拿 `defaultVoiceId` 直接查库校验：读到的是保存前状态，会放过"取消勾选 + 设为默认"的组合。
- ❌ CosyVoice 实时流先聚合完整音频再下发：这等于取消了实时通道。

## NOTES

- `views.py` 40KB / 836 行，没有拆分意图：所有聊天与供应商相关都在一处便于看上下文；改一个端点要先定位区段。
- LLM 供应商当前以 OpenAI 兼容协议为主（自定义 base_url + key + model_name）；非兼容协议（Anthropic 原生等）暂未接入。
- 聊天测试覆盖了模型切换、SSE 兼容（`data:{...}`）、200 + 普通 JSON 兜底场景。
