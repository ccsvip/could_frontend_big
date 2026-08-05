# 优化三合一实时语音管线首包延迟

## Goal

让设备侧 `/ws/realtime/` 三合一链路（ASR → LLM → TTS）达到「豆包式」真流式播报：文字刚开始出现就有音频跟上，而不是等几十个字。

## 背景：实测基线

设备 `apifox`，租户 24（杨老板的公司），`runtime-api-console.html` 阶段计时：

| 区间 | 实测 | 归因 |
|---|---|---|
| 开始->LLM开始 | 100ms | 正常，不动 |
| LLM开始->首字 | 2.32s | 上游 TTFT，`forced_search` 强制检索所致（**本任务不改**） |
| LLM开始->播报片段 | 3.12s | 首字 2.32s + 等攒满 80 字 |
| 播报片段->TTS ready | 1.32s | 上游连接懒开 + 6 次串行 ORM 全压关键路径 |
| 段间空档 | — | CosyVoice 每段一次 `run-task` RTT，收发不重叠 |

关键证据（生产日志）：

```
realtime.agent.tts_started device_code=apifox first_segment_length=80
firstSegment: "腾讯总部（即腾讯滨海大厦）的具体地址是： 广东省深圳市南山区海天二路33号腾讯滨海大厦
这是腾讯集团的主要办公总部所在地，位于深圳湾科技生态园核心区域，毗邻深圳"
```

正好 80 字，从「毗邻深圳」中间硬切，第 2 段以「湾口岸」开头。该回答开头只用了 `：` / `\n\n` / `，`，均不在 `DEFAULT_TTS_SEGMENT_BOUNDARIES = '。！？!?；;'` 内，因此一路攒到 `chunk_size=80` 上限。

## Requirements

### R1 首段渐进切分（对应「几十个字才播报」）

- `backend/apps/ai_models/services/tts.py` 新增软边界集 `，,：:、` 与换行，与现有硬边界并列参与切段判定。
- 切段阈值改为按段序渐进：第 1 段 12 字、第 2 段 30 字、第 3 段起 80 字（维持现状）。
- 渐进状态不得由调用方手工维护段计数——`pop_tts_text_segments` 是纯函数式增量 API，段序信息必须能从入参推导或由调用方以显式参数传入，不允许引入模块级可变状态。
- 数字小数点、有序列表序号（`1.` / `2)`）不得被当作边界——沿用既有 `_is_tts_boundary` 判定。
- 软边界不得让首段碎到无法播报：软边界触发时仍需满足最小字数下限（不低于 4 字），否则继续累积。

### R2 TTS 上游预热（对应 `播报片段->TTS ready 1.32s`）

- `_agent_tts_worker` 在 `await queue.get()` **之前**完成全部准备工作：6 次 `thread_sensitive=True` ORM 解析（`resolve_tts_realtime_connection` / `resolve_realtime_tts_voice` / `get_adapter_for_voice` / `ensure_channel` / `effective_config` / `_resolve_connection_tts_session_config`）+ 上游 WebSocket 握手 + 首个 `run-task`/`task-started` 往返。
- 这些准备与 LLM 请求并行发生（两者都在 `agent.session.start` 后启动）。
- 预热失败必须仍走现有 `tts.error` 错误码语义（`TTS_UNAUTHORIZED` / `TTS_VOICE_NOT_AVAILABLE` / `TTS_NOT_READY`），且不得因为提前发生而在 LLM 尚未开始时就把整个 agent 会话打死——错误上报时机可以提前，但 `agent.error` 的既有边界不变。
- 会话被 `agent.session.cancel` / 客户端断开取消时，预热出去的空闲上游连接必须被回收，不得泄漏。
- 预热完成但 LLM 最终无文本（`LLM_EMPTY_RESPONSE`、命令派发未命中且回答为空）时，空闲上游连接同样要正常关闭。

### R3 CosyVoice 单 task 贯穿 + 并发 reader（对应段间空档）

