# Implement — TTS 音色级授权与公司隔离

按依赖顺序分 6 步。每步结束都能独立跑通验证命令，中途中断不会留下半破状态。

## 前置

```bash
docker compose exec backend python manage.py test apps.ai_models apps.devices
```

先记录**改动前**的基线（应该全绿）。R1 的迁移前后等价性验收依赖这条基线。

## Step 1 — 数据模型与迁移

改 `backend/apps/ai_models/models.py`：

- [x] `TenantTTSProviderGrant` 加 `GRANT_MODE_ALL` / `GRANT_MODE_SELECTED` / `GRANT_MODE_CHOICES` 常量与 `grant_mode` 字段（design §2.1）
- [x] 新增 `TenantTTSVoiceGrant`，照 `TenantLLMModelGrant`（`models.py:100-125`）抄形状，含 `objects = TenantManager()` 与 `uniq_tenant_tts_voice_grant` 约束（design §2.2）
- [x] `TTSVoice` 加 `owner_tenant`（`null=True, blank=True, on_delete=CASCADE, related_name='owned_tts_voices'`）。**不要**给 `TTSVoice` 加 `TenantManager`（design §2.3 明确禁止）
- [x] `TTSVoice.is_visible` 的 `verbose_name` 改为「平台上架」（`models.py:623`）

```bash
docker compose exec backend python manage.py makemigrations ai_models
```

- [x] 确认生成 `0049` 起的迁移，且**没有** `RunPython` 回填（design §7：default 与 null 已让存量落在行为不变的位置）
- [x] 若 makemigrations 把三处并成一个文件，手工拆成 0049/0050/0051 以便单独回滚

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test apps.ai_models apps.devices
```

此时行为应与改动前完全一致（只加了列，没人读）。

## Step 2 — 授权推导（核心）

改 `backend/apps/ai_models/services/tts_authorization.py`：

- [x] `get_effective_tts_voices_for_tenant` 按 design §3 加两个 `.filter()`
- [x] **守住 §3 不变量 2**：`grant_mode` 条件必须与 `provider__tenant_grants__tenant/is_active` 在**同一个** `.filter()` 调用里
- [x] **守住 §3 不变量 3**：末尾 `.distinct()` 不能丢
- [x] 新增 `tts_voice_grant_ids_for_tenant(tenant, provider)`（design §3.1）
- [x] 其余 8 个函数签名与行为不动

先写测试再改实现，`backend/apps/ai_models/tests/test_tts_authorization.py` 补：

- [x] `all` 模式行为与今天一致（对比 id 集合）
- [x] `selected` 模式只返回 active 音色 grant 覆盖的音色
- [x] 卡片 grant `is_active=False` 时音色 grant 也不生效
- [x] **「A 卡 all + B 卡 selected」组合**（design §9 首要风险）：断言两卡结果集互不影响
- [x] `owner_tenant=A` 的音色：A 可见、B 不可见
- [x] `owner_tenant=None` 行为不变
- [x] `selected` 模式下新增平台音色不自动进入公司集合
- [x] 结果集长度断言（防 `.distinct()` 丢失）

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_authorization
```

## Step 3 — 收归裸 `is_visible` 判定 + 删死代码

- [x] `services/tts.py:195 get_available_tts_voices` / `:203 is_voice_available` 加 docstring：「平台维度，禁止用于公司可用性判定」（prd R2）
- [x] `serializers.py:652` 的裸 `not voice.is_visible` 换成授权推导（具体写法见 Step 4，两处是同一个改动点）
- [x] 删除 `realtime_tts.py:90 resolve_tts_voice` 及唯一引用 `tests/test_tts_api.py:703-707`
- [x] `views.py:547`（CosyVoice 超管试听）、`devices/serializers.py:54`（超管旁路）**保留不动**

```bash
grep -rn "resolve_tts_voice" backend/    # 只应剩 resolve_realtime_tts_voice
docker compose exec backend python manage.py test apps.ai_models apps.devices
```

## Step 4 — API 契约（GET / PUT / 校验 / 写入）

`backend/apps/ai_models/serializers.py`（`TenantTTSCardAuthorizationSerializer`, 581-676）：

- [x] 归一化 grants 时解析 `grantMode`（缺省 `all`）与 `voiceIds`；校验每个 id 属于该 provider 且 `owner_tenant in (None, tenant)`；跨公司 id 与不存在 id 共用同一条文案防探测（design §4.3.1）
- [x] `_validate_default_voice`：基于 `normalized_grants` 推演**保存后**的可用集合来判断，不要调 `is_tts_voice_effective_for_tenant`（读的是保存前状态 —— design §4.3.2，第二大风险）
- [x] 新增 `_validate_voice_revocation_not_in_use`：失授权集合 = 保存前可用 − 保存后可用；逐个查 `tts_voice_usage_for_tenant`，非空即 400，文案带引用位置计数，风格对齐 `_validate_disable_not_in_use`（`serializers.py:655-676`）
- [x] 校验顺序：卡片级 `_validate_disable_not_in_use` 先判，命中即抛，不与音色级重复报错

`backend/apps/ai_models/views.py`（`TenantTTSCardAuthorizationView`, 1314-1416）：

