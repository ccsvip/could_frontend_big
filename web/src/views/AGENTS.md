[web](../../AGENTS.md) > src > **views**

# web/src/views AGENTS.md

## OVERVIEW

14 个页面模块，每个 = 一级路由 = 一个目录 + `index.tsx`。所有页面挂在 `DashboardLayout` 下，登录页除外。

## STRUCTURE

```
views/
├── login/                       # 公开页（GuestGuard）
├── account-applications/        # 账号申请审核
├── asr-management/              # 语音识别供应商
├── chat-room/                   # AI 聊天工作台（1069 行单文件，最复杂）
├── command-management/          # 控制指令工作台（5 sub-pages，见子 AGENTS.md）
├── device-management/           # 设备管理
├── knowledge-base/              # 知识库（上传 + 下载 + 批量）
├── llm-management/              # LLM 供应商
├── model-management/            # 3D 模型资产
├── not-found/                   # 兜底
├── resource-management/         # 图片/视频资源（双路由复用 + key 隔离）
├── scrolling-text-management/   # 滚动字幕
├── tts-management/              # TTS 供应商
└── voice-tone-management/       # 音色（voiceCode）
```

## CONVENTIONS

- **入口文件**：每个目录必须有 `index.tsx`，并 `export const XxxPage`（PascalCase + `Page` 后缀），`router/index.tsx` 按命名导入。
- **权限守卫**：每条路由都套 `<PermissionGuard permission="...">`，权限串与后端菜单配置一一对应。
- **Antd 组件**：统一用 `antd@5`；`Form.useForm()` 优先，不要裸 state 管理表单。
- **页面状态**：默认放 `useState` / `useReducer`，**不**进 Zustand；只有跨页共享（auth）才进 store。
- **路由复用**：当一个 Page 组件被多条路由挂载（如 `ResourceManagementPage`），路由处必须传 `key="resource-image"` / `key="resource-video"`，强制重建实例。

## ANTI-PATTERNS

- ❌ 把页面拆成大量 `components/`：本项目惯例是单页面单文件（即使到 1000+ 行也不拆），除非真正可复用。
- ❌ 在页面内直接 `axios.get`：必须经 `src/api/modules/*`。
- ❌ 在 chat-room 加本地打字机队列、临时消息切换：流式直接按 chunk 更新 `streamingContent`，正式消息匹配后才清。
- ❌ 把 `processing_status` 做成可编辑下拉：知识库前台**只展示**，状态去 `/admin/`。
- ❌ 控制指令分类下拉缓存死：用户新增分类成功后，本地选项必须立即同步，不能要刷新。

## NOTES

- `chat-room/index.tsx`（41KB / 1069 行）和 `command-management/workspace.tsx`（48KB / 1133 行）是项目里最大的两个 React 文件，改动前先读完。
- 资源管理页（图片 vs 视频）共享同一组件，靠 `resourceType` prop + 路由 `key` 隔离；视频卡片只在缩略图上显示首帧，**不**叠播放按钮，播放统一走"预览"弹窗。
- 知识库页：单文件上传成功后**前端本地** toast `文档已上传，等待管理员审核`（不复用后端 message）；多文件并发池上限 3。
- 模型管理页：`localUrl` / `effectiveUrl` 后端运行时生成，前端只读展示。
