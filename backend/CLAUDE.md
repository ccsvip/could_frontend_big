[根目录](../CLAUDE.md) > **backend**

# backend 模块 CLAUDE

## 模块职责

`backend/` 负责 Django API、JWT 认证、账号申请流程、设备管理、后台管理（SimpleUI）与异步任务（Celery）。

## 入口与启动

- Django 入口：`manage.py`（默认 `config.settings.dev`）
- URL 根：`config/urls.py`
- Celery 入口：`config/celery.py`
- settings：`config/settings/base.py`、`dev.py`、`prod.py`

## 对外接口

- 认证与账号：
  - `POST /api/v1/auth/login/`
  - `POST /api/v1/auth/refresh/`
  - `GET /api/v1/auth/me/`
  - `POST /api/v1/auth/change-password/`
  - `POST /api/v1/auth/account-applications/`
  - `GET /api/v1/auth/account-applications/manage/`（仅管理员）
  - `PATCH /api/v1/auth/account-applications/manage/<pk>/`（仅管理员）
- 设备：
  - `GET /api/v1/devices/`
  - `POST /api/v1/devices/`（仅管理员）
  - `GET /api/v1/devices/stats/`
- 音色：
  - `GET /api/v1/resources/voice-tones/`
  - `POST /api/v1/resources/voice-tones/`
  - `PATCH /api/v1/resources/voice-tones/<pk>/`
  - `DELETE /api/v1/resources/voice-tones/<pk>/`
- 模型：
  - `GET /api/v1/resources/models/`
  - `POST /api/v1/resources/models/`
  - `PATCH /api/v1/resources/models/<pk>/`
  - `DELETE /api/v1/resources/models/<pk>/`
- 控制指令：
  - `GET /api/v1/commands/control/`
  - `POST /api/v1/commands/control/`
  - `PATCH /api/v1/commands/control/<pk>/`
  - `DELETE /api/v1/commands/control/<pk>/`
  - `GET /api/v1/commands/control/export/`
  - `POST /api/v1/commands/control/import/`
- 知识库：
  - `GET /api/v1/knowledge-base/`
  - `GET /api/v1/knowledge-base/<pk>/`
  - `POST /api/v1/knowledge-base/`
  - `GET /api/v1/knowledge-base/<pk>/download/`
  - `POST /api/v1/knowledge-base/bulk-download/`
 - 聊天室：
  - `GET /api/v1/ai-models/chat/conversations/`
  - `POST /api/v1/ai-models/chat/conversations/`
  - `GET /api/v1/ai-models/chat/conversations/<pk>/`
  - `PATCH /api/v1/ai-models/chat/conversations/<pk>/update-title/`
  - `PATCH /api/v1/ai-models/chat/conversations/<pk>/update-config/`
  - `POST /api/v1/ai-models/chat/conversations/<pk>/send/`
 - 知识库（已批准约束，落地时必须保持）：
  - `GET /api/v1/knowledge-base/`
  - `GET /api/v1/knowledge-base/<pk>/`
  - `POST /api/v1/knowledge-base/`
  - `GET /api/v1/knowledge-base/<pk>/download/`
  - `POST /api/v1/knowledge-base/bulk-download/`

## 关键依赖与配置

