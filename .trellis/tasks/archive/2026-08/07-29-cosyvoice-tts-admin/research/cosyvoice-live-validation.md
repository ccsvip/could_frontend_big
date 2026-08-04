# CosyVoice v3.5-plus：不改动资源的连通性验证研究

**范围。** 本文只研究如何使用服务器保存的凭据验证北京地域 CosyVoice 集成；没有读取、复制、输出或调用任何实际 API Key，也没有向阿里云发出请求。除明确标为“本仓库观察”或“推断”的段落外，API 结论均来自阿里云百炼（Model Studio）一手文档。研究日期：2026-07-29。

## 结论

**推荐的最小、非变更性 live check 是只完成 WebSocket 握手后立即关闭连接：**

1. 仅使用已加密保存的 API Key 在服务端内存中构造 `Authorization: Bearer <key>`；不得记录该头、异常对象中包含的请求头或 Key。
2. 只连接北京端点 `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`。
3. 成功升级为 WebSocket 即记录“WSS endpoint + TLS/network + API Key authentication succeeded”，随后立即关闭；**不发送任何 WebSocket message**，尤其不发送 `run-task`、`continue-task` 或 `finish-task`。
4. 只向超管返回脱敏的结果类别（成功、网络/TLS/DNS、401/403 鉴权、其他握手失败），不返回请求头、Key、完整上游响应或连接 URL 中的业务空间标识。

这是唯一能同时验证网络、北京 WSS 服务端点和凭据鉴权、而不发起 TTS 任务的有文档依据的检查。阿里云明确说明 `Authorization` 在 WebSocket **握手阶段**验证，缺失或无效 Key 使握手以 HTTP 401/403 失败；并将 `run-task` 定义为“建立连接后立即发送”以启动任务。[WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api) [客户端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-client-events)

**边界：** 握手成功并不证明 `cosyvoice-v3.5-plus` 有可用权限，也不证明某个音色可合成；它只证明 endpoint、到达路径及 API Key 在握手鉴权上可用。这是上面“不调用模型、不生成音频”的直接代价。[推断：文档将鉴权限定在握手，而模型和音色参数在后续 `run-task` 中提交。]

如必须同时验证 HTTPS 定制服务，使用下文的 `list_voice` 作为**次选**检查。它不会创建、更新或删除音色，但官方响应为 CosyVoice 报告 `usage.count: 1`，且会返回音色元数据；因此它不是零副作用或零成本保证，不能取代最小 WSS 握手。

## 官方协议事实

### 北京端点、认证和地域隔离

| 能力 | 官方北京端点 | 必要认证 | 依据 |
| --- | --- | --- | --- |
| 实时 CosyVoice WebSocket | `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference` | 握手头 `Authorization: Bearer <API Key>` | [WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api) |
| 声音复刻 / 声音设计 / 查询 | `POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization` | `Authorization: Bearer <API Key>`；`Content-Type: application/json` | [声音复刻 HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api)、[声音设计 HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references) |

