# 技术设计：优化三合一实时语音管线首包延迟

对应 `prd.md` 的 R1 / R2 / R3。三块改动互相独立可分别回滚，但按 R1 → R2 → R3 的顺序落地收益最平滑（R1 单独就能把「几十个字才播报」压到十几个字）。

## 0. 现状时序 vs 目标时序

```
现状（一段一 task，全部懒开）：
  agent.session.start ─┬─ LLM 请求 ──── 2.32s TTFT ──── delta… 攒到 80 字 ──┐
                       └─ tts worker: await queue.get()  ←────────阻塞───────┘
                                                                  ↓
                                          6 次串行 ORM (thread_sensitive 同一线程)
                                                → WS 握手 → run-task → task-started
                                                → tts.ready            [+1.32s]
                                                → continue-task ×N → finish-task
                                                → 收完本段音频 → 下一段再来一遍 run-task

目标（预热 + 单 task 贯穿）：
  agent.session.start ─┬─ LLM 请求 ──── 2.32s TTFT ──── delta… 12 字即出段 ──┐
                       └─ tts worker 预热：6 次 ORM → WS 握手 → run-task     │
                          → task-started（与 LLM 并行，全部藏在 TTFT 里）    │
                          → await queue.get()  ←──────────────────────────────┘
                                     ↓
                          tts.ready（立即，已就绪）→ continue-task(段1)
                          reader_task 并发收音频；段2 的 continue-task 不等段1 音频收完
                          … 回答结束 → finish-task → task-finished → tts.done
```

关键点：预热的全部耗时（1.32s 中的绝大部分）被 LLM 的 2.32s TTFT 完全遮蔽，不再串在关键路径上。

## 1. R1 首段渐进切分

### 改动边界

只改 `backend/apps/ai_models/services/tts.py`，且**只改 `pop_tts_text_segments`**。

`split_tts_text` 保持原样。理由：它有 6 个生产调用点（`realtime_tts.py:246,360`、`cosyvoice_realtime.py:154,230`、`tts.py:504,588`），语义是「把一段已定稿文本切成上游可接受的块」，不是「决定何时开始播报」。渐进阈值只对后者有意义。R3 里 CosyVoice 对每个下游段仍调 `split_tts_text`，首段 12 字会原样通过（<80），不受影响。

### 新常量

```python
DEFAULT_TTS_SEGMENT_BOUNDARIES = '。！？!?；;'          # 不动
DEFAULT_TTS_SOFT_SEGMENT_BOUNDARIES = '，,：:、\n'      # 新增：软边界
DEFAULT_TTS_WORD_GAP_BOUNDARIES = '）)】」』》”’ '       # 新增：词间空隙（末位是半角空格）
PROGRESSIVE_TTS_CHUNK_SIZES = (12, 30)                  # 第1段 12 字、第2段 30 字起放行词间空隙
MIN_SOFT_BOUNDARY_CHUNK_SIZE = 4                        # 软边界触发的最小字数下限
```

### 段序如何传入（prd R1 硬约束：不得引入模块级可变状态）

`pop_tts_text_segments` 新增关键字参数 `emitted_segments: int = 0`，语义是「**本次调用之前**已经发给下游的段数」。纯函数式，段序完全由入参决定：

```python
def pop_tts_text_segments(buffer, *, chunk_size=80, emitted_segments=0, ...):
    ...
    for index, char in enumerate(stripped):
        current += char
        current_length = len(current)
        soft_limit = _tts_chunk_limit(emitted_segments + len(chunks), chunk_size)
        if (
            current_length >= chunk_size
            or _hits_tts_boundary(stripped, index, current_length)
            or (current_length >= soft_limit and _hits_tts_word_gap(stripped, index))
        ):
            ...
```

**渐进值是「放行阈值」而非「硬切点」**（这是相对初版设计的修正）：初版把 12/30 当成硬上限，实测把基线首段切成 `'腾讯总部（即腾讯滨海大厦'`（12 字，断在词中间），违反 AC1 的「不在词中间断开」。现在唯一的硬上限仍是 `chunk_size`（80）；达到渐进值只是额外**允许**在「词间空隙」（闭合括号/引号、半角空格）处收束，硬/软标点边界的判定完全不受渐进值影响。

