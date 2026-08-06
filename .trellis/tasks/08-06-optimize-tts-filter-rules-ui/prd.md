# 优化智能体对话设置过滤规则 UI

## Goal

在 `/ai-models/applications/:id` → 对话设置中，对「播报过滤」做全套体验重做（信息架构 + 文案 + 交互 + 视觉），让运营能一眼看懂「播报前会删什么 / 不会删什么」，并用 chip + 快捷预设低成本配置字符黑名单与不播报片段。

**不改**后端字段语义、过滤算法、设备运行时契约、试听链路入参形状。

## Background

入口：`web/src/views/application-management/index.tsx` → `renderConversationSettingsTab` → Voice Settings Card（回复播报下方）。

| 能力 | 字段 | 现网 UI 问题 |
|------|------|-------------|
| 过滤表情 | `ttsFilterEmoji` | pill 开关尚可，但与字符/片段层级混杂 |
| 过滤半角空格 | `ttsFilterPunctuation` 含 `' '` | 文案「CR/LF」偏实现向 |
| 过滤换行 | `ttsFilterPunctuation` 含 `'\r\n'` | 同上 |
| 可见字符黑名单 | `ttsFilterPunctuation` 去掉空白 | 单行 Input，难扫读、无预设 |
| 不播报片段 | `ttsFilterExcludePatterns[]` | 列表可用，视觉与上半区不统一；`text-sm`/`text-xs` 未走 fluid |

辅助（同文件，语义保留）：

- `visibleTtsFilterPunctuation` / `buildTtsFilterPunctuation`
- `normalizeTtsFilterExcludePatterns`（trim + 去重 + 最多 20）
- 上限：punctuation 总长 64（含隐藏 space/CR/LF）；片段单条 120 字

约束：

- 仅上述三字段改 LLM→TTS 文本；不剥 Markdown、不折叠空白、不硬切长度
- 试听：`agentAudio.playText` / stream 仍传 `{ punctuation, emoji, excludePatterns }`
- Token：`text-fluid-*`、`brand-*`；禁业务页 `!` / `teal-*` / `text-[Npx]`
- 左栏 `minmax(360px, 560px)`，chip/预设必须可 wrap

## Decisions

| ID | 决策 | 结论 |
|----|------|------|
| D1 | 范围 | 全套体验重做 |
| D2 | 字符过滤交互 | Chip 可删标签 + 快捷预设 + 自定义添加 |
| D3 | 预设字符 | 精简 Markdown：`-` `*` `#` `_` `` ` `` `~` `>` `\|` |
| D4 | API/算法 | 不变；空格/换行仍投影进 `ttsFilterPunctuation`，不进 chip |
| D5 | 播报关 / TTS 未就绪 | 过滤区**始终完整可配**（与播报开关解耦） |
| D6 | 效果预览 | 不做独立预览；靠右侧调试区试听 |
| D7 | 不播报片段编辑 | 仅删 + 重加，不行内编辑 |
| D8 | 组件拆分 | 优先同文件内聚小组件/辅助函数；若 JSX 块过大再抽同目录小组件（不新建路由/状态库） |

## Requirements

### R1 信息架构

在「回复播报」主开关下重组为三个子区块（顺序固定）：

1. **自动过滤** — 三个开关：表情、半角空格、换行  
2. **不播报字符** — chip 列表 + 预设 + 自定义添加  
3. **不播报文本** — 输入添加 + 列表删除（上限展示）

每个子区块有简短运营向说明；去掉「CR/LF」「字面反斜杠和 n」等实现黑话。保留一句能力边界提示：**不会自动删除 Markdown 结构或中文句读，只去掉你明确勾选/添加的内容**。

### R2 自动过滤开关

- 表情 → `ttsFilterEmoji`
- 半角空格 / 换行 → 仍通过 `buildTtsFilterPunctuation` 写入 punctuation 隐藏字符
- 开关在窄屏自动换行；`!canUpdate` 时禁用
- 文案示例（可微调，语义不变）：
  - 过滤表情
  - 过滤半角空格
  - 过滤换行

### R3 不播报字符（Chip + 预设）

- 将 `visibleTtsFilterPunctuation(ttsFilterPunctuation)` 拆成单字符 chip，点击删除（或 chip 关闭）即从集合移除并 `buildTtsFilterPunctuation` 写回
- 快捷预设固定 8 项：`- * # _ \` ~ > |`；已选中的预设呈选中态，再点可取消（toggle）
- 自定义添加：输入 1+ 可见字符后确认（Enter/按钮）；自动去掉空格/CR/LF（改走对应开关）；去重；空输入提示
- 长度：与现网一致，visible + 隐藏字符总长 ≤ 64；超限阻止添加并 `message.warning`
- 空态：明确「未添加不播报字符」
- 空格/换行**永不**出现在 chip 列表

