# 公司侧 CosyVoice 分配与可扩展 TTS 架构设计

## Problem Statement

公司侧现在只有一个隐含的阿里云/Qwen TTS provider。用户需要超管把 CosyVoice v3.5-plus 卡片分配给公司，并且后续新增 TTS 卡片时不复制公司侧接口、设备运行时逻辑和授权逻辑。

根本问题不是“让公司页面多一个 CosyVoice 下拉项”，而是把 TTS 变成一个深 module：调用方只知道“当前 tenant 授权了哪些卡片、可用哪些 voice、选中了哪个 voice、该渲染哪组公共配置字段、如何试听或运行”，供应商请求参数、凭据和协议差异留在 module implementation 和 adapter 里。

## Domain Model

新增 `TenantTTSProviderGrant`，对齐现有 `TenantLLMModelGrant` 的授权体验，但授权对象是 TTS 卡片。当前代码中 `TTSProvider` 承担卡片角色：

- `tenant -> tenants.Tenant`
- `provider -> TTSProvider`
- `is_active`
- `public_config -> JSONField(default=dict)`
- `created_at`
- `updated_at`
- `objects = TenantManager()`
- `UniqueConstraint(fields=['tenant', 'provider'], name='uniq_tenant_tts_provider_grant')`

有效音色集合由卡片授权动态派生：

- tenant 对 provider/card 有 active grant。
- provider/card active。
- voice active + visible。
- adapter 声明该 voice/company channel 可运行。

已授权卡片下未来新增的 active/visible/company-runnable 音色自动进入公司侧 `voices` 集合。MVP 不做卡片内 per-tenant 音色排除；如果后续需要精细控制，再增加 voice-level exception，而不是改变主授权语义。

保留 `TenantTTSSettings.default_voice`，但语义收窄为“公司默认授权音色”。读写默认音色时都必须通过授权校验。

`TenantTTSSettings.tts_session_config` 作为历史 Qwen 配置来源保留兼容读，但新写入应进入 `TenantTTSProviderGrant.public_config`。数据迁移或首次读取时，把旧 Qwen session config 映射为 Aliyun/Qwen provider grant 的 `public_config`。CosyVoice public config 独立存储在 CosyVoice provider grant 上，避免不同卡片字段互相污染。

## Deep Module Interface

在 `backend/apps/ai_models/services/tts.py` 或相邻 module 中建立 tenant-scoped TTS interface，视图层和设备层都通过它进入：

- `get_effective_tts_voices_for_tenant(tenant, *, provider_code=None, model_code=None)`
- `get_effective_tts_voice_for_tenant(tenant, *, provider_code=None, model_code=None)`
- `resolve_tenant_tts_voice(tenant, raw_voice_id=None, *, provider_code=None, model_code=None, allow_fallback=True)`
- `ensure_tts_voice_authorized_for_tenant(tenant, voice_id, *, provider_code=None, model_code=None)`
- `tts_provider_usage_for_tenant(tenant, provider)`
- `tts_voice_usage_for_tenant(tenant, voice)`
- `tts_provider_has_active_company_authorization(provider)`

这些 helper 是公司 options、默认保存、试听、设备绑定、设备应用音色选择、HTTP runtime、统一 WebSocket TTS 和删除保护的唯一授权入口。调用方不能直接用用户传入的 `voiceId` 查 `TTSVoice.objects`。

## Provider Adapter

TTS provider adapter 是供应商差异的 seam。真实外部依赖属于 true external dependency，生产 adapter 调第三方，测试 adapter/mock 只验证 module interface 的可观察结果。

推荐 adapter interface：

- `provider_code`
- `company_runtime_capabilities(provider)`
- `public_provider_summary(provider)`
- `public_model_options(provider)`
- `public_config_schema(provider, *, channel)`
- `public_session_config(provider, grant=None, tenant_settings=None)`
- `effective_config(provider)`
- `normalize_public_controls(raw_controls)`
- `build_http_request(text, voice, config, controls)`
- `build_realtime_session(config, voice, controls)`
- `stream_realtime_text(text, voice, config, controls, send)`
- `stream_realtime_segments(segments, voice, config, controls, send)`
- `synthesize_pcm(text, voice, config, session_config=None)`
- `supports_realtime(config)`

