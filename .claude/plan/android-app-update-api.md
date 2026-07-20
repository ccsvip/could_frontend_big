# 安卓应用升级功能计划

## 目标

实现全局统一 APK 发布、Android 检查更新和状态上报，并同时提供 Django Admin 与 React 超级管理员上传入口。

## 功能分解

1. 不可变发布记录与 APK 文件存储。
2. RSA/SHA-256 更新信息签名。
3. Android 设备检查更新、Range 下载和状态上报。
4. 超级管理员 REST 管理接口与 Django Admin。
5. React 上传、启停和发布记录页面。

## 实施步骤

详细技术边界和顺序以 Trellis 任务为唯一事实来源：

- `.trellis/tasks/07-20-android-app-update-api/prd.md`
- `.trellis/tasks/07-20-android-app-update-api/design.md`
- `.trellis/tasks/07-20-android-app-update-api/implement.md`

按“领域模型与存储 → 签名和设备 API → 管理/下载 → React 页面 → 全量验证”的顺序实施。发布后只允许启用或停用，不允许替换或删除 APK。

## 验收标准

- 合法设备能获得全局最新且可验签的发布信息，无更新时得到稳定的空发布响应。
- APK 支持完整下载和 Range 续传，内容与发布时 SHA-256 一致。
- 两个管理入口均能上传新版本，只有超级管理员有权访问。
- 已发布记录不可替换或删除，停用后不再参与最新版本选择。
- 后端目标测试、迁移检查、Django check 和前端构建全部通过。

