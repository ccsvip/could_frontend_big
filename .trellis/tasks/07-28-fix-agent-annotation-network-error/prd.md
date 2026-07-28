# 修复智能体标注提问网络错误

## Goal

使管理端的 **Web Debugging Conversation** 在用户问题命中 **Agent Annotation** 时，像非标注问题、安卓运行时一样完成回答；不得向页面暴露 `TypeError: network error`。

## Confirmed Facts

- 根因：命中 Annotation 且回复块包含图片/视频资源时，`ChatConversationViewSet.send()` 的异步 SSE generator 内同步调用 `serialize_reply_blocks()`；其 ORM 查询在 ASGI async context 抛出 `SynchronousOnlyOperation`，响应已开始后连接被关闭，浏览器表现为 `TypeError: network error`。
- 文本型标注不会查询资源，因此原有 CORS/SSE 复现能通过，未能覆盖此分支。
- 认证跨域预检与文本型 Annotation SSE 均正常；故不修改前端 fetch、CORS 或安卓运行时协议。

## Requirements

- R1：定位并修复网页调试 SSE 请求或响应处理在 Annotation 命中路径上的失败根因。
- R2：保持既有会话鉴权、租户范围、取消请求、流式文本/内容块、知识引用和回答后建议问题的行为。
- R3：不得修改安卓或后端运行时对话协议，除非可复现证据证明浏览器端修复无法单独完成。

## Acceptance Criteria

- [x] AC1：真实 Docker ASGI 服务上，以 Bearer JWT 和 `Origin: http://localhost:5175` 发送命中图片回复块的 Annotation 请求，返回完整 `text/event-stream`、媒体块与 `data: [DONE]`，不再断开连接。
- [x] AC2：`apps.ai_models.tests.test_chat_api` 的普通 OpenAI SSE、无空格 `data:` SSE、第三方流式与非流式回复共 12 项回归通过。
- [x] AC3：`test_send_returns_annotation_without_calling_model` 覆盖 tenant-scoped image reply block，异步 drain 整条 SSE 并断言完整块与终止事件；修复前会触发 `SynchronousOnlyOperation`。
- [x] AC4：`docker compose exec -T -w /app web npm run build` 通过。

## Verification

- 实际失败复现：带图片回复块的跨域 SSE 请求此前在 `httpx` 中稳定报 `RemoteProtocolError: incomplete chunked read`；后端日志定位到 `SynchronousOnlyOperation`。
- 修复后：相同真实请求返回 `200`，CORS preflight 与 `access-control-allow-origin` 通过，完整 SSE 负载和终止事件均可读取。
- 浏览器自动化未运行：本机 Puppeteer Chromium 缺少 `libatk-1.0.so.0`；上述 ASGI wire 测试覆盖了导致浏览器 `TypeError` 的断流条件。浏览器不再报错是基于完整合规跨源 SSE 响应的 [INFERENCE]。

## Out of Scope

- 标注内容、命中规则或安卓运行时行为调整。
- 与本缺陷无关的聊天体验或 API 重构。