Aliyun/Qwen adapter 兼容当前 `tts_session_config`、`model_code`、Qwen voice/model capability 逻辑。

CosyVoice adapter 从 `CosyVoiceSettings` 读取加密凭据、WebSocket URL、HTTPS 定制 URL、默认测试文本和远程 voice code。公司响应只返回公共摘要，不返回 API Key、WSS URL、HTTPS URL 或 provider-specific parameters。

CosyVoice realtime adapter 必须把官方上游任务协议归一化到本系统统一 WebSocket 下游契约：

- 上游：`run-task` 创建任务，`continue-task` 发送文本，`finish-task` 结束任务。
- 下游：先发 `tts.ready`，中间逐块转发二进制音频，结束发 `tts.done`，错误发 `tts.error`。
- 文本分段仍复用本地 `split_tts_text` / agent segment queue 语义。
- 不把 CosyVoice 上游 task id、WSS URL、API Key 暴露给公司或设备客户端。

未来新增 TTS 卡片时，只新增 provider/card 管理页面、provider settings model 或 JSON 配置、以及 adapter；公司授权表、公司 options、设备绑定和运行时解析不改结构。

## Adapter Readiness And Request Routing Contract

公司侧看到的是所有已授权卡片下可运行 voice 的扁平集合；不是一个单 provider 配置页，也不是全平台音色列表。每条 voice 必须带公共 provider/card 信息，例如 `providerId`、`providerCode`、`providerName`、`configSchemaKey`、`supportedChannels` 和可公开的 `capabilities`。

后端请求路由必须以解析后的 voice 为准：

```python
voice = ensure_tts_voice_authorized_for_tenant(tenant, voice_id)
adapter = get_tts_provider_adapter(voice.provider.code)
capabilities = adapter.company_runtime_capabilities(voice.provider)
controls = adapter.normalize_public_controls(request_controls)
config = adapter.effective_config(voice.provider)
pcm = adapter.synthesize_pcm(text=text, voice=voice, config=config, controls=controls)
```

关键约束：

- `voiceId` 是真实路由键；`providerCode` 只能作为可选过滤或一致性校验，不能覆盖 `voice.provider.code`。
- 公司请求不能携带 provider 私有参数。公司侧最多传 `text`、`voiceId`、`channel` 和该 provider/card `public_config_schema` 声明的公共 controls，例如语速、音调、音量、采样率、音频格式、风格、指令控制。
- 公司配置 UI 根据选中 voice 的 provider/card schema 渲染表单；切换到另一张卡片时，前端必须切换 schema，并只提交目标 schema 允许的字段。
- 每个 provider/card 的公共配置存放在当前 tenant 对该 card 的 grant `public_config` 中。运行时只读取已解析 voice 所属 card 的 public config，再合并设备覆盖和本次请求 overrides。
- adapter 负责把通用 controls 映射成 provider-specific payload。Qwen adapter 生成 Qwen realtime `session.update` / HTTP 参数；CosyVoice adapter 生成 CosyVoice `run-task` / `continue-task` / `finish-task` 参数。
- adapter 必须声明 `supportsCompanyHttpTest`、`supportsCompanyHttpRuntime`、`supportsCompanyRealtime`。CosyVoice v3.5-plus MVP 必须声明并实现 `supportsCompanyRealtime=true`，否则该任务不算完成。
- provider 配置不完整、adapter 未实现、voice metadata 缺少必需字段、或通用 controls 无法映射时，adapter 返回明确错误；TTS module 不允许跨 provider fallback。
- 公司 options 默认只返回 company-runnable voices。超管授权页可以展示不可运行原因，避免分配后公司侧看到一个必定请求失败的音色。

## Super Admin REST API

新增超管公司 TTS 卡片授权资源，路径跟现有 LLM 授权入口保持同一 settings namespace，同时保持资源名词路径：

- `GET /api/v1/settings/tts/tenants/{tenantId}/card-authorizations/`
- `PUT /api/v1/settings/tts/tenants/{tenantId}/card-authorizations/`

响应形状：

