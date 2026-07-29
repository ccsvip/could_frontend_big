# 超管 CosyVoice v3.5-plus 管理

## Goal

在平台超管 `/settings/tts` 中增加与 Qwen3-TTS 完全隔离的 CosyVoice v3.5-plus 管理卡片、专属接口和专属配置页面。

CosyVoice 仅使用运营人员通过音色复刻或音色设计创建的远程音色；不提供、迁移或恢复任何 Qwen、Long、Loong 或推测的 CosyVoice 预置系统音色目录。

## Requirements

1. CosyVoice 卡片必须跳转到 `/settings/tts/cosyvoice`，不能打开通用 Qwen 设置页面。
2. 专属超管接口保存 API Key、WSS 实时地址、HTTPS 定制地址、启用状态、默认测试文本与默认自定义音色；API Key 仅加密存储且仅返回掩码。
3. 音色复刻只接受可访问的 HTTPS 音频 URL；音色设计只接受 `zh` 或 `en`；可选复用现有头像资源。
4. 仅持有 `CosyVoiceProfile` 的音色可列出、编辑、测试、设为默认或删除；删除必须先删除远程音色成功后才删除本地记录。
5. 通用平台 TTS 设置接口和统一实时 WebSocket 不得选择 CosyVoice；现有 Qwen 公司 API、音色逻辑和实时流程保持不变。

## Acceptance Criteria

- [ ] 仅超管可访问 CosyVoice 设置、试听、复刻、设计和音色管理接口。
- [ ] API Key 不会在响应中明文返回；WSS/HTTPS 地址和复刻音频 URL 的协议受到校验。
- [ ] CosyVoice 运行时 `session.update` 使用 `cosyvoice-v3.5-plus` 与自定义音色，且不携带 Qwen 专属字段。
- [ ] 通用 TTS 接口和 WebSocket 拒绝 CosyVoice，不会回退或泄露其专属凭据。
- [ ] 前端构建与目标后端回归测试通过。
