---
name: Solin LLM Configuration Design System
description: 数字人后台管理平台 (solin) 的大语言模型配置界面设计系统
colors:
  primary: "#14b8a6"
  primary-hover: "#0d9488"
  primary-deep: "#0f766e"
  primary-bg: "#f0fdfa"
  neutral-bg: "#eef3f1"
  neutral-card: "#ffffff"
  neutral-border: "#edf2f0"
  neutral-text: "#0f172a"
  neutral-muted: "#64748b"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  mono:
    fontFamily: "Consolas, 'SFMono-Regular', Monaco, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "14px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral-card}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
---

# Design System: Solin LLM Configuration

## 1. Overview

**Creative North Star: "The Technical Sanctuary (科技静修所)"**

本项目设计旨在为开发与运维人员打造一个低认知负荷、高信息清晰度、科技感且克制的管理系统界面。我们摒弃了市面上 SaaS 模板常见的高饱和度霓虹渐变、过度圆角、深色磨砂玻璃等干扰视线的设计。所有的信息呈现都应当遵循直观、严谨的网格逻辑。

### Key Characteristics:
- **克制的主色调**：以青绿色 (Teal) 承载品牌主色，严格控制其出现比例，不抢占内容焦点。
- **等宽对齐**：API 端点、API 密钥、系统标识符、模型代号等字段必须等宽字体化，防错防漏。
- **界面呼吸感**：使用舒缓的行间距与轻量的表头，降低复杂表格的数据噪音。

## 2. Colors

整个页面风格冷静克制，色彩主要用于表示可操作状态与功能区隔，杜绝无意义的视觉粉饰。

### Primary
- **Brand Teal** (#14b8a6 / oklch(0.70 0.17 190)): 用于主操作按钮、关键品牌元素及启用状态的高亮表示。
- **Hover Teal** (#0d9488 / oklch(0.62 0.17 190)): 用于主动作按钮悬浮态。
- **Deep Teal** (#0f766e / oklch(0.51 0.14 190)): 用于激活、选中的文字颜色。

### Neutral
- **Background** (#eef3f1): 全局页面背景，带有极低饱和度的冷色 off-white，带来清爽的技术感。
- **Card Fill** (#ffffff): 卡片及模态框的底色。
- **Ink Main** (#0f172a): 主要标题和主体正文文字。
- **Ink Muted** (#64748b): 辅助说明文字、未激活状态的标签。
- **Border Light** (#edf2f0): 页面分割线、轻量卡片描边。

### Named Rules
**The Teal Core Rule.** 整个页面除代表成功/失败/警告的语义颜色（绿色、红色、黄色）外，所有的彩色视觉焦点、主操作区和激活边框统一使用 Teal。禁止引入紫色、蓝色或粉色。

## 3. Typography

**Display Font:** -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif
**Body Font:** -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif
**Label/Mono Font:** Consolas, "SFMono-Regular", Monaco, monospace

### Hierarchy
- **Display** (Bold (700), 1.25rem (20px), 1.25): 用于主要板块头部大标题，传达自信。
- **Headline** (SemiBold (600), 1.0rem (16px), 1.4): 用于 Modal 标题、卡片子块大字。
- **Title** (Medium (500), 0.875rem (14px), 1.4): 表格表头、Form Label。
- **Body** (Regular (400), 0.875rem (14px), 1.5): 正文文字、表格行内文字。
- **Label/Mono** (Regular (400), 0.75rem (12px), 1.5): 适用于 API 地址、秘钥等技术串。

### Named Rules
**The Mono Alignment Rule.** 所有密钥、环境变量名、端点 URL 和真实模型代号统一使用等宽字体样式，并配以轻量灰底，提高阅读准确性。

## 4. Elevation

本系统提倡扁平化的视觉流，避免大阴影干扰眼球。主要通过 `Border Light` 进行物理分割，仅在悬浮与重点气泡弹窗时使用微阴影。

### Shadow Vocabulary
- **Card Shadow** (`0 1px 2px rgba(15, 23, 42, 0.04), 0 6px 18px rgba(15, 23, 42, 0.04)`): 卡片及容器在正常态下的极轻量阴影。
- **Hover Shadow** (`0 4px 10px rgba(15, 23, 42, 0.06), 0 12px 32px rgba(15, 23, 42, 0.08)`): 可操作的卡片在鼠标悬停时的立体高光阴影。

## 5. Components

### Buttons
- **Shape:** 8px 圆角 (`rounded-md`)
- **Primary:** Teal 填充 (#14b8a6)，白色文字。悬停状态渐变过渡至 Hover Teal (#0d9488)。
- **Secondary / Bordered:** 细描边 (#edf2f0)，悬停边框及文字高亮为 Deep Teal (#0f766e)。

### Cards / Containers
- **Corner Style:** 12px 或 14px 圆角
- **Border:** 1px 实线描边，颜色为 Border Light (#edf2f0)。
- **Shadow:** 默认使用 `Card Shadow`。

### Inputs / Fields
- **Corner Style:** 8px 圆角
- **Focus:** 激活时边框高亮为 Teal，内阴影发光限制在極淡的 Teal 晕影。

### Status Tags
- **Component:** `<StatusTag />` (`web/src/components/status-tag.tsx`)
- **Tokens:** Uses `brand-*` semantic color pairs (`online`, `offline`, `active`, `inactive`, `bound`, `unbound`, `pending`) with a pulsing or static dot indicator.
- **Typography:** Built-in `text-fluid-xs` responsive fluid typography.

## 6. Do's and Don'ts

### Do:
- **Do** 在所有主要操作按钮、激活状态、和品牌标识上统一使用 Teal 青绿色。
- **Do** 限制 Card 与表格容器的圆角大小至 12px - 14px 之间，保持冷静的结构。
- **Do** 确保所有的 API Key、Endpoint、Model Name 使用 `font-mono` 样式承载并支持复制。

### Don't:
- **Don't** 使用侧边色条描边（如 border-left 4px 紫色条）来区分状态或分类卡片。
- **Don't** 使用紫色 (#8b5cf6) 或粉色作为激活主色或界面点缀。
- **Don't** 在表头或文字上使用非功能性的渐变色裁剪 (`background-clip: text`)。
