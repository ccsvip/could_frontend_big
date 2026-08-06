# MinIO 设置页增加连通性测试

## Goal
在 `/settings/minio` 提供连通性测试，让管理员能在保存配置前后确认 MinIO 地址、密钥和存储桶配置可用。

## Background
 - 页面文件：`web/src/views/minio-settings/index.tsx`，同一表单同时维护 `local` MinIO 与 `r2` 配置。
 - 前端 API：`web/src/api/modules/settings.ts` 当前只有 `GET/PATCH /settings/minio/` 和视频额度接口。
 - 后端入口：`backend/apps/resources/views.py:432` 的 `MinioSettingsView`，仅 `IsSuperUser` 可访问；路由为 `/api/v1/settings/minio/`。
 - MinIO 客户端：`backend/apps/resources/services/minio_client.py` 已有 `_build_client`、`_require_complete`，但 `_ensure_bucket` 会创建 bucket 并设置公开读策略，不适合作为无副作用的连通性测试。
 - 现有测试约定：`backend/apps/resources/tests/test_minio_settings_api.py` 覆盖配置读取、保存、权限和环境变量回退；前端有 `web/scripts/test-minio-settings-static.mjs` 静态检查。
 - 已运行 GitNexus query 定位设置页面、API、视图、服务和测试；已对 `MinioSettingsView` 做 upstream impact，结果为 LOW，直接影响 `resources/urls.py` 等 3 个导入方，无业务执行流受影响。

## Requirements
 - 在 MinIO 设置页面提供“测试连接”入口。
 - 测试不得把密钥返回给浏览器或写入日志；错误需要显示可定位的用户提示。
 - 测试应复用现有 MinIO 配置解析和客户端构建逻辑，避免复制鉴权/endpoint 规则。
 - 测试不得创建 bucket、修改 bucket policy 或写入业务对象。
 - 保持现有配置保存、读取、R2 配置和视频额度功能不变。

## Acceptance Criteria
 - 超级管理员在 `/settings/minio` 点击测试后看到加载状态，成功时看到成功提示和可选延迟信息。
 - Endpoint、Access Key、Secret Key、Bucket 任一错误或缺失时，接口返回非 2xx，页面显示明确失败提示且不泄露 secret。
 - 使用当前表单值测试时，未保存的新地址/凭据可以被验证；密码框留空时按现有“保持已保存密钥”语义处理。
 - 非超级管理员不能调用该测试接口。
 - 后端自动化测试覆盖成功、失败/不完整配置、权限和无副作用边界；前端构建及浏览器实测通过。

## Out of Scope
 - 不改变已有 MinIO 配置保存、读取和删除语义。
 - 不测试 R2 连接，除非现有产品契约要求测试当前 active backend。
 - 不暴露密钥等敏感信息。

## Open Questions
 - 测试范围与未保存配置语义需用户确认。