```python
def _tts_chunk_limit(segment_ordinal: int, chunk_size: int) -> int:
    """segment_ordinal 是 0-based：0 → 第 1 段。"""
    if 0 <= segment_ordinal < len(PROGRESSIVE_TTS_CHUNK_SIZES):
        return min(PROGRESSIVE_TTS_CHUNK_SIZES[segment_ordinal], chunk_size)
    return chunk_size
```

`min(..., chunk_size)` 保证调用方显式传小 `chunk_size` 时不会被渐进阈值放大。

边界判定拆成两个小 helper。标点边界（硬/软并列，软边界带下限）：

```python
def _hits_tts_boundary(stripped: str, index: int, current_length: int) -> bool:
    char = stripped[index]
    if char in DEFAULT_TTS_SEGMENT_BOUNDARIES:
        return _is_tts_boundary(stripped, index)
    if char in DEFAULT_TTS_SOFT_SEGMENT_BOUNDARIES:
        return current_length >= MIN_SOFT_BOUNDARY_CHUNK_SIZE and _is_tts_boundary(stripped, index)
    return False
```

词间空隙（只在段长已达渐进值时参与判定）：

```python
def _hits_tts_word_gap(text: str, index: int) -> bool:
    char = text[index]
    if char not in DEFAULT_TTS_WORD_GAP_BOUNDARIES:
        return False
    if char == ' ' and re.search(r'(?:^|\s)\d+[.)]$', text[:index]):
        return False        # '1. 打开门' 的序号后空格不成空隙（AC2）
    return _is_tts_boundary(text, index)
```

`_is_tts_boundary` 原样复用 → 数字小数点（`3.14`）、有序列表序号（`1.` / `2)`）仍不成边界（AC2）。`\n` 作为软边界成立的前提是 `sanitize_tts_text(preserve_sentence_boundaries=True)` 会保留单个 `\n`（把 `\n{2,}` 折成 `\n`）——这是现有行为，不改。

### 调用方

唯一生产调用方 `config/realtime.py:_pop_llm_tts_segments` 增加一个透传参数：

```python
def _pop_llm_tts_segments(buffer, session, *, emitted_segments=0, flush=False):
    return tts_services.pop_tts_text_segments(buffer, emitted_segments=emitted_segments, ...)
```

平台 LLM 流式循环（`realtime.py:1188-1217`）已有一个本地 `segment_index` 计数用于 `llm.tts_segment` 的序号；把它作为 `emitted_segments` 传入即可，不新增状态、不引入模块级变量。

### 基线回答验算（AC1，已实测）

`"腾讯总部（即腾讯滨海大厦）的具体地址是：广东省深圳市南山区海天二路33号腾讯滨海大厦。这是腾讯集团…"`

首段在第 13 字的 `）` 处收束 → `'腾讯总部（即腾讯滨海大厦）'`：12 字达到渐进放行值后，第 13 字是闭合括号（词间空隙）即切段。第 2 段 `'的具体地址是：'` 命中 `：` 软边界。首段 13 字 ≤ 15 且断在括号外沿，两条 AC1 子句都满足，`first_segment_length=80` 消失。逐字流式模拟与一次性 `flush=True` 切点一致。

### 兼容与回滚

- 签名新增关键字参数带默认值 → 旧调用（含 `apps/ai_models/tests/test_tts_api.py:41-42`）行为受软边界与词间空隙影响，**期望值已按实测更新**。
- `config/tests/test_realtime_websocket.py:813` 的 markdown/列表用例语义不变（`assertNotIn('**'/'1.'/'2.')` 全部保留），期望段数与切点按新切分更新（AC2）。
- 回滚：`_hits_tts_boundary` 软边界分支 `return False` + 循环里去掉 `_hits_tts_word_gap` 分支，即回到现状。

## 2. R2 TTS 上游预热

### 新增适配器契约（保持 seam 不破）

`tts_adapters.BaseTTSAdapter` 新增一个可选方法，默认不预热：

