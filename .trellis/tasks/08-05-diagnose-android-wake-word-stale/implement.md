# 实施计划：隔离 Android 运行时唤醒词配置

## 实施顺序

1. 读取后端数据库、权限和测试规范；核对唤醒词多对多关系的历史模型与迁移编号。
2. 修改 `DeviceRuntimeConfigView._wake_words_payload`：按设备租户和启用状态过滤关联唤醒词。
3. 新增数据迁移，删除 `WakeWord.tenant_id != Device.tenant_id`（含任一空租户）的关联表行，不删除业务实体。
4. 添加回归测试：构造绕过 Serializer 的历史跨租户关联；HTTP 配置与 WebSocket 完整配置只返回同租户唤醒词；迁移只清理无效关联。
5. 在 Docker Compose 中应用迁移，使用目标 OPPO 设备码验证“你好小乐”消失、“你好小灵”仍存在，并确认 WebSocket 刷新载荷一致。

## 验证命令

```powershell
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py migrate --check
docker compose exec backend python manage.py makemigrations --check --dry-run
```

## 风险与控制

- 迁移删除关系行是不可逆的数据清理；范围以租户不匹配为唯一条件，当前开发库为 1 条。
- 运行时过滤是防泄露边界，不能仅依赖一次性数据清理。
- 保持既有 `X-Device-Code`、REST 响应字段、统一 WebSocket `type` 与完整配置契约不变。
