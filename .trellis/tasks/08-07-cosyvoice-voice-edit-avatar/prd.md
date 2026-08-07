# CosyVoice 音色编辑与头像上传

## Goal

平台超管在 `/settings/tts/cosyvoice` 以「头像卡片墙」管理 CosyVoice 自定义音色：可编辑音色元数据，并通过本地上传更换**音色头像**，支持头像预览；上传后持久化并在列表/试听相关 UI 中生效。

## Background

- 现网页为表格 + 复刻/设计 Modal，头像仅创建时可选静态路径 Select；**无编辑入口**，**无本地上传**，列表不展示头像。
- 原型结论（已确认）：
  - 列表采用 **Variant B 头像卡片墙**
  - 更换头像只支持 **本地上传**（不要系统预设、不要图片资源库）
  - 去掉路径文本与「预览大图」文案按钮；卡片上头像仍可点开展示预览
  - 保留编辑（名称/启用/默认）与试听/删除能力
- 后端 `TTSVoice.avatar_path` 为 `CharField`；`PATCH /api/v1/settings/tts/cosyvoice/voices/{id}/` 已支持 JSON 写 `avatarPath`/`displayName`/`isActive`/`isDefault`，但**不接受文件上传**。

## Confirmed Facts

- 路由：`web/src/router/index.tsx` → `settings/tts/cosyvoice`，`SuperuserGuard`
- 前端 API：`web/src/api/modules/cosyvoice.ts`（`updateCosyVoiceVoice` 当前 JSON PATCH）
- 后端：`CosyVoiceVoiceDetailView.patch` + `CosyVoiceVoiceWriteSerializer`
- 读侧 `avatarPath` 对以 `/` 开头的路径会 `build_absolute_uri`
- 服务配置（API Key / WSS / 定制 URL / 试听文本）仍须保留，不受列表 UI 改版影响

## Requirements

### R1 列表：头像卡片墙
- 自定义音色以卡片网格展示：大头像、名称、voiceCode、默认/启用/来源标签
- 主操作：更换头像、试听、编辑；保留删除（二次确认）
- 保留「复刻音色」「设计音色」入口

### R2 编辑音色
- 可修改：显示名称、启用、设为默认
- 提交走现有 `PATCH .../voices/{id}/`，成功后刷新列表
- 失败时明确错误提示

### R3 音色头像本地上传
- 「更换头像」仅提供本地上传（拖拽/点击），不展示系统预设与图片资源库
- 支持常见图片（至少 PNG/JPEG），单文件
- 上传成功后写回该音色头像并在卡片即时反映
- UI 不展示具体存储路径/URL 字符串

### R4 头像预览
- 点击卡片头像可预览大图（lightbox/modal）
- 预览区不展示路径文本

### R5 服务配置区
- 保留现有服务配置表单能力（启用、API Key、WebSocket、定制 API、默认音色、试听文本、保存）
- 可与卡片墙同页上下布局，不因改版丢失配置能力

### R6 权限与隔离
- 仅超管可访问（现有 `IsSuperUser` / `SuperuserGuard`）
- 不引入租户越权路径

## Acceptance Criteria

- [ ] AC1：超管打开 `/settings/tts/cosyvoice`，音色以卡片墙展示且显示当前头像（无头像时有占位）
- [ ] AC2：可编辑名称/启用/默认并持久化；刷新后仍正确
- [ ] AC3：可本地上传图片更换音色头像并持久化；刷新后卡片仍显示新头像
- [ ] AC4：更换头像 UI 无系统预设、无图片资源库、无路径文本、无「预览大图」按钮
- [ ] AC5：点击头像可预览大图
- [ ] AC6：试听、删除、复刻、设计、服务配置保存仍可用
- [ ] AC9：复刻音色弹窗可本地上传可选头像；提交后新音色持久化头像路径；无头像时 JSON 复刻仍可用
- [ ] AC7：相关后端测试覆盖「multipart 上传头像」与「编辑字段」；前端 `npm run build` 通过
- [ ] AC8：生产构建不包含 prototype switcher / A·C 变体入口

## Out of Scope

- 系统预设头像选择
- 从图片资源库挑选头像
- 安卓端头像编辑
- CosyVoice 上游音色参数（语速等）改版
- 非 CosyVoice 供应商音色页改造
- 批量改头像

## Key Decisions

| 决策 | 结论 | 来源 |
|------|------|------|
| 列表形态 | B 卡片墙 | 用户选定原型 |
| 换头像来源 | 仅本地上传 | 用户明确要求 |
| 创建流 avatar | 复刻可在创建时本地上传头像（可选）；设计仍可创建后更换 | 用户要求复刻创建上传 |
| 存储模型 | 继续用 `avatar_path` 存可访问路径；上传文件写入 media 存储 | 避免 ImageField 迁移，兼容静态路径存量 |
| 原型代码 | 正式落地后移除 `?variant=` 与 prototype 目录依赖 | 避免生产污染 |

## Risks

- 旧静态 `/static/tts/voices/...` 与新 `/media/...` 混存：读侧须都能显示
- multipart 与 JSON 并存：PATCH 需同时支持 JSON 字段更新与文件上传
- 头像文件体积：需校验类型/大小，避免过大文件

## Open Questions

（无阻塞项）