```python
async def prepare_realtime_stream(self, *, voice, config, controls=None):
    """返回一个可选的预热句柄；不支持预热的卡片返回 None。"""
    return None
```

`stream_realtime_segments` 增加 `prepared=None` 关键字参数。`AliyunQwenTTSAdapter` 忽略它（继续走 `realtime_tts._stream_tts_segments_audio` 自己开连接），`CosyVoiceTTSAdapter` 透传给 `stream_cosyvoice_realtime_segments`。`_ADAPTERS` 注册表与 `get_adapter_for_voice` 的路由逻辑一行不动。

预热句柄是 `cosyvoice_realtime.CosyVoicePrewarmedTask`：

```python
class CosyVoicePrewarmedTask:
    def __init__(self, context, upstream, task_id): ...
    async def aclose(self) -> None:   # 幂等；重复调用是 no-op
        ...
```

`aclose()` 只负责 `await context.__aexit__(None, None, None)`（对齐 `close_asr_session` 的既有 idiom），并置 `self._closed = True`。不发 `finish-task`——空闲上游直接关连接即可，上游按连接断开清理 task。

### `_agent_tts_worker` 重构

```python
async def _agent_tts_worker(send, connection, command_id, device_code, request_id, trace_id, payload):
    queue = connection.agent_tts_queue
    if queue is None:
        return
    try:
        prepared_bundle = await _prepare_agent_tts(send, connection, command_id, device_code,
                                                  request_id, trace_id, payload)
        if prepared_bundle is None:
            return                      # 错误已通过 tts.error 上报
        first_segment = await queue.get()          # ← 预热已完成，这里才阻塞
        if first_segment is None:
            return                      # LLM 无文本；finally 负责回收空闲连接
        await _run_agent_tts_stream(send, command_id, queue, device_code, request_id, trace_id,
                                    first_segment, payload, prepared_bundle)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception('Agent TTS stream failed: ...')
        await _send_realtime_error(send, 'tts.error', command_id, 'TTS_UPSTREAM_ERROR', ...)
    finally:
        await connection.close_agent_tts_prepared()
```

`_prepare_agent_tts` 是从现在的 `_run_agent_tts_stream:1901-1940` **原样搬出来**的那 6 次 ORM 解析 + 校验，错误码与错误分支一一保留：

| 步骤 | 失败错误码（不变） |
|---|---|
| `resolve_tts_realtime_connection('')` → None | `TTS_UNAUTHORIZED` |
| `resolve_realtime_tts_voice(...)` → 无 voice | `resolution.error_key or 'TTS_VOICE_NOT_AVAILABLE'` |
| `get_adapter_for_voice` / `ensure_channel` / `effective_config` 抛异常 | `TTS_NOT_READY` |
| `is_tts_configured(config)` 为假 | `TTS_NOT_READY` |
| `_resolve_connection_tts_session_config` | （沿用现有分支） |
| **新增** `adapter.prepare_realtime_stream(...)` 抛异常 | `TTS_NOT_READY` |

成功后把 `(adapter, voice, config, session_config, prepared)` 打包返回，并把 `prepared` 挂到 `connection.agent_tts_prepared`（新字段，初始 `None`）。

`_run_agent_tts_stream` 保留 `realtime.agent.tts_started`（含 `first_segment_length`）与 `_log_agent_voice_pipeline('tts.request', ...)` 日志——它们仍在第一段真正开播的位置，AC3 靠「预热日志时间戳 < `realtime.agent.tts_started` 时间戳」验证，所以 `_prepare_agent_tts` 另发一条 `realtime.agent.tts_prewarmed`（带 `elapsed_ms`）。

### 错误上报边界（prd R2 硬约束）

预热失败只发 `tts.error`，**不发 `agent.error`、不取消 `agent_task`**。worker 直接 return，LLM 侧继续跑完并正常发 `llm.done` / `agent.done`。`agent_tts_queue` 是无界队列，`_queue_agent_tts_segment` 在 worker 已退出时 put 也不会阻塞；`_run_agent_llm_and_finish` 的 `put(None)` + `gather(worker)` 因 worker 已结束而立即返回。`agent.error` 的既有触发点（`_run_llm_session_body` 的 `error_event_type='agent.error'`）一行不动。