```json
{
  "tenant": { "id": 1, "name": "公司A", "isActive": true },
  "providers": [
    {
      "id": 10,
      "code": "cosyvoice",
      "name": "CosyVoice",
      "isActive": true,
      "sortOrder": 20,
      "grantIsActive": true,
      "supportedChannels": ["httpTest", "httpRuntime", "realtime"],
      "publicConfigSchema": {
        "schemaKey": "cosyvoice",
        "fields": []
      },
      "voices": [
        {
          "id": 101,
          "providerId": 10,
          "providerCode": "cosyvoice",
          "displayName": "客服女声",
          "voiceCode": "remote-voice-id",
          "supportedChannels": ["httpTest", "httpRuntime", "realtime"],
          "capabilities": { "speechRate": true, "pitchRate": true, "volume": true },
          "gender": "female",
          "avatarPath": "/static/tts/voices/voice_female_one.png",
          "isActive": true,
          "isVisible": true,
          "sortOrder": 1,
          "effectiveAuthorized": true,
          "isDefault": true,
          "usage": { "tenantDefault": true, "deviceCount": 2, "deviceApplicationCount": 1 }
        }
      ],
      "usage": { "tenantDefault": true, "deviceCount": 2, "deviceApplicationCount": 1 },
      "canDisableGrant": false
    }
  ],
  "defaultVoiceId": 101
}
```

请求形状：

```json
{
  "cardGrants": [
    { "providerId": 10, "isActive": true, "publicConfig": { "speech_rate": 1.0, "volume": 50 } },
    { "providerId": 11, "isActive": false }
  ],
  "defaultVoiceId": 101
}
```

校验规则：

- `tenantId` 必须是启用公司。
- `providerId` 必须存在并代表可授权 TTS 卡片。
- `defaultVoiceId` 必须属于本次启用授权的 provider/card。
- 默认音色所属 provider 和 voice 必须启用，voice 必须可见。
- `publicConfig` 只能包含该 provider/card `publicConfigSchema` 声明的字段；未知字段返回 400。
- 关闭授权时不删除历史 grant，只置 `is_active=false`。
- 关闭仍被默认音色、设备或设备应用引用的卡片授权时返回 400 和 usage 摘要。

## Company Options Contract

现有公司 options 是单 provider flat shape。新 contract 保留迁移兼容字段，同时增加 provider-neutral 字段：

```json
{
  "providers": [
    {
      "id": 1,
      "code": "aliyun",
      "name": "阿里云 TTS",
      "isActive": true,
      "defaultModelCode": "instructional",
      "modelOptions": [],
      "supportedChannels": ["httpTest", "httpRuntime", "realtime"],
      "publicConfigSchema": {
        "schemaKey": "aliyun-qwen",
        "fields": []
      },
      "voices": []
    },
    {
      "id": 10,
      "code": "cosyvoice",
      "name": "CosyVoice",
      "isActive": true,
      "defaultModelCode": "cosyvoice-v3.5-plus",
      "modelOptions": [],
      "supportedChannels": ["httpTest", "httpRuntime", "realtime"],
      "publicConfigSchema": {
        "schemaKey": "cosyvoice",
        "fields": [
          { "name": "speech_rate", "label": "语速", "type": "slider", "min": 0.5, "max": 2, "step": 0.05 },
          { "name": "volume", "label": "音量", "type": "slider", "min": 0, "max": 100, "step": 1 }
        ]
      },
      "voices": []
    }
  ],
  "provider": { "code": "aliyun", "name": "阿里云 TTS", "isActive": true },
  "defaultVoiceId": 101,
  "sampleRate": 24000,
  "ttsSessionConfig": {},
  "defaultTestText": "默认试听文本",
  "voices": [
    {
      "id": 101,
      "providerId": 10,
      "providerCode": "cosyvoice",
      "displayName": "客服女声",
      "voiceCode": "remote-voice-id",
      "configSchemaKey": "cosyvoice",
      "supportedChannels": ["httpTest", "httpRuntime", "realtime"],
      "capabilities": { "speechRate": true, "pitchRate": true, "volume": true }
    }
  ]
}
```

`voices` 是当前 tenant 所有有效授权 voice 的扁平列表，用于兼容旧前端。`providers[].voices` 是新页面按供应商分组展示的主数据。`provider` 是默认 voice 所属 provider；如果没有默认 voice，则取第一个有授权 voice 的 provider；如果没有任何授权 voice，则返回 inactive/empty 摘要供前端展示“请联系超管分配音色”。

