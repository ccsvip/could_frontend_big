# 修复设备状态心跳错误映射

## Goal

让安卓端发送的 `device.status.ping` 根据 `payload.deviceCode` 返回设备真实运行时状态，避免在设备未登记、未授权、停用或未绑定可用应用时统一显示“设备状态会话尚未启动”。

## Background

- 安卓端已在心跳 payload 中发送 `deviceCode`、`requestId` 和 `traceId`。
- `backend/config/realtime.py:_handle_device_status_ping` 当前不读取 payload，只检查连接内的 `device_status_device_id`。
- `device_status_device_id` 仅在 `device.status.start` 成功后设置；启动校验失败后，后续心跳固定返回 `1017`。
- 设备运行时错误目录已定义 `1001` 至 `1009`，覆盖设备码、登记、公司绑定、公司状态、设备启停、授权过期、智能体绑定和应用启用状态。

## Requirements

- 心跳必须解析 camelCase `deviceCode`，并兼容现有 snake_case `device_code`。
- 心跳必须解析并回传非空 `requestId` / `traceId`，保持统一实时错误关联字段约定。
- 心跳携带设备码时，必须通过现有集中式设备运行时校验返回具体业务错误，不得降级为 `1017`。
- 状态校验必须覆盖：设备码缺失、设备未登记、重复设备码、未绑定公司、公司停用、设备停用、授权过期、绑定应用未启用、未绑定可用智能体。
- 设备通过校验但当前连接尚未建立设备状态会话时，心跳应建立/恢复该连接的设备状态会话并返回正常 `device.status.pong`，避免安卓必须依赖一次成功的独立 start 才能恢复心跳。
- 已建立会话的正常心跳继续更新时间并返回 `device.status.pong`，不得改变统一 WebSocket URL 或事件类型。
- 不新增错误码，不修改安卓端协议，不削弱 tenant 隔离或设备码认证。

## Acceptance Criteria

- [x] 携带已停用设备码的 `device.status.ping` 返回 `1006 设备已停用`，不返回 `1017`。
- [x] 携带未绑定公司设备码的心跳返回 `1004 设备未绑定公司`。
- [x] 携带未绑定可用智能体/应用的设备码返回 `1008 设备未绑定可用智能体`；绑定应用已停用时返回 `1009 设备绑定应用未启用`。
- [x] 携带有效设备码、但未先发送 `device.status.start` 的心跳返回 `device.status.pong`，并建立可在断开时正确置离线的连接状态。
- [x] 心跳错误响应保留请求 `id`，并在请求提供非空关联 ID 时回传 `requestId` 和 `traceId`。
- [x] 现有正常 start、ping、disconnect 在线状态流程继续通过。
- [x] 相关 Django WebSocket 测试在 Docker Compose 后端容器内通过。

## Out Of Scope

- 修改安卓客户端发送格式。
- 新增 WebSocket URL 或新增公开错误码。
- 调整 HTTP heartbeat 的兼容行为。
