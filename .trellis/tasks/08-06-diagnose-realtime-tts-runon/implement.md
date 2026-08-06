# Implement: 智能体 TTS 严格过滤与无损分段

## Preconditions

- [ ] 用户批准本任务的最终规划摘要后才开始产品代码修改
- [ ] 运行 `trellis-before-dev`，读取 implement/check manifests 中的规范
- [ ] 重新读取所有目标文件的最新片段，适应用户并行改动
- [ ] 对将修改的导出/跨层符号重新运行 GitNexus impact；HIGH/CRITICAL 必须先告警

## Checklist

### 1. 固定规则契约的回归测试

- [ ] 在 `backend/apps/ai_models/tests/test_tts_api.py` 先写失败测试：规则留空时完整保留 Markdown、列表横线、空格、CR/LF 和句读
- [ ] 写失败测试：字符/emoji/排除文本只按页面配置和既定顺序删除
- [ ] 写分段守恒测试：`''.join(segments) == expected_filtered_text`
- [ ] 写全切点参数化测试：将同一回答按每一个可能 delta 边界输入，flush 后结果与一次性规则函数一致
- [ ] 覆盖跨 delta 排除文本、重叠规则、完全删除、未完成前缀 flush

### 2. 后端规则过滤与无损分段

- [ ] 在 `backend/apps/ai_models/services/tts.py` 提取唯一完整文本规则函数，固定“不播报文本 → emoji → 配置字符”顺序
- [ ] 实现携带原始边界元数据的有状态流式排除文本过滤器；字符被删时边界信号仍保留
- [ ] emoji 与字符过滤改为明确的逐字符阶段
- [ ] 重写 `split_tts_text()` / `pop_tts_text_segments()`：只切片，不 strip、折叠、替换或恢复字符
- [ ] 删除不再有职责的 Markdown TTS sanitizer/默认过滤分支；迁移全部调用者，不留别名
- [ ] 后端两个切分器与前端 segment extractor 只在原文句读、CR/LF 或最终 flush 处分段；边界字符归前段
- [ ] 删除 12/30/80 长度阈值、空格/闭合括号/引号切点及所有 `length >= 80` 分支，不增加替代硬上限
- [ ] 流式实现只处理新增 delta，禁止反复扫描/复制完整累计回答；无排除文本时过滤器不得暂存前缀；空白-only delta 不得被判空丢弃


### 3. WebSocket 与 adapter 无损传递

- [ ] `backend/config/realtime.py`：移除 `_send_llm_tts_segment()` 等 TTS 边界的 `.strip()`
- [ ] `_agent_tts_segments()` 使用同一个流式规则状态，不在每个 delta 重跑完整 sanitizer
- [ ] `backend/apps/resources/services/command_dispatch.py` 使用同一规则/分段入口
- [ ] `backend/apps/ai_models/services/cosyvoice_realtime.py` 不裁剪 segment；`continue-task` 发送原切片
- [ ] 检查 `realtime_tts.py`、`tts_adapters.py` 和其他 provider adapter，删除所有页面规则之外的文本变换
- [ ] 确保 `llm.tts_segment` 事件、结构化日志和 adapter 收到的文本逐字符相同；只跳过页面规则删除后的真正空字符串
- [ ] 保持 `_prepare_agent_tts()` 先于 `queue.get()`；上游 task 有效的正常路径首段前不新增 ORM、网络或其他 awaited 操作
- [ ] 保持单 CosyVoice task、双工 `continue-task` 和 PCM 到达即转发，不等待上一段音频
- [ ] CosyVoice `continue-task` 只发送真实安全切片，不把消息边界当作新增标点；其他 adapter 仅在真实边界或 flush 时 commit
- [ ] 在 CosyVoice adapter 校验单消息 20,000、累计 200,000 字符；首段前陈旧预热句柄按 23 秒限制安全重建；流中不可分超限句显式 TTS 失败且不阻塞 `agent.done`
- [ ] 保持 ASR/LLM 会话、设备鉴权、控制命令、中断、错误隔离、WebSocket type 与 `agent.done` 契约不变


### 4. 特殊字符 API 与数据迁移

- [ ] `AgentApplicationSerializer.ttsFilterPunctuation` 设置 `trim_whitespace=False`
- [ ] validator 只去重和校验 64 字符，不裁剪 U+0020/CR/LF
- [ ] 新增 ai_models 数据迁移：精确字面 `\\n` 的 draft/published 改为真实 `" \r\n"`
- [ ] reverse migration 只回退精确迁移值，不触碰其他自定义字符
- [ ] API 测试覆盖保存、读取、发布快照、runtime_config 与 `is_published_current`

### 5. 智能体页面特殊字符选项

- [ ] 保持 `ttsFilterPunctuation` 为唯一 canonical state，不新增 API 布尔字段
- [ ] 可见字符输入框隐藏 U+0020/CR/LF，但保留其他字面字符
- [ ] 增加“过滤半角空格”和“过滤换行（CR/LF）”可视化选项
- [ ] toggle 直接向 canonical string 添加/删除真实字符
- [ ] 更新 payload normalization、dirty 检测、published mismatch 与帮助文案
- [ ] 遵守 `brand-*`、`text-fluid-*`、响应式和 Tabler 图标规范，不增加历史 token 违规

### 6. 浏览器播报严格契约

