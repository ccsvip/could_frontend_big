# 统一实时错误码与超管目录

## Goal

为 `/ws/realtime/` 提供一致、可由客户端稳定判断的错误码契约，并让平台超管通过一级菜单“错误码中心”查看每个错误的含义与处置建议。

## Confirmed Facts

- 设备运行时错误目录已定义 9 个 `DEVICE_*` 常量（含业务状态码），位于 `backend/apps/devices/services/runtime.py:25-33`。
- 当前 WebSocket 错误形状不一致：通用协议错误使用 `type: error` 和嵌套 `error.code/error.message`（`backend/config/realtime.py:2600-2611`）；`agent.error` / `llm.error` 将运行时错误码平铺在顶层（`backend/config/realtime.py:2475-2478`）；部分 ASR/TTS 与“设备未绑定可用智能体”仅返回文本 message。
- 用户已决定：超管 UI 必须展示错误码，并以一级菜单“错误码中心”呈现。

## Requirements

- 统一 `/ws/realtime/` 的错误 payload，使错误事件始终包含稳定错误码与面向操作者的具体错误信息。
- 将设备运行时、实时协议及后续 ASR/TTS/LLM 错误收口到单一错误目录；错误码应可供协议、服务端和超管 UI 复用。
- 增加仅平台超管可访问的“错误码中心”一级菜单，供检索错误码、默认提示、说明、推荐处理方式及适用通道。
- 保持现有请求关联字段 `id`、`requestId`、`traceId`；直接切换为嵌套 `error.code` / `error.message`，不再在 WebSocket 顶层保留旧 `code`、`statusCode`、`message`。

## Acceptance Criteria

- [ ] 所有 WebSocket 错误事件使用一致的错误对象，至少含 `code` 与 `message`；同一业务状态不再在不同命令中以裸文本、通用错误或平铺字段混用。
- [ ] 错误目录是后端、WebSocket 和超管 UI 的唯一语义来源；错误码不可由 UI 任意修改。
- [ ] 超管可从一级菜单打开错误码中心，搜索并查看每个已目录化错误码的分类、默认提示、说明、推荐处理方式和适用通道。
- [ ] 非超管无法访问错误码目录 API 或菜单。
- [ ] 设备运行时现有错误、通用实时协议错误及受影响 ASR/TTS/LLM 路径具有针对性回归测试。
- [ ] 前端构建及相关后端测试通过。

## Out of Scope

- 错误发生记录、告警、聚合统计或按设备查询的错误日志。
- 允许通过 UI 修改协议错误码或默认返回文案。
- 将历史 HTTP 错误响应整体改造成新 WebSocket 协议。

## Key Decisions

- 错误目录首期由代码静态维护、超管只读查看；不新增持久化模型、写入 API 或文案覆盖层。
- WebSocket 采用直接切换策略：所有错误事件仅使用嵌套 `error.code` / `error.message`；已部署客户端必须同步迁移。

