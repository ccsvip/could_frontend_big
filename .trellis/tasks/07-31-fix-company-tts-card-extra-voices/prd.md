# 移除公司 TTS 卡片异常 Loong 音色

## Goal

从阿里云/Qwen TTS 卡片中移除数据库里异常残留的 54 个 `long*` / `loong*` 音色，确保公司侧只看到仓库定义的 48 个正常 Qwen 音色。

## Background

- 已直接检查当前 Docker 数据库：阿里云卡片共有 102 个音色，其中 48 个与 `backend/apps/ai_models/migrations/0015_tts_settings.py` 的规范种子一致，另外 54 个是 ID 103–156、编码以 `long` / `loong` 开头的异常音色。
- 异常集合从 `龙昂扬 (Long Anyang)` / `longanyang` 开始，到 `Bella 3.0 (Loongbella V3)` / `loongbella_v3` 结束；全部处于 `is_active=true`、`is_visible=true`。
- Git 历史 `19ea4ca`（2026-06-15，添加 TTS 音色资源）只包含当前 48 个正常音色；全仓历史没有提交这些 54 个 Loong 音色，说明它们不是当前代码或规范种子的一部分，而是现有数据库中的历史残留数据。
- 最近提交 `ea290f5`（2026-07-30）把公司 options 从“按当前 Qwen model profile 过滤”改成“返回已授权卡片的全部启用且可见音色”，因此这 54 条历史残留首次全部暴露到公司侧。`54d669d` 的目录正文又直接遍历 `options.voices`，使问题在页面上完整可见。
- 引用检查结果：54 个异常音色的公司默认引用数为 0、设备绑定数为 0、设备应用引用数为 0，可以安全清理，不会使现有绑定失效。

## Requirements

- 通过可审计、可随部署执行的数据迁移，删除阿里云 provider 下精确匹配异常清单的 54 个音色。
- 删除条件必须同时限定 `provider.code='aliyun'` 和明确的 54 个 `voice_code`，不得用宽泛前缀误删未来合法音色。
- 保留规范种子中的 48 个正常 Qwen 音色，包括 Dylan、Jada、Sunny、Jennifer 等标准播报音色。
- 保留 CosyVoice 及其复刻/设计音色；不得影响公司卡片授权、默认音色、设备运行时、HTTP TTS 或统一 WebSocket 契约。
- 公司侧音色目录正文应使用已计算的 `availableVoices`，与下拉选择器和“可用 N 个”计数保持一致，避免以后数据库出现不支持当前 profile 的音色时再次全部显示。

## Acceptance Criteria

- [ ] 数据迁移前可识别 54 个异常 Loong 音色；迁移后阿里云卡片只剩规范的 48 个正常音色。
- [ ] `longanyang`、`longanhuan_v3`、`loongkyong_v3`、`longhua_v3`、`loongbella_v3` 等异常编码均不存在。
- [ ] Cherry、Dylan、Jada、Sunny、Jennifer、Radio Gol 等正常音色仍存在。
- [ ] CosyVoice 自定义音色数量和内容不变。
- [ ] 公司侧目录、选择器和可用数量使用同一可用音色集合。
- [ ] 相关 Django 测试通过，前端 `npm run build` 通过。

## Out of Scope

- 修改 TTS 卡片授权粒度。
- 删除或隐藏规范种子中的正常 Qwen 音色。
- 修改第三方上游音色资源。
