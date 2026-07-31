# 修复 cosyvoice TTS 卡片授权测试失败

## Goal

让 CosyVoice 卡片在**任何新建环境**里都能被超管分配给公司，并让 `test_tts_card_authorization_api.py` 的 3 个失败用例转绿。

当前 `cosyvoice` 这张 TTS 卡片只以**手工数据**形式存在于现网库（`ai_models_ttsprovider.id=4`），没有任何 migration 播种它。后果分两层：

1. **测试层**：测试库只跑 migration，`0015_tts_settings` 只播种 `aliyun`，于是 `TTSProvider.objects.get(code='cosyvoice')` 抛 `DoesNotExist`。
2. **产品层（更要紧）**：`CosyVoiceTTSAdapter` 已在 `tts_adapters._ADAPTERS` 注册，而 `TenantTTSCardAuthorizationView._response_payload` 的候选来源是 `grantable_tts_providers()`（即 `TTSProvider.objects.all()`）与 adapter 注册表的**交集**。任何全新部署（新客户、重建库、CI）都没有 `cosyvoice` 行 → 超管在「公司 TTS 卡片授权」页面永远看不到 CosyVoice，功能等于不存在。`0043_cosyvoice_settings` 建了 `CosyVoiceSettings`（对 `TTSProvider` 的 OneToOne），却没有建被指向的那张卡片行，属于同一处遗漏。

## Requirements

- 以数据 migration 幂等播种 `code='cosyvoice'` 的 `TTSProvider` 行，向 `0015_tts_settings` 播种 `aliyun` 的既有写法对齐。
- **不得覆盖**现网已存在的 `cosyvoice` 行上任何已配置字段（`api_key` / `base_url` / `model` / `sample_rate` / `tts_session_config` / `default_voice` / `is_active`）。现网这行是人工配好的，migration 只负责"缺则补"。
- CosyVoice 的运行时凭据归属不变：仍在 `CosyVoiceSettings`，本任务不把密钥搬进 `TTSProvider`。
- 播种一张卡片行即可，**不**播种 CosyVoice 音色（音色来自音色复刻/设计流程，`CosyVoiceProfile` 逐条产生，不存在固定清单）。
- 不改 `TenantTTSCardAuthorizationView` / `grantable_tts_providers()` / adapter 注册表的现有行为与契约。
- 不修改 3 个失败用例的断言来迁就现状——它们表达的期望（新环境应能看到并分配 CosyVoice）是对的，缺的是播种。

## Constraints

- 新迁移接在 `ai_models/0046_llmprovider_api_protocol` 之后，编号 `0047`。
- 必须可逆但**不得毁数据**：数据 migration 无法区分「本次新建的行」与「现网人工建的行」，所以 `reverse` 定为 `migrations.RunPython.noop`（可回滚、不删卡片）。理由：误删现网 `id=4` 那张已被公司授权引用的卡片会级联删掉 `TenantTTSProviderGrant`（`on_delete=CASCADE`），代价远高于回滚后多留一行。如实现者想改成真删，必须先给出区分依据。
- 播种默认值不得引入新的 settings/env 依赖；CosyVoice 端点默认值取 `apps.ai_models.services.cosyvoice` 里的既有常量或留空。

## Acceptance Criteria

- [ ] `docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_card_authorization_api --noinput` 全绿（原 1 failure + 2 errors 归零）。
- [ ] `docker compose exec backend python manage.py test apps.ai_models apps.devices --noinput` 相对基线无新增失败（基线：本任务开工前除这 3 条外的结果）。
- [ ] 在现网库上 `migrate` 后，`TTSProvider.objects.get(code='cosyvoice')` 的 `id` 仍为 4，且 `api_key` / `base_url` / `model` / `sample_rate` / `tts_session_config` / `default_voice_id` / `is_active` 与迁移前逐字段一致（迁移前后各 dump 一次比对）。
- [ ] 全新库（`migrate` 到最新）上 `TTSProvider.objects.filter(code='cosyvoice').exists()` 为真，且 `GET /api/v1/settings/tts/tenants/<id>/card-authorizations/` 的 `providers[].code` 含 `cosyvoice`。
- [ ] `manage.py migrate ai_models 0046` 反向执行不报错，且现网那张人工卡片与其公司授权（`TenantTTSProviderGrant`）仍在。
- [ ] `manage.py check` 0 issues。

## Out of Scope

- 07-31 的 Sentry `PYTHON-DJANGO-47` / `-48`（`ImportError: TenantTTSProviderGrant`）。那次是切分支后未重启 `solin_backend` 造成的进程内模块缓存错配，源码无缺陷，已重启恢复并在 Sentry 备注根因后关闭。
- CosyVoice 音色复刻 / 音色设计链路本身。
- 给 CosyVoice 卡片补默认音色或默认 `tts_session_config` 调优。