- `stream_cosyvoice_realtime_segments` 改为 `realtime_tts._stream_tts_segments_audio` 的同构结构：一条上游连接 + 独立 `reader_task`，发文本与收音频重叠。
- **整个回答只开一个上游 task**：`run-task` 发一次（由 R2 在预热阶段发出），每个下游段的文本作为若干 `continue-task` 追加，回答结束发一次 `finish-task`。段与段之间不再有 `run-task`/`task-started` RTT，音频连续流回。
- 该结构的已知代价（用户已确认接受）：task 协议按 task 分帧而非按 `continue-task` 分帧，上游不告知「这帧音频属于哪段文本」。因此 `tts.segment_start` / `tts.segment_end` 退化为**近似标记**——在把该段文本发往上游时发 `segment_start`，在下一段 `segment_start` 之前补发上一段的 `segment_end`。
  - 下游事件序列与类型完全不变：`tts.ready` → `tts.segment_start` → binary PCM → `tts.segment_end` → `tts.done`；段序号仍从 1 递增且与文本一一对应。
  - 客户端按到达顺序播放 PCM，不依赖 segment 标记，播放行为不受影响（`app.js` 只处理 `tts.ready` / `tts.done`）。
  - 仅 `runtime-api-console.html` 调试面板的「文本 ↔ 音频」对应关系会漂移；这是显式接受的取舍。
- `task-failed` 必须仍能中断整条流并抛错；reader_task 异常不得被静默吞掉。
- 单 task 长时间存活期间不得因上游空闲超时被动断开而静默丢音频——断连必须走既有 `ConnectionClosed` 错误路径。

### 明确不在本任务范围

- **不改 `forced_search`**：`LLM开始->首字 2.32s` 是上游 TTFT，关掉强制检索属产品取舍（影响回答时效性/准确性），需独立决策。
- **不修 `_pop_llm_tts_segments` 的 O(n²) 重复 sanitize**：CPU 浪费但非首包瓶颈。
- 不动前端 `playPcmChunk` 的 20ms/50ms 调度余量。
- 不动 ASR 段。
- 不新增租户/智能体可配字段（切分阈值本轮写死为常量）。

## Acceptance Criteria

- [ ] AC1：以基线日志里那条「腾讯总部」回答为输入，`pop_tts_text_segments` 首段长度 ≤ 15 字且不在词中间断开；`first_segment_length=80` 不再出现。
- [ ] AC2：`config/tests/test_realtime_websocket.py:813` 既有 markdown/列表序号用例的语义仍成立（数字小数点与 `1.` / `2.` 不成为边界，`**` 被清除）；期望值按新阈值更新后测试通过。
- [ ] AC3：`_agent_tts_worker` 中 6 次 ORM 解析与上游握手发生在 `await queue.get()` 之前，可由日志时序验证（预热日志时间戳早于 `realtime.agent.tts_started`）。
- [ ] AC4：`agent.session.cancel` 后没有残留上游 WebSocket 连接（`close_agent_session` 路径覆盖预热态 worker）。
- [ ] AC5：`stream_cosyvoice_realtime_segments` 在多段输入下，整条流只发出 **1 次** `run-task` 与 **1 次** `finish-task`，段文本以 `continue-task` 追加；第 2 段文本的发送不晚于第 1 段音频收完——由单测以 fake upstream 断言消息顺序与 action 计数。
- [ ] AC6：`python manage.py test apps.ai_models.tests config.tests` 全绿。
- [ ] AC7：实测复验（设备 `apifox` / 杨老板的公司）：`LLM开始->播报片段` 相对 `LLM开始->首字` 的增量 ≤ 400ms；`播报片段->TTS ready` ≤ 200ms。

## Notes

- 测试授权：设备 `apifox`，公司「杨老板的公司」，密钥已配置，可直接实测。
- 实际生效的 TTS 卡片是 `cosyvoice`（voiceId 258），不是 `AliyunQwenTTSAdapter`；`realtime_tts.py` 的 reader_task 结构是本任务 R3 的参照实现。
- 影响面（gitnexus impact，upstream）：`pop_tts_text_segments` LOW / 0 生产调用方；`_run_agent_tts_stream` LOW / 3 层皆在 `config` 内；`stream_cosyvoice_realtime_segments` 报 HIGH 但 `direct: 1`，唯一调用方是 `CosyVoiceTTSAdapter.stream_realtime_segments`，模块归因为索引噪声。