`publicConfigSchema` 是公司侧动态渲染配置 UI 的依据。前端选择某个 voice 后，通过 `voice.providerId/providerCode/configSchemaKey` 找到对应 provider schema，渲染该卡片允许配置的字段。保存时仍提交默认 voice 的 `voiceId` 和公共 controls；后端用选中 voice 所属 adapter 校验并归一化。

`ttsSessionConfig` 在迁移期表示默认 voice 所属 adapter 归一化后的公共 controls，不再代表可直接透传给上游的 provider request payload。新实现的 authoritative 配置来源是 `TenantTTSProviderGrant.public_config`；上游请求 payload 只能由 adapter 生成。

## Runtime Data Flow

1. 超管创建或导入 provider voices。
2. 超管通过 `TenantTTSProviderGrant` 授权 selected cards/providers 给 tenant。
3. 公司 options 读取 `get_effective_tts_voices_for_tenant(tenant)`。
4. 公司默认音色保存调用 `ensure_tts_voice_authorized_for_tenant`，并把公共配置写入所选 voice 所属 provider/card 的 grant `public_config`。
5. 设备和设备应用 serializer 的 TTS voice 字段调用同一授权 helper。
6. 设备 runtime config 解析 voice 优先级：
   - 设备绑定 voice，如果仍属于设备 tenant 已授权卡片且 voice 仍有效。
   - 公司默认 voice，如果仍属于 tenant 已授权卡片且 voice 仍有效。
   - tenant 已授权卡片下第一个有效 voice。
   - 无可用 voice 时返回空 `voiceTones` 或明确 runtime 错误，按现有 endpoint contract 选择。
7. HTTP runtime TTS 和统一 WebSocket TTS 先根据 `voiceId` / 设备绑定 / 公司默认解析 voice，再根据 `voice.provider` 选择 adapter；`providerCode` 只能作为一致性校验，不能让请求跨 provider 回退。
8. adapter 校验 provider 是否支持当前 channel；不支持时返回明确错误或在 options 阶段不暴露该运行方式。
9. Runtime config 通知保持现有完整配置推送，不新增 WebSocket URL，也不发送增量 voice-only payload。

## Unified Realtime WebSocket Contract

统一实时入口保持 `/ws/realtime/`，不新增 CosyVoice 专用业务 WebSocket URL。

客户端输入契约保持不变：

```json
{
  "type": "tts.session.start",
  "id": "tts-session-1",
  "payload": {
    "token": "JWT 或空",
    "tenantId": 2,
    "deviceCode": "ANDROID-001",
    "text": "你好",
    "voiceId": 101,
    "providerCode": "cosyvoice",
    "sessionConfig": {}
  }
}
```

兼容规则：

- `providerCode` 可选。旧 Web/设备客户端不传时，后端仍必须通过 `voiceId`、设备绑定音色或公司默认音色解析 provider。
- 如果 `providerCode` 存在且与解析出的 `voice.provider.code` 不一致，返回 `tts.error`，不能按请求里的 provider 跨卡片执行。
- 下游响应保持现有契约：`tts.ready`、`tts.segment_start`/`tts.segment_end`、二进制音频 chunk、`tts.done`、`tts.cancelled`、`tts.error`。
- Qwen adapter 的上游协议仍是 `session.update`、`input_text_buffer.append`、`input_text_buffer.commit`、`session.finish`。
- CosyVoice adapter 的上游协议是 `run-task`、`continue-task`、`finish-task`，并把上游 bytes 直接转发成下游二进制音频 chunk。
- `_run_agent_tts_stream` 使用同一 adapter streaming interface，确保设备/Agent 语音会话选择 CosyVoice 音色时也实时输出，而不是退化为先聚合再播放。

## Runtime Config Realtime Notifications

这里有第二类必须保持实时的 WebSocket：设备运行时配置订阅。它和 TTS 音频流不是一回事，二者都要满足。

继续复用统一 `/ws/realtime/` 下的 `device.runtime_config.subscribe`：

