# 安卓应用升级接口技术设计

## 1. 边界与模块

新增独立 Django 应用 `apps.app_updates`，统一拥有发布记录、签名、下载、设备检查与状态事件契约，避免把全局发布能力塞进租户化的 `devices` 或 `resources` 模块。

前端新增超级管理员页面 `/settings/app-updates`，只消费发布管理 API，不参与 SHA-256、签名、版本选择或下载地址计算。

```text
Django Admin ─┐
              ├─> AppRelease（不可变发布） ─> Range APK 下载
React 超管页 ─┘                │
                               ├─> 检查更新 ─> 动态 expiresAt + RSA 签名
Android 设备 ─ X-Device-Code ──┘
                 └─────────────> AppUpdateEvent（追加式状态事件）
```

## 2. 数据模型

### AppRelease

- `release_id`：服务端生成的稳定、全局唯一字符串，对外作为 lookup。
- `package_name`、`version_name`、`version_code`、`version_info`：发布版本元数据；`version_code` 全局唯一。
- `apk_file`：`FileField`，保留上传时原始 APK 文件名。
- `file_name`、`file_size`、`sha256`：创建时由后端从文件计算，此后只读。
- `force_upgrade_version_code`：非负且不得高于本发布的 `version_code`。
- `release_notes`、`is_active`、`created_by`、时间字段。
- 发布创建后除 `is_active` 外不允许修改；不提供删除能力。

最新发布定义为 `is_active=True` 中 `version_code` 最大的记录。停用记录不参与检查，但文件内容永不被替换。

### AppUpdateEvent

- 保存设备、发布、包名、更新前/目标版本、状态、消息和客户端发生时间。
- 事件只追加，不提供更新与删除 API。
- 状态仅允许文档规定的八种枚举值。

## 3. 文件存储与下载

第一期使用项目现有 `MEDIA_ROOT` + `FileField`，Django Admin 和 React 管理 API 共用同一创建服务。仓库 Docker 开发环境将整个 `backend/` 挂载到宿主机，因此文件不会随容器重启丢失。

新增稳定下载端点：

```http
GET /api/v1/app-update-releases/{releaseId}/apk/
```

- 下载无需 JWT 或设备头，安全性由更新信息签名、文件 SHA-256 和 Android APK 证书共同保证。
- 支持完整下载和单段 `Range` 请求，返回 `200` / `206` / `416`、`Content-Length`、`Content-Range`、`Accept-Ranges: bytes`、文件名和 SHA-256 ETag。
- 只读取模型绑定的文件路径，不接收任意文件系统路径。
- 停用发布不再允许新下载；已下载文件仍由客户端按签名和摘要验证。

未来迁移到 MinIO/R2 时保持模型服务和 `downloadUrl` 契约不变，仅替换存储/下载适配器。

## 4. 签名与配置

使用 `cryptography` 实现文档约定的 `SHA256withRSA`（RSASSA-PKCS1-v1_5 + SHA-256）。私钥只从环境配置加载：

- `APP_UPDATE_PRIVATE_KEY_BASE64`：Base64 编码的 PEM 私钥；
- `APP_UPDATE_PRIVATE_KEY_FILE`：容器内 PEM 文件路径，作为可选替代；
- `APP_UPDATE_SIGNATURE_TTL_SECONDS`：响应有效期，默认 7 天；
- `APP_UPDATE_PACKAGE_NAME`：允许的 Android 包名，默认 `com.solin.digital`。

检查请求命中更新时，服务端基于当前绝对下载 URL、动态 `expiresAt` 和最新发布字段构造无结尾换行的 UTF-8 原文并即时签名。缺少或非法私钥时返回明确 `503`，绝不返回未签名发布。

## 5. API 与权限

### Android 公共接口

- `POST /api/v1/app-updates/check/`：`AllowAny` 进入传输层，但必须调用 `get_runtime_device(..., require_tenant=True)` 校验 `X-Device-Code`。
- `POST /api/v1/app-updates/report/`：同样校验设备并持久化事件。
- 请求/响应追踪复用 `config.request_id.get_request_id/get_trace_id`。
- 包名固定校验；未知字段向前兼容，缺失或类型错误返回 `400`。

### 超级管理员管理接口

- `GET/POST /api/v1/app-update-releases/`：列表与 multipart 上传。
- `GET/PATCH /api/v1/app-update-releases/{releaseId}/`：详情与仅 `isActive` 状态切换。
- 不开放 `PUT`、`DELETE` 或 APK 替换端点。
- 后端使用严格 `IsSuperUser`，不能用会放行 `is_staff` 的通用平台权限代替。
- 发布管理 API 不进入租户作用域，也不复用公司权限码；公司管理员、员工和非超级管理员 staff 一律返回 `403`。

## 6. Django Admin

- 新建页允许上传 APK 并填写版本、强制阈值和发布说明。
- 文件名必须为 `.apk` 且严格满足 `versionInfo + ".apk" == fileName`。
- 新建时自动计算大小和 SHA-256；变更页除 `is_active` 外全部只读。
- 禁止删除，列表突出版本号、文件大小、启用状态、SHA-256 和创建时间。

## 7. React 页面设计

页面延续现有 antd + Tailwind 设计系统，不采用 UI 技能生成的独立蓝色/字体方案：

- 使用 `.page-hero`、`container`、`rounded-xl`、`shadow-card` 和 `brand-*` token。
- 页面只有一个主操作“上传新版本”；顶部概览当前生效版本，下方为发布记录表格。
- 上传弹窗使用竖向表单和单文件 Dragger，展示可见标签、格式提示、上传百分比、提交中禁用态和字段级错误。
- 表格在小屏使用 `scroll={{ x: ... }}`；机器标识使用 `text-fluid-xs font-mono`，其余文字使用 `text-fluid-*`。
- 图标只从 `@tabler/icons-react` 单次导入，避免 emoji、硬编码主色、`teal-*` 和 Tailwind `!` 覆盖。
- 路由和侧栏均只对 `isSuperuser` 可见，后端权限仍是最终安全边界。
- 公司侧菜单树、公司作用域路由和租户 API 模块不增加任何应用升级管理入口。

## 8. 兼容性、运维与回滚

- 新表和新路由是增量变更，不影响现有设备运行时、WebSocket 或租户业务 API。
- 未配置私钥时管理上传和无更新响应仍可用；只有需要返回新版本的检查请求返回 `503`。
- 回滚应用代码不会删除发布文件或数据库记录；重新部署后可继续使用。
- 错误发布通过停用回滚，禁止覆盖原 APK；重新发布必须使用更高 `versionCode`。
