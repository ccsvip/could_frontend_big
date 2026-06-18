[backend](../../AGENTS.md) > apps > **devices**

# apps/devices AGENTS.md

## OVERVIEW

安卓设备与多模态应用运行时管理 app。当前核心模型：
- 公司内设备应用 `DeviceApplication`
- 安卓设备档案 `Device`
- 设备分组 `DeviceGroup`
- 设备激活 / 心跳 / 配置日志 `DeviceAuthLog`
- 历史兼容表 `DeviceAuthorizationCode`（不再参与安卓运行时）

安卓端不登录、不注册、不拿后台 JWT，也不拿设备 token。安卓只提交设备码 `deviceCode` 和设备参数；设备码和授权码是同一个业务概念。后端根据 `deviceCode` 查询设备档案，拿到公司与绑定应用后返回该应用资源包。新上报但尚未绑定的设备先进入待绑定状态。

## STRUCTURE

```
devices/
├── models.py                         # DeviceApplication / DeviceGroup / Device / DeviceAuthLog
├── serializers.py                    # 后台管理 payload + 应用资源包选择 + 设备绑定
├── views.py                          # 后台 ViewSet + /device-auth/activate/ + /device-runtime/*
├── admin.py                          # Django admin 展示
├── urls.py                           # /devices/* /device-applications/* /device-auth/*
└── management/commands/
    ├── seed_devices.py               # 开发演示应用 / 分组 / 设备种子
    └── seed_operations_periodic_tasks.py
```

## WHERE TO LOOK

| 任务 | 位置 | 注意 |
|------|------|------|
| 改设备字段 | `models.py` + `serializers.py` + `admin.py` | `Device.code` 是安卓上报的设备码，也是授权码 |
| 改应用资源包 | `DeviceApplication` / `DeviceApplicationSerializer` | 应用可选择图片/视频、滚动文本、音色、模型、指令组 |
| 改安卓激活接口 | `DeviceActivationView` | `POST /api/v1/device-auth/activate/`，只收 `deviceCode` + 设备参数 |
| 改设备运行时接口 | `DeviceRuntimeConfigView` / `DeviceRuntimeHeartbeatView` / `apps.devices.websocket` | 只按 `deviceCode` 查设备，不使用设备 token |
| 改后台设备页 API | `DeviceViewSet` | lookup 是 `code`，兼容 `/devices/{code}/` |
| 改统计 | `DeviceViewSet.stats` | 缓存 key 必须带 tenant 维度 |
| 改启动默认数据 | `management/commands/seed_devices.py` | compose 每次 backend 启动都会跑，必须幂等 |

## CONVENTIONS

- **设备码即授权码**：不要再把 `authCode` 和 `deviceCode` 拆成两个字段。安卓只传 `deviceCode`。
- **安卓无账号体系**：安卓端不提交用户账号、公司 ID、后台 JWT 或设备 token。
- **设备绑定由后台决定**：新 `deviceCode` 首次上报可创建待绑定设备；后台再绑定公司、应用、分组、授权类型和到期时间。
- **配置按绑定应用返回**：`deviceCode -> Device -> tenant/application -> resources`。未绑定应用时配置接口返回错误，不返回资源包。
- **在线状态靠 WebSocket**：安卓端只维护统一 `/ws/realtime/` 并发送 `device.status.start` / `device.status.ping`；旧设备状态专用 WebSocket 入口已退役，不要新增或恢复使用。连接成功置 `status=online`，连接断开置 `status=offline`。`POST /device-runtime/heartbeat/` 仅兼容旧端更新 `last_heartbeat` / 版本信息，不再决定在线 / 离线。
- **后台设备页实时同步**：管理端只维护统一 `/ws/realtime/` 并发送 `devices.events.subscribe` 订阅设备事件；旧设备事件专用 WebSocket 入口已退役，不要新增或恢复使用。公司账号只接收本公司事件；超管公司视图必须传 `tenantId` 收窄范围。设备绑定 / 再授权 / 撤销和运行时上下线都要发布事件，前端收到后刷新当前筛选列表。
- **后台可编辑范围**：后台主要编辑设备名称、位置、应用、分组、启停、授权类型、到期时间；设备名称不由安卓上报，首次登记默认“待修改”；安卓上报的软件版本、系统版本、主板信息不要手工改写。
- **tenant 范围**：所有带 `tenant` 的模型必须用 `TenantManager`，并经 `TenantScopedQuerysetMixin` 收窄后台查询。

## ANTI-PATTERNS

- ❌ 让安卓端提交 `authCode + deviceCode` 两个码：设备码和授权码是一回事。
- ❌ 让安卓端登录或携带后台 JWT：安卓没有后台账号体系。
- ❌ 要求安卓端保存设备 token：运行时接口只按 `deviceCode` 查询。
- ❌ 让未绑定设备拿资源包：必须先后台绑定应用。
- ❌ 应用资源包跨 tenant 选择资源：`DeviceApplication` 的 M2M 资源必须属于同一公司。
- ❌ 用 HTTP heartbeat 判定在线 / 离线：在线状态必须来自 WebSocket 连接生命周期；HTTP heartbeat 只做兼容字段更新。
- ❌ 删除或改名 `seed_devices`：根 compose 启动链路固定调用它。

## RUNTIME API

```http
POST /api/v1/device-auth/activate/
```

请求示例：
```json
{
  "deviceCode": "ANDROID-BOARD-001",
  "softwareVersion": "1.0.0",
  "systemVersion": "Android 14",
  "mainboardInfo": "rk3588",
  "deviceInfo": {}
}
```

后续安卓端继续只带 `deviceCode`：

```http
GET /api/v1/device-runtime/config/?deviceCode=ANDROID-BOARD-001
POST /api/v1/device-runtime/heartbeat/
WS /ws/realtime/
{"type":"device.status.start","id":"device-status-1","payload":{"deviceCode":"ANDROID-BOARD-001"}}
{"type":"devices.events.subscribe","id":"devices-sub-1","payload":{"token":"<JWT>","tenantId":<公司ID>}}
```

心跳请求示例：
```json
{
  "deviceCode": "ANDROID-BOARD-001",
  "softwareVersion": "1.0.1",
  "systemVersion": "Android 14",
  "deviceInfo": {}
}
```

## TESTS

```bash
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api
docker compose exec backend python manage.py test apps.tenants.tests.test_cross_tenant_isolation apps.tenants.tests.test_isolation_contract
```
