# 统一实时错误码与超管目录：实施计划

## 1. Establish the canonical backend catalogue

1. 新增 `backend/apps/error_codes/`，定义不可变的 WebSocket 错误目录、分类和查询函数；覆盖现有 `DEVICE_*`、实时协议、ASR、TTS、LLM、agent 会话状态及安全兜底错误。
2. 将 `RuntimeDeviceError` 改为从该目录获得 code、默认 message 和现有业务状态码，保留 HTTP 行为。
3. 添加只读 serializer、ViewSet/APIView 与 `apps.error_codes.urls`；在根 URL 配置注册 `GET /api/v1/error-codes/` 与 `GET /api/v1/error-codes/{code}/`，仅 `IsSuperUser` 可访问。
4. 添加目录 API 测试：字段、关键字/分类筛选、详情 lookup、非超管拒绝访问。

## 2. Normalize realtime error emission

1. 在 `backend/config/realtime.py` 建立唯一的 WebSocket 错误发送函数：接收 event type、关联 ID 与目录错误定义，输出嵌套 `error: {code, message}`。
2. 将 `_send_error`、`_realtime_error_payload` 及 agent/LLM/ASR/TTS 处理分支迁移到该函数；移除旧的运行时错误平铺字段与裸 message 错误事件。
3. 将 `DEVICE_AGENT_UNBOUND`、`DEVICE_TENANT_UNBOUND` 等状态转为明确的目录错误，而不是 `RuntimeError` 文本或 `device_not_found`。
4. 将未知/上游失败映射到安全目录错误，保留服务端日志与 trace ID，但不把原始异常暴露给设备。
5. 更新 `config.tests.test_realtime_websocket`、设备运行时与 ASR/TTS 测试，断言统一结构及旧顶层字段缺失。

## 3. Add the read-only superadmin UI

1. 新增 `web/src/api/modules/error-codes.ts`，以手写严格 TypeScript 类型请求目录 API。
2. 新增 `web/src/views/error-code-center/index.tsx`：搜索、分类筛选、响应式列表与详情；遵循 brand token、流体排版、Tabler 图标与 antd Table 规范。
3. 在 `web/src/router/index.tsx` 惰性注册 `/error-codes`，使用 `SuperuserGuard`。
4. 在 `web/src/layouts/dashboard-layout.tsx` 将“错误码中心”添加为超管一级菜单；仅 `isSuperuser` 渲染该项，不能改变既有租户管理菜单的授权语义。
5. 如现有前端含 WebSocket 错误消费者，迁移为读取 `payload.error.code` 和 `payload.error.message`。

## 4. Validate and review

1. 运行目录 API 与实时协议目标 Django 测试：
   ```bash
   docker compose exec backend python manage.py test apps.error_codes.tests config.tests.test_realtime_websocket apps.devices.tests.test_device_authorization_api apps.ai_models.tests.test_asr_realtime apps.ai_models.tests.test_tts_api --keepdb
   ```
2. 在 `web/` 运行：
   ```bash
   npm run build
   ```
3. 使用超管账号打开 `/error-codes`：验证一级菜单、列表、筛选、详情和非超管路由/API 拒绝访问；使用 WebSocket Communicator 覆盖各类错误事件。
4. 实现后执行 GitNexus 变更影响检查，确认只覆盖错误目录、实时命令处理和超管导航预期执行流。

## Rollback

无迁移。若客户端直接切换出现生产兼容问题，回退本变更所含后端和前端版本；恢复现有 WebSocket 字段结构。
