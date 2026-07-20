# 实现安卓应用升级接口

## Goal

依据 `wiki/app-update-api-contract.md` 实现 Android 设备可调用的软件升级后端能力，并提供 Django Admin 与前端超级管理员发布入口，使合法设备能够检查全局最新 APK，并上报下载、校验和安装状态。

## Background

- 所有公司和设备统一使用一个最新版本，不按租户、设备、型号、渠道或 CPU 架构筛选 APK。
- 版本新旧只比较 `versionCode`；时间、文件名和 `versionName` 不参与比较。
- Android 运行时不使用 JWT，通过 `X-Device-Code` 识别设备；仓库已有 `apps.devices.services.runtime.get_runtime_device` 作为统一校验边界。
- 仓库当前没有应用升级模块或发布记录模型，但已有 Django Admin、React 超级管理员页面、Django `FileField` 和 MinIO/R2 对象存储能力。
- 当前契约固定使用 `POST /api/v1/app-updates/check/` 和预留的 `POST /api/v1/app-updates/report/`。

## Requirements

1. 检查更新接口必须校验 `X-Device-Code`，拒绝未登记、停用或无权使用的设备。
2. 请求体必须验证 `packageName`、`versionName`、`versionCode`、`versionInfo` 的类型和必填约束。
3. 后台必须从全局发布源选择最高的有效 `versionCode`，严格按契约返回 `hasUpdate`、`forceUpgradeVersionCode` 和 `release`。
4. 有更新时必须返回文档约定的完整发布字段，并使用 RSA/SHA-256 对规定原文签名；公钥和私钥不得通过接口下发。
5. 发布记录必须保证 `versionInfo + ".apk" == fileName`、SHA-256 为小写十六进制、`forceUpgradeVersionCode` 不高于可更新目标版本。
6. APK 下载地址允许 HTTP 或 HTTPS；已发布的同一 URL 不得指向被覆盖的内容。
7. 状态上报接口必须按文档字段接收并追加保存设备更新事件，不允许通过业务 API 修改或删除历史事件。
8. 请求和响应使用现有 `requestId` / `traceId` 追踪方式，错误响应保持可定位且不泄露其他租户或发布内部信息。
9. Django Admin 必须支持超级管理员上传 APK、填写版本与发布说明并维护发布记录。
10. React 超级管理员页面必须提供 APK 上传与发布记录管理入口；非平台超级管理员不可访问对应页面或管理 API。
11. APK 上传成功后由后台统一计算并保存 `fileSize`、SHA-256、原始文件名与下载地址，前端不得提交或覆盖这些派生字段。
12. 发布记录必须保持不可变：已上传 APK 及其版本、文件摘要和签名关联字段不得替换或删除；超级管理员只能上传新版本以及启用或停用已有发布。
13. 公司侧不得暴露任何发布管理能力：公司管理员、公司员工以及仅有 `is_staff` 的非超级管理员均不得获得发布列表、详情、上传或启停权限，也不得在菜单或路由中看到应用升级管理入口。

## Acceptance Criteria

- [ ] 合法设备当前版本低于全局最新版本时，接口返回 `200`、`hasUpdate=true` 和完整且可验签的 `release`。
- [ ] 当前版本等于或高于全局最新版本时，接口返回 `200`、`hasUpdate=false`、`release=null`。
- [ ] 不存在发布记录时按“无更新”返回，不产生 500。
- [ ] 缺失或无效设备码、停用设备、非法请求字段分别返回明确的 4xx 错误结构。
- [ ] 强制升级阈值为 `0` 和非零值的判断均符合新版契约，并禁止产生“需要强制升级但没有可用 release”的响应。
- [ ] 签名原文字段顺序、UTF-8 编码和换行拼接规则与文档一致，并有固定输入的回归测试。
- [ ] 状态上报接口接受全部约定状态，拒绝未知状态和不一致的版本字段。
- [ ] Django Admin 和前端超级管理员页面均能上传 APK 并创建可被检查更新接口选中的发布记录。
- [ ] 前端上传过程有明确的进行中、成功和字段级失败反馈，页面在小屏下不产生非表格区域的横向溢出。
- [ ] 普通公司管理员和员工无法查看页面，也无法调用发布管理 API。
- [ ] `is_staff=True` 但 `is_superuser=False` 的账号同样无法访问任何发布管理 API，证明权限边界只认平台超级管理员。
- [ ] 超级管理员可以启用或停用发布；停用版本不参与最新版本选择，且所有管理入口均不允许替换 APK 或删除发布记录。
- [ ] 新模型迁移可执行，Django system check 与目标测试通过。

## Out of Scope

- Android 客户端代码。
- 按公司、租户、设备、渠道、ABI 或灰度比例分发不同 APK。
- 后台定时检查、客户端自动下载、自动安装、升级通知和当前阶段的强制升级 UI 拦截。
