# 修复唤醒词删除服务器错误

## Goal

让任意公司在 `/devices?tab=wakeWords` 中删除指定唤醒词时稳定返回成功；修复“索灵测试”现有重复 ID 数据，且不影响任一公司其他唤醒词。

## Confirmed Facts

- 后端日志确认 `DELETE /api/v1/wake-words/1/` 连续返回 `500 Internal Server Error`。
- `devices_wakeword` 当前没有任何 PostgreSQL 约束；`id=1` 同时存在“你好小灰”和“你好小灵”两行，违反 Django 模型及 `0016_wakeword.py` 所声明的主键约束。
- 两条 `id=1` 记录在 ORM 查询中都显示绑定同一设备；现有中间表引用无法区分绑定原本属于哪一条重复记录。
- 现有 `perform_destroy` 与前端 `deleteWakeWord` 均按 ID 定位；重复 ID 使详情删除查询不唯一，从而导致 500。
- 现有单条删除回归测试通过，但未覆盖数据库主键约束缺失及重复 ID 的历史数据。

## Requirements

1. 在全表范围修复所有重复唤醒词 ID 并恢复主键约束，使任意公司中的每条唤醒词均有稳定、全局唯一的 ID。
2. 删除任意公司的一条唤醒词返回 HTTP 204；同公司和其他公司的未删除唤醒词及其配置继续可用。
3. 修复后仍向关联运行时设备发布完整的唤醒词配置刷新事件。
4. 迁移必须对已具备正确主键约束的数据库安全、幂等地跳过数据修复。

## Acceptance Criteria

- [ ] “索灵测试”租户原先 ID 冲突的两条唤醒词可分别显示并分别删除；删除一条后另一条仍存在。
- [ ] 任一公司均不能存在重复唤醒词 ID；删除一家公司的一条唤醒词不会删除、修改或阻断其他公司唤醒词的读取与删除。
- [ ] `devices_wakeword.id` 具有主键约束，数据表不再包含重复 ID，序列下一值大于现有最大 ID。
- [ ] 目标 Django 测试覆盖同公司定向删除、跨公司隔离、删除事件契约及异常历史数据修复。
- [ ] `docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb` 通过。

## Out of Scope

- 不改变唤醒词文本规则、设备绑定 UI 或实时事件协议。
- 不修改无关设备、应用或语音功能。

## Key Decision

对于重复 ID 的历史数据，保留创建时间最早的记录及其现有设备绑定；在当前数据中即保留“你好小灰”的绑定。后续重复记录重新分配唯一 ID 且保持未绑定，避免把无法归属的旧绑定复制到多个唤醒词。
