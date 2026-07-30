# 公司侧 CosyVoice 分配与可扩展 TTS 架构

## Goal

平台超管已经可以维护 CosyVoice v3.5-plus 卡片、配置和自定义音色。下一步要让超管像分配 LLM 模型一样，把可用 TTS 卡片授权给指定公司；公司侧只能查看、默认选择、设备绑定和运行时使用已授权卡片下的有效音色。

这次改造同时要把公司侧 TTS 从“固定阿里云/Qwen 单供应商”推进为卡片/供应商中立的音色目录。未来超管继续增加 TTS 卡片时，每个卡片可以有自己的配置、凭据、请求参数和公司侧配置 UI schema，但公司侧运行时仍只消费稳定的授权音色契约。

## Confirmed Facts

- 现有 LLM 分配模式以 `TenantLLMModelGrant` 记录公司与模型授权关系，并在超管授权接口中按公司返回供应商、模型和授权状态：`backend/apps/ai_models/models.py:87`、`backend/apps/ai_models/views.py:1129`、`backend/apps/ai_models/serializers.py:526`。
- 当前 TTS 已有平台供应商、音色、CosyVoice 专属设置和公司默认音色，但没有公司 TTS 卡片授权表：`backend/apps/ai_models/models.py:549`、`backend/apps/ai_models/models.py:598`、`backend/apps/ai_models/models.py:625`、`backend/apps/ai_models/models.py:681`。
- 当前公司 TTS options、默认音色保存、试听和 HTTP runtime TTS 都固定取阿里云/Qwen provider，未按公司授权过滤：`backend/apps/ai_models/views.py:447`、`backend/apps/ai_models/views.py:666`、`backend/apps/ai_models/views.py:686`、`backend/apps/ai_models/views.py:706`。
- 当前设备绑定音色校验只要求音色启用、可见、供应商启用，没有按设备所属公司过滤：`backend/apps/devices/serializers.py:39`、`backend/apps/devices/serializers.py:133`。
- 当前设备运行时配置会返回当前设备音色，设备未绑定时回退公司默认音色；该解析现在仍可能回退到平台默认音色：`backend/apps/devices/views.py:852`、`backend/apps/devices/views.py:862`。
- 设备运行时配置 WebSocket 已通过统一入口推送完整配置，后续不能新增业务 WebSocket URL 或只推增量字段：`backend/apps/devices/realtime.py:57`、`backend/config/realtime.py:431`。
- 现有 `device.runtime_config.subscribe` 已支持 tenant 级 runtime config 变更事件：没有指定 `deviceCode` 的 `device.voice_configuration.changed` 会按 tenant 推送给已订阅设备，并由服务端重新构建完整配置：`backend/apps/devices/realtime.py:57`、`backend/apps/devices/realtime.py:120`、`backend/apps/devices/tests/test_device_authorization_api.py:3097`。
- 现有统一实时 TTS 使用 `/ws/realtime/` 的 `tts.session.start` / `tts.session.cancel` 命令，前端接收 `tts.ready`、二进制音频、`tts.done` 和 `tts.error`；当前后端先按 `providerCode` 取 provider，再解析 voice，并且显式拒绝 `providerCode=cosyvoice`：`backend/config/realtime.py:2380`、`backend/config/realtime.py:2401`、`backend/apps/ai_models/realtime_tts.py:89`、`backend/apps/ai_models/realtime_tts.py:130`。
- 现有 CosyVoice TTS 服务已经按上游 `run-task`、`continue-task`、`finish-task` 协议聚合 PCM，并有服务级测试覆盖；但尚未接入统一 WebSocket 的实时逐块转发：`backend/apps/ai_models/services/tts.py:439`、`backend/apps/ai_models/tests/test_tts_api.py:177`。
- 公司 TTS 前端目前由公司 TTS 管理、设备管理和应用管理共同消费同一个 options contract，并假设存在单个 `provider` 字段：`web/src/api/modules/tts.ts:73`、`web/src/views/tts-management/index.tsx:80`、`web/src/views/device-management/index.tsx:372`、`web/src/views/application-management/index.tsx:724`。
- 父任务曾要求通用平台 TTS 接口和统一实时 WebSocket 暂不选择 CosyVoice，目的是避免 CosyVoice 专属参数混入 Qwen 流程：`.trellis/tasks/07-29-cosyvoice-tts-admin/prd.md:15`。本任务在引入 provider adapter 后明确扩展该边界：公司和设备 realtime 必须能选择已授权 CosyVoice 音色，但仍不得复用或混入 Qwen 参数。

