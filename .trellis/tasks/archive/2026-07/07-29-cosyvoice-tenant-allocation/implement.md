# 公司侧 CosyVoice 分配与可扩展 TTS 架构实施计划

## Preconditions

- 先由用户审核并确认 `prd.md` / `design.md` / `implement.md`。
- 用户确认最终规划后，才能运行 `python ./.trellis/scripts/task.py start .trellis/tasks/07-29-cosyvoice-tenant-allocation`。
- 开始代码修改前加载 `trellis-before-dev`，按目标 layer 读取 `.trellis/spec/`。
- Inline mode：不整理 `implement.jsonl` / `check.jsonl`，Phase 2 通过 `trellis-before-dev` 读取 artifacts/specs。
- 修改任何函数、类或方法前按 AGENTS 规则运行 GitNexus `impact`，并把 direct callers、affected processes、risk level 告知用户；HIGH/CRITICAL 先警告再继续。

## Required GitNexus Impact Targets Before Edits

- `TenantTTSSettings`
- `TTSVoice`
- `get_effective_tts_voice_for_tenant`
- `get_available_tts_voices`
- `_build_company_tts_options_payload`
- `_select_company_tts_voice`
- `_select_device_runtime_tts_voice`
- `CompanyTTSDefaultVoiceView`
- `CompanyTTSTestView`
- `TTSRuntimeView`
- `_run_tts_session_body`
- `_run_agent_tts_stream`
- `_stream_tts_audio`
- `_stream_tts_segments_audio`
- `resolve_tts_provider`
- `publish_device_event_sync`
- `build_device_runtime_config_event`
- `AvailableTTSVoicePrimaryKeyField`
- `DeviceSerializer`
- `DeviceApplicationSerializer`
- `DeviceRuntimeConfigView._device_voice`
- `resolve_tts_voice`
- `CompanyTtsOptions`

## Implementation Phases

1. 后端模型与迁移
   - 新增 `TenantTTSProviderGrant` model、admin 注册和 related names。当前 `TTSProvider` 作为超管 TTS 卡片边界。
   - `TenantTTSProviderGrant` 增加 `public_config JSONField(default=dict)`，用于保存该 tenant 在该卡片下的公共运行配置。
   - 生成 schema migration。
   - 增加 data migration：为所有 active tenant 创建当前 Aliyun/Qwen provider/card 的 active grants；不授权 CosyVoice。
   - 迁移或兼容读取旧 `TenantTTSSettings.tts_session_config` 到 Aliyun/Qwen grant `public_config`。
   - 检查迁移可重复执行和空 provider 场景。

2. TTS tenant authorization helper
   - 增加 tenant-scoped effective voice 查询。
   - effective voice 从 active card grant + active provider + active/visible voice + adapter channel readiness 动态派生。
   - 改造默认音色解析， fallback 只能在当前 tenant 已授权卡片下的有效音色内发生。
   - 增加 card public config 读取/保存 helper：只读取解析后 voice 所属 provider/card 的 grant `public_config`。
   - 增加 usage helper，统计某张卡片及其音色是否命中 tenant default、device binding、device application references。
   - 增加 provider/voice active authorization helper，用于删除保护。

3. Provider adapter
   - 抽出 Aliyun/Qwen adapter，保持当前 session config、model_code、voice capability 行为。
   - 增加 CosyVoice adapter 的公共摘要和 synthesis/runtime 参数边界。
   - 增加 adapter readiness/capabilities：`supportsCompanyHttpTest`、`supportsCompanyHttpRuntime`、`supportsCompanyRealtime`。
   - 增加 adapter 的 `publicConfigSchema`，用于公司 TTS 管理页按所选卡片动态渲染配置 UI。
   - 增加 `normalize_public_controls` 和 request builder，确保上游 provider-specific payload 只由 adapter 生成。
   - adapter 保存配置时按 `publicConfigSchema` 白名单清理/校验字段；未知字段返回 400。
   - 增加 realtime streaming interface：单文本和 segment queue 都由 adapter 输出统一下游事件/二进制音频。
   - CosyVoice realtime 必须打通 `run-task` / `continue-task` / `finish-task` 并逐块转发上游 bytes；不得退化成先聚合完整音频再发送。

4. 超管授权 API
   - 新增 `TenantTTSCardAuthorizationSerializer` 或 `TenantTTSProviderAuthorizationSerializer`。
   - 新增 `TenantTTSCardAuthorizationView` 或 `TenantTTSProviderAuthorizationView`。
   - 注册 `GET/PUT /api/v1/settings/tts/tenants/{tenantId}/card-authorizations/`。
   - 保存卡片授权时校验 default voice 和使用中停用限制。
   - 响应包含 provider/card groups、card grant state、card `publicConfig`、card 下 voice 列表、defaultVoiceId、usage/canDisableGrant。
   - 启用/停用授权、保存 card `publicConfig` 或变更默认音色后，发布 tenant 级 `device.voice_configuration.changed`，让已订阅设备通过现有 `device.runtime_config.subscribe` 收到完整运行时配置刷新。

