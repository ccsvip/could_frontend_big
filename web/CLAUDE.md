[根目录](../CLAUDE.md) > **web**

# web 模块 CLAUDE

## 模块职责

`web/` 提供数字人后台管理平台前端界面，负责登录流程、设备管理、账号申请审核页面，以及统一请求与登录态管理。

## 入口与启动

- 入口：`src/main.tsx`
- 路由：`src/router/index.tsx`
- 本地启动：`npm run dev`
- 构建：`npm run build`

## 对外接口

本模块通过 API 客户端调用后端接口：
- 认证：`/auth/login/` `/auth/me/` `/auth/account-applications/` `/auth/account-applications/manage/`
- 认证补充：`/auth/change-password/` 用于顶栏用户菜单修改密码，成功后前端清理登录态并跳转 `/login`。
- 设备：`/devices/` `/devices/stats/`
- 音色：`/resources/voice-tones/`
- 模型：`/resources/models/`
- 控制指令：`/commands/control/`、`/commands/control/export/`、`/commands/control/import/`
- 知识库（已批准约束，落地时必须保持）：
  - `/knowledge-base/`
  - `/knowledge-base/<id>/download/`
  - `/knowledge-base/bulk-download/`

关键文件：
- `src/api/client.ts`
- `src/api/modules/auth.ts`
- `src/api/modules/devices.ts`
- `src/api/modules/voice-tones.ts`

## 关键依赖与配置

- 依赖：React 18、react-router-dom 6、Ant Design 5、Zustand、Axios、dayjs
- 构建链：Vite + TypeScript + Tailwind
- 配置文件：
  - `package.json`
  - `vite.config.ts`
  - `tailwind.config.ts`
  - `tsconfig*.json`

## 数据模型

前端核心数据类型：
- 认证：`LoginResponse`、`CurrentUser`、`AuthState`、`AppMenu`
- 账号申请：`AccountApplicationRecord`
- 设备：`DeviceRecord`、`DeviceStatsResponse`
- 音色：`VoiceToneRecord`、`VoiceToneListResponse`
- 模型：`ModelAssetRecord`、`ModelAssetListResponse`
- 知识库（已批准约束）：
  - `KnowledgeBaseRecord`
  - `KnowledgeBaseListResponse`
  - `KnowledgeBaseUploadItemState`（逐文件进度 / 成功 / 失败）

## 测试与质量

- 当前未发现模块内测试目录或 `*.spec.ts(x)` 文件。
- 建议优先补充：
  1. `src/api/modules/*` 的请求与错误分支测试
  2. `src/router/index.tsx` 的守卫跳转测试
  3. `src/store/auth.ts` 的状态与持久化一致性测试

## 常见问题 (FAQ)

- Q: 为什么会跳回 `/login`？
  - A: `src/api/client.ts` 在 401 响应拦截器中会清理登录态并重定向。
- Q: 登录态存在哪里？
  - A: Zustand + localStorage（`token`、`refreshToken`、`username`、`role`、`permissions`、`menus`）。应用启动且本地存在 token 时，`src/router/index.tsx` 会主动调用 `/auth/me/` 校准最新权限上下文。
- Q: 菜单和页面权限由谁决定？
  - A: 后端返回的 `role`、`permissions`、`menus` 是唯一事实来源；前端只做展示层过滤与守卫。
- Q: 为什么图片管理和视频管理不能直接复用同一份本地状态？
  - A: `src/views/resource-management/index.tsx` 会被两个资源路由复用，切换 `resourceType` 时必须通过路由 `key` 或组件内重置逻辑隔离实例，否则图片页的列表、筛选条件或弹窗状态会残留到视频页。
- Q: 独立聊天室页面还存在吗？
  - A: 不存在。`/ai-models/chat` 和“AI大模型/聊天室”菜单已移除；聊天底层 API 仍用于应用管理里的调试会话。
- Q: 为什么某些兼容供应商明明返回了 SSE，前端还是没字？
  - A: `src/api/modules/chat.ts` 的流解析必须同时兼容 `data:{...}` 与 `data: {...}`；LongCat 的 chunk 前缀是前者，如果只匹配带空格版本，浏览器端会把所有 chunk 都忽略掉。
