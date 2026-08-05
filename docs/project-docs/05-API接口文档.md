# 05 — API 接口文档

本章涵盖 REST API 端点、统一响应包络、鉴权机制、WebSocket 协议。OpenAPI Schema 可通过 `/api/schema/` 获取，Swagger UI 在 `/api/docs/`，ReDoc 在 `/api/redoc/`。

## 5.1 通用约定

### 5.1.1 基础前缀

所有业务 API 挂载在 `/api/v1/` 下。账号认证模块额外挂载在 `/api/v1/auth/` 子前缀。`ApiV1RootView`（`GET /api/v1/`）列出主要端点。

### 5.1.2 鉴权

| 客户端 | 方式 | 说明 |
|--------|------|------|
| Web SPA | `Authorization: Bearer <access_token>` | JWT，access 30min / refresh 7d |
| Android 设备 | `X-Device-Code: <deviceCode>` | 设备码认证，无需 JWT |
| WebSocket | payload 内 `token` 或 query param | 按 command 解析租户/设备 |

CORS 允许头含 `x-device-code` / `x-request-id` / `x-trace-id`；暴露头含 `x-request-id` / `x-trace-id` / `x-audio-source-format` / `x-audio-sample-rate` / `x-audio-channels` / `x-tts-voice`。

### 5.1.3 统一响应包络

成功：DRF view 直接返回业务数据。

失败：`config/exceptions.py` 统一转为：

```json
{
  "status": "error",
  "message": "错误信息",
  "code": 400,
  "data": null
}
```

字段验证错误：`message` 为分号拼接的字段错误；`data` 可选携带 `response_data`。数据库完整性错误与 Django ValidationError 同样走该包络。

### 5.1.4 分页与命名

- 分页：`StandardPageNumberPagination`，`PAGE_SIZE=10`，DATETIME 格式 `%Y-%m-%d %H:%M:%S`。
- 字段命名：前端契约 `camelCase`，后端模型 `snake_case`，由 Serializer 映射。

## 5.2 REST API 端点清单

> 说明：DRF `ModelViewSet` 默认提供标准 6 方法（GET 列表 / POST 创建 / GET 详情 / PUT 全量 / PATCH 局部 / DELETE 删除），下表仅额外列出 `@action` 与 `APIView` 端点。

### 5.2.1 账号认证（`/api/v1/auth/`）

| 路径 | 方法 | 用途 | 权限 |
|------|------|------|------|
| `/auth/login/` | POST | JWT 登录（写入 `tenant_id` claim） | AllowAny |
| `/auth/refresh/` | POST | JWT 刷新 | — |
| `/auth/me/` | GET | 当前用户 + 菜单 + 权限 + 角色 | IsAuthenticated |
| `/auth/change-password/` | POST | 修改密码，清除 `must_change_password` | IsAuthenticated |
| `/auth/account-applications/` | POST | 公开提交账号申请（手机号唯一） | AllowAny |
| `/auth/account-applications/manage/` | GET | 申请列表 | CanViewAccountApplications |
| `/auth/account-applications/manage/{pk}/` | GET / PATCH | 申请详情 / 审核 | CanReviewAccountApplications |

### 5.2.2 租户与员工（`/api/v1/`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/tenants/` | 全套 CRUD | 平台超管：公司 CRUD |
| `/tenants/{id}/menus/` | GET / PUT | 读/写该公司 menuIds + permissionPointIds |
| `/menus/catalog/` | GET | 可分配菜单目录 + 权限点 |
| `/employees/` | GET/POST/PATCH | 公司管理员：员工 CRUD |
| `/employees/{id}/reset-password/` | POST | 重置员工密码 + 置 `must_change_password` |
| `/roles/` | 全套 CRUD | 租户级角色 CRUD（钳制本公司） |
| `/my-tenant/catalog/` | GET | 本公司视角可分配目录 |

