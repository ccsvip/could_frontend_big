Status: ready-for-agent

# UI 设计 System 规范融合与排版布局优化 Spec

## Problem Statement

目前前端代码库（`web/src/`）在整体 UI 呈现和架构规范上存在以下主要问题：
1. **排版规范断层**：项目在 `styles/index.css` 中定义了响应式 `text-fluid-*`（基于 `clamp()`）的排版体系，但多数页面（如智能体控制台、设备管理等）仍然充斥着硬编码的静态 Tailwind 字号（`text-xs`、`text-sm`、`text-base` 等 300+ 处），导致 2K/4K 高屏分辨率下字号比例不协调。
2. **状态指示分散**：设备的在线/离线、智能体的启用/停用、知识库绑定状态在不同模块中通过行内 className 硬编码 Tailwind 颜阶（如 `bg-emerald-50 text-emerald-700`），缺乏统一的状态标签组件与 Token 映射。
3. **布局与滚动条体验**：在中等屏（如 1366px 笔记本）及双栏/三栏复杂配置页面下，容器高度计算与 `overflow` 设置容易引发多层嵌套滚动条。
4. **Ant Design 与 Tailwind 融合粒度**：部分自定义卡片的圆角、内边距与阴影样式与 Ant Design Theme Token 的解耦和约束尚未完全标准化。
5. **交互微动画缺乏**：高频操作（试听播放、智能体调试、状态切换、列表加载）缺乏骨架屏与微动画反馈，缺少现代化高级 AI 产品视觉质感。

## Solution

建立统一的前端 UI 规范治理与优化方案：
1. 全面重构业务页面字号映射，严格替换硬编码 `text-xs` / `text-sm` / `text-lg` 为 `text-fluid-*`，实现流体响应式排版。
2. 抽离统一的状态标签组件 `<StatusTag />` 与状态 Token 字典，收敛全局在线、离线、启用、停用、绑定状态的视觉表现。
3. 规范主内容区与多栏组件的 Flex/Grid 布局与固定高度策略，彻底消除中屏多重嵌套滚动条。
4. 整理并标准化卡片 padding、margin、rounded 及 shadow Token，增强 Ant Design Theme 与 Tailwind 组件的一致性。
5. 引入细腻的交互微动画与 Skeleton 骨架屏加载状态，提升产品的高级视觉品质与操作反馈体验。

## User Stories

1. 作为平台管理员，我在 2K/4K 高分辨率大屏上浏览控制台时，希望所有页面的字体大小能根据屏幕宽度平滑流体缩放，以获得比例清晰协调的排版视感。
2. 作为运维人员，我在设备管理、智能体控制台与日志页面查看设备/智能体状态时，希望看到外观统一、视觉语义清晰的状态标签，以便快速识别在线或异常状态。
3. 作为中屏笔记本用户，我在智能体编排或知识库配置面板进行深度设置时，希望页面结构自然适配窗口高度，不要出现主窗口与侧面板同时滚动的多重滚动条。
4. 作为系统使用者，我在执行高频异步操作（如一键测试音色、智能体加载、表格刷新）时，希望看到流畅的微动画和骨架屏反馈，而不是突兀的白屏或静态等待。
5. 作为前端开发者，我在开发新功能页面时，希望能够复用统一的流体字号类和规范状态组件，避免在 CSS/Tailwind 中硬编码字阶和颜色值。

## Implementation Decisions

- **组件与层级抽象**：
  - 新增/完善全局统一状态组件 `web/src/components/status-tag.tsx`，集中管理设备、应用、知识库等领域的业务状态 Tag 渲染。
  - 重构 `web/src/views/` 下的重点页面（包括 `application-management`、`device-management`、`knowledge-base` 等），将静态字阶（`text-xs`/`text-sm`/`text-base`/`text-lg`/`text-xl`）集中替换为 `text-fluid-*` 语义类。
- **布局与滚动治理**：
  - 调整 `DashboardLayout` 主内容容器与子页面的 Flex 增长属性（`flex-1 min-h-0`），确保垂直方向自适应，滚动条仅由最内层指定 Content Scroll 容器承载。
- **样式 Token 校验**：
  - 配合现有的 `scripts/check-tailwind-tokens.js` 预提交守卫规则，继续严格杜绝新增 `!` 强制覆盖和 `teal-*` 硬编码。
- **架构契约与隔离**：
  - 不改变任何后端 REST API 契约和数据结构，改动完全限定在前端渲染层 (`web/src/`)。

## Testing Decisions

- **测试原则**：
  - 不测试底层样式实现的 CSS 细节，而是通过 UI 构建检查与运行态界面交互断言功能正常。
  - 优先进行 `npm run build` TypeScript 类型检查与 Vite 构建验证。
- **测试覆盖点**：
  - 执行 `npm run build`，确保所有 TSX 改动无类型报错及构建错误。
  - 运行 `node scripts/check-tailwind-tokens.js` 验证无新增 `!` 及 `teal-*` 违规。
  - 在常见分辨率断点下测试页面布局渲染，验证滚动条行为与响应式断点表现。

## Out of Scope

- 后端 API 结构调整或数据库 Migration。
- 新增非 UI 相关的业务功能逻辑。

## Further Notes

- 该优化方案将按页面和组件分步推进，确保 diff 保持小步迭代、可审查、可回滚。