- 设备订阅时发送 `type=device.runtime_config.subscribe` 和 `payload.deviceCode`。
- 服务端仍返回 `type=device.runtime_config.subscribed`。
- 推送内容必须由 `DeviceRuntimeConfigView._config_payload(...)` 重新构建完整配置，而不是只发变更后的 voiceId、providerCode 或 publicConfig 增量。
- 不新增 CosyVoice/TTS 专用 runtime config WebSocket URL。

以下变更会影响设备有效音色或 TTS 参数，必须发布 `device.voice_configuration.changed`：

- 超管启用某个 tenant 的 TTS card grant。
- 超管停用某个 tenant 的 TTS card grant。MVP 中如果该 card 仍被默认音色、设备绑定或设备应用引用，应先 400 阻止；允许停用的情况仍要推送 tenant 级刷新。
- 超管或公司保存某张 card 的 `publicConfig`。
- 公司默认音色变更。
- 平台启停 provider、启停 voice 或隐藏 voice，且该 provider/voice 处于某些 tenant 的 active grant 中。
- 设备自己的 `voiceToneId` / `voiceToneConfig` 变更继续走现有 device-level 事件。

事件形状复用现有约定：

```json
{
  "type": "device.voice_configuration.changed",
  "tenantId": 2,
  "refresh": {
    "endpoint": "/api/v1/device-runtime/config/",
    "reason": "voiceConfigurationChanged"
  }
}
```

当只影响单台设备时可带 `deviceCode` / `deviceCodes`；当影响公司默认音色、card grant、card publicConfig 或 provider/voice 可见性时使用 tenant 级事件，不枚举所有设备。现有订阅过滤逻辑会按 tenant 匹配，再为每个订阅设备重建自己的完整 config。这样设备有显式绑定时仍看到自己的绑定音色，没有显式绑定时会实时切到新的公司默认或授权 fallback。

## Device Binding Impact

`/api/v1/devices/` 的绑定语义保持不变：

- `voiceToneId` 仍表示当前设备显式绑定的 TTS 音色。
- `voiceToneConfig` 仍表示当前设备的语速、音调、音量覆盖项。
- 运行时仍只返回当前设备实际使用的一个 voice，不返回候选列表。
- 设备绑定 voice 的优先级仍高于公司默认 voice。

实际变化是授权校验收紧：

- `DeviceSerializer.voiceToneId` 和 `DeviceApplicationSerializer.voiceToneIds` 不能再使用全局 active/visible voice queryset，必须使用当前 request tenant 已授权卡片派生出的 effective voice queryset。
- 公司设备管理页的下拉选项来自 company TTS options，因此天然只展示公司已授权音色集合。
- 保存 `/devices/{deviceCode}/` 时，如果 `voiceToneId` 不属于该设备 tenant 的有效授权，返回 400。
- 已绑定 voice 如果仍在有效授权内，迁移和后续保存不会清空。
- 已绑定 voice 如果授权被撤销或平台停用，`DeviceRuntimeConfigView._device_voice` 必须把它视为无效，再按公司默认授权 voice 或第一个授权 voice 回退；不得返回未授权绑定。
- 超管主动停用卡片授权时先通过 usage helper 查该卡片下所有 voice 的 `TenantTTSSettings.default_voice`、`Device.tts_voice` 和 `DeviceApplication.tts_voices`，有引用就阻止停用，避免设备运行时突然变声。

## Android Runtime Compatibility Contract

安卓设备不参与 provider/card 差异处理。后端必须保持安卓已使用的运行时契约稳定，让 CosyVoice、多卡片授权和 provider-specific 参数都停留在服务端。

冻结契约：

