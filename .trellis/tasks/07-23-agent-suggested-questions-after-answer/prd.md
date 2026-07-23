# 智能体回答后下一步建议问题

## Goal

在智能体每一轮**平台 LLM 有效回答完成之后**，自动生成并返回「下一步建议问题」（动态 follow-up），并在以下三条通道一致可用：

1. 智能体网页调试会话（SSE `/ai-models/chat/conversations/<id>/send/`）
2. 三合一 WebSocket（`/ws/realtime/` 的 `agent.session` 链路）
3. 单独 HTTP LLM / 语音问答接口（`POST /api/v1/device/voice-chat`）

用户价值：降低多轮冷启动成本，引导继续提问；与已有「开场白 + 静态建议问题」互补，而不是替代。

**硬约束（用户强调）：不得弄乱现有上下文逻辑** —— 动态建议必须是主回答完成后的旁路二次调用，禁止并入主对话 `messages` / history / agent memory。

## Background / Confirmed Facts

### 已有能力（静态，不自动生成）

- `AgentApplication` 已有：
  - `opening_message_enabled` / `opening_message`：开场白
  - `suggested_questions`（JSON 列表）：**静态**建议问题，最多 10 条，单条 ≤120 字
- 设计文档 `docs/superpowers/specs/2026-06-16-agent-conversation-settings-design.md` 明确 V1：**不自动生成建议问题**（本任务新增「可选自动生成」，与该 V1 静态能力并存）
- 前端 `web/src/views/application-management/index.tsx` 已在调试预览展示静态 `suggestedQuestions`，点击即发送
- 设备运行时配置已下发静态 `suggestedQuestions` / `openingMessage*`

### 三条对话通道（代码锚点）

| 通道 | 入口 | 主回答完成点 |
|------|------|----------------|
| 网页调试 | `ChatConversationViewSet.send` → SSE | `backend/apps/ai_models/views.py` ~2155+；SSE 末尾 `data: [DONE]`；已有 `title`/`summary` 旁路事件模式可复用 |
| 三合一 WS | `agent.session.*` → `_run_agent_llm_and_finish` | `backend/config/realtime.py`；`llm.done.payload` 含 `answerText` 等 |
| HTTP 单独调用 | `DeviceVoiceChatView.post` | `backend/apps/devices/views.py`；响应 `answerText` / `answerBlocks` |

### 上下文现状（硬约束相关）

- 网页：`ChatConversation` + `ChatMessage` 历史 + `system_prompt` 参与上游 `messages`
- 三合一 / HTTP：`runtime_config()` + 会话记忆 / `session_store` + 知识库上下文 + 指令命中短路
- 主回答链路已含 RAG / 标注命中 / 第三方机器人 / 指令 dispatch

### 参考实现（Dify Suggested Questions After Answer）

- 主回答结束后**二次、非流式** LLM 调用
- 仅读最近少量历史
- 强制 JSON 数组输出
- 解析失败 → 空列表；**不**写入会话历史消息

## Decisions (resolved)

| 决策 | 结论 |
|------|------|
| 开关粒度 | 每个智能体「对话设置」独立开关 |
| 默认值 | **关闭**（`false`） |
| 静态 vs 动态展示 | 开场用静态；答后**优先动态，空则回退静态**；不并存堆叠 |
| 第三方机器人 | **不需要**本功能；第三方后端路径不生成 |
| 生成模型 | **复用智能体主 LLM 模型**（V1 不可另选） |
| 指令命中短路 | **不生成** |
| 本轮响应字段 | **`followUpSuggestedQuestions: string[]`** |
| 配置开关字段 | **`followUpSuggestedQuestionsEnabled`**（DB：`follow_up_suggested_questions_enabled`） |
| 条数 / prompt | **V1 仅开关**；固定 3 条；内置中文友好 prompt；temperature 偏低固定 |

## Requirements

### R1. 生成语义

