# 安卓应用升级接口实施计划

## 1. 后端领域与存储

- [x] 创建 `apps.app_updates` 应用并接入 `INSTALLED_APPS`、根路由和 API 根说明。
- [x] 实现 `AppRelease`、`AppUpdateEvent` 及约束，生成并审查迁移。
- [x] 实现统一发布创建服务：校验 APK 文件名、计算大小/SHA-256、生成 releaseId，保证创建失败不残留数据库记录。
- [x] 实现发布不可变约束和仅启用/停用的状态切换。

## 2. 签名、检查与上报

- [x] 增加 `cryptography` 依赖和应用升级环境配置读取。
- [x] 实现确定性签名原文构造、RSA PKCS#1 v1.5/SHA-256 签名与 UTC `expiresAt`。
- [x] 实现检查请求 Serializer、设备校验、全局最新版本选择和文档响应结构。
- [x] 实现状态上报 Serializer 和追加式事件保存。
- [x] 为设备错误、请求错误、签名配置错误提供带 requestId/traceId 的明确响应。

## 3. 管理与下载入口

- [x] 实现严格超级管理员发布管理 ViewSet：列表、创建、详情、仅 isActive PATCH。
- [x] 实现完整下载与单段 Range 流式响应，覆盖 200/206/416 和响应头。
- [x] 注册 Django Admin，新建可上传，变更仅允许切换启用状态，禁止删除。

## 4. React 超级管理员页面

- [x] 新增 `api/modules/app-updates.ts`，集中维护发布 DTO、分页、multipart 上传进度和启停接口。
- [x] 新增应用升级管理页：当前版本概览、发布表格、上传弹窗、进度及错误反馈。
- [x] 在超级管理员设置菜单和路由中增加入口，并使用严格 `isSuperuser` 守卫。
- [x] 按项目 token、流体排版、响应式表格和 Tabler 图标规范完成 UI 自查。

## 5. 自动化验证

- [x] 后端测试：发布字段/文件校验、不可变性、超级管理员权限，以及公司管理员、员工、非超级管理员 staff 的拒绝场景。
- [x] 后端测试：有更新、无更新、无发布、设备异常、包名错误、强制阈值和缺失私钥。
- [x] 后端测试：固定原文验签、完整下载、Range 下载、非法 Range、停用发布。
- [x] 后端测试：全部上报状态、未知状态和版本不一致。
- [x] 运行 `docker compose exec backend python manage.py makemigrations --check`。
- [x] 运行目标 Django 测试（容器，`--keepdb`）和 `python manage.py check`。
- [x] 在 `web/` 运行 `npm run build`，并运行 Tailwind token 守卫。
- [x] 核对 `git diff`，确保无无关格式化、凭据或其他用户改动。

## 风险与回滚点

- 大文件哈希在上传请求内同步执行；第一期保持简单，若实测 APK 体积导致请求耗时不可接受，再独立引入后台校验状态机。
- 私钥配置是上线门槛，不能提交到仓库；部署前需由运维注入并把对应公钥交给 Android。
- 数据迁移完成后不自动删除表或文件；功能回滚优先移除路由/菜单并停用发布。
