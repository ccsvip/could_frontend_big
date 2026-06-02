[backend](../../AGENTS.md) > apps > **devices**

# apps/devices AGENTS.md

## OVERVIEW

安卓设备授权与运行时管理 app。当前设备功能已从旧的“设备 CRUD + 状态统计”替换为：

- 公司内设备应用 `DeviceApplication`
- 一次性授权码 `DeviceAuthorizationCode`
- 安卓设备档案 `Device`
- 设备分组 `DeviceGroup`
- 设备授权/心跳/配置日志 `DeviceAuthLog`
- 安卓运行时激活、配置拉取、心跳接口

安卓端不登录、不注册；只提交后端生成的一次性授权码和安卓端生成的唯一设备码。后端校验授权码后绑定设备到应用，并返回设备运行时 token。

## STRUCTURE

```
devices/
├── models.py                         # DeviceApplication / DeviceAuthorizationCode / DeviceGroup / Device / DeviceAuthLog
├── serializers.py                    # 后台管理 payload + 应用资源包选择 + 授权码生成
├── views.py                          # 后台 ViewSet + /device-auth/activate/ + /device-runtime/*
├── tokens.py                         # 设备运行时 token 签发/解析
├── admin.py                          # Django admin 展示
├── urls.py                           # /devices/* /device-applications/* /device-auth/*
└── management/commands/
    ├── seed_devices.py               # 开发演示应用/分组/设备种子
    └── seed_operations_periodic_tasks.py # 系统运维 Celery beat 种子
```

## WHERE TO LOOK

| 任务 | 位置 | 注意 |
|------|------|------|
| 改设备字段 | `models.py` + `serializers.py` + `admin.py` | `Device.code` 是安卓端生成的设备码，不是后端生成 |
| 改应用资源包 | `DeviceApplication` / `DeviceApplicationSerializer` | 应用可选择图片/视频、音色、模型、指令分组 |
| 改授权码逻辑 | `DeviceAuthorizationCode` + `DeviceActivationView` | 一码一设备；激活后状态改为 `used` |
| 改安卓激活接口 | `DeviceActivationView` | `POST /api/v1/device-auth/activate/`，无需后台 JWT |
| 改设备运行时接口 | `DeviceRuntimeConfigView` / `DeviceRuntimeHeartbeatView` | 使用设备 token，不使用后台用户 token |
| 改后台设备页 API | `DeviceViewSet` | lookup 仍是 `code`，兼容 `/devices/{code}/` |
| 改统计 | `DeviceViewSet.stats` | 缓存 key 仍必须带 tenant 维度 |
| 改启动默认数据 | `management/commands/seed_devices.py` | compose 每次 backend 启动都会跑，必须幂等 |

## CONVENTIONS

- **一码一设备**：授权码只能激活一台设备。`DeviceAuthorizationCode.status` 从 `unused` 变为 `used` 后不得再绑定新设备。
- **设备码来源**：`Device.code` 是安卓端生成并保证唯一的设备码；后端只校验、存储、用于 lookup，不主动生成。
- **安卓无账号体系**：安卓端只传 `authCode` + `deviceCode` + 设备信息；不要让安卓端走后台用户登录/注册。
- **设备 token 独立**：`tokens.py` 生成的是设备运行时 token，只能访问 `/device-runtime/*`，不能复用后台 SimpleJWT 权限。
- **设备数据隔离**：设备运行日志、心跳、授权日志等挂 `Device`；公司公共资源挂 `DeviceApplication`，设备只能拿到绑定应用的资源包。
- **在线状态首版靠心跳**：`POST /device-runtime/heartbeat/` 更新 `last_heartbeat` 和 `status=online`。WebSocket 可后续增加，不要在未确认前引入 Channels 依赖。
- **后台可编辑范围**：后台主要编辑设备名称、分组、启停、授权类型/到期时间；安卓上报的软件版本、系统版本、主板信息不要手工改写。
- **tenant 范围**：所有带 `tenant` 的模型必须用 `TenantManager`，并经 `TenantScopedQuerysetMixin` 收窄后台查询。

## ANTI-PATTERNS

- ❌ 把授权码做成多设备共享：当前业务已明确“一码一设备”。
- ❌ 让安卓端提交公司 ID、用户账号或后台 JWT：安卓只知道授权码和设备码。
- ❌ 后端生成 `Device.code`：设备码由安卓端生成。
- ❌ 让设备 token 访问后台管理接口：设备运行时权限和后台用户权限必须隔离。
- ❌ 应用资源包跨 tenant 选择资源：`DeviceApplication` 的 M2M 资源必须属于同一公司。
- ❌ 为在线/离线首版强行引 WebSocket：当前依赖只有 ASGI/uvicorn，没有 Channels；先用心跳，后续再扩展。
- ❌ 删除或改名 `seed_devices`：根 compose 启动链路固定调用它。

## RUNTIME API

```http
POST /api/v1/device-auth/activate/
```

请求示例：

```json
{
  "authCode": "ABCD-1234",
  "deviceCode": "ANDROID-BOARD-001",
  "deviceName": "大厅安卓设备",
  "softwareVersion": "1.0.0",
  "systemVersion": "Android 14",
  "mainboardInfo": "rk3588"
}
```

成功后返回设备 token。后续安卓端带：

```http
Authorization: Bearer <device-runtime-token>
```

访问：

```http
GET /api/v1/device-runtime/config/
POST /api/v1/device-runtime/heartbeat/
```

## TESTS

```bash
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api
docker compose exec backend python manage.py test apps.tenants.tests.test_cross_tenant_isolation apps.tenants.tests.test_isolation_contract
```
