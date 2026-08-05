# 执行计划：优化三合一实时语音管线首包延迟

依据 `prd.md` 与 `design.md`。三步骤按 R1 → R3 → R2 顺序落地（R3 先于 R2：`prepared=None` 的自给分支让 R3 能独立跑通并被单测覆盖，R2 再把预热句柄接进去）。每步都有独立的验证命令与回滚点。

## 前置

- [ ] 确认 backend 容器在跑：`docker compose ps solin_backend`（healthy）
- [ ] 记录基线：`docker compose exec backend git rev-parse HEAD`（回滚锚点）
- [ ] 跑一遍现状全绿基线：`docker compose exec backend python manage.py test apps.ai_models.tests config.tests`
  - 验证：全部 PASS。若已有失败，先记录，不要归因到本任务。

## 步骤 1：R1 首段渐进切分（`apps/ai_models/services/tts.py`）

- [x] 1.1 impact 门禁：`impact({target: "pop_tts_text_segments", direction: "upstream"})`
  - 预期 LOW / 1 生产调用方。若报 HIGH 先向用户报告再动手。
- [x] 1.2 新增常量（`tts.py` 第 22 行 `DEFAULT_TTS_SEGMENT_BOUNDARIES` 旁）：
      `DEFAULT_TTS_SOFT_SEGMENT_BOUNDARIES = '，,：:、\n'`、`DEFAULT_TTS_WORD_GAP_BOUNDARIES = '）)】」』》”’ '`、`PROGRESSIVE_TTS_CHUNK_SIZES = (12, 30)`、`MIN_SOFT_BOUNDARY_CHUNK_SIZE = 4`
- [x] 1.3 新增 `_tts_chunk_limit(segment_ordinal, chunk_size)`、`_hits_tts_boundary(stripped, index, current_length)` 与 `_hits_tts_word_gap(text, index)`（放在 `_is_tts_boundary` 附近），**不改 `_is_tts_boundary`**
- [x] 1.4 `pop_tts_text_segments` 新增 `emitted_segments: int = 0` 关键字参数；循环体内把
      `len(current) >= chunk_size or (char in separators and _is_tts_boundary(...))`
      换成 `len(current) >= chunk_size or _hits_tts_boundary(...) or (len(current) >= _tts_chunk_limit(...) and _hits_tts_word_gap(...))`
      —— **渐进值是词间空隙的放行阈值，不是硬切点**（硬上限仍只有 `chunk_size`，否则首段会断在词中间，违反 AC1）；删掉函数内 `separators = set(DEFAULT_TTS_SEGMENT_BOUNDARIES)` 这行局部变量
- [x] 1.5 **不动 `split_tts_text`**（6 个生产调用点依赖现行为）
- [x] 1.6 `config/realtime.py:_pop_llm_tts_segments` 加 `emitted_segments=0` 参数并透传；两个 LLM 流式循环各自维护 `emitted_tts_segments` 计数并传入
  - 注意：`flush=True` 的收尾调用也要传当前计数
- [x] 1.7 新增单测（`apps/ai_models/tests/test_tts_api.py`）：
      ① 基线「腾讯总部」原文 → 首段 `'腾讯总部（即腾讯滨海大厦）'`（13 字 ≤15，断在闭合括号）（AC1）
      ② `emitted_segments=0/1/2` 分别对应 12/30/80 放行阈值
      ③ 软边界 4 字下限：`'好，'` 不出段，`'你好吗，'` 出段
      ④ `3.14` 与 `1. 列表项` 不在小数点/序号处断开（AC2 回归）
- [x] 1.8 更新既有测试期望值：`config/tests/test_realtime_websocket.py:813` 的段数与切点
  - **只改期望值，不改用例语义**：`assertNotIn('**')` / `assertNotIn('1.')` / `assertNotIn('2.')` 必须保留（AC2）
- [x] 验证：`docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api config.tests.test_realtime_websocket` → 123 tests OK
- [ ] 回滚点 1：`_hits_tts_boundary` 软边界分支改 `return False` + 循环里去掉 `_hits_tts_word_gap` 分支

## 步骤 2：R3 CosyVoice 单 task 贯穿 + 并发 reader（`services/cosyvoice_realtime.py`）

- [x] 2.1 impact 门禁：`impact({target: "stream_cosyvoice_realtime_segments", direction: "upstream"})`
  - 实测报 **CRITICAL**（impactedCount 49 / 17 processes / 13 modules）而非计划里预期的 HIGH，但 `summary.direct: 1`（唯一 depth-1 调用方 `CosyVoiceTTSAdapter.stream_realtime_segments`）。已向用户复述并归因为索引噪声：扇出条目（`Perform_update` / `Download` / `Bulk_download` 走 business cache，以及 knowledge_base / accounts / devices / resources 模块）与 CosyVoice WebSocket 代码之间没有执行路径。