官方同时列出新加坡端点，但本任务要求北京专用。因此验证程序必须只允许上述两个 `cn-beijing.maas.aliyuncs.com` 精确端点；不能因“官方也支持新加坡”而放宽为跨地域 host。阿里云通用文档也说明不同地域的 endpoint 和 API Key 不通用。[WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api) [什么是阿里云百炼](https://help.aliyun.com/zh/model-studio/what-is-model-studio)

API Key 是 bearer credential：阿里云警告任何获得 Key 的人都能以该身份发起请求并产生费用，且明文仅在创建时显示一次。因此检查实现不得把 Key 放入日志、API 响应、异常详情、测试 fixture、任务文件或浏览器端。[获取 API Key](https://help.aliyun.com/zh/model-studio/get-api-key)

### 实时 TTS 不存在“ping”业务事件

官方 WebSocket 文档描述的业务序列是：连接 → `run-task` → `task-started` → 一个或多个 `continue-task` → `finish-task` → `task-finished`。`run-task` 负责启动语音合成任务，`continue-task` 发送待合成文本；后者才产生音频流和字符用量。官方客户端事件只列出这三个客户端事件，没有单独的“health”、“ping”或“validate credentials”业务消息。[WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api) [客户端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-client-events) [服务端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-server-events)

因此：

- **握手、立即关闭**：没有发送任务启动事件，因而是推荐的非 TTS 验证。
- **发送 `run-task` 后再用 `finish-task`/`directive: cancel`**：不生成文本音频的风险较低，但已经启动一个任务；不属于最小检查。北京的 CosyVoice v2 及以上才支持 `directive: cancel`，不可把取消当成“从未创建任务”。[客户端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-client-events)
- **发送任意 `continue-task`**：明确请求合成文本，服务端会返回音频及字符用量；不适合连通性检查。[WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api) [服务端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-server-events)

## 次选：非变更的 HTTPS 定制服务验证

官方对 `voice-enrollment`（CosyVoice）定义了同一 HTTPS endpoint 上的四类操作：`create_voice`、`list_voice`、`query_voice` 和 `delete_voice`；声音复刻还定义 `update_voice`。其中 **`list_voice` 和 `query_voice` 是读取操作**，不会创建、更新或删除音色。[声音复刻 HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api) [声音设计 HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references)

### 建议请求（仅在确实需要验证 HTTPS 时）

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "list_voice",
    "page_size": 1,
    "page_index": 0
  }
}
```

以保存的 Key 仅在服务器内存中放入 `Authorization: Bearer <key>`，并向配置的北京 HTTPS endpoint `POST` 以上 body。`list_voice` 不需要已知音色 ID，因此即使没有本地自定义音色也可用于认证与 endpoint 检查。官方文档允许可选 `prefix` 过滤；若应用确有一个**非秘密、仅本集成产生的固定前缀**，可加上它以缩小返回范围。不要把用户输入的前缀带入检查请求。

**成功判据：** HTTP 成功响应且 body 为预期对象并包含 `output.voice_list`。只保留“成功 / 上游 HTTP 状态 / request_id（如本项目的隐私与日志规则允许）”；不要持久化或把 `voice_list` 返回给浏览器。该列表包含 `voice_id`、状态、创建/修改时间，声音设计列表还可能带声音描述和预览文本。[声音复刻 HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api) [声音设计 HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references)

若已有本地、由本集成拥有的 CosyVoice voice ID，需要确认特定音色是否仍可用时，可改用：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "query_voice",
    "voice_id": "<local CosyVoice voice id>"
  }
}
```

这是已文档化的只读操作；返回 `status` 可为 `DEPLOYING`、`OK` 或 `UNDEPLOYED`。仅 `OK` 表示审核通过、可正常使用。请求体中的 ID 必须只来自该集成自己的本地 CosyVoice profile，不能接受任意用户提交的 upstream ID。[声音复刻 HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api)

### HTTPS 检查的风险和限制

| 检查 | 资源变更 | 已知风险 / 限制 | 适用性 |
| --- | --- | --- | --- |
| 只握手 WSS 后关闭 | 无任务、无音频、无音色变更 | 不证明模型或音色可合成 | **默认推荐** |
| `list_voice`, `page_size: 1` | 无 create/update/delete | 官方 CosyVoice 示例仍给出 `usage.count: 1`；可能留下用量/审计记录；响应含音色元数据 | 仅在需验证 HTTPS 时使用 |
| `query_voice` | 无 create/update/delete | 同样有用量/审计与元数据风险；依赖已存在且本集成拥有的 ID | 检查既有音色状态时使用 |
| `run-task` + cancel | 无音色变更 | 已启动 TTS task；不能证明零计费/零审计 | 不推荐作连通性检查 |
| 任意 `continue-task` | 无音色变更 | 产生 TTS 音频和字符用量 | 禁止用于此检查 |
| `create_voice` / `update_voice` / `delete_voice` | **改变远端音色** | 违反本任务的非变更要求 | 禁止 |

“`list_voice`/`query_voice` 不改变音色”是由其与官方独立列出的创建、更新、删除 action 的语义区分得出；“可能留下审计记录”是通用操作风险，不是阿里云在这些页面中的明确承诺。**[推断]** 因此不得声称这些 HTTP reads 无成本，尤其是官方示例对 CosyVoice list 的 `usage.count` 为 1。

## 与当前仓库实现的兼容性观察（不改动代码）