### 5.2.3 设备（`/api/v1/`，`lookup_field='code'`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/devices/` | GET/POST | 设备列表/创建 |
| `/devices/{code}/` | GET/PATCH/PUT/DELETE | 设备详情（按 code） |
| `/devices/stats/` | GET | 设备统计 |
| `/devices/chat-logs/` | GET | 设备对话日志 |
| `/devices/logs/` | GET | 设备授权日志 |
| `/devices/authorizations/` | GET | 设备授权请求列表 |
| `/devices/{code}/deletion-impact/` | GET | 删除前影响评估 |
| `/devices/{code}/bind/` | POST | 绑定设备（应用/分组/授权） |
| `/devices/{code}/ignore/` | POST | 忽略授权请求 |
| `/devices/{code}/name/` | PATCH | 仅修改设备名称 |
| `/devices/{code}/authorize/` | POST | 再次授权 |
| `/devices/{code}/revoke/` | POST | 撤销授权 |
| `/device-groups/` | 全套 CRUD | 设备分组 |
| `/device-applications/` | 全套 CRUD | 设备应用 |
| `/device-authorization-codes/` | 全套 CRUD | 设备授权码 |
| `/device-authorization-requests/` | 全套 CRUD | 设备授权请求 |
| `/wake-words/` | 全套 CRUD | 唤醒词 |
| `/device-chat-sessions/` | GET / DELETE | 设备对话会话（按 `?deviceCode=` 过滤） |
| `/device-auth/activate/` | POST | 安卓激活（AllowAny） |
| `/device-runtime/config/` | GET | 设备运行时配置（`?deviceCode=`） |
| `/device-runtime/resources/` | POST | 设备运行时资源包 |
| `/device-runtime/heartbeat/` | POST | 兼容旧端心跳 |
| `/device/voice-chat/` | POST | 设备语音聊天入口 |

### 5.2.4 AI 模型与会话 — 平台超管（`/api/v1/settings/`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/settings/llm/providers/` | 全套 CRUD | LLM 供应商 |
| `/settings/llm/providers/{provider_id}/models/` | GET / POST | 供应商下模型 |
| `/settings/llm/models/` | 全套 CRUD | LLM 模型，含 `{id}/test/` POST 测速 |
| `/settings/llm/test-settings/` | GET / PATCH | LLM 测速参数单例 |
| `/settings/llm/tenants/{tenant_id}/authorization/` | GET / PUT | 公司 LLM 模型授权 |
| `/settings/third-party-chatbots/providers/` | 全套 CRUD | 第三方机器人供应商 |
| `/settings/third-party-chatbots/applications/` | 全套 CRUD | 第三方机器人应用 |
| `/settings/third-party-chatbots/integrations/` | 全套 CRUD | 第三方机器人方案实例（A/B） |
| `/settings/third-party-chatbots/tenants/{tenant_id}/authorization/` | GET / PUT | 公司第三方机器人授权 |
| `/settings/asr/` | GET / PATCH | ASR 全局配置 |
| `/settings/asr/test/` | POST | ASR 配置测试 |
| `/settings/tts/providers/` | GET | TTS 供应商列表 |
| `/settings/tts/providers/{provider_code}/` | GET / PATCH | 单供应商详情 |
| `/settings/tts/providers/{provider_code}/test/` | POST | TTS 配置测试 |
| `/settings/tts/cosyvoice/` | GET / PATCH | CosyVoice 设置 |
| `/settings/tts/cosyvoice/test/` | POST | CosyVoice 测试 |
| `/settings/tts/cosyvoice/voices/enroll/` | POST | 音色复刻 |
| `/settings/tts/cosyvoice/voices/design/` | POST | 音色设计 |
| `/settings/tts/cosyvoice/voices/{voice_id}/` | PATCH / DELETE | CosyVoice 音色详情 |
| `/settings/tts/tenants/{tenant_id}/card-authorizations/` | GET / PUT | 公司 TTS 卡片授权 |
| `/settings/knowledge-base/models/` | GET / PATCH | 平台知识库模型设置 |
| `/settings/knowledge-base/tenants/{tenant_id}/authorization/` | GET / PUT | 公司知识库模型授权 |

### 5.2.5 AI 模型与会话 — 公司业务（`/api/v1/ai-models/`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/ai-models/llm/options/` | GET | 公司可用 LLM 选项 |
| `/ai-models/llm/default-model/` | GET / PATCH | 公司默认 LLM 模型 |
| `/ai-models/llm/models/{model_id}/test/` | POST | 公司 LLM 测试 |
| `/ai-models/third-party-chatbots/options/` | GET | 公司可用第三方机器人选项 |
| `/ai-models/tts/options/` | GET | 公司可用 TTS 选项 |
| `/ai-models/tts/default-voice/` | GET / PATCH | 公司默认音色 |
| `/ai-models/tts/test/` | POST | 公司 TTS 测试 |
| `/ai-models/tts/runtime/` | POST | TTS 运行时（设备侧） |
| `/ai-models/asr/status/` | GET | ASR 状态 |
| `/ai-models/asr/config/` | GET | ASR 配置 |
| `/ai-models/asr/filler-words/` | GET / PATCH | 公司 ASR 语气词词表 |
| `/ai-models/asr/runtime-settings/` | GET / PATCH | 公司 ASR 运行时设置 |
| `/ai-models/asr/device-status/` | GET | 设备 ASR 状态（`X-Device-Code`） |
| `/ai-models/asr/test/` | POST | ASR 测试 |
| `/ai-models/asr/replacement-rules/` | 全套 CRUD | ASR 替换规则 |
| `/ai-models/applications/` | 全套 CRUD | Agent Application（智能体） |
| `/ai-models/applications/{id}/conversations/` | POST | 为智能体创建会话 |
| `/ai-models/applications/{id}/web-conversation-history/` | DELETE | 清空 web 端历史 |
| `/ai-models/applications/{id}/publish/` | POST | 发布智能体配置 |
| `/ai-models/applications/{id}/annotations/` | GET / POST | 智能体标注 |
| `/ai-models/applications/{id}/annotations/from-message/` | POST | 从消息创建标注 |
| `/ai-models/applications/{id}/annotations/{annotation_id}/` | PATCH / DELETE | 单标注 |
| `/ai-models/applications/{id}/stats/` | GET | 智能体统计 |
| `/ai-models/chat/conversations/` | 全套 CRUD | 聊天会话 |
| `/ai-models/chat/conversations/{id}/update-title/` | PATCH | 修改会话标题 |
| `/ai-models/chat/conversations/{id}/update-config/` | PATCH | 修改会话配置 |
| `/ai-models/chat/conversations/{id}/messages/{message_id}/feedback/` | PATCH | 消息反馈 |
| `/ai-models/chat/conversations/{id}/send/` | POST | 发送消息（SSE 流式） |