- [ ] `web/src/views/tts-realtime-playback.ts` 删除隐式 Markdown/空白清理；无规则调用必须是 identity
- [ ] `web/src/views/application-management/use-agent-audio.ts` 的 segment extractor 返回无损切片，不用 `trim()` 丢弃空白-only delta
- [ ] 实现 TypeScript 跨 delta 排除前缀与原始边界元数据保护，静态播放和流式播放复用同一规则语义
- [ ] 单次和流式路径各只应用一轮规则；删除队列消费阶段第二次排除文本/字符过滤
- [ ] 使用共享 fixture 对照 Python/TypeScript：Markdown、空格、换行、emoji、配置字符、跨 delta pattern、过滤边界字符
- [ ] 中断/重开 session 时同步清空规则过滤器状态，不能泄漏到下一次回答

### 7. 定向验证

- [ ] 容器内运行 ai_models TTS/API/adapter 定向测试
- [ ] 容器内运行 realtime WebSocket 与 command dispatch 定向测试
- [ ] 运行前端 build/type check
- [ ] 浏览器验证智能体页面：两个特殊字符选项、保存、刷新、发布、dirty/mismatch
- [ ] 用 `apifox` 只问“你们公司有哪些产品”，保存 requestId/traceId/conversationId
- [ ] 对账 answerText、规则期望、`llm.tts_segment` 拼接、CosyVoice `continue-task`
- [ ] 实际播放并确认产品项顺序与停顿；未配置 `-` 时验证横线确实保留
- [ ] 运行并保留预热顺序、单 task、双工发送、取消/空回答资源回收、TTS 失败仍到达 `agent.done` 的既有测试
- [ ] 用固定 delta 序列断言首个真实停顿边界在到达它的同一次处理内 emit；80/81/200 字无句读文本非 flush 时不得产生 segment
- [ ] 浏览器连续执行三次指定问题，记录关键区间中位数；要求 `segment → ready <= 102ms`、`ready → PCM <= 1.15s`
- [ ] 检查 GitNexus 影响面与定向测试，确认未改变 ASR、LLM、设备鉴权、控制命令和非目标 adapter 行为
- [ ] 运行 GitNexus `detect_changes()`，确认只波及预期 TTS/智能体配置流程

### 8. Smoke test 通过后的清理

- [ ] 删除旧 sanitizer、无用 import、旧默认常量、重复规则函数和过时注释
- [ ] 检查 API 类型、相关文档和调试控制台是否需同步；只更新真实受影响契约
- [ ] 运行最终定向测试与前端 build，确认清理未改变结果

## Validation Commands

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_tts_api apps.ai_models.tests.test_agent_application_api apps.ai_models.tests.test_tts_adapters --keepdb
docker compose exec backend python manage.py test config.tests.test_realtime_websocket apps.resources.tests --keepdb
docker compose exec web npm run build
```

最终真实验证使用 `/ws/realtime/` 的 `agent.session.start`，设备码固定为 `apifox`，问题固定为“你们公司有哪些产品”。

## Expected Files

| 文件 | 目的 |
|---|---|
| `backend/apps/ai_models/services/tts.py` | 唯一规则函数、流式规则状态、无损分段 |
| `backend/apps/ai_models/serializers.py` | 空格/换行 round-trip |
| `backend/apps/ai_models/migrations/0055_*.py` | 历史字面 `\\n` 数据迁移 |
| `backend/config/realtime.py` | 设备三合一流式状态与无损事件 |
| `backend/apps/resources/services/command_dispatch.py` | 控制命令回复统一契约 |
| `backend/apps/ai_models/services/cosyvoice_realtime.py` | 上游 `continue-task` 无损文本 |
| `backend/apps/ai_models/realtime_tts.py` | 非 CosyVoice 实时路径复用 |
| `web/src/views/tts-realtime-playback.ts` | 浏览器规则函数 |
| `web/src/views/application-management/use-agent-audio.ts` | 浏览器流式状态与无损分段 |
| `web/src/views/application-management/index.tsx` | 特殊字符可视化配置 |
| 相关定向测试 | 固定跨层契约和迁移行为 |

## Risk Gates

- GitNexus 已评估主要后端符号与流式 splitter 为 LOW；前端同名 sanitizer 结果有两个候选，实施前按 UID 重跑。
- 若有 adapter 依赖 `strip()` 才能通过上游校验，不能恢复静默裁剪；应在分段器中保持原文并仅避免发送真正空字符串，再以 provider 实测决定是否需要明确错误。
- 不允许通过修改 system prompt、知识库答案或默认过滤字符来让本次样本“看起来通过”。
- 任一正常路径性能结构守卫失败（新增首段 await/I/O、真实边界到达后延迟入队、取消预热、单 task 变多 task、双工变串行）都必须回退实现，不允许恢复字符硬切或仅放宽毫秒阈值；唯一例外是已接近供应商 23 秒上限且尚未承载文本的陈旧预热 task 重建。
- 真实网络计时超限先在同环境重跑；只有确定性结构守卫通过且重复结果恢复后才可归因于阿里公网抖动。
- 不可分句段触及供应商字符/时间极限时必须明确 TTS 失败并保留 LLM 正常完成；禁止为规避上游限制静默插入标点或从中间截断。

## Out of Scope

- 修改“你们公司有哪些产品”的答案内容
- 自动加入 `-`、`*`、标点或 Markdown 默认过滤
- 更换音色、CosyVoice 模型或 WebSocket 协议
- 新增第二条业务 WebSocket