- [x] 2.2 新增 `CosyVoicePrewarmedTask`（持 `context` / `upstream` / `task_id`，`aclose()` 幂等 + 只 `__aexit__`，异常仅记日志）
- [x] 2.3 新增 `prewarm_cosyvoice_realtime(*, voice, config, controls)`：`_open_upstream` → `__aenter__` → `run-task` → `_await_task_started` → 返回句柄。失败时必须先 `__aexit__` 再抛，不留半开连接。
- [x] 2.4 新增 `_forward_stream_audio(upstream, send, *, segment_queue, task_id, stats)`，仿 `apps/ai_models/realtime_tts.py:399` `_forward_tts_upstream_audio` 的 `ensure_segment_started` / `finish_active_segment` 闭包（**注意实际路径不在 `services/` 下**）
  - **闭包条件必须改写，不能原样照搬**：`realtime_tts` 靠上游的 `response.audio.done` 收尾每段，CosyVoice 单 task 下没有这类事件。原条件 `if active_segment is not None: return` 会退化成「只有第 1 段有标记、后续段一对都不发」。实测改为「`segments_finished` 才短路；`active_segment is not None and segment_queue.empty()` 时维持当前段；否则取下一段（先 `finish_active_segment()`）」，保证每段恰好一对标记、序号递增；代价是标记比音频跑得偏前（design.md 已记录）。
  - 事件映射：非空 `bytes` → 段标记 + 转发；`task-failed` → `raise RuntimeError(_extract_cosyvoice_task_error(header))`；`task-finished` → 收尾 + `tts.done` + return；上游先关 → `raise RuntimeError('CosyVoice upstream closed before task finished.')`
- [x] 2.5 重写 `stream_cosyvoice_realtime_segments`：加 `prepared=None`；`prepared` 为空时自行 `prewarm_cosyvoice_realtime`；`tts.ready` 在预热后立即发；单 `reader_task`；每段 `segment_queue.put` + `continue-task`*N；结束 `put(None)` + 一次 `finish-task` + `await reader_task`；任何异常先 `cancel()` + `gather(return_exceptions=True)` 再抛；`finally` 里 `await prepared.aclose()`
- [x] 2.6 保留既有 `except ConnectionClosed` / `except Exception` 两个日志分支（含 `total_audio_chunks` 口径改为 `stats['audio_chunks']`）
- [x] 2.7 **删除** `_forward_task_audio`（已核实唯一调用方就是 `stream_cosyvoice_realtime_segments:253`，被 2.4 取代后成为死代码；`stream_cosyvoice_realtime_text` 有自己的转发逻辑，不依赖它）
- [x] 2.8 **不动** `stream_cosyvoice_realtime_text`（单段变体本来就是 1 run-task + 1 finish-task）
- [x] 2.9 改造测试替身 `FakeCosyVoiceUpstream`（`test_tts_adapters.py:13-57`）——这是本步最容易踩的坑：
      现状是「`finish-task` 才吐音频 + 队列空即 `StopAsyncIteration`」，在并发 reader 下会让 reader 一开工就撞到「upstream closed before task finished」。
      已改为 `asyncio.Queue` 驱动：`__anext__` 用 `await asyncio.wait_for(queue.get(), timeout=1)` 真正等待（超时视作上游静默关闭）；`continue-task` 到达即入队对应音频帧；`finish-task` 入队 `task-finished`。保留 `sent` / `actions()` / `fail` 语义，删掉未使用的 `tasks` 参数，新增 `timeline`（记录 send/recv 交错时序）与 `fail_mid_stream`。
- [x] 2.10 重写 `test_segment_stream_opens_one_task_per_segment` → `test_segment_stream_uses_single_task_for_whole_answer`（AC5）：
      断言 `actions().count('run-task') == 1`、`count('finish-task') == 1`、`count('continue-task') >= 2`；
      交错时序另立 `test_segment_stream_does_not_wait_for_previous_segment_audio`：断言第 2 段的 `continue-task` 早于第 1 帧音频被 reader 消费（`timeline` 里 `('recv', 'audio')` 的首次位置）；
      断言 `collector.types()` 仍是 `tts.ready → segment_start → binary… → segment_end → segment_start → binary… → segment_end → tts.done`