### 5.2.6 资源与指令（`/api/v1/`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/resources/images/` | 全套 CRUD | 图片资源 |
| `/resources/images/bulk/` | POST | 批量创建 |
| `/resources/videos/` | 全套 CRUD | 视频资源 |
| `/resources/scrolling-texts/` | 全套 CRUD | 滚动文本 |
| `/resources/scrolling-texts/{id}/content/` | GET / POST | 滚动文本内容 |
| `/resources/voice-tones/` | 全套 CRUD | 音色 |
| `/resources/models/` | 全套 CRUD | 模型资产 |
| `/commands/groups/` | 全套 CRUD | 指令分组 |
| `/commands/control/` | 全套 CRUD | 控制指令 |
| `/commands/tasks/` | 全套 CRUD | 任务指令 |
| `/commands/points/` | 全套 CRUD | 点位 |
| `/commands/data/` | GET | 指令数据查询 |
| `/commands/control-recognition-policy/` | GET / PATCH / DELETE | 控制指令识别策略 |
| `/commands/export/enabled-groups/` | GET | 导出已启用分组 |
| `/commands/export/commands/` | GET | 导出指令 |
| `/settings/minio/` | GET / PATCH | MinIO 配置单例 |
| `/settings/minio/quotas/` | GET / PATCH | 公司视频额度 |
| `/resources/upload-config/` | GET | 上传配置 |
| `/resources/presign/` | POST | 上传预签名 |
| `/resources/videos/upload-config/` | GET | 视频上传配置 |
| `/resources/videos/presign/` | POST | 视频上传预签名 |

### 5.2.7 知识库（`/api/v1/`）

注意：`knowledge-bases`（复数）是知识库 ViewSet，`knowledge-base`（单数）是文档 ViewSet。

| 路径 | 方法 | 用途 |
|------|------|------|
| `/knowledge-bases/` | 全套 CRUD | 知识库 |
| `/knowledge-bases/{id}/documents/` | GET / POST | 知识库下文档列表/上传 |
| `/knowledge-bases/{id}/recall-test/` | POST | 召回测试 |
| `/knowledge-bases/{id}/media-assets/` | GET / POST | 配套素材 |
| `/knowledge-bases/{id}/media-assets/{asset_id}/` | PATCH / DELETE | 单素材 |
| `/knowledge-bases/{id}/index/` | POST | 触发知识库索引 |
| `/knowledge-base/` | 全套 CRUD | 知识文档 |
| `/knowledge-base/{id}/download/` | GET | 单文件下载（FileResponse，二进制） |
| `/knowledge-base/bulk-download/` | POST | 批量 ZIP 下载（≤20 个 / ≤200MB，二进制） |
| `/knowledge-base/{id}/index/` | POST | 触发文档索引 |
| `/knowledge-base/{id}/chunks/` | GET | 文档分块列表 |
| `/knowledge-base/{id}/chunks/{chunk_id}/` | PATCH | 修改分块 |

> 知识库下载是统一响应包络的例外，返回原生二进制流。

