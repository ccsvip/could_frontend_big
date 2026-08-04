# 实施计划：修复唤醒词删除服务器错误

## 实施顺序

1. 读取 backend 规范和迁移测试约定。
2. 新增 `devices` 迁移：仅在缺失主键时全表修复重复 ID、保留每组最早记录绑定、建立主键并校准序列。
3. 为该迁移加入 PostgreSQL 数据修复回归测试，包含跨公司数据。
4. 扩展唤醒词 API 测试：同租户删除两条中的指定一条，以及跨公司隔离；验证 204、剩余记录与实时事件。
5. 在开发数据库应用迁移，确认“你好小灰”保留设备绑定、“你好小灵”得到新 ID 且可删除；核对其他公司唤醒词不受影响。

## 验证命令

```powershell
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api --keepdb
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test apps.devices.tests --keepdb
```

完成后检查：`devices_wakeword` 主键、全表无重复 ID、序列大于最大 ID；再从 `/devices?tab=wakeWords` 删除“你好小灵”，并读取另一家公司唤醒词确认可独立操作。

## 风险与控制

- 历史共享绑定没有可恢复归属。按确认决策保留给最早记录，绝不复制给重分配记录。
- 迁移只对缺少主键的异常表写入；健康库不执行修复。
- 不修改 API 或前端，减少回归面。