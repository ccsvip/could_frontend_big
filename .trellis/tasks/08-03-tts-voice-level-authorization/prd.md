# TTS 音色级授权与公司隔离

## Goal

让超管能按公司灵活分配 TTS 音色（数量不固定，可多可少），并堵住 CosyVoice 复刻音色跨公司可见的隔离缺口。

## Background

超管后台 `/settings/tts` 现有两个入口：卡片列表页（`web/src/views/tts-settings/index.tsx`）和公司卡片授权页（`web/src/views/tts-card-authorization/index.tsx`）。当前授权单位是「卡片」，无法表达「A 公司 3 个音色、B 公司 20 个音色」。以下事实均已在代码中核实。

### 授权模型现状

- `TenantTTSProviderGrant` 唯一约束 `(tenant, provider)`，无音色维度（`backend/apps/ai_models/models.py:722-747`）。
- 可用音色推导：卡片有 active grant → 该卡下所有 `is_active + is_visible` 音色全部可用（`backend/apps/ai_models/services/tts_authorization.py:26-44`）。只有「0 个」和「全部」两态。
- 前端已把该限制写死在提示里：「MVP 不支持在卡片内排除单个音色」（`web/src/views/tts-card-authorization/index.tsx:185`）。
- `TenantTTSProviderGrant.public_config` 承载「该公司在这张卡上的会话参数」，与音色授权是两件事。
- 已有 per-item 授权先例可参照：`TenantLLMModelGrant`（`models.py:100`）。

### 唯一入口（改造受益点）

`tts_authorization.py` 是唯一 sanctioned 入口，消费方已全部收敛：

- `apps/ai_models/views.py`（公司选项 / 默认音色保存 / 公司试听 / 设备 runtime）
- `apps/devices/serializers.py:55`（设备音色可选集）、`apps/devices/views.py`
- `apps/ai_models/realtime_tts.py:173` `:176` → `config/realtime.py:1909` `:2424`（实时 WS）

因此授权推导下沉到音色级后，上述调用点无需改签名。

### `is_visible` 语义

- `TTSVoice.is_visible`（`models.py:623`）是平台级全局字段。
- 但超管卡片详情页该列表头写的是「公司可见」（`web/src/views/tts-settings/index.tsx:356`），语义误导。
- 已产生过真实事故：`9dbab53 修复公司 TTS 卡片异常 Loong 音色越权展示`（删除 54 个残留 `long*/loong*` 音色 + 公司侧改用 `availableVoices`）。
- `is_visible` 判定散落在授权链路之外：`services/tts.py:197` `:206`、`realtime_tts.py:103` `:117` `:206`、`views.py:547`、`serializers.py:652`、`devices/serializers.py:54`。
- 其中 `realtime_tts.py:90 resolve_tts_voice` 已是死代码：仅被 `test_tts_api.py:703` 引用，`config/realtime.py` 两处入口已全部改用 `resolve_realtime_tts_voice`。它含 3 处绕过授权推导的裸判定。

### 现有取消授权保护

卡片级硬阻断：`canDisableGrant`（`views.py:1356`）+ `_validate_disable_not_in_use`（`serializers.py:655-676`），检查公司默认音色 / `Device.tts_voice` / `DeviceApplication.tts_voices` 三处引用。

### CosyVoice 归属缺口

- `CosyVoiceProfile`（`models.py:668-691`）只有 `voice` 外键，**无 tenant**；`TTSVoice` 也无 owner 字段。
- 复刻/设计出的音色落进共享 `cosyvoice` provider 池，任何被授权该卡片的公司都能看到并合成 → A 公司的代言人音色可被 B 公司使用。
- 当前 `CosyVoiceEnrollView` / `CosyVoiceDesignView` / `CosyVoiceVoiceDetailView` 均为 `IsSuperUser`（`views.py:563` `:576` `:589`），尚未开放公司自助，所以现在是「结构性隔离缺口」而非「已被利用的越权」。

## Requirements

### R1 授权粒度下沉到音色级