- `GET /api/v1/device-runtime/config/` 路径、`X-Device-Code` 认证方式和顶层响应语义保持不变。
- `resources.voiceTones` 仍是当前设备实际使用音色的数组；仍只返回当前 voice，不返回候选音色集合。
- voice payload 继续包含 `id`、`name`、`voiceCode`、`audioUrl`、`iconUrl`，并保留 `speechRate`、`pitchRate`、`volume` 这些已有通用配置字段。
- `POST /api/v1/ai-models/tts/runtime/` 路径、`X-Device-Code`、`voiceId`、`text`、`wrapWav`/`format` 等既有请求语义保持不变。
- HTTP TTS runtime 继续返回音频 body，content type 仍为 `audio/pcm` 或 `audio/wav`，并保留 `X-Audio-Source-Format`、`X-Audio-Sample-Rate`、`X-Audio-Channels`、`X-TTS-Voice` 响应头。
- 新增 provider 信息、capabilities 或调试字段只能是 optional additive 字段；不能要求安卓识别后才能正常播放。
- 安卓请求里的 `voiceId` 仍代表音色选择。后端用 `voiceId -> tenant authorization -> voice.provider.code -> adapter` 解析，不要求安卓传 `providerCode` 或 CosyVoice 私有参数。

因此，本任务可以避免安卓代码修改；需要修改的是后端运行时解析和 Web 管理端/超管端展示授权集合。严格表述是：只要安卓当前只依赖上述既有字段和接口，就不需要安卓发版。

## Web Frontend Changes

- `web/src/api/modules/tts.ts` 扩展 `CompanyTtsOptions`、`TtsVoiceRecord`、provider/card 类型和 `publicConfigSchema` 类型，保留 `provider` 兼容字段。
- 公司 TTS 管理页按 provider/card 分组展示授权音色；选择音色后按该音色所属卡片 `publicConfigSchema` 渲染不同配置 UI，保存默认音色时传 `voiceId` 和 schema 白名单内的公共配置字段，不展示 provider 私有参数。
- 设备管理音色选择器只使用 company options 返回的授权音色，option label 可带 provider name。
- 应用管理页 `ttsReady` 改为基于 `defaultVoiceId` 和默认 provider 摘要，同时兼容旧 `provider` 字段。
- 超管租户授权入口复用 LLM 分配的交互模式，但资源改为 TTS provider/card。

## Compatibility And Migration

- 一次性数据迁移为所有 active tenant 创建当前 Aliyun/Qwen provider/card 的显式 active grants，保持升级前公司可见性。
- 迁移不授权 CosyVoice 卡片；CosyVoice 必须由超管显式分配。
- 新 tenant 默认没有 TTS card grants，直到超管授权。
- 已授权卡片下新增或复刻的 future voices 默认自动进入该 tenant 的有效 voice 集合。
- 保留旧 `provider` 和 `voices` 字段一个迁移窗口，前端完成多 provider 消费后再考虑移除。
- 本任务有意扩展父任务中“统一实时 WebSocket 暂不选择 CosyVoice”的限制。扩展的前提是 adapter seam 已建立，CosyVoice 不再进入 Qwen 通用参数路径。

## Security And Tenant Isolation

- 所有公司和设备入口从 authenticated tenant 或 `X-Device-Code` 对应 device.tenant 推导 tenant，不能信任请求里的 tenantId。
- Platform admin 按公司浏览时复用既有 tenant scope 机制。
- 公司、设备和 realtime 响应都不包含 provider credentials 或 CosyVoice settings URLs。
- 删除 provider/voice 前检查 active company authorization，避免删除正在授权或使用的资源。

## Rollback Shape

- 数据库 rollback 的主要边界是 `TenantTTSProviderGrant` migration；生产使用后不要直接删除 grants。
- 如果 CosyVoice realtime adapter 不完整，不能上线 CosyVoice company-runnable 授权；只能通过停用 CosyVoice card grant 或 provider 回退，Aliyun/Qwen adapter 和存量 grants 独立保留。
- 公司 options 保留旧字段，必要时可短期回退到 Aliyun adapter，但不能绕过 tenant grant helper。

## Key Files

- `backend/apps/ai_models/models.py`
- `backend/apps/ai_models/serializers.py`
- `backend/apps/ai_models/views.py`
- `backend/apps/ai_models/services/tts.py`
- `backend/apps/ai_models/realtime_tts.py`
- `backend/apps/devices/serializers.py`
- `backend/apps/devices/views.py`
- `backend/apps/devices/tts_voice_config.py`
- `backend/apps/devices/realtime.py`
- `backend/config/realtime.py`
- `web/src/api/modules/tts.ts`
- `web/src/views/tts-management/index.tsx`
- `web/src/views/device-management/index.tsx`
- `web/src/views/application-management/index.tsx`