- [x] `_response_payload` 每张卡加 `grantMode` / `authorizedVoiceCount`
- [x] `_voice_payload`（1365-1382）加 `voiceGrantIsActive` / `canRevoke` / `ownerTenant`
- [x] 卡片音色列表（`views.py:1347`）过滤掉 `owner_tenant` 属于其他公司的音色（design §4.1）
- [x] `put` 事务内追加音色 grant 同步：仅 `selected` 模式下 upsert 目标集合 `is_active=True`、其余置 `False`；`all` 模式不清空已有勾选（design §4.4）
- [x] `publish_tenant_tts_config_changed` 仍在事务内、写入之后

测试 `tests/test_tts_card_authorization_api.py`：

- [x] 旧 payload（无 `grantMode`）语义不变
- [x] `all → selected` 只勾 2 个，GET 与公司选项都只剩 2 个
- [x] 同一 PUT 内「取消勾选 + 设为默认」被拒
- [x] 取消勾选被默认音色 / 设备 / 设备应用引用的音色 → 400 且事务回滚（断言库里没写入）
- [x] `canRevoke=false` 出现在上述音色上
- [x] B 公司提交 A 公司私有音色 id → 400，文案与不存在 id 相同
- [x] 两家公司同卡各持不同数量互不影响

```bash
docker compose exec backend python manage.py test apps.ai_models apps.devices
```

## Step 5 — CosyVoice 归属写入

- [x] `services/cosyvoice.py:_create_voice` 加 `owner_tenant=None` 参数并透传给 `TTSVoice.objects.create`；`enroll_cosyvoice_voice` / `design_cosyvoice_voice` 同步加参数
- [x] `sort_order` 计算（`cosyvoice.py:204`）保持平台维度不变
- [x] `CosyVoiceEnrollSerializer` / `CosyVoiceDesignSerializer` 加可选 `ownerTenantId`（空 = 平台公有，非空须 active 公司）
- [x] 视图权限仍 `IsSuperUser`，不开放公司自助

- [x] 测试：带 `ownerTenantId` 复刻 → 该公司可用、另一公司拿不到；不带 → 全平台行为不变

## Step 6 — 前端

`web/src/api/modules/tts.ts`：

- [x] `TenantTtsCardGrantPayload` 加 `grantMode?` / `voiceIds?`
- [x] `TenantTtsCardAuthorization` 加 `grantMode` / `authorizedVoiceCount`
- [x] `TenantTtsCardAuthorizationVoice` 加 `voiceGrantIsActive` / `canRevoke` / `ownerTenant`

`web/src/views/tts-card-authorization/index.tsx`：

- [x] 卡片头部加「全部音色 / 指定音色」Segmented（只改本地 state，保存时统一 PUT，与 `toggleGrant` 同风格）
- [x] 头部计数 `{card.voices.length} 个音色`（line 217）→「已授权 N / 共 M 个音色」
- [x] `selected` 模式下音色行渲染 Checkbox；`canRevoke=false` 且已勾选时 disabled + Tooltip 说明引用位置
- [x] 删除 line 185 的过期 Alert
- [x] 私有音色行加归属公司 Tag
- [x] `saveAuthorization` 的 `cardGrants` 带上 `grantMode` / `voiceIds`

`web/src/views/tts-settings/index.tsx:356`：

- [x] 列头「公司可见」→「平台上架」

```bash
cd web && npm run build
```

## 最终验证

```bash
docker compose exec backend python manage.py test apps.ai_models apps.devices
cd web && npm run build
```

- [ ] 人工冒烟：同一家公司一张卡 `all → selected` 只勾 2 个 → 公司侧 `/ai-models/tts/options/` 只剩 2 个；设备可选集、试听、runtime 同步收窄（需起完整栈 + 超管登录，自动化等价覆盖已在 `test_tts_card_authorization_api` 里）
- [x] `detect_changes()` 确认改动范围只落在预期符号上（项目 CLAUDE.md 强制要求，提交前）

## 风险文件与回滚点

| 文件 | 风险 | 回滚点 |
|---|---|---|
| `services/tts_authorization.py` | 全部 6 条消费路径的唯一出口，写错即全量影响 | Step 2 结束；git revert 单文件即可 |
| `serializers.py` `_validate_default_voice` | 读保存前状态会放过非法组合 | Step 4 结束 |
| 迁移 0049/0050 | 回滚会丢音色勾选与归属数据（退回卡片级全部，无可用性事故） | 三个迁移拆开，可逐个 `migrate ai_models 0048` |
| `realtime_tts.py` 删死代码 | 无数据影响，但需确认 `config/realtime.py` 两处入口未被牵连 | Step 3 结束，`grep` 为空即安全 |

## 提交前检查

- [x] `python manage.py test apps.ai_models apps.devices` 全绿（`apps.devices` 缺 `__init__.py`，须显式点名四个测试模块；余下 RAG / device 失败为 HEAD 既有，与本任务无关）
- [x] `npm run build`（含 `tsc -b`）通过
- [x] prd Acceptance Criteria 逐条对照勾完
- [x] `.trellis/spec/backend/tts-tenant-card-authorization.md` 按 Phase 3.3 更新（授权推导契约已变，spec 必须同步）