- Q: 应用管理里的调试会话怎样消费流式回复？
  - A: `src/views/application-management/index.tsx` 调用 `src/api/modules/chat.ts` 的 `sendMessageStream`，直接按 chunk 更新 `streamingContent`，并通过 `src/components/chat-markdown.tsx` 实时渲染 Markdown。
- Q: 应用管理里的系统提示词和参数怎样生效？
  - A: 选择应用后，页面通过 `updateConversationConfig` 把应用的 `llmModelId`、`systemPrompt`、`temperature` 和 `maxTokens` 同步到调试会话；后续发送会沿用这些会话配置。
- Q: 视频管理卡片上的缩略图和播放交互应该是什么行为？
  - A: 视频列表卡片应优先展示视频首帧缩略图；播放统一通过现有“预览”按钮进入弹窗控制，不在缩略图上叠加播放按钮；若首帧获取失败则退回占位态。
- Q: 音色页面里哪个字段是实际传给后端业务方的？
  - A: `src/api/modules/voice-tones.ts` 和 `src/views/voice-tone-management/index.tsx` 统一使用 `voiceCode`，它对应后端的 `voice_code`，是可编辑但全局唯一的音色标识字符串。
- 控制指令页的分类筛选与新增/编辑表单分类选项需要共享同一份最新分类集合；当用户录入新分类并保存成功后，前端必须立即把该分类同步回本地选项，避免下拉需要刷新页面才出现。
- Q: 模型页面里的本地地址能手工编辑吗？
  - A: 不能。`src/api/modules/models.ts` 与 `src/views/model-management/index.tsx` 只读消费后端返回的 `localUrl` / `effectiveUrl`；本地完整地址由后端根据上传文件路径运行时生成。
- Q: 知识库上传成功为什么不能直接复用后端 success message？
  - A: 知识库 `create` 约定要兼容原生 DRF 成功形状，所以前端必须在单文件上传 2xx 成功后，本地直接弹出固定文案 `文档已上传，等待管理员审核`，而不是依赖后端 envelope/message。
- Q: 知识库下载为什么要单独做 axios helper，而不是直接复用 `httpClient` 或 `fetch`？
  - A: 下载链路既要和 `src/api/client.ts` 保持相同的 `baseURL`、Bearer 注入与 401 清理登录态语义，又要局部处理 Blob 成功体、Blob(JSON) 错误体、`Content-Disposition` 文件名解析和保存时机；共享拦截器容易导致双 toast 或误把错误 Blob 当文件保存，因此必须集中在 `src/api/modules/knowledge-base.ts` 的独立 axios helper 中处理，且不要再引入 `fetch` 平行实现。
- Q: 知识库多文件上传的并发规则是什么？
  - A: 前端必须采用“单文件独立请求 + 并发池”模式，最多同时 3 个上传；第 4 个文件要等待空位后再发起，并为每个文件维护独立进度、成功/失败状态。
- Q: 知识库页面能修改处理状态吗？
  - A: 不能。前台页面只允许展示 `processing_status` / `processing_result` 的只读状态；所有状态维护都必须去 Django admin 完成。
- Q: 知识库批量下载前端需要注意什么？
  - A: 需要把重复点击保护、loading、Blob 错误解包和文件名优先级处理一起做好；后端规则固定为“最多 20 个有效文件、总大小最多 200MB、重复 id 去重、非法/不存在 id 过滤后为空时报错”。

## 相关文件清单

- `src/main.tsx`
- `src/router/index.tsx`
- `src/layouts/dashboard-layout.tsx`
- `src/store/auth.ts`
- `src/api/client.ts`
- `src/api/modules/auth.ts`
- `src/api/modules/devices.ts`
- `src/api/modules/knowledge-base.ts`
- `src/views/login/index.tsx`
- `src/views/device-management/index.tsx`
- `src/views/account-applications/index.tsx`
- `src/views/knowledge-base/index.tsx`
- `src/views/voice-tone-management/index.tsx`
- `src/api/modules/models.ts`
- `src/views/model-management/index.tsx`
- `src/api/modules/knowledge-base.ts`（知识库下载 helper 与 CRUD 模块，待/进行中）
- `src/views/knowledge-base-management/index.tsx`（知识库页面，待/进行中）

## 变更记录 (Changelog)

