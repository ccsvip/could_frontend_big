# 修复设备首次运行时配置错误码

## Goal

确保安卓设备首次上报后、尚未完成后台授权绑定时，请求 `GET /api/v1/device-runtime/config/` 返回设备未登记错误 `1002`，而不是误报设备未绑定智能体 `1008`，让安卓端按正确状态进入等待授权流程。

## Background

- `POST /api/v1/device-auth/activate/` 会为首次上报的未知设备码创建一条待绑定 `Device` 记录；该记录没有公司、设备应用或智能体应用（`backend/apps/devices/views.py:563-571`）。
- 配置接口当前调用 `get_runtime_device(..., allow_expired=True)` 时没有要求公司绑定，因此待绑定记录会通过基础查找（`backend/apps/devices/views.py:779-805`）。
- 随后的智能体检查发现 `effective_agent_application` 为空，返回 `1008 / 44021 / 设备未绑定可用智能体`（`backend/apps/devices/views.py:802-806`）。
- 用户确认：首次上报但尚未授权绑定的设备，对配置接口应返回 `1002`。

## Requirements

- `/api/v1/device-runtime/config/` 必须在检查应用或智能体绑定前识别首次上报产生的待绑定设备。
- 待绑定设备返回现有错误目录中的 `1002` 契约，不新增错误码，不修改错误目录文案。
- 已绑定公司但未绑定或未启用智能体的设备继续返回 `1008`，避免掩盖真实配置错误。
- 未知设备码仍返回 `1002`；已授权且配置完整的设备行为保持不变。
- 修改范围仅限 HTTP 运行时配置接口及其回归测试；不改变激活接口创建待绑定记录的业务流程，也不调整 WebSocket 协议。

## Acceptance Criteria

- [x] 首次调用激活接口创建 `bindingStatus=pending` 的设备后，再请求运行时配置，HTTP 响应的 `code` 为 `1002`、`statusCode` 为 `44004`、`message` 为 `设备未登记`。
- [x] 数据库中完全不存在的设备码请求运行时配置时仍返回同一 `1002` 契约。
- [x] 已绑定公司但没有可用智能体的设备请求运行时配置时仍返回 `1008 / 44021`。
- [x] 已有设备授权 API 目标测试通过。

## Out of Scope

- 修改 `POST /api/v1/device-auth/activate/` 的待绑定设备登记行为。
- 重编号或重命名 `1002`、`1008` 及其旧业务状态码。
- 修改统一 WebSocket 错误 payload。

## Key Decision

- “首次未授权”按设备是否已有数据库记录来判断会产生错误语义；配置接口应将无公司归属的待绑定记录视为尚未完成运行时登记，并映射为用户指定的 `1002`。
