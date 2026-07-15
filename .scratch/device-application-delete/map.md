# 设备应用删除功能

## Destination

形成可实施的设备应用删除规格：删除设备应用时安全解除设备关联，保留授权码为可重新分配的未分配授权码，并在管理界面清楚展示实际影响。

## Notes

- 范围为 `/devices?tab=applications` 的 Device Application（设备应用），不涉及 Agent Application（智能体）。
- 遵循 REST API、租户隔离和既有 `DevicePermissionMixin` 权限模型。
- 设备运行时与授权流程受影响时，需要验证 `X-Device-Code` 与统一 WebSocket 配置通知不被破坏。

## Decisions so far

- [删除关联设备应用的生命周期](issues/01-device-application-deletion-lifecycle.md) - 删除会解除设备关联，并将原有关联授权码保留为未分配授权码。
- [删除确认交互](issues/02-deletion-impact-confirmation.md) - 删除前展示实际受影响的设备和授权码数量，用户确认后执行。

## Not yet specified

- 未分配授权码在授权中心的展示、筛选、重新分配入口和已使用授权码的处理规则。
- 删除提交与运行时配置刷新之间的事务边界及失败反馈。
- 前后端回归测试需要覆盖的设备解绑、授权码重分配和租户隔离场景。

## Out of scope

- 删除或修改 Agent Application（智能体）及其会话历史。