- `TenantTTSProviderGrant` 保留为「凭证 + 会话参数 + 卡片开关」边界，新增 `grant_mode`：`all`（卡下全部音色）/ `selected`（仅勾选音色）。
- 新增 `TenantTTSVoiceGrant(tenant, voice, is_active)`，唯一约束 `(tenant, voice)`，参照 `TenantLLMModelGrant` 形态。
- 授权推导仍只改 `get_effective_tts_voices_for_tenant` 一处：`grant_mode='all'` 或存在 active 音色 grant。
- 存量 grant 全部落在 `grant_mode='all'`（由字段 default 保证），上线行为零变化。
- 平台新增音色：`all` 模式公司自动获得；`selected` 模式公司默认不可用（不自动补授）。
- 不引入数量配额（`apps/tenants` 目前无任何配额概念，避免新造商业套餐抽象）。

### R2 `is_visible` 语义澄清

- 不重命名字段（避免与主线 diff 混在一起，也不动 API 契约 `isVisible`）。
- `TTSVoice.is_visible` 的 `verbose_name` 改为「平台上架」（`models.py:623`），超管卡片详情页列头「公司可见」同步改为「平台上架」（`web/src/views/tts-settings/index.tsx:356`）。
- 授权页面的「全局可用/全局停用」列语义保持不变（`tts-card-authorization/index.tsx:249-253`），公司维度可用性由该行的「公司可用」标签承担。
- 把授权链路之外的裸 `is_visible` 判定收归到 `tts_authorization`，公司侧可见性只有一个来源：
  - `services/tts.py:195 get_available_tts_voices` / `:203 is_voice_available` 只服务平台维度，加 docstring 明确「非公司维度，禁止用于公司可用性判定」。
  - `apps/devices/serializers.py:54` 超管旁路保持（超管看平台全集）。
  - `serializers.py:652` 默认音色校验改为走授权推导，替掉裸 `is_visible` 检查。
  - `views.py:547`（CosyVoice 超管试听）属平台维度，保留。
- 删除死代码 `realtime_tts.py:90 resolve_tts_voice` 及其唯一引用 `test_tts_api.py:703-707`。

### R3 CosyVoice 复刻音色归属公司

- `TTSVoice` 新增 `owner_tenant`（FK → `tenants.Tenant`，`null=True` = 平台公有音色）。
- 授权推导内部硬过滤：`owner_tenant IS NULL OR owner_tenant = <当前公司>`。不在页面层过滤。
- 复刻 / 设计接口支持指定归属公司，留空即平台公有；存量音色为 `null`（保持现有行为）。
- 归属不等于授权：私有音色仍需公司持有该卡 grant，且在 `selected` 模式下仍需超管勾选。推导规则保持单一，无例外分支。
- 超管侧仍可见全部音色（`devices/serializers.py:52` 超管旁路语义不变）。

### R4 取消勾选的使用中保护

- 沿用现有卡片级硬阻断语义（`serializers.py:655 _validate_disable_not_in_use`），下沉到音色维度。
- 触发条件：某音色本次保存后将失授权（取消勾选，或 `all → selected` 且未勾选），且仍被公司默认音色 / `Device.tts_voice` / `DeviceApplication.tts_voices` 引用。
- 行为：整个 PUT 400 失败，错误信息带引用位置计数，与卡片级现有文案风格一致。
- 授权页 GET 为每个音色返回 `canRevoke`，前端在勾选框上禁用并提示，避免保存后才报错。

### R5 超管授权页承载音色级操作

- 每张卡片头部新增授权范围切换：「全部音色」/「指定音色」，对应 `grantMode`。
- 「指定音色」模式下每个音色行出现勾选框；「全部音色」模式下勾选框隐藏或整体置灰。
- 卡片头部显示「已授权 N / 共 M 个音色」，取代当前固定的「M 个音色」（`tts-card-authorization/index.tsx:217`）。
- 删除已过期的提示文案「MVP 不支持在卡片内排除单个音色」（`tts-card-authorization/index.tsx:185`）。
- 私有音色行显示归属公司标签；非当前公司名下的私有音色不出现在该公司的授权列表里。
- PUT 契约扩展为 `cardGrants: [{ providerId, isActive, grantMode, voiceIds }]`，`defaultVoiceId` 不变。

## Acceptance Criteria