- 2026-04-10T14:36:29+08:00：初始化模块文档，补充入口、接口、依赖、测试缺口与关键文件。
- 2026-04-13T15:02:11+08:00：补充资源管理页跨路由复用时的状态隔离说明，约束图片/视频页面使用独立组件实例。
- 2026-04-13T15:50:00+08:00：补充音色管理接口、数据类型与 `voiceCode` 字段语义说明。
- 2026-04-14T10:10:00+08:00：更新视频管理卡片的缩略图与播放交互约束，取消封面覆盖播放按钮，统一通过现有“预览”按钮进入弹窗播放。
- 2026-04-14T12:18:00+08:00：补充模型管理接口、数据类型与本地地址只读生成规则，新增模型管理页面入口说明。
- 2026-04-20T16:30:00+08:00：聊天室新增“聊天模型”选择器，直接消费 LLM 管理中已启用供应商/模型；新建会话默认绑定当前选中模型，会话内切换时调用 `/ai-models/chat/conversations/<id>/update-config/` 同步更新后端绑定配置。
- 2026-04-20T16:55:00+08:00：聊天室前端流解析兼容 `data:{...}` 与 `data: {...}` 两种 SSE 事件格式，修复 LongCat 流式响应有内容但界面未渲染的问题。
- 2026-04-20T17:10:00+08:00：聊天室界面新增“流式回复”开关，默认开启；关闭后仍复用原有 SSE 渲染链路，但后端会请求上游非流式响应并一次性展示完整回答。
- 2026-04-20T17:25:00+08:00：聊天室继续沿用前端 SSE 渲染，但配合后端改为真正异步流式输出后，开启“流式回复”时页面可实时显示 chunk，不再表现为阻塞式整段返回。
- 2026-04-20T17:35:00+08:00：聊天室流式模式新增打字机效果，前端先缓存上游 chunk 再按字符逐步渲染；非流式模式保持一次性整段显示，视觉反馈差异更明确。
- 2026-04-20T17:45:00+08:00：聊天室补充本地助手临时气泡过渡层，流式/非流式完成后在服务端正式消息刷新到位前保持回复可见，修复内容闪一下再完整显示的问题。
- 2026-04-20T17:52:00+08:00：聊天室进一步改为复用同一份 `streamingContent` 贯穿回复完成到正式消息落库的整个过渡期，减少本地临时消息对象切换，继续压低闪烁概率。
- 2026-04-20T18:00:00+08:00：聊天室新增无依赖 Markdown 渲染组件 `src/components/chat-markdown.tsx` 与配套样式，正式助手消息按 Markdown 格式展示，流式临时气泡保留纯文本打字机效果。
- 2026-04-20T18:08:00+08:00：聊天室继续向 Dify 风格体验靠拢，流式中的助手消息也改为实时 Markdown 渲染；顶部新增“复制全部回复”按钮，便于一键复制当前会话中的全部助手回复文本。
- 2026-04-20T18:20:00+08:00：聊天室移除本地伪打字机队列，直接按上游 chunk 实时刷新 Markdown 内容，并持续复用同一份 `streamingContent` 到正式消息匹配为止，进一步压低闪烁和样式跳变。
- 2026-04-20T18:35:00+08:00：聊天室右侧新增系统提示词面板并持久化到会话；助手消息复制改为每条单独复制；无依赖 Markdown 渲染补齐表格和分隔线支持。
- 2026-04-20T18:45:00+08:00：聊天室支持首轮回复后自动生成会话标题，后端使用当前模型生成简短中文标题并回写列表，前端刷新会话列表后自动显示新标题。
- 2026-04-20T19:05:00+08:00：聊天室进入第二阶段工作台形态：左侧支持会话搜索；右侧支持 `temperature` / `maxTokens` 参数调优与提示词模板；最新一条助手消息支持重新生成；代码块支持独立复制按钮。
- 2026-04-21T13:20:00+08:00：新增知识库已批准约束说明，记录一级菜单 `/knowledge-base`、前端本地上传成功 toast、单文件并发池上限 3、独立 axios 下载 helper、前台只读状态展示与批量下载交互约束。
- 2026-06-11T00:00:00+08:00：移除独立聊天室页面与 `/ai-models/chat` 路由；聊天底层 API 保留给应用管理调试会话使用。