- 仅当：开关开启 + 平台 LLM 后端 + 本轮真正完成平台 LLM 助手回答
- 输出固定最多 **3** 条非空短问题；语言与最新助手回复一致
- 二次调用使用智能体主 `llm_model`，非流式，`run_llm_chat_completion`（或等价）
- **上下文隔离**：
  - 不得把建议生成 prompt 并入主对话 system/user
  - 不得把建议问题存为 `ChatMessage` / 设备会话 turn / agent memory
  - 不得改变现有 history 截断、RAG 注入、指令命中、TTS 过滤逻辑
  - 失败/超时/解析失败 → `[]`，主回答与现有事件流必须仍成功

### R2. 三通道一致交付

- **网页**：SSE 在 `[DONE]` 前增加事件，例如 `{"followUpSuggestedQuestions":[...]}`；前端解析后展示；点击 = 普通用户消息发送
- **三合一 WS**：在 `llm.done.payload` 增加 `followUpSuggestedQuestions`（不得新增会打断 ASR→LLM→TTS 顺序的阻塞事件；生成可在 `llm.done` 发送前旁路完成，失败则 `[]`）
- **HTTP `device/voice-chat`**：成功 JSON 增加 `followUpSuggestedQuestions: string[]`
- 三条通道共用**同一后端生成服务**

### R3. 与静态建议问题的关系

- 静态 `suggested_questions` / API `suggestedQuestions` 语义不变
- 展示：开场静态；答后优先 `followUpSuggestedQuestions`，空则回退静态

### R4. 触发边界

| 场景 | 是否生成 |
|------|----------|
| 开关关 | 否 → `[]` |
| 第三方机器人后端 | 否 → `[]`（可不调用服务） |
| 平台 LLM 答完 | 是（开关开时） |
| 标注命中固定答（网页 annotation） | 否（非 LLM） |
| 指令命中短路 | 否 |
| 停止/cancel/超时无 LLM/主失败 | 否 |

### R5. 配置与发布

- 对话设置 UI 增加开关「回答后建议问题」/ 等价文案，默认关
- 字段进入 `build_publish_config` / `runtime_config` / 设备 runtime agent 配置
- 未发布草稿与已发布语义与现有开场白字段一致（走同一 publish 机制）

### R6. 质量与测试

- 单测：生成服务 prompt/解析/失败空列表；开关关不调用 LLM
- 契约：SSE / `llm.done` / voice-chat 字段
- 回归：主 `messages` 组装路径不被污染

## Acceptance Criteria

- [ ] AC1：网页调试会话中，开关开启且平台 LLM 流式结束后展示本轮 `followUpSuggestedQuestions`；点击后作为普通用户消息发送
- [ ] AC2：三合一 WebSocket 在有效平台 LLM 回答完成后，`llm.done.payload.followUpSuggestedQuestions` 存在（数组，可空），ASR→LLM→TTS 顺序不被破坏
- [ ] AC3：`POST /api/v1/device/voice-chat` 成功响应包含 `followUpSuggestedQuestions: string[]`（开关关或未生成时为 `[]`）
- [ ] AC4：动态建议使用独立二次 LLM 调用；主对话请求的 `messages` 不包含建议生成指令
- [ ] AC5：动态建议不落库为会话消息、不进入下一轮 history / agent memory
- [ ] AC6：生成失败/超时/解析失败时返回 `[]`，主回答仍成功
- [ ] AC7：静态开场白建议问题能力保持可用，配置 API 兼容
- [ ] AC8：自动化测试覆盖生成服务与至少一条通道集成契约
- [ ] AC9：第三方会话机器人后端的智能体在任意通道均不触发动态建议二次 LLM
- [ ] AC10：开关默认 `false`；对话设置可改并可发布到 runtime_config

## Out of Scope

- 不做建议问题 TTS 播报
- 不强制 ground 到知识库 chunk
- 第三方机器人路径不实现本功能
- 不做独立模型选择、条数配置、自定义 prompt（V1）
- 不改造 ASR VAD / 指令命中主逻辑（仅挂钩完成点）
- 不做设备原生 App UI（仅协议字段；网页调试 UI 必须做）

## Technical Notes (pointer)

详见同目录 `design.md` / `implement.md`。
