# WebSocket 三合一探索记录

## 结论

项目不是新增三个 WebSocket URL，而是通过唯一 `/ws/realtime/` 入口按 `message.type` 路由。所谓三合一，是 `agent.session.start` 在同一连接和会话标识下编排 ASR、LLM、TTS：

- 文本模式：`payload.text` 有值，`_handle_agent_session_start` 直接启动 `_start_agent_llm_task`。
- 语音模式：`payload.text` 为空，先 `_start_agent_asr_session`；客户端发送 binary PCM，ASR 完成后拼出 `questionText`，再启动 LLM。
- LLM 输出流同时发送 `llm.delta`，按文本分段发送 `llm.tts_segment`，通过 `agent_tts_worker` 队列驱动 TTS 上游；TTS 返回 `tts.ready`、`tts.segment_start`、binary 音频、`tts.segment_end`、`tts.done`。
- LLM 完成后发送 `llm.done`，整个 Agent 编排最后发送 `agent.done`。异常统一使用 `agent.error` / `asr.error` / `llm.error` / `tts.error` 及错误码。

## 关键源码

- `backend/config/asgi.py:10-17`：只将 `/ws/realtime/` 交给 `realtime_websocket_application`。
- `backend/config/realtime.py:382-428`：接受连接，循环等待客户端消息或设备事件队列，断开时统一清理。
- `backend/config/realtime.py:447-532`：解析 JSON/binary 并按 `type` 分发；同时支持设备状态、设备事件、运行时配置、独立 ASR/TTS/LLM 和 Agent 命令。
- `backend/config/realtime.py:829-890`：Agent 启动、文本/语音模式判定、TTS worker 初始化。
- `backend/config/realtime.py:1520-1785`：Agent ASR 上游、VAD、转写、`asr.done` 后转交 LLM。
- `backend/config/realtime.py:1023-1334`：LLM 会话准备、指令分发/模型流式回答、`llm.delta`、TTS 分段、`llm.done`。
- `backend/config/realtime.py:1868-1992`：Agent TTS 队列与适配器，上游音频事件通过同一 WebSocket 返回。
- `backend/config/tests/test_realtime_websocket.py:3405-3592`：三合一语音回归测试，验证 `asr.done < llm.started`、`llm.tts_segment < tts.ready`、`tts.segment_start < binary < tts.segment_end < tts.done`、最后为 `agent.done`。

## GitNexus 探索

- 仓库上下文：`could_frontend_big`，595 files / 38,210 symbols / 300 processes。
- Query 定位到 `realtime_websocket_application`、`_handle_client_event`、`_handle_agent_session_start`、`_run_llm_session_body`、`_agent_asr_upstream_to_client` 等关键符号。
- Context 已核对统一入口、Agent 启动、LLM 会话和 ASR 回传的 callers/callees。
- GitNexus 进程资源当前只返回通用高排名进程，未能按 query 返回的 `proc_*` 标识读取对应 trace；因此以源码调用链和三合一回归测试作为最终证据。

## Excalidraw

- Checkpoint：`d4b0057d13264e86b8`
- 图中包含统一入口、命令路由、文本/语音分支、ASR、LLM、TTS、事件顺序、错误出口和连接清理。
