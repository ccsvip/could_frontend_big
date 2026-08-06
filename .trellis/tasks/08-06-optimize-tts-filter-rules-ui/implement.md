# Implement: 过滤规则 UI 全套重做

## Checklist

1. **纯函数**（`application-management/index.tsx` 顶层，紧挨现有 `buildTtsFilterPunctuation`）
   - [ ] `TTS_FILTER_CHAR_PRESETS`
   - [ ] `listVisibleTtsFilterChars`
   - [ ] `removeTtsFilterChar` / `toggleTtsFilterChar` / `addTtsFilterChars`（统一 64 上限与 hiddenCost）
   - [ ] 保持 `visibleTtsFilterPunctuation` / `buildTtsFilterPunctuation` / `normalizeTtsFilterExcludePatterns` 语义

2. **UI 替换**（`renderConversationSettingsTab` 内 Voice Card：过滤规则 + 不播报文本两段）
   - [ ] 三子区块结构（自动过滤 / 不播报字符 / 不播报文本）
   - [ ] 开关文案去 CR/LF
   - [ ] Chip 列表 + 预设 toggle + 自定义 Input/添加
   - [ ] 不播报文本样式 fluid 化与统一空态
   - [ ] 草稿 state：`newTtsFilterCharInput`（字符）；复用 `newTtsFilterExcludePattern`

3. **可选** 若区块 JSX 过长 → 抽 `tts-filter-rules-panel.tsx`，props 按 design.md

4. **不动**
   - save/dirty/apply/试听传参字段名
   - API modules
   - 后端

5. **验证**
   - [ ] 手动：预设 toggle、自定义多字符、删 chip、空格/换行开关与 chip 隔离、64 上限、片段 20/120、关播报仍可编、只读权限
   - [ ] 保存回读
   - [ ] 调试区试听仍过滤
   - [ ] `cd web && npm run build`

## Risky points

- `Array.from` 与现网一致，勿 `split('')`
- `buildTtsFilterPunctuation` 已对 visible 去隐藏字符；chip 路径不要二次把 space 写进 visible
- maxLength 计算：hidden 占 1 或 2，与现 Input maxLength 公式对齐
- 大文件冲突：只改过滤子树 + 顶层 helper，避免无关 format

## Validation commands

```bash
cd web && npm run build
# optional token guard on changed tsx:
node scripts/check-tailwind-tokens.js
```

## Rollback

`git checkout -- web/src/views/application-management/index.tsx`（及若有的 panel 文件）