数据与迁移
- [x] 迁移后所有存量 `TenantTTSProviderGrant.grant_mode == 'all'`，所有存量 `TTSVoice.owner_tenant is None`。
- [x] 迁移前后同一公司的 `get_effective_tts_voices_for_tenant` 结果集完全一致（回归测试对比 id 集合）。

R1 音色级授权
- [x] `grant_mode='all'` 时公司获得卡下全部 `is_active + is_visible` 音色（与现有行为一致）。
- [x] `grant_mode='selected'` 时公司仅获得 active 音色 grant 覆盖的音色；未勾选音色不出现在公司选项、设备可选集、试听、runtime 与实时 WS 任一路径。
- [x] `selected` 模式下新增平台音色后，公司不会自动获得它。
- [x] 卡片 grant `is_active=False` 时，即使音色 grant 存在也不可用（卡片开关优先）。
- [x] 一家公司同时持有「A 卡 all + B 卡 selected」时两卡结果集互不影响。
- [x] 未授权音色 id 走 `ensure_tts_voice_authorized_for_tenant` 仍返回统一文案「所选音色未授权或已停用」，不泄露 id 是否存在。

R2 语义澄清
- [x] `realtime_tts.py resolve_tts_voice` 已删除，全仓无引用（`grep` 为空），实时链路测试仍通过。
- [x] 默认音色保存校验不再直接读 `voice.is_visible`，改由授权推导判定。

R3 归属隔离
- [x] `owner_tenant=A` 的音色：A 公司在 `all` 模式下可用；B 公司即使持有同卡 `all` 模式 grant 也拿不到，且授权页上看不到该音色。
- [x] B 公司显式提交 A 公司私有音色 id 作为默认音色 / 设备音色 / runtime voiceId，全部 400。
- [x] `owner_tenant=None` 的平台公有音色行为与迁移前一致。

R4 使用中保护
- [x] 取消勾选仍被公司默认音色引用的音色 → PUT 400，错误信息含引用位置。
- [x] 取消勾选仍被设备或设备应用引用的音色 → PUT 400，且数据库未发生任何写入（事务回滚）。
- [x] 同一次 PUT 内既取消勾选、又把该音色设为默认音色 → 400（校验基于保存后状态，而非保存前）。
- [x] 授权页 GET 对上述音色返回 `canRevoke=false`。

R5 页面
- [x] 超管可在同一家公司的一张卡上从「全部音色」切到「指定音色」并只勾 2 个音色，保存后公司侧只看到这 2 个。
- [x] 两家公司在同一张卡上可各自持有不同数量的音色授权，互不影响。
- [x] `npm run build`（含 `tsc -b`）通过。

回归
- [x] `python manage.py test apps.ai_models apps.devices` 无本任务引入的新失败（`apps.ai_models` 334 → 337，新增 3 条 CosyVoice 归属测试；余下 10 条 RAG 失败与 4 条 devices 失败在 HEAD 上即存在，与本任务无关）。

## Out of Scope

以下均为本次评审中确认存在、但不在本任务范围的问题，锚点一并留存以便后续单独立项：

- **授权审计字段与并发保护**：`granted_by` / `valid_until` / 版本号乐观锁。`PUT` 目前是整份覆盖写且无版本号（`views.py:1398`），并发下静默后写覆盖。
- **默认音色失授权的显式信号**：现状是静默回落 `authorized.first()`（`tts_authorization.py:74-78`），无任何提示；GET payload 未来可加「默认音色已失效」标记。
- **授权页 GET 查询优化**：每音色约 4 次查询（`views.py:1365-1382`），且 `views.py:1347` 的 `order_by` 使 `prefetch_related('voices')` 失效；粒度下沉后会更重。可用聚合 `values().annotate(Count)` 替掉 per-voice 查询。
- **adapter 层供应商知识外泄收敛**：后端 2 处 + 前端 2 处硬编码 provider code。
- **授权页多公司交互**：`page_size: 1000` 改分页搜索、脏态保护、保存前 diff 预览。
- **公司自助复刻 CosyVoice 音色**：本任务只补归属字段与隔离推导，不开放非超管入口。
- **数量配额（`voice_quota`）**：`apps/tenants` 无配额概念，不新造商业套餐抽象。
