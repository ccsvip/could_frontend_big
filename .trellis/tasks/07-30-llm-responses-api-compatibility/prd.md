# LLM Responses API 兼容

## Goal

平台管理员可在每个标准 LLM 供应商中选择 OpenAI 兼容协议：既有 Chat Completions 或新版 Responses API。选择后，平台的上游调用遵循所选协议，且既有供应商继续工作。

## Confirmed Facts

- `/settings/llm/providers/` 管理平台标准 LLM 供应商；`LLMProvider` 当前只有供应商标签、基础 URL 和密钥，没有协议字段。
- 管理页的供应商表单未暴露 `providerType`；新供应商由 API 默认写为 `openai`。
- `llm_services.py` 的普通、流式、工具流式和测速调用均将地址归一为 `/chat/completions`，并按 `choices` 结构解析响应。
- `test_llm_model_usage.py:252-260` 断言测速请求为 Chat Completions URL 和请求体。

## Requirements

1. 为标准 LLM 供应商持久化协议选择，管理 API 和 `/settings/llm` 管理页可读写与展示该选择。
2. 已有供应商迁移为 Chat Completions，保证不变更现有行为。
3. 当供应商选择 Chat Completions 时，沿用现有 URL、请求体与响应解析。
4. 当供应商选择 Responses API 时，调用 `/responses`，构造 Responses 协议请求并解析普通与 SSE 流式响应。
5. 协议选择由供应商决定，供应商下的全部模型使用相同上游协议。
6. 不创建新的业务 HTTP 或 WebSocket 入口。
7. Responses 模式必须保留函数工具调用和联网搜索能力；调用方继续接收既有的文本增量与工具调用事件契约。

## Acceptance Criteria

- [ ] 管理员创建、编辑并重新加载供应商后，能看到并修改“Chat Completions / Responses API”协议选择。
- [ ] 已有供应商默认采用 Chat Completions，现有聊天与测速契约不变。
- [ ] Responses 供应商的普通聊天、流式聊天与测速请求发至 `/responses`，并能从 Responses 返回值取得文本。
- [ ] Responses 模式把现有 OpenAI Chat Completions 函数工具定义、工具调用流事件和联网搜索设置转换为对应的 Responses 请求与事件；资源控制命令继续可执行。
- [ ] 相关后端测试覆盖两个协议的 URL、请求体、文本/工具调用解析与失败路径；前端构建通过。

## Key Decision

Responses 模式完整兼容现有平台 LLM 能力：普通与流式聊天、函数工具调用、联网搜索、测速，以及聊天页面的标题和摘要生成。

## Out of Scope

- 改造第三方机器人集成。
- 自动探测供应商支持的协议。
- 改变现有租户授权、模型选择或实时传输入口。
