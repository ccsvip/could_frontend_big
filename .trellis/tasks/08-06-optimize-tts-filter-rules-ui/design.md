# Design: 过滤规则 UI 全套重做

## Scope boundary

- **In**: `web/src/views/application-management/index.tsx` 对话设置 Voice Card 内过滤相关 JSX + 顶层纯辅助函数；必要时同目录抽展示小组件。
- **Out**: API、Serializer、过滤算法（`tts-realtime-playback.ts` / 后端 filter）、其它 Tab。

## Data model (unchanged)

```
ttsFilterEmoji: boolean
ttsFilterPunctuation: string  // 可见字符 ∪ 可选 ' ' ∪ 可选 '\r\n'，去重后 join，总长 ≤ 64
ttsFilterExcludePatterns: string[]  // normalize: trim, dedupe, max 20, each ≤ 120
```

UI 投影：

```
visibleChars = Array.from(visibleTtsFilterPunctuation(punctuation))  // chip 数据源
filtersSpace = punctuation.includes(' ')
filtersLineBreak = punctuation.includes('\r') || punctuation.includes('\n')
```

写回：

```
buildTtsFilterPunctuation(visibleJoined, filtersSpace, filtersLineBreak)
```

## Interaction design

### 自动过滤

三个开关横排/wrap，图标可保留（MoodSmile / Space / CornerDownLeft），文案去技术黑话。

### 不播报字符

```
[说明]
[chip][chip][chip] … | 空态
预设: [-][*][#][_][`][~][>][|]   // toggle，选中 = 集合内
[ Input 自定义 ] [添加]
```

状态操作（均落到单一 `setTtsFilterPunctuation`）：

| 动作 | 逻辑 |
|------|------|
| 删 chip `c` | visible 去掉 c，rebuild |
| toggle 预设 `c` | 有则删、无则加（先检查 64 上限） |
| 自定义提交 | `Array.from(input)` 去掉空白与空字符，逐个并入 Set；超限中止并提示；清空 input |

上限计算：

```
hiddenCost = (space?1:0) + (lineBreak?2:0)  // '\r\n' 两字符
room = 64 - hiddenCost - visibleChars.length
```

添加前 `room < 新增去重后新字符数` → warning。

### 不播报文本

保持现有 add/remove/normalize；样式与字符区统一（fluid 字号、圆角列表行、虚线空态、`n/20` Tag）。

## Component shape

推荐（降低 `index.tsx` 膨胀）：

1. **同文件顶层纯函数**（必做）  
   - `TTS_FILTER_CHAR_PRESETS = ['-', '*', '#', '_', '`', '~', '>', '|'] as const`  
   - `listVisibleTtsFilterChars(punctuation: string): string[]`  
   - `toggleTtsFilterChar(punctuation, char, space, lineBreak): { next: string; error?: string }`  
   - `addTtsFilterChars(punctuation, rawInput, space, lineBreak): { next: string; error?: string; added: number }`  
   - `removeTtsFilterChar(...)`  
   纯函数便于日后单测，主组件只绑 state。

2. **可选抽离** `tts-filter-rules-panel.tsx`（若 JSX > ~80 行）  
   Props：  
   `canUpdate`, `emoji`, `onEmojiChange`, `punctuation`, `onPunctuationChange`, `excludePatterns`, `onExcludePatternsChange`  
   内部自持 `newCharInput` / `newExcludeInput` 草稿 state。  
   **不**接入 react-query/全局 store。

主组件保留：`ttsFilter*` state、save/dirty/apply、试听传参。

## Copy (canonical)

| 位置 | 文案 |
|------|------|
| 自动过滤标题 | 自动过滤 |
| 自动过滤说明 | 播报前去掉这些内容；不影响聊天区原文显示 |
| 过滤换行 | 过滤换行（不再写 CR/LF） |
| 不播报字符标题 | 不播报字符 |
| 不播报字符说明 | 逐字去掉；半角空格与换行请用上方开关。不会自动删除 Markdown 或中文句读 |
| 不播报文本标题 | 不播报文本 |
| 不播报文本说明 | 整段匹配移除；其余内容继续播报 |
| 字符空态 | 未添加不播报字符 |
| 文本空态 | 暂未配置不播报文本 |
| 超限 | 不播报字符过多（含空格/换行占用），请先删除部分字符 |

## Visual tokens

- 小节标题：`text-fluid-sm font-bold text-slate-700`（或与 Card 主标题区分的次级）
- 说明：`text-fluid-xs text-slate-400`
- Chip：`rounded-full` / `border-slate-200` / `bg-slate-50`；选中预设可用 `border-brand-200 bg-brand-50 text-brand-700`
- 列表行：`rounded-xl border border-slate-100 bg-slate-50/60`
- 禁止：`!` 前缀、`teal-*`、`text-[Npx]`、`text-sm`/`text-xs` 混用在本子树

## Compatibility

- 已存 punctuation 含任意可见字符：chip 全量展示，不限于预设
- 已含 space/CR/LF：只反映在开关，不进 chip
- 旧数据无迁移

## Rollback

单文件/单组件 UI 回退；无 DB、无 API 迁移。
