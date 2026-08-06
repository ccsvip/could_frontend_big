# Aliyun CosyVoice WebSocket streaming findings

Verified against Alibaba Cloud Model Studio documentation on 2026-08-06.

## Primary sources

- [CosyVoice WebSocket API](https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api)
- [CosyVoice WebSocket streaming synthesis](https://help.aliyun.com/zh/model-studio/websocket-for-cosyvoice)
- [CosyVoice client events / `continue-task`](https://help.aliyun.com/document_detail/3032843.html)

## Protocol facts

1. The client and service establish a WebSocket connection before starting a synthesis task.
2. The client sends `run-task` and waits for the service `task-started` event.
3. One task may receive one or more `continue-task` messages containing synthesis text.
4. The client sends `finish-task` after all text, then waits for `task-finished`.
5. Complete sentences are synthesized immediately; incomplete sentences are buffered until later text or `finish-task`.
6. Audio is returned as WebSocket binary frames; lifecycle events are text frames.
7. Task messages in one synthesis task must use the same task identifier.
8. Each `continue-task` message accepts at most 20,000 characters; one task accepts at most 200,000 characters cumulatively.
9. The interval between sends must not exceed 23 seconds.

## Implication for this task

The existing one-connection/one-task/multiple-`continue-task` architecture is compatible with natural low-latency streaming. Alibaba does not require the application to delete Markdown, spaces, newlines, list markers, or punctuation before synthesis. A `continue-task` message boundary is not itself an acoustic boundary: the service buffers incomplete sentences. The application should submit lossless slices at original punctuation/newlines or final flush and must not force an 80-character speech break.

The provider's 20,000-character per-message and 200,000-character cumulative limits are protocol guards, not recommended sentence sizes. If the prewarmed task approaches the 23-second interval limit before receiving its first safe slice, an unused stale task can be closed and recreated when text is ready; fake keepalive text and partial-sentence cuts are prohibited. If a single indivisible span exceeds the provider limit during an active stream, failing TTS explicitly preserves semantics better than silently cutting or inserting punctuation.

The observed product-item concatenation therefore originates before the Alibaba upstream call: local sanitizers remove whitespace/Markdown and trim segments before `continue-task` is built.
