# 排查安卓唤醒词未刷新

## Goal

找出并修复 Android 设备在后台删除唤醒词后仍显示“你好小乐”的原因，确保设备运行时配置与后台当前数据一致。

## Confirmed Facts

- 目标设备是“索灵测试”租户的 OPPO PKC110，设备码为 `fa72a823000fccf169f95f41ca7fd67c1c578da77bae15d2635512aeb2a131fc`。
- `GET /api/v1/device-runtime/config/` 使用该设备码返回 HTTP 200，且实际返回了“你好小乐”和“你好小灵”。因此 Android 显示“你好小乐”不是本地缓存或 WebSocket 未刷新。
- “你好小乐”(ID 14) 属于“北京应天海乐科技发展有限公司”；OPPO 设备(ID 11) 属于“索灵测试”。两者存在一条历史跨公司多对多绑定；当前库共检测到 1 条此类无效绑定。
- `DeviceRuntimeConfigView._wake_words_payload` 仅按 `device.wake_words.filter(is_active=True)` 查询，未再次约束 `WakeWord.tenant_id == device.tenant_id`，故将这条无效绑定泄露到设备运行时配置。
- 删除端点及统一 WebSocket 刷新机制均会重建并推送完整配置；WebSocket 最终也调用同一 `_config_payload`，所以根因位于后端配置查询而非 Android UI。

## Requirements

1. 用可重复的设备码请求或等价测试确认 Android 实际接收的唤醒词配置。
2. 定位“你好小乐”来自后端当前数据、设备绑定、旧 WebSocket 消息，还是 Android 本地缓存。
3. 若需要修复，删除后 Android 不经重新安装即可得到完整且最新的唤醒词配置。
4. 不改变租户隔离、设备码认证或统一 WebSocket 协议。

## Acceptance Criteria

- [ ] 能以设备码确认目标 Android 的 `GET /api/v1/device-runtime/config/` 响应及其唤醒词字段。
- [ ] 能明确解释“你好小乐”的来源，并有可复现的红/绿验证路径。
- [ ] 修复后目标设备显示与后台当前绑定唤醒词完全一致，删除词不再出现。
- [ ] 关联的 HTTP / WebSocket / Android 缓存路径均不回归。

## Out of Scope

- 不修改无关设备、TTS、智能体或唤醒词文本规则。

## Key Decision

- 持久化层清除全部跨租户唤醒词—设备关联；运行时查询同时强制 `WakeWord.tenant_id == device.tenant_id` 作为纵深防御。当前仅有 OPPO—“你好小乐”这一条无效关联。

## Open Questions

- 无。