- 依赖：Django、DRF、simplejwt、drf-spectacular、SimpleUI、Celery、Redis、PostgreSQL 驱动、Pillow
- 关键配置：
  - 数据库：`DATABASE_URL`
  - JWT：`JWT_ACCESS_MINUTES`、`JWT_REFRESH_DAYS`
  - Celery：`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
  - 静态资源：`STATIC_URL = '/static/'`、`STATIC_ROOT = BASE_DIR / 'staticfiles'`
- 配置文件：`requirements.txt`、`config/settings/*.py`
- compose 场景下 backend 启动前需执行 `python manage.py collectstatic --noinput`，否则 `/admin/` 与 `/api/docs/` 可能样式缺失。

## 数据模型

- `apps/accounts/models.py`
  - `AccountApplication(applicant_name, phone, email, reason, status, created_at, updated_at)`
- `apps/devices/models.py`
  - `Device(code, name, location, status, last_heartbeat, created_at, updated_at)`
- `apps/resources/models.py`
  - `Resource(name, resource_type, category, file, description, created_at, updated_at)`（Django admin 中明确显示为“资源（图片/视频）”）
  - `VoiceTone(name, voice_code, content[ASR结果], icon, audio, is_active, is_visible, created_at, updated_at)`
  - `ModelAsset(name[unique], model_type, orientation, thumbnail, model_file, model_size, cloud_url, is_visible, created_at, updated_at)`（Django admin 中明确显示为“模型管理”）
- 知识库（已批准约束，落地时建议为独立 app `apps/knowledge_base`，否则至少保持 `resources/knowledge_base` 子模块隔离）
  - `KnowledgeBaseDocument(title, file, file_name, file_extension, file_size, description, processing_status, processing_result, uploaded_by, download_count, created_at, updated_at)`
  - `processing_status` 固定为 `pending / processing / completed / failed`
  - 首版状态修改只能通过 Django admin 完成，不提供业务状态更新 API

## 测试与质量

- 当前已新增 `apps/resources/tests/test_voice_tone_api.py`，覆盖音色 CRUD、唯一标识、ASR 结果映射、图标/音频上传与清空、可见性字段行为。
- 当前已新增 `apps/resources/tests/test_model_asset_api.py` 与 `test_model_asset_access_data.py`，用于覆盖模型名称唯一、模型文件/云端地址约束、本地地址生成、权限控制与菜单权限回填。
- 当前已新增 `apps/resources/tests/test_admin_model_asset.py`，用于覆盖 Django admin 中“模型管理”入口与 `ModelAsset` 后台页的正确映射，避免与图片/视频资源后台串页。
- 知识库落地时需补充：
  1. `apps.knowledge_base.tests.test_access_data`（若采用 A）或 `apps.resources.knowledge_base.tests.test_access_data`（若采用 C），覆盖菜单/权限回填与无 `knowledge_base.manage`
  2. `apps.knowledge_base.tests.test_api`（若采用 A）或 `apps.resources.knowledge_base.tests.test_api`（若采用 C），覆盖 raw DRF CRUD、下载二进制/错误 envelope、zip 限制、served/attempted 计数与无状态更新业务 API
- 建议继续补充：
  1. 登录失败/成功、刷新、`/me` 权限测试
  2. 账号申请审核状态流转与自动建号测试
  3. 设备 CRUD 与 `stats` 缓存分支测试

## 常见问题 (FAQ)

- Q: compose 里 DB/Redis 主机应写什么？
  - A: 应使用容器服务名 `db`、`redis`，不要用 `localhost`。
- Q: Celery 不可用时接口会失败吗？
  - A: 任务触发处对 `OperationalError` 做了兜底，不阻断主流程。
- Q: 为什么标准 OpenAI 兼容模式有时“发消息后没回复”？
  - A: 某些兼容供应商在 `stream=true` 时仍然返回普通 JSON 完整响应而不是 SSE 分片；`apps/ai_models/views.py` 的聊天流式端点现在会优先解析 SSE，若检测到 200 + 普通 JSON，则回退读取 `choices[0].message.content` 并照常转成前端可消费的 SSE 片段。
- Q: 现在该看哪些日志排查聊天室问题？
  - A: 查看 `apps/ai_models/views.py` 输出的 `chat.send.*` 和 `chat.conversation.config_updated` 日志，重点看 `conversation_id`、`provider_id`、`model_name`、`api_url`、`status_code`、`content_type`、`completed_sse` / `completed_plain_json`、`timeout` / `exception`；日志不会打印 API Key 和完整用户消息正文。
- Q: LongCat 明明返回了流式 chunk，为什么本地还是没显示？
  - A: LongCat 的 SSE 事件行为 `data:{...}`，冒号后没有空格；如果解析器只认 `data: `，整段流会被静默跳过。`apps/ai_models/views.py` 现在已兼容 `data:` 后可选空格格式。
- Q: LongCat/OpenAI 兼容地址到底该填什么？
  - A: `apps/ai_models/views.py` 现在会统一规范化 `api_base_url`：支持填写 `https://api.longcat.chat/openai`、`https://api.longcat.chat/openai/v1` 或完整 `https://api.longcat.chat/openai/v1/chat/completions`，最终都会归一到正确的 chat completions 地址。
- Q: 关闭聊天室“流式回复”后会怎样？
  - A: 后端仍通过 `/send/` 返回 SSE 给前端，但上游请求会改成非流式，待完整回答返回后一次性推送到页面，便于和流式模式做对比排查。
- Q: 为什么明明上游按 chunk 返回，浏览器还是阻塞显示？
  - A: 在当前 `uvicorn + ASGI` 链路下，如果 `StreamingHttpResponse` 使用同步 generator，ASGI 适配层可能先把内容整体消费完再返回；`apps/ai_models/views.py` 现已改为 `httpx.AsyncClient` + 异步生成器，确保真正边到边流式输出。
- Q: 系统提示词现在是怎么参与请求的？
  - A: `ChatConversation.system_prompt` 会在 `apps/ai_models/views.py` 的 `send` 端点里被插入到上游 `messages` 历史最前面，作为 `system` 角色消息发送；前端右侧面板通过 `update-config` 持久化这个字段。
- Q: 对话标题现在会自动生成吗？
  - A: 会。如果会话标题仍是默认值“新对话”，`apps/ai_models/views.py` 会在首轮助手回复成功后，复用当前会话绑定的同一模型发起一次轻量标题生成请求，并把生成结果回写到 `ChatConversation.title`。
- Q: 右侧参数面板和重新生成现在怎么生效？
  - A: `temperature` 与 `max_tokens` 已存到 `ChatConversation` 并在 `send` 请求体里真实传给上游；`send` 还支持 `regenerateMessageId`，当前仅允许对最后一条助手消息进行重生成，后端会删除该条助手回复并复用前一条用户消息重新请求模型。
- Q: 知识库状态为什么不能通过普通业务 API 修改？
  - A: 这是首版硬边界。知识库状态维护完全留在 Django admin，仅 `staff/superuser` 可在 `/admin/` 修改 `processing_status` / `processing_result`；普通前端 API 不提供任何状态更新入口。
- Q: 知识库下载接口为什么不能复用 success envelope？
  - A: 单个下载和批量 zip 都必须返回真正的二进制响应；只有错误仍走 `backend/config/exceptions.py` 的 JSON envelope，这样前端下载 helper 才能正确区分 Blob 成功体与 Blob(JSON) 错误体。
- Q: 批量下载的 `download_count` 代表“真的下载完成”吗？
  - A: 不是。首版约定是 served/attempted 口径：zip 开始回传即视为已服务成功，对压缩包内实际包含的每个文档各 `+1`；被过滤掉的非法/重复/不存在 id 不计数。

## 相关文件清单

- `manage.py`
- `config/urls.py`
- `config/celery.py`
- `config/settings/base.py`
- `apps/accounts/models.py`
- `apps/accounts/serializers.py`
- `apps/accounts/views.py`
- `apps/accounts/urls.py`
- `apps/accounts/tasks.py`
- `apps/devices/models.py`
- `apps/devices/serializers.py`
- `apps/devices/views.py`
- `apps/devices/urls.py`
- `apps/devices/tasks.py`
- `apps/devices/management/commands/seed_devices.py`
- `apps/resources/models.py`
- `apps/resources/serializers.py`
- `apps/resources/views.py`
- `apps/resources/urls.py`
- `apps/resources/admin.py`
- `apps/knowledge_base/*`（方案 A）或 `apps/resources/knowledge_base/*`（方案 C，作为唯一 fallback）

## 变更记录 (Changelog)

- 2026-04-10T14:36:29+08:00：初始化模块文档，补充接口清单、配置要点、数据模型与测试缺口。
- 2026-04-13T15:50:00+08:00：补充音色管理接口、数据模型与音色 API 测试说明。
- 2026-04-13T18:04:58+08:00：同步音色模型为 ASR结果/图标/音频/前端可见结构，并补充 Pillow 依赖说明。
- 2026-04-14T12:18:00+08:00：新增模型管理接口与 `ModelAsset` 数据模型说明，记录模型 API / 迁移回填 / 测试覆盖范围。
- 2026-04-14T12:45:00+08:00：补充 Django admin 资源分组的命名与入口校验说明，区分“模型管理”与“资源（图片/视频）”。
- 2026-04-20T16:30:00+08:00：聊天室新增 `update-config` 接口以支持前端显式切换会话绑定模型；`send` 端点补充 OpenAI 兼容模式下 200 + 普通 JSON 完整响应的兜底解析，并新增聊天 API 测试覆盖模型切换与非 SSE 兼容响应场景。
- 2026-04-20T16:45:00+08:00：聊天室后端增加关键诊断日志，记录会话模型切换、最终请求 URL、HTTP 状态码、SSE/普通 JSON 命中路径及 timeout/exception，便于定位兼容供应商无回复问题且不泄露 API Key / 完整消息。
- 2026-04-20T16:55:00+08:00：聊天室后端 SSE 解析改为兼容 `data:{...}` 与 `data: {...}` 两种事件行格式，并新增对应测试，修复 LongCat 流式 chunk 被静默忽略的问题。
- 2026-04-20T17:10:00+08:00：聊天室后端新增 OpenAI 兼容地址规范化逻辑与非流式上游请求支持，兼容 LongCat `/openai` / `/openai/v1` 路径填写方式，并为前端“流式回复”开关提供后端能力。
- 2026-04-20T17:25:00+08:00：聊天室后端切换为 `httpx.AsyncClient` + 异步 `StreamingHttpResponse` 生成器，修复 `uvicorn + ASGI` 下流式 chunk 被整段消费、前端表现为阻塞回复的问题。
- 2026-04-20T18:35:00+08:00：聊天室会话新增 `system_prompt` 字段与迁移，右侧系统提示词面板保存后会真实进入上游 `messages` 请求链路；同时保留 OpenAI 兼容地址规范化与异步流式输出。
- 2026-04-20T18:45:00+08:00：聊天室新增自动标题生成逻辑，若会话标题仍为默认占位值，则在首轮回复完成后调用当前绑定模型生成简短标题并回写数据库。
- 2026-04-20T19:05:00+08:00：聊天室会话新增 `temperature` / `max_tokens` 配置并真实参与上游请求，`send` 端点支持最后一条助手消息重生成；配合前端搜索与模板能力，聊天室进入第二阶段工作台形态。
- 2026-04-21T13:20:00+08:00：新增知识库已批准约束说明，记录预期 API、文档模型字段、admin-only 状态维护边界、raw DRF + 二进制下载契约，以及 A/C 两种结构下需要补充的测试路径。