### 空闲连接回收（AC4）

三条泄漏路径，一个出口：

| 路径 | 回收点 |
|---|---|
| `agent.session.cancel` / 客户端断开 → `close_agent_session` 取消 worker | worker 的 `finally` → `close_agent_tts_prepared()`；`close_agent_session` 在 gather 完 worker 之后再兜一次 |
| LLM 无文本（`LLM_EMPTY_RESPONSE` / 命令派发未命中且回答为空）→ `queue.put(None)` | worker 收到 `None` 直接 return，同一个 `finally` |
| 正常播报 → 所有权移交给 `stream_cosyvoice_realtime_segments` | 该函数在自己的 `finally` 里 `await prepared.aclose()`；worker 的 `finally` 再调一次是幂等 no-op |

`RealtimeConnection` 新增字段 `agent_tts_prepared = None` 与方法：

```python
async def close_agent_tts_prepared(self) -> None:
    prepared, self.agent_tts_prepared = self.agent_tts_prepared, None
    if prepared is not None:
        try:
            await prepared.aclose()
        except Exception:
            logger.exception('realtime.agent.tts_prewarm_close_failed')
```

`close_agent_session` 在现有「取消 + gather worker」之后、重置 `agent_*` 字段之前插一行 `await self.close_agent_tts_prepared()`，并把 `agent_tts_prepared = None` 加入字段重置清单。`aclose()` 幂等 + 异常吞掉（只记日志），保证关闭失败不会把 `close_agent_session` 打断。

### 为什么预热能与 LLM 真并行

`_handle_agent_session_start:872-875` 已经在 `_start_agent_llm_task` **之前**用 `asyncio.create_task` 起了 worker，两者本来就在同一 event loop 上并发。现在 worker 在 `queue.get()` 之前有了实际工作，6 次 `thread_sensitive=True` ORM 仍然串行（同一 executor 线程），但那段串行发生在 LLM 的 2.32s TTFT 窗口内，不占关键路径。ASR 模式下预热与 ASR 并行，收益更大。

## 3. R3 CosyVoice 单 task 贯穿 + 并发 reader

### 结构（对齐 `realtime_tts._stream_tts_segments_audio`）

```python
async def stream_cosyvoice_realtime_segments(*, segments, voice, config, send,
                                             controls=None, exclude_patterns=None, prepared=None):
    controls = controls or {}
    own_prepared = prepared is None
    prepared = prepared or await prewarm_cosyvoice_realtime(voice=voice, config=config, controls=controls)
    upstream, task_id = prepared.upstream, prepared.task_id
    stats = {...}
    try:
        await _send_ready(send, config=config, voice_code=voice.voice_code)   # 已就绪，立即
        segment_queue: asyncio.Queue[dict | None] = asyncio.Queue()
        reader_task = asyncio.create_task(
            _forward_stream_audio(upstream, send, segment_queue=segment_queue, task_id=task_id, stats=stats))
        try:
            segment_index = 0
            async for segment in segments:
                text = normalize_tts_text(segment, config)
                if not text: continue
                chunks = split_tts_text(text, exclude_patterns=exclude_patterns)
                if not chunks: continue
                segment_index += 1
                await segment_queue.put({'index': segment_index, 'text': text})
                for chunk in chunks:
                    await upstream.send(json.dumps(_continue_task_message(task_id, chunk)))
                    await asyncio.sleep(0)
            await segment_queue.put(None)
            await upstream.send(json.dumps(_finish_task_message(task_id)))
            await reader_task
        except BaseException:
            reader_task.cancel()
            await asyncio.gather(reader_task, return_exceptions=True)
            raise
    except ConnectionClosed as exc:
        logger.error('tts.cosyvoice.realtime.segments_connection_closed code=%s ...', getattr(exc, 'code', None))
        raise
    except Exception:
        logger.exception('tts.cosyvoice.realtime.segments_failed ...')
        raise
    finally:
        await prepared.aclose()
```