### 5.2.8 审计、应用更新、错误码（`/api/v1/`）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/audit/logs/` | GET | 操作日志列表（ReadOnly） |
| `/audit/logs/{id}/` | GET | 单条日志 |
| `/audit/logs/clear/` | DELETE | 清空日志（需 CanClearAuditLogs） |
| `/app-update-releases/` | 全套 CRUD | 应用发布（`lookup_field='release_id'`） |
| `/app-update-releases/threshold/` | GET / PATCH | 强制升级阈值 |
| `/app-update-releases/{release_id}/apk/` | GET | APK 文件下载 |
| `/app-updates/check/` | POST | 客户端检查更新 |
| `/app-updates/report/` | POST | 客户端上报升级事件 |
| `/error-codes/` | GET | 错误码列表（`?keyword=` / `?category=`，需 IsSuperUser） |
| `/error-codes/{code}/` | GET | 单个错误码详情 |

## 5.3 WebSocket 协议

### 5.3.1 连接

单一入口：`ws(s)://<host>/ws/realtime/`。所有命令通过 JSON 文本帧的 `type` 字段路由，音频通过二进制帧传输。

### 5.3.2 消息格式

请求帧：

```json
{ "type": "<command>", "id": "<commandId>", "payload": { ... } }
```

响应帧：

```json
{ "type": "<eventType>", "id": "<commandId>", "payload": { ... } }
```

错误帧：

```json
{ "type": "asr.error", "id": "<commandId>",
  "error": { "code": "ASR_UPSTREAM_ERROR", "message": "..." },
  "requestId": "...", "traceId": "..." }
```

### 5.3.3 命令清单

| 客户端 type | 服务端响应 type | 用途 |
|-------------|-----------------|------|
| `ping` | `pong` | 心跳 |
| `devices.events.subscribe` | `devices.events.subscribed` / `devices.event` | 订阅公司设备事件 |
| `devices.events.unsubscribe` | `devices.events.unsubscribed` | 取消订阅 |
| `device.runtime_config.subscribe` | `device.runtime_config.subscribed`（完整配置） | 订阅设备运行时配置 |
| `device.runtime_config.unsubscribe` | `device.runtime_config.unsubscribed` | 取消订阅 |
| `device.status.start` | `device.status.started` / `device.status` | 设备上线 |
| `device.status.ping` | `device.status.pong` | 设备心跳 |
| `device.voice.bind` | `device.voice.bound` + `device.voice_configuration.changed` | 绑定设备音色 |
| `asr.session.start` | `asr.ready` / `asr.transcript` / `asr.input_stopped` / `asr.done` | ASR 会话 |
| `asr.session.finish` | — | 触发 ASR 收尾 |
| `asr.session.cancel` | `asr.cancelled` | 取消 ASR |
| `tts.session.start` | `tts.segment_start` / `tts.segment` / `tts.done` | TTS 会话 |
| `tts.session.cancel` | `tts.cancelled` | 取消 TTS |
| `llm.session.start` | `llm.started` / `llm.delta` / `llm.tts_segment` / `llm.done` | LLM 会话 |
| `llm.session.cancel` | `llm.cancelled` | 取消 LLM |
| `agent.session.start` | `agent.started` / `asr.*` / `llm.*` / `tts.*` / `agent.done` | Agent 综合管线 |
| `agent.session.finish` | — | 触发 ASR→LLM 收尾 |
| `agent.session.cancel` | `agent.cancelled` | 取消 Agent |

未知命令返回 `error` + `REALTIME_UNKNOWN_COMMAND`。

### 5.3.4 错误码

错误码定义在 `apps/error_codes/catalogue.py`，共 35 条（1001–1035），按 category 分组：设备运行时（1001–1009）、实时协议（1010–1018）、ASR（1019–1022）、TTS（1023–1027）、LLM（1028–1032）、智能体（1033–1034）、内部错误（1035）。常见错误码：`REALTIME_UNAUTHORIZED`、`ASR_NOT_READY`、`ASR_UPSTREAM_ERROR`、`TTS_VOICE_NOT_AVAILABLE`、`LLM_UPSTREAM_ERROR`、`DEVICE_AGENT_UNBOUND`、`REALTIME_UNKNOWN_COMMAND`、`INTERNAL_ERROR`。

### 5.3.5 运行时配置事件

`device.runtime_config.subscribed` 始终推送**完整**配置（即使仅音色变更），包含：设备基础信息、绑定应用资源、智能体运行时配置、当前 TTS 音色 + 播放控制、唤醒词、控制指令、点位、滚动字幕。事件 `action` 字段取值：`initial` / `wakeWordsChanged` / `voiceConfigurationChanged` / `scrollingTextsChanged` / `runtimeAvailabilityChanged`。

## 5.4 API 文档工具

- Swagger UI：`/api/docs/`
- ReDoc：`/api/redoc/`
- OpenAPI Schema：`/api/schema/`
- Browsable API：`/api/v1/`（`ApiV1RootView` 列出主要端点）

Schema 由 drf-spectacular 生成，含 `BearerAuth` 安全方案，支持 `deepLinking` / `persistAuthorization` / `filter`。