- [x] 2.11 `test_segment_stream_still_completes_when_no_segments_arrive` 期望不变（`['tts.ready', 'tts.done']`）——新结构下仍成立
- [x] 2.12 新增 `task-failed` 中途失败用例 `test_segment_stream_propagates_mid_stream_task_failure`：reader 抛错向上冒，不被静默吞
- [x] 验证：`docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_adapters` → 22 tests OK；顺带 `test_tts_api` + `config.tests.test_realtime_websocket` → 103 tests OK
- [ ] 回滚点 2：恢复 per-segment `run-task` 循环体 + `_forward_task_audio`

## 步骤 3：R2 TTS 上游预热（`services/tts_adapters.py` + `config/realtime.py`）

- [x] 3.1 impact 门禁：`impact({target: "_run_agent_tts_stream", direction: "upstream"})` → LOW（direct=2，范围仅 `config`）
- [x] 3.2 `BaseTTSAdapter` 新增 `async def prepare_realtime_stream(self, *, voice, config, controls=None): return None`；`stream_realtime_segments` 签名加 `prepared=None`
- [x] 3.3 `CosyVoiceTTSAdapter.prepare_realtime_stream` → `prewarm_cosyvoice_realtime(...)`；`stream_realtime_segments` 透传 `prepared`
- [x] 3.4 `AliyunQwenTTSAdapter` 只加 `prepared=None` 形参并忽略（保持 `realtime_tts` 路径不变）
- [x] 3.5 `RealtimeConnection.__init__` 新增 `self.agent_tts_prepared = None`；新增 `async def close_agent_tts_prepared(self)`（取出置空 → `await aclose()` → 异常仅 `logger.exception`）
- [x] 3.6 从 `_run_agent_tts_stream` 原样搬出 6 次 ORM 解析 + 校验为 `_prepare_agent_tts(...)`，逐条保留 `TTS_UNAUTHORIZED` / `resolution.error_key or TTS_VOICE_NOT_AVAILABLE` / `TTS_NOT_READY`；末尾调 `adapter.prepare_realtime_stream(...)`
- [x] 3.7 `_prepare_agent_tts` 成功时打 `realtime.agent.tts_prewarmed`（含 `elapsed_ms` / `device_code` / `request_id` / `trace_id`）
- [x] 3.8 `_agent_tts_worker`：`_prepare_agent_tts` 在 `await queue.get()` 之前；`None` → return；`finally` 回收 `connection.close_agent_tts_prepared()`
- [x] 3.9 `_run_agent_tts_stream` 收 `prepared_bundle` 参数，删掉已搬走的解析段；保留 `realtime.agent.tts_started`（含 `first_segment_length`）与 `_log_agent_voice_pipeline('tts.request', ...)`（含 `firstSegment`）
- [x] 3.10 `close_agent_session`：在取消并等待 worker 后兜底关闭 `agent_tts_prepared`，随后重置字段
- [x] 3.11 确认预热失败只发 `tts.error`、不发 `agent.error`、不取消 `agent_task`
- [x] 3.12 新增 `config/tests/test_realtime_websocket.py` 回归：预热先于首个 queue wait；取消和空回答都会调用 `aclose()`；预热失败发 `tts.error` 但 LLM 仍发 `agent.done`
- [x] 验证：`docker compose exec backend python manage.py test config.tests.test_realtime_websocket.RealtimeWebSocketTests.test_agent_tts_worker_prewarms_before_waiting_for_first_segment config.tests.test_realtime_websocket.RealtimeWebSocketTests.test_agent_session_cancel_closes_prepared_tts_upstream config.tests.test_realtime_websocket.RealtimeWebSocketTests.test_empty_agent_answer_closes_prepared_tts_upstream config.tests.test_realtime_websocket.RealtimeWebSocketTests.test_agent_tts_prewarm_failure_reports_tts_error_without_agent_error --keepdb` → 4 tests OK
- [ ] 回滚点 3：`_agent_tts_worker` 不调 `_prepare_agent_tts`，全链路 `prepared=None`（R3 自给分支兜住）

## 步骤 4：全量验证（AC6）

- [ ] `docker compose exec backend python manage.py test apps.ai_models.tests config.tests`
  - 门禁：**全绿**。任一失败必须修到绿，不得标记完成。
- [ ] `detect_changes({scope: "compare", base_ref: "main"})`
  - 门禁：受影响符号与执行流不超出 `tts.py` / `cosyvoice_realtime.py` / `tts_adapters.py` / `realtime.py` 四个文件的预期范围。超出即向用户报告。