以下是本次在本仓库中读取到的事实，不是 Alibaba 文档结论。

1. `backend/apps/ai_models/services/cosyvoice.py` 将 WSS 和 customization URL 精确限制为北京 host/path，符合上表的北京 endpoint；`CosyVoiceSettings` 的 key 经加密字段读取。[本仓库观察]
2. `backend/apps/ai_models/services/tts.py` 用 `Authorization: Bearer …` 建立连接，符合官方握手认证要求；但随后发送的是 `type: "session.update"`、`input_text_buffer.append`、`input_text_buffer.commit`、`session.finished` 这一套事件。[本仓库观察]
3. 当前官方 CosyVoice 文档要求的是 `header.action: "run-task"`（含 `task_id`、`streaming: "duplex"` 和 audio/tts payload），再使用 `continue-task` 和 `finish-task`。这与上述仓库事件形状不同。**[推断：在未改为官方协议前，成功 WSS 握手不能证明本仓库的完整 TTS runtime 可工作；不得把握手 check 标作“试听成功”。]** [客户端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-client-events)
4. 当前服务从创建响应读取 `output.voice`，并在删除时发送 `input.voice`；当前官方 CosyVoice `voice-enrollment` 文档的 create/query/list/delete 字段则为 `voice_id`（`input.voice_id`，创建返回 `output.voice_id`）。**[推断：该字段差异会阻断或错误地管理 CosyVoice 音色，需在单独的实现修正中对照官方文档处理。]** [声音复刻 HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api) [声音设计 HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references)
5. 当前声音设计请求传入 `language_hints` 字符串；官方 CosyVoice 声音设计定义它为数组，且仅处理第一个元素。**[推断：应发送如 `["zh"]`，而非裸字符串。]** [声音设计 HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references)

这些观察说明应把验证结果拆开报告：

- **“WSS handshake verified”**：只代表配置的 WSS endpoint 与 Key；
- **“Customization read verified”**：只代表 HTTPS endpoint、Key 和只读 voice-management action；
- **“End-to-end CosyVoice synthesis verified”**：只有在协议与字段差异修正后，以一个经批准的受控 TTS 调用才能声明，且那不再是本研究要求的非变更检查。

## 建议的安全实现边界

- 检查仅能由超管触发；从服务端的 `CosyVoiceSettings` 解密 API Key，绝不接受浏览器传来的 Key。
- 不把解密值、`Authorization`、上游请求对象、WebSocket URL、音色列表、音色 ID 或完整 exception 序列化回响应/日志。对上游错误只分类为 `authentication`（401/403 handshake）、`network_or_tls`、`timeout` 或 `upstream`。
- 将超时设为有限值，确保连接在验证成功或失败后关闭。连接成功后不发送任何 text/binary frame。
- HTTPS read 必须使用固定的 `voice-enrollment` 与 `list_voice`/`query_voice` body；禁止前端覆盖 model、action、host、voice ID 或 headers。
- 验证前后不创建、删除、更新本地记录，不创建、删除或更新远端音色，不发音频文本，不保存上游音色数据。

## 来源

1. 阿里云百炼，[Qwen-Audio-TTS/CosyVoice WebSocket API 参考](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api)（北京 WSS、握手认证、交互顺序）。
2. 阿里云百炼，[客户端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-client-events)（`run-task`、`continue-task`、`finish-task` 与取消限制）。
3. 阿里云百炼，[服务端事件](https://help.aliyun.com/zh/model-studio/cosyvoice-server-events)（task 状态、音频/字符用量事件）。
4. 阿里云百炼，[声音复刻 HTTP API 参考](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api)（CosyVoice `voice-enrollment` 的 create/list/query/update/delete、字段与状态）。
5. 阿里云百炼，[声音设计 HTTP API 参考](https://help.aliyun.com/zh/model-studio/voice-design-api-references)（北京 customization endpoint、CosyVoice read actions 与字段）。
6. 阿里云百炼，[获取 API Key](https://help.aliyun.com/zh/model-studio/get-api-key)（Key 保管、权限与费用风险）。
7. 阿里云百炼，[什么是阿里云百炼](https://help.aliyun.com/zh/model-studio/what-is-model-studio)（地域 endpoint / API Key 不通用）。