### R4 不播报文本片段

- 保持 `MAX_TTS_EXCLUDE_PATTERN_COUNT=20`、`MAX_TTS_EXCLUDE_PATTERN_LENGTH=120`、normalize 去重
- 添加：Input + 按钮 + Enter；满额禁用
- 列表：只读展示 + 删除；不行内编辑
- 视觉与 R3 统一（圆角、间距、fluid 字号、空态虚线框）
- 计数 Tag：`n/20`

### R5 视觉与 token 收口（本区块）

- 本 Voice 过滤相关标题/说明/列表文案统一 `text-fluid-*`（不再混 `text-sm`/`text-xs`/`text-base` 于该过滤子树）
- 与对话设置其它 Card 的「标题 + 说明 + 控件」节奏对齐，但不强制改开场白/建议问题整卡
- 禁止新增 `!` 前缀类、`teal-*`、硬编码像素字号

### R6 状态与保存契约（回归）

- `applyApplicationState` / dirty check / `handleSaveConfig` payload 字段名与归一化逻辑保持正确
- 试听与 stream playback 继续使用当前 state 中的三字段
- 无后端、无 API module 变更

## Out of Scope

- 后端 Serializer/模型拆字段或迁移默认值
- TTS 过滤算法、分段边界、CosyVoice 协议
- 独立「过滤效果预览」组件
- 不播报片段行内编辑 / 拖拽排序
- 正则、Markdown 自动剥离等新过滤能力
- 设备管理页、运行时配置其它 UI
- 对话设置其它卡片的全面重构

## Acceptance Criteria

- [ ] AC1 对话设置 → 回复播报下可见三个子区块：**自动过滤 / 不播报字符 / 不播报文本**，顺序与 R1 一致
- [ ] AC2 自动过滤三开关文案无「CR/LF」等实现黑话；开关行为与现网字段映射一致（表情独立 bool；空格/换行写入 punctuation）
- [ ] AC3 不播报字符以 chip 展示；删除 chip 后 state 与将保存的 `ttsFilterPunctuation` 同步去掉该字符
- [ ] AC4 预设 `- * # _ \` ~ > |` 可 toggle 添加/移除；已存在时呈选中态
- [ ] AC5 自定义添加支持多可见字符拆入集合、去重；拒绝纯空白；隐藏空白不进 chip
- [ ] AC6 punctuation 总长（含隐藏 space/CR/LF）超过 64 时不能再添加，并有明确提示
- [ ] AC7 不播报文本仍最多 20 条、单条 120 字；仅支持添加与删除；计数与空态正确
- [ ] AC8 回复播报关闭或 TTS 未就绪时，过滤三区仍完整可编辑（`canUpdate` 为真时）
- [ ] AC9 `!canUpdate` 时全部控件只读/禁用
- [ ] AC10 保存后重新进入详情，三字段回读与保存值一致（含空格/换行开关状态）
- [ ] AC11 调试区试听/流式播报仍按当前过滤规则生效（无回归）
- [ ] AC12 本改动区块无新增 `!` 前缀 Tailwind、`teal-*`、`text-[Npx]`；窄屏 chip/预设换行不撑破左栏
- [ ] AC13 `npm run build`（`web/`）通过

## Risks / Notes

- `index.tsx` 已很大：新增 UI 逻辑尽量抽文件顶层纯函数 + 小渲染片段，避免再堆 100+ 行进主组件中部
- chip 拆字符时注意多码点/代理对：现网 punctuation 按 `Array.from` 字符处理，新增逻辑必须一致
- 预设 toggle 与自定义添加共用同一集合，避免两套 state