`run-task` 由 `prewarm_cosyvoice_realtime` 发出（R2 阶段），整条流只此一次；`finish-task` 只在 `async for` 正常结束后发一次 → AC5。`own_prepared` 分支让这个函数在没有预热句柄时仍能独立工作（`stream_realtime_segments` 被非 agent 路径调用时），预热逻辑与流式逻辑共用同一个 `prewarm_cosyvoice_realtime`。

段与段之间不再有 `run-task`/`task-started` RTT，也不再 `await _forward_task_audio(...)`——第 2 段的 `continue-task` 在 `async for` 的下一轮立刻发出，与 reader 收第 1 段音频重叠（AC5 后半）。

### reader：段标记与音频帧解耦

`_forward_stream_audio` 是 `_forward_task_audio` 的替代，机制照搬 `realtime_tts._forward_tts_upstream_audio:399-459` 的 `ensure_segment_started` / `finish_active_segment` 闭包：

```python
active_segment = None
segments_finished = False

async def finish_active_segment():
    nonlocal active_segment
    if active_segment is None:
        return
    await _send_segment_end(send, int(active_segment['index']))
    active_segment = None

async def ensure_segment_started():
    nonlocal active_segment, segments_finished
    if segments_finished:
        return
    if active_segment is not None and segment_queue.empty():
        return              # 没有待播段就维持当前段
    segment = await segment_queue.get()
    if segment is None:
        segments_finished = True
        return
    await finish_active_segment()
    active_segment = segment
    await _send_segment_start(send, int(segment['index']), str(segment['text']))
```

事件分派：

| 上游事件 | 动作 |
|---|---|
| `bytes`（非空） | `ensure_segment_started()` → 原样转发 → `stats` 累加 |
| `task-failed` | `raise RuntimeError(_extract_cosyvoice_task_error(header))` |
| `task-finished` | `finish_active_segment()` → `tts.done` → return |
| 上游先关闭 | `raise RuntimeError('CosyVoice upstream closed before task finished.')` |

段标记近似语义（prd 已确认接受，落地时进一步放宽）：CosyVoice **没有** `response.audio.done` 这类逐段音频结束事件（`realtime_tts` 有，所以那边的闭包能靠上游事件收尾），单 task 下音频帧完全不带段归属。因此 `ensure_segment_started` 的实际规则是「每收到一帧音频，若队列里还有待播段就前移一段（先 `finish_active_segment()` 再开新段）；队列空则维持当前段」，即**段标记比它标注的音频跑得更前**，而不是「段 N 的 `segment_start` 在该段第一帧音频到达时发出」。

照搬 `realtime_tts` 的原始条件（`if active_segment is not None: return`）在这里会退化成「只有第 1 段有标记、后续段一个都不发」——比跑得偏前更糟（N 段文本只出 1 对标记）。现规则保证的是**格式正确**：每段恰好一对 `segment_start` / `segment_end`，序号从 1 递增，顺序不乱。下游事件类型与序列不变：`tts.ready` → `tts.segment_start` → binary PCM → `tts.segment_end` → … → `tts.done`。已核实无任何客户端功能性依赖这两个事件的对齐关系（见「已知代价」）。

`await reader_task`（而不是 fire-and-forget）保证 reader 的异常向上冒；任何异常路径都先 `cancel()` + `gather(return_exceptions=True)`，不静默吞（prd R3）。`ConnectionClosed`（含单 task 长存期间的上游空闲超时被动断开）沿用既有 except 分支，向上抛给 `_agent_tts_worker` → `TTS_UPSTREAM_ERROR`，不静默丢音频。

`stream_cosyvoice_realtime_text`（单段变体，127-200）不动——它本来就是一次 `run-task` + 一次 `finish-task`，没有段间空档问题。

### 已知代价

`runtime-api-console.html` 调试面板的「文本 ↔ 音频」对应关系会漂移。已核实 `app.js`（只处理 `tts.ready` / `tts.done` / `tts.error`）、`runtime-api-console.html`（功能上只消费 `llm.tts_segment` / `tts.ready` / `tts.done` / `tts.error`）、`android-api-simulator.html`（都不处理）**没有任何一处功能性依赖 `tts.segment_start` / `tts.segment_end`**，播放行为不受影响。