- 2026-08-05 全量命令已执行：418 tests / 275.205s，**失败 11**，均位于本任务未修改的 knowledge retrieval 测试（10 项，结果为 `mode='disabled'` 或空上下文）与 `config.tests.test_realtime_fast_command_dispatch.CommandDispatchPolicyTests.test_borderline_control_match_uses_llm_confirmation_and_keeps_configured_reply`（多出 `fixedExecutionReply=''`）。本任务相关回归已单独通过：`apps.ai_models.tests.test_tts_api.TTSServiceTests` 7 passed，`apps.ai_models.tests.test_tts_adapters` + 4 个预热/关闭/失败边界回归 26 passed；markdown/列表序号回归另行执行。
- AC2 定向命令 `config.tests.test_realtime_websocket.RealtimeWebSocketTests.test_llm_tts_segments_skip_markdown_tokens_and_list_numbers`：1 passed（`**`、`1.` / `2.` 均不会流入 TTS 文本）。

## 步骤 5：实测复验（AC7）

设备 `apifox`，公司「杨老板的公司」（用户已授权，密钥已配）。

- [ ] 5.1 重启 backend 让改动生效：`docker compose restart backend`，等 healthy
  - 记忆提示：切分支/改模块后 backend 必须重启，否则懒加载 urlconf 会撞上缓存旧模块
- [ ] 5.2 打开 `device-chat/runtime-api-console.html`，接 `apifox`，发与基线同类问题（「腾讯总部在哪」）
- [ ] 5.3 读阶段计时面板（注意 `markAgentTiming` 是 first-write-wins，量的是每个事件**首次**出现）：
      - `LLM开始->播报片段` 减 `LLM开始->首字` ≤ **400ms**
      - `播报片段->TTS ready` ≤ **200ms**
- [ ] 5.4 查日志确认结构生效：
      `docker compose logs backend --since 5m | grep -E "tts_prewarmed|tts_started|first_segment_length|segments_finished"`
      - `realtime.agent.tts_prewarmed` 时间戳 **早于** `realtime.agent.tts_started`（AC3）
      - `first_segment_length` ≤ 15，不再是 80（AC1）
- [ ] 5.5 主观复听：音频是否连续、段间无明显空档；文字刚出现十几个字即起播
- [ ] 若 AC7 未达标：记录实测数字与日志，回到 `design.md` 定位是哪一段仍在关键路径上，**不要盲目调阈值**
- 实测记录（2026-08-05，实际 `apifox` / CosyVoice 258）：backend 已重启并 healthy。因共享 browser daemon 启动失败（已报 harness issue），使用容器内真实 `/ws/realtime/` WebSocket 发送 `agent.session.start`（问题「腾讯总部在哪？请用两句话简要回答。」）替代控制台协议验证。首次 `llm.delta=2627.4ms`、`llm.tts_segment=2970.4ms`，增量 **343.0ms**；`tts.ready=2971.1ms`，段→ready **0.7ms**，均满足 AC7。日志证实 `tts_prewarmed elapsed_ms=431` 早于 `tts_started`；下游收到 177 个 PCM 二进制帧并完整收到 `tts.done`/`agent.done`。该回答第 1 段为 32 字：符合设计的「12 字仅放行词间空隙、绝不硬切词中」而非 AC1 的基线文本；AC1 仍以该基线专用单测判定。
- 未完成：浏览器无法启动，故未对 `runtime-api-console.html` 做主观复听；协议层真实流已完成但不等同于人工听感。

## 步骤 6：收尾

- [x] 更新 `backend/CLAUDE.md` FAQ：新增「为什么首段这么短 / 预热在哪发生 / 段标记为什么是近似的」三条
- [x] 更新 `.trellis/spec/backend/index.md` 与 TTS realtime 契约：记录预热顺序、单 task 取舍、近似段标记、关闭所有权与回归测试
- [ ] `detect_changes()` 再跑一次后提交（Trellis 3.4）；提交信息用中文，说明 R1/R2/R3 三块与已接受的段标记取舍

## 审查门禁汇总

| 门禁 | 位置 | 通过条件 |
|---|---|---|
| impact 上报 | 1.1 / 2.1 / 3.1 | 每个被改符号都跑过；HIGH 必须先向用户复述 |
| 单元测试 | 步骤 1/2/3 末 | 分步全绿 |
| 全量测试 | 步骤 4 | `apps.ai_models.tests config.tests` 全绿 |
| detect_changes | 步骤 4 / 6 | 影响面不超出四个文件 |
| 实测 | 步骤 5 | 两个延迟阈值达标 + 日志时序正确 |

## 已知不做（prd 明确排除，勿越界）

`forced_search`（2.32s TTFT 的真因）、`_pop_llm_tts_segments` 的 O(n²) 重复 sanitize、前端 `playPcmChunk` 的 20ms/50ms 调度余量、ASR 段、新增租户/智能体可配字段。