## Requirements

1. 新增公司 TTS 卡片授权关系，授权粒度为 TTS 卡片/供应商。当前代码里的 `TTSProvider` 作为卡片边界；如果后续拆出独立 `TTSCard` 模型，外部授权语义保持不变。
2. 超管可按公司查看所有可分配 TTS 卡片、卡片下音色、卡片运行能力、卡片授权状态和使用情况，并启用或停用某个公司对某张卡片的授权。
3. 公司侧 TTS options 返回当前公司在所有已授权 TTS 卡片下的有效音色集合，必须保留扁平 `voices` 集合供现有页面和设备/应用选择器兼容，同时增加 `providers`/`cards` 分组数据供按卡片渲染配置 UI。
4. 公司侧 TTS options 只返回当前公司已授权卡片下、供应商启用、音色启用且音色可见的音色；不能返回全平台未授权卡片的音色。
5. 公司默认音色必须来自当前公司有效授权；保存默认音色时如果未授权、停用、不可见或供应商停用，必须返回明确 400。
6. 设备绑定音色、设备应用可选 TTS 音色、HTTP runtime TTS 和统一 WebSocket TTS 都必须通过同一套 tenant-scoped 音色解析逻辑，不能直接按 `voiceId` 查询全局音色。
7. 所有公司侧试听、HTTP runtime TTS、统一 WebSocket TTS 请求必须以解析后的 `voice.provider` 选择 provider adapter；不得用公司请求里的 provider 参数决定真实上游协议。
8. 不同卡片的请求参数必须由各自 adapter 生成和校验。公司侧配置页面可以根据所选音色所属卡片渲染不同配置 UI，但提交内容必须是该卡片声明的公共配置字段，不能直接提交 API Key、URL 或任意 provider 私有 payload。
9. 每个公司-卡片授权必须保存该卡片自己的 `publicConfig`，并按该卡片 `publicConfigSchema` 校验；Qwen 和 CosyVoice 配置不能共用或覆盖同一个无类型 JSON。
10. CosyVoice v3.5-plus 在 MVP 必须支持统一实时 WebSocket TTS。`/ws/realtime/` 路径、`tts.session.start` / `tts.session.cancel` 命令、`tts.ready` / 二进制音频 / `tts.done` / `tts.error` 下游契约保持不变。
11. Qwen/Aliyun realtime adapter 使用现有 `session.update` / `input_text_buffer.*` 协议；CosyVoice realtime adapter 必须使用 `run-task` / `continue-task` / `finish-task` 协议，并把上游二进制音频逐块转发给同一个 WebSocket 下游。
12. 统一 realtime 的 voice/provider 解析必须支持旧客户端不传 `providerCode`：优先从 `voiceId`、设备绑定音色或公司默认音色解析出 voice，再从 `voice.provider` 选择 adapter；`providerCode` 只能作为一致性校验。
13. adapter 缺少必需配置、无法实时连接、无法把通用控制项映射到该供应商、或未来卡片不支持 realtime 时，必须返回明确 `tts.error`；不能静默回退到其它卡片。CosyVoice 卡片如果 realtime adapter 不完整，不允许标记为 company-runnable。
14. 每张卡片必须向公司 options 暴露安全的 `publicConfigSchema`/`runtimeConfigSchema`，前端根据选中音色的 `providerId/providerCode` 选择对应 schema 渲染表单；后端再次按 schema 白名单校验保存值。
15. 设备绑定音色优先级保持不变：设备已绑定且仍有效时优先使用；设备没有有效绑定时才使用公司默认音色；公司默认也无效时才使用该公司第一个有效授权音色。
16. `/devices/` 设备绑定字段语义保持为“当前设备绑定音色”，但可选范围从全局 active/visible 音色收紧为当前设备所属公司已授权卡片下的有效音色。
17. 已绑定音色如果所属卡片仍在授权内且音色仍有效，升级和重新保存设备时不得被清空；如果卡片授权被撤销或音色被停用，运行时不能继续返回该音色。
18. 超管停用卡片授权时，如果该卡片下任一音色仍被公司默认音色、设备绑定或设备应用引用，MVP 必须阻止停用并返回使用情况摘要；不得静默改变线上设备运行时音色。
19. 如果音色或供应商被平台停用导致既有绑定失效，运行时必须按授权规则重新解析或返回可定位错误，不能回退到未授权平台默认音色。
20. 公司侧 API 不暴露 API Key、WebSocket URL、HTTPS 定制 URL、供应商私有请求参数或其它凭据；只暴露 provider/voice/session/config schema 的公共摘要。
21. 后端需要引入供应商适配边界，让 Qwen/Aliyun、CosyVoice 和未来卡片的请求参数差异集中在 adapter 内部；新增供应商不应改动公司授权表结构。
22. 超管授权 API 使用 REST 风格资源路径，字段保持前端 camelCase 约定，并沿用 LLM 授权的 GET/PUT 保存体验。
23. 存量阿里云/Qwen 公司侧行为需要兼容：迁移时为已有 active tenant 创建当前阿里云/Qwen 卡片的显式授权，并把旧 `TenantTTSSettings.tts_session_config` 迁移/兼容读取为阿里云/Qwen 卡片 `publicConfig`；新租户和新增卡片必须由超管显式授权后才可见。
24. 已授权卡片下未来新增的 active/visible/company-runnable 音色默认自动进入该公司的 `voices` 集合。
25. MVP 不支持卡片内按公司排除单个音色；如需控制某个音色不可给公司使用，使用平台音色 `is_visible/is_active` 或后续拆成独立卡片。
26. 公司数据必须 100% 按 tenant 隔离；普通公司账号不得通过 query 参数、tenantId 或 voiceId 越权访问其它公司数据。
27. 安卓设备运行时契约必须保持向后兼容：`GET /api/v1/device-runtime/config/`、`POST /api/v1/ai-models/tts/runtime/`、`X-Device-Code`、`resources.voiceTones` 当前音色数组、音频响应格式和现有响应头不得改名、删除或改语义；新增字段只能是可选 additive 字段。
28. 安卓侧不得需要传 provider 私有字段、providerCode 或新的 CosyVoice 参数。安卓仍只按现有逻辑提交 `voiceId`/文本/通用音频参数，后端根据授权 voice 的 `voice.provider` 完成路由和请求参数生成。
29. 超管卡片授权、公司默认音色、卡片 `publicConfig`、provider/voice 启停/可见性等任何会改变设备有效 TTS 音色或运行参数的变更，必须复用现有 `/ws/realtime/` 的 `device.runtime_config.subscribe` 通道发送完整 runtime config 刷新事件；不能只依赖前端页面刷新或下一次 HTTP 拉取。