## 4. 数据流与契约汇总

### 下游 WS 事件（对客户端零变更）

`agent.started` → `asr.*` → `llm.started` → `llm.delta`* → `llm.tts_segment`* → `tts.ready` → (`tts.segment_start` → PCM* → `tts.segment_end`)* → `tts.done` → `llm.done` → `agent.done`。错误仍是 `tts.error`（`TTS_UNAUTHORIZED` / `TTS_VOICE_NOT_AVAILABLE` / `TTS_NOT_READY` / `TTS_UPSTREAM_ERROR`）与 `agent.error`。

### 内部签名变更

| 符号 | 变更 |
|---|---|
| `tts.pop_tts_text_segments` | `+ emitted_segments: int = 0` |
| `realtime._pop_llm_tts_segments` | `+ emitted_segments=0`（透传） |
| `tts_adapters.BaseTTSAdapter.prepare_realtime_stream` | 新增，默认 `return None` |
| `tts_adapters.*.stream_realtime_segments` | `+ prepared=None` |
| `cosyvoice_realtime.prewarm_cosyvoice_realtime` | 新增 |
| `cosyvoice_realtime.CosyVoicePrewarmedTask` | 新增 |
| `cosyvoice_realtime.stream_cosyvoice_realtime_segments` | `+ prepared=None`；内部改单 task + reader |
| `cosyvoice_realtime._forward_task_audio` | 被 `_forward_stream_audio` 取代（后者签名带 `segment_queue`） |
| `realtime._prepare_agent_tts` | 新增（从 `_run_agent_tts_stream` 搬出） |
| `realtime._run_agent_tts_stream` | `+ prepared_bundle` 参数；删掉搬走的解析段 |
| `RealtimeConnection` | `+ agent_tts_prepared` 字段、`+ close_agent_tts_prepared()` 方法 |

数据库、迁移、REST API、租户/授权派生逻辑（`tts_authorization.py`）**零改动**。

## 5. 影响面与风险

gitnexus impact（upstream）：`pop_tts_text_segments` LOW（1 生产调用方）；`_run_agent_tts_stream` LOW（3 层皆在 `config` 内）；`stream_cosyvoice_realtime_segments` 报 HIGH 但 `direct: 1`，唯一调用方是 `CosyVoiceTTSAdapter.stream_realtime_segments`，HIGH 系索引噪声。

| 风险 | 缓解 |
|---|---|
| 单 task 长存被上游空闲超时断开 | 走既有 `ConnectionClosed` → `TTS_UPSTREAM_ERROR`；实测复验（AC7）时观察是否出现 |
| 首段 12 字导致音色/语调不自然 | 阈值是常量，可一行调大；本轮不做可配置（prd 明确排除） |
| 预热在 ASR 模式下提前很久（用户长时间说话） | 空闲连接由 `close_agent_tts_prepared` 三路径覆盖；若上游有空闲上限，表现为断连错误而非静默 |
| 段标记漂移误导调试 | 只影响调试面板，已在 prd 显式接受 |

## 6. 回滚形状

三块独立：
- R1：`_hits_tts_boundary` 软边界分支 `return False` + 循环里去掉 `_hits_tts_word_gap` 分支。
- R2：`_agent_tts_worker` 不调 `_prepare_agent_tts`，改回在 `_run_agent_tts_stream` 内解析；`prepared` 全链路传 `None`。
- R3：`stream_cosyvoice_realtime_segments` 恢复 per-segment `run-task` + `_forward_task_audio`（`prepared=None` 时的独立路径已经覆盖了「自己开连接」的形态，回滚只需换回循环体）。

R2 与 R3 有耦合：R3 的单 task 依赖 R2 在预热阶段发出 `run-task`。若只回滚 R2，`prepared=None` 分支会让 R3 在流式入口自行预热，仍为单 task，功能正确，只是丢掉并行收益。反向（只回滚 R3、保留 R2）也成立：`prepared` 句柄可以被 per-segment 版本用作第一段的连接。
