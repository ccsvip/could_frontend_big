# 技术设计：隔离 Android 运行时唤醒词配置

## 根因与边界

OPPO 设备属于“索灵测试”，但历史多对多表把它关联到另一租户的“你好小乐”。`DeviceRuntimeConfigView._wake_words_payload` 只沿 `device.wake_words` 查询，未验证唤醒词租户，因此 HTTP 配置和 WebSocket 完整配置都会泄露该词。

Android 已收到错误的后端 HTTP 响应；不修改 Android 缓存或显示代码。

## 修复设计

1. `_wake_words_payload(device)` 在关联查询中同时约束 `tenant_id=device.tenant_id` 和 `is_active=True`。这使任何遗留或未来意外跨租户关系均无法进入运行时配置。
2. 新增数据迁移，删除唤醒词所属租户与设备所属租户不一致的多对多关联。迁移只删关系表的无效行，不删任一唤醒词或设备；空租户关系也视为无效。
3. 迁移位于 `0025_repair_wakeword_primary_key` 之后。既有创建/更新 Serializer 的跨租户校验保持不变。
4. HTTP `GET /api/v1/device-runtime/config/` 与 `device.runtime_config.subscribed` 都复用 `_config_payload`，无需改变接口或 WebSocket 协议；修复后二者自动返回相同的租户内完整配置。

## 兼容性与回滚

- 有效同租户绑定不受影响。
- 无效跨租户绑定从业务约束看从不合法；回滚不恢复已清理的错误关联。
- 在迁移尚未执行的短暂窗口，运行时查询过滤已经阻止泄露；迁移完成后持久数据也一致。

## 验证

- 用历史无效关联构造设备租户 A、唤醒词租户 B 的场景，断言 HTTP 与 WebSocket 完整配置均不含 B 的唤醒词。
- 断言迁移仅移除跨租户关联、保留有效关联。
- 对实际 OPPO 设备码请求配置，断言“你好小乐”不再返回且“你好小灵”仍存在。
