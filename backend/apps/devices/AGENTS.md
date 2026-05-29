[backend](../../AGENTS.md) > apps > **devices**

# apps/devices AGENTS.md

## OVERVIEW

数字人设备 CRUD + 状态统计 + 两个启动种子命令。业务模型很小，但种子命令参与 compose 启动链路。

## STRUCTURE

```
devices/
├── models.py                         # Device(code/name/location/status/last_heartbeat)
├── serializers.py                    # list/detail/stats payload
├── views.py                          # DeviceViewSet + /devices/stats/
├── admin.py                          # SimpleUI 设备后台
├── urls.py                           # /devices/*
└── management/commands/
    ├── seed_devices.py               # 开发演示设备种子
    └── seed_operations_periodic_tasks.py # 系统运维 Celery beat 种子
```

## WHERE TO LOOK

| 任务 | 位置 | 注意 |
|------|------|------|
| 改设备字段 | `models.py` + `serializers.py` + `admin.py` | `code` 是外部稳定标识 |
| 改设备 API | `views.py` | lookup 不是 pk |
| 改统计 | `views.py:stats` | 当前缓存 key 为 `device_stats` |
| 改启动默认设备 | `management/commands/seed_devices.py` | compose 每次 backend 启动都会跑 |
| 改周期任务种子 | `management/commands/seed_operations_periodic_tasks.py` | 虽在 devices app，实际是系统运维任务 |

## CONVENTIONS

- **lookup_field = `code`**：详情/更新/删除路由用设备编号，不用数据库 id。
- **种子命令幂等**：两个命令都用 `update_or_create` / `get_or_create`，必须可重复执行。
- **启动链路依赖**：根 `docker-compose.yaml` 的 backend command 固定跑 `seed_operations_periodic_tasks` 和 `seed_devices`；改名会破坏启动。
- **状态统计缓存**：`/devices/stats/` 缓存 300 秒；涉及租户或批量更新时要同步考虑缓存 key/失效。

## ANTI-PATTERNS

- ❌ 在测试或前端用 pk 调设备详情：路由 lookup 是 `code`。
- ❌ 删除 `seed_operations_periodic_tasks` 或把它挪走但不改 compose：Celery beat 周期任务会空。
- ❌ 让 seed 命令创建重复设备：必须以 `code` 作为幂等键。
- ❌ 多租户改造后继续使用全局 `device_stats` 缓存 key：会跨公司串统计。

## NOTES

- `seed_operations_periodic_tasks.py` 当前注册 `config.tasks.cleanup_old_celery_results`，不是设备业务任务；位置是历史便利选择。
- `Device.code` 当前全局唯一；多租户时通常应改为 `(tenant, code)` 唯一。