5. 公司 TTS API
   - 改造 `_build_company_tts_options_payload` 为 provider-neutral contract，同时保留 `provider` 和 flat `voices`。
   - company options 的扁平 `voices` 返回所有已授权卡片下可运行音色的集合，并在 `providers[].voices` 中按 provider/card 分组。
   - 每条 voice 返回 `providerId`、`providerCode`、`providerName`、`configSchemaKey`、`supportedChannels` 和公开 capabilities。
   - 每个 provider/card 返回 `publicConfigSchema`，供公司 TTS 管理页根据选中音色动态渲染不同配置 UI。
   - 改造 `CompanyTTSDefaultVoiceView`，默认音色必须是有效授权。
   - 改造 `CompanyTTSDefaultVoiceView` 保存逻辑，按选中 voice 的 provider/card schema 校验公共配置字段，并写入该 provider/card grant 的 `public_config`。
   - 公司默认音色或当前 card `public_config` 变更后发布 tenant 级 `device.voice_configuration.changed`，不能只更新 Web 页面状态。
   - 改造 `CompanyTTSTestView`，试听 voiceId 必须是有效授权，provider 和请求参数都从 voice adapter 推导。
   - 明确无授权音色时 options/runtime/test 的响应。

6. 设备与 runtime
   - 改造 `AvailableTTSVoicePrimaryKeyField` 或替换为 tenant-aware field，用于设备绑定和设备应用音色选择。
   - 确保 `DeviceSerializer.voiceToneId` 保存未授权音色时返回 400，保存已授权音色时继续写入 `Device.tts_voice`。
   - 确保 `DeviceApplicationSerializer.voiceToneIds` 也按 tenant 授权过滤，避免设备应用层绕过公司授权。
   - 改造 `DeviceRuntimeConfigView._device_voice`，旧绑定失效时只回退 tenant 授权音色。
   - 保持安卓运行时配置 payload 兼容：`resources.voiceTones` 仍只表示当前音色，且 voice item 保留 `id/name/voiceCode/audioUrl/iconUrl/speechRate/pitchRate/volume`。
   - 保留 `DeviceViewSet.perform_update` 的 voice 配置变更通知行为，仍推完整 `/api/v1/device-runtime/config/` refresh。
   - 改造 `TTSRuntimeView` 和 `realtime_tts.resolve_tts_voice`，voiceId、device voice、tenant default 都走同一授权 helper，并按解析后的 `voice.provider.code` 选择 adapter。
   - 改造 `_run_tts_session_body`：先解析 connection 和 voice，再由 `voice.provider` 取 config/adapter；`providerCode` 只做一致性校验。
   - 改造 `_run_agent_tts_stream`：设备/Agent realtime TTS 也按设备绑定音色或公司默认音色派生 provider，不要求 payload 传 `providerCode`。
   - 改造 `realtime_tts._stream_tts_audio` / `_stream_tts_segments_audio` 为 adapter dispatch；Qwen 保留现有 session.update 流程，CosyVoice 走 run-task/continue-task/finish-task。
   - 确认 `X-Device-Code` 仍从 device 推导 tenant。
   - 确认安卓不需要传 `providerCode`、CosyVoice URL、API Key 或 provider-specific 请求参数。
   - 保持 HTTP TTS runtime audio body、`audio/pcm`/`audio/wav` content type 和 `X-Audio-*` / `X-TTS-Voice` 响应头兼容。
   - 确认 runtime config WebSocket 仍推完整配置。
   - 确认 provider/voice 启停、隐藏、授权或配置变化触发的是 tenant 级 runtime config 刷新；设备自身绑定变化继续触发 device-level 刷新。

7. 前端类型和公司侧页面
   - 更新 `web/src/api/modules/tts.ts` 类型。
   - 公司 TTS 管理页支持 provider/card 分组、无授权 empty state、保存默认音色。
   - 公司 TTS 管理页根据选中音色所属 provider/card 的 `publicConfigSchema` 渲染对应配置 UI；切换音色时切换 schema，并清理不属于目标 schema 的旧配置字段。
   - 设备管理音色选择器只展示授权音色，并可显示 provider label。
   - 应用管理 TTS ready/session 逻辑兼容多 provider 和旧字段。
   - 遵守现有设计 token、Tabler icon、fluid text、StatusTag 规则。

8. 超管授权 UI
   - 增加公司 TTS 卡片授权入口，交互对齐 LLM 分配。
   - 展示 provider/card groups、card grant switch、卡片下音色预览、default radio/select、usage 阻止信息。
   - MVP 不提供卡片内单音色排除；卡片授权后公司侧看到该卡片下所有有效可运行音色。

9. Tests
   - 新增公司 TTS 授权 API 测试。
   - 更新公司 TTS options/default/test/runtime 测试。
   - 更新设备授权 API 测试，覆盖 `/devices/` PATCH 未授权音色失败、已授权 Qwen/CosyVoice 绑定成功、设备绑定优先于公司默认、授权撤销阻止、runtime fallback 不越权。
   - 新增或更新安卓兼容契约测试：`GET /api/v1/device-runtime/config/` 返回的 `resources.voiceTones[0]` 保留既有字段；CosyVoice 授权音色作为当前 voice 时也保持相同 shape。
   - 新增或更新 HTTP TTS runtime 兼容测试：安卓只携带 `X-Device-Code`、`voiceId` 和文本即可请求；响应仍是音频 body、既有 content type 和 `X-Audio-*` / `X-TTS-Voice` headers。
   - 更新 realtime TTS voice resolution 测试。
   - 新增 adapter 路由测试：同一 tenant 同时授权 Qwen 和 CosyVoice 卡片，选择 Qwen voice 只生成 Qwen payload，选择 CosyVoice voice 只生成 CosyVoice payload。
   - 新增统一 WebSocket CosyVoice 测试：`tts.session.start` 选择 CosyVoice voice 后，上游收到 `run-task`、`continue-task`、`finish-task`，客户端收到 `tts.ready`、二进制音频、`tts.done`。
   - 新增旧客户端兼容测试：`tts.session.start` 不传 `providerCode` 但传 CosyVoice `voiceId` 时仍正确路由；传入与 voice 不匹配的 `providerCode` 时返回 `tts.error`。
   - 新增设备/Agent realtime 测试：设备绑定 CosyVoice 音色或公司默认 CosyVoice 音色时，`_run_agent_tts_stream` 走 CosyVoice adapter 并实时转发 segment audio。
   - 新增 provider/card config schema 测试：company options 返回每张授权卡片的 `publicConfigSchema`；默认音色保存时只接受所选卡片 schema 白名单内字段，拒绝混入另一张卡片字段。
   - 新增 per-card config isolation 测试：同一 tenant 同时配置 Qwen 和 CosyVoice，两个 provider/card grant 的 `public_config` 互不覆盖；runtime 只读取当前 voice 所属卡片配置。
   - 新增 unsupported/config incomplete 测试：adapter 未配置或不支持当前 channel 时返回明确错误，不回退其它 provider。
   - 新增 runtime config WebSocket 测试：设备订阅 `device.runtime_config.subscribe` 后，超管授权/停用授权、保存 card `publicConfig`、公司默认音色变更、provider/voice 启停或隐藏会收到 `device.runtime_config.subscribed`，`action=voiceConfigurationChanged`，且 payload 包含重新构建的完整 config。
   - 覆盖 CosyVoice 与 Aliyun/Qwen 并存、未授权公司不可见、凭据不泄露。

## Validation Commands

```bash
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py migrate --plan
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api --keepdb
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb
docker compose exec backend python manage.py test config.tests.test_realtime_websocket --keepdb
docker compose exec backend python manage.py test apps.ai_models.tests.test_llm_company_settings_api --keepdb
```

前端：

```bash
cd web
npm run build
```

提交前：

```bash
node .gitnexus/run.cjs status
```

然后运行 GitNexus `detect_changes({ "scope": "all", "repo": "could_frontend_big" })`，确认影响面只落在 TTS 授权、设备 voice runtime 和相关前端消费。

## Risk Points

- `TenantTTSSettings.default_voice` 目前可指向任意 visible voice；迁移和保存校验必须避免旧默认音色绕过授权。
- `TenantTTSSettings.tts_session_config` 是单 JSON，不适合多 provider；必须迁移/兼容为 Aliyun/Qwen grant `public_config`，新写入不能继续依赖单字段。
- 设备 `tts_voice` 是长期绑定字段；授权撤销和 provider 停用后 runtime 必须二次校验。
- TTS 授权、默认音色和 card `publicConfig` 变更不一定会修改 `Device` 行；必须显式发布 tenant 级 runtime config 事件，否则在线设备不会实时感知新音色或参数。
- `DeviceApplicationSerializer.voiceToneIds` 也使用全局可见音色查询，不能漏掉。
- 前端 `CompanyTtsOptions.provider` 当前是单 provider 假设；迁移期必须保留兼容字段。
- CosyVoice runtime 请求参数与 Qwen 不同；adapter 必须完整覆盖 HTTP 和统一 WebSocket realtime，不能跨 provider fallback。
- 单个 `TenantTTSSettings.tts_session_config` 是历史 Qwen 形状；实现时要把它当默认 voice adapter 的公共 controls，不允许直接透传为任意 provider 的上游 payload。

## Rollback Points

- 模型迁移是主要 rollback 边界。生产使用后不要删除 grants，只能通过禁用 grant/provider 回退。
- 公司 options 保留旧字段，前端可逐页迁移。
- CosyVoice card grants 可按 tenant 禁用；Aliyun/Qwen adapter 和存量 grants 独立保留。
