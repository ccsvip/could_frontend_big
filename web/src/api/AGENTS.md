[web](../../AGENTS.md) > src > **api**

# web/src/api AGENTS.md

## OVERVIEW

axios 客户端 + 11 个领域模块。`client.ts` 注入 Bearer / 401 拦截 / dev 媒体地址改写；模块文件薄薄一层包装，不存业务状态。

## STRUCTURE

```
api/
├── client.ts                # httpClient 单例 + ApiResponse 类型 + 401 拦截
└── modules/
    ├── auth.ts              # /auth/login, /me, /change-password, account-applications
    ├── chat.ts              # /ai-models/chat/conversations/* + SSE 解析
    ├── commands.ts          # /commands/groups,control,tasks,export,import
    ├── devices.ts           # /devices/, /devices/stats/
    ├── knowledge-base.ts    # /knowledge-base + 独立 axios 下载 helper
    ├── llm-providers.ts     # /ai-models/llm-providers/*
    ├── models.ts            # /resources/models/
    ├── point-management.ts  # /commands/points/
    ├── resources.ts         # /resources/images, /resources/videos
    ├── scrolling-texts.ts   # /resources/scrolling-texts/
    └── voice-tones.ts       # /resources/voice-tones/
```

## CONVENTIONS

- **唯一 axios 实例** = `httpClient`，`baseURL = VITE_API_BASE_URL || '/api/v1'`，`timeout = 10000`。
- **响应解析**：服务端统一 envelope `{status, message, data}`；模块函数应返回 `data` 而非整包，错误由全局拦截器 `message.error()`，调用方仅处理业务分支。
- **401**：拦截器自动 `clearAuth()` + 跳 `/login`，模块内**不要**重复处理。
- **流式接口** (`chat.ts` 的 send)：用 `fetch` + `ReadableStream` 解析 SSE；事件行**必须**同时兼容 `data:{...}` 与 `data: {...}`（冒号后 0/1 个空格）。
- **下载** (`knowledge-base.ts`)：独立 axios 实例，处理 Blob 成功体 / Blob(JSON) 错误体 / `Content-Disposition` 文件名解析；**不要**复用 `httpClient` 拦截器。
- **大小写**：前端字段统一 camelCase，与后端 snake_case 在模块内做映射（如 `voice_code` ↔ `voiceCode`、`local_url` ↔ `localUrl`）。

## ANTI-PATTERNS

- ❌ 在模块内 `try/catch` 后再 `message.error`：会和拦截器双 toast。
- ❌ 用 `fetch` 替代 `httpClient`（除聊天 SSE 与 知识库下载这两个明确豁免点）。
- ❌ 把 `localUrl` / `effectiveUrl` 当成可写字段往后端 PATCH：后端运行时生成，前端只读。
- ❌ 复用 `httpClient` 实例去做 `responseType: 'blob'`：拦截器会把 JSON 错误体丢给业务，错误处理跑偏。

## NOTES

- `commands.ts` 最大（6.5KB），覆盖 5 个 sub-resource，写完务必跑一遍 `commands/groups` 与 `commands/control` 页面联调。
- `chat.ts` 流解析失败的常见原因：上游返回 200 + 普通 JSON（非 SSE），后端会兜底回退；前端**也**要兼容 `data:` 后空格可选格式。
- 添加新模块时，向 `client.ts` 之外的位置新建 axios 实例只在以下场景被允许：响应类型必须是 Blob 且与 JSON 错误体共存。