## Acceptance Criteria

- [ ] 数据库存在公司 TTS 卡片授权关系，至少包含 `tenant`、`provider/card`、`is_active`、`public_config`、创建/更新时间，并对 `(tenant, provider/card)` 做唯一约束。
- [ ] 数据迁移为已有 active tenant 创建当前阿里云/Qwen 卡片授权，升级后存量公司 TTS 不中断；迁移不会授权 CosyVoice 或未来新增卡片。
- [ ] 超管可通过公司 TTS 授权 API 获取卡片、卡片下音色、授权状态、使用情况和默认音色，并可保存卡片授权状态与默认音色。
- [ ] 默认音色不在启用授权内、音色不可见、音色停用或供应商停用时，超管授权保存和公司默认音色保存都返回明确 400。
- [ ] 公司 TTS options、公司试听、公司默认音色保存、设备绑定、设备应用音色选择、设备 runtime config、HTTP runtime TTS 和统一 WebSocket TTS 均只接受当前公司已授权卡片下的有效音色。
- [ ] `/devices/` PATCH 绑定未授权 `voiceToneId` 返回明确 400；绑定已授权 Qwen 或 CosyVoice 音色均成功保存，并继续触发现有完整 runtime config 变更通知。
- [ ] 设备已有有效授权音色绑定时，runtime config 优先返回设备绑定音色，不被公司默认音色覆盖。
- [ ] 公司被授权多个 TTS 卡片后，公司 options 的扁平 `voices` 返回所有已授权卡片下的有效音色集合，并能按 provider/card 分组；公司侧选择任一音色后，配置 UI 按该音色所属卡片 schema 渲染，后端按该音色所属 provider adapter 发起请求。
- [ ] Qwen 与 CosyVoice 同时授权给同一公司时，选择 Qwen 音色只展示和保存 Qwen 公共配置，选择 CosyVoice 音色只展示和保存 CosyVoice 公共配置；两者不会复用或混入对方私有字段。
- [ ] Qwen 和 CosyVoice 的公司卡片配置分别存储；保存 CosyVoice 配置不会覆盖 Qwen `model_code/instructions`，保存 Qwen 配置不会把 Qwen 字段传入 CosyVoice。
- [ ] 统一 WebSocket `/ws/realtime/` 支持已授权 CosyVoice 音色：客户端仍发送 `tts.session.start`，后端向 CosyVoice 上游发送 `run-task`、`continue-task`、`finish-task`，并向客户端返回既有 `tts.ready`、二进制音频 chunk、`tts.done` 或 `tts.error`。
- [ ] 统一 WebSocket 在旧客户端不传 `providerCode` 时，也能根据 `voiceId`、设备绑定音色或公司默认音色解析出 CosyVoice provider 并正确路由；如果传了不匹配的 `providerCode`，返回明确错误。
- [ ] 设备/Agent 的实时 TTS 流也支持已授权 CosyVoice 设备绑定音色和公司默认音色，仍走统一 WebSocket 入口，不新增业务 WebSocket URL。
- [ ] 未实现 adapter、adapter 配置不完整或 adapter 不支持当前运行方式时返回明确错误，不跨 provider 回退；CosyVoice realtime adapter 不完整时不得通过验收。
- [ ] CosyVoice 卡片被授权给公司后，公司侧能看到并选择该卡片下有效音色；未授权公司完全看不到该卡片下音色，也不能通过 voiceId 调用成功。
- [ ] 停用仍被使用的卡片授权时返回 400，并包含至少公司默认、设备数量、设备应用数量中的命中信息。
- [ ] 授权停用或平台停用后，公司侧和设备侧响应不包含该音色；运行时不会回退到未授权平台默认音色。
- [ ] 公司侧和设备侧响应不包含明文供应商凭据、CosyVoice 定制接口地址或 provider 私有请求参数；公司侧只接收安全的公共配置 schema。
- [ ] 安卓不需要修改代码即可继续拉取运行时配置和请求 TTS：runtime config 仍返回 `resources.voiceTones[0].id/name/voiceCode/audioUrl/iconUrl/speechRate/pitchRate/volume`，HTTP TTS runtime 仍使用 `X-Device-Code` 并返回 `audio/pcm` 或 `audio/wav` 以及既有 `X-Audio-*` / `X-TTS-Voice` 响应头。
- [ ] 超管启用/停用 TTS 卡片授权、保存卡片 `publicConfig`、公司保存默认音色、平台启停或隐藏已授权音色后，已通过 `device.runtime_config.subscribe` 订阅的设备能收到 `device.runtime_config.subscribed`，`action=voiceConfigurationChanged`，并携带服务端重新构建的完整运行时配置。
- [ ] 前端公司 TTS 页面、设备管理页面和应用管理页面能消费新的 provider-neutral options contract，并兼容迁移期 `provider` 字段。
- [ ] 至少新增或更新后端回归测试覆盖授权可见性、越权 voiceId 拒绝、默认音色授权校验、使用中授权停用阻止、设备运行时过滤、CosyVoice 与 Qwen 并存。
- [ ] 前端构建通过 `npm run build`，后端目标 Django 测试通过 Docker Compose `--keepdb`。

## Out Of Scope

- 不把 CosyVoice 凭据分配给公司；公司只获得使用已授权卡片下远程自定义音色的权限。
- 不新增多个业务 WebSocket URL。
- 不在本任务内重做超管 CosyVoice 音色复刻、音色设计或远程删除流程，父任务已覆盖。
- 不在公司侧暴露供应商私有请求参数表单；后续新增卡片只扩展超管卡片和后端 adapter。
- MVP 不支持卡片内按公司排除单个音色；后续如需要，再新增 per-tenant voice deny/allow exception。
