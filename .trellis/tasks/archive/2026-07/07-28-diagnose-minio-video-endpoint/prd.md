# 排查 MinIO 地址切换后视频仍指向旧服务器

## Goal

确定并修复：平台超级管理员把 `/settings/minio` 的 MinIO 地址从 A 服务器切换到 B 服务器后，公司账号查看视频仍请求或播放 A 服务器资源的问题。

## Confirmed Facts

- `/settings/minio` PATCH 直接保存单例 `MinioConfig`；`get_minio_settings()` 每次调用都从该记录读取，没有进程内配置缓存，因此不需要重启 Docker。
- 当前配置 endpoint 为 `192.168.182.129:9000`；现有视频均保存为 `object_key`，没有 `cloud_url`，URL 应由当前配置动态生成。
- 公司资源列表继承 `CachedBusinessResponseMixin` 并缓存包含 `fileUrl` 的完整响应；缓存默认有效期为 300 秒。
- `MinioSettingsView.patch()` 保存配置后没有清理 `resources` 缓存命名空间。缓存命中时，列表不会再次调用序列化器，仍返回切换前 A 的 URL。

## Requirements

- 修改 MinIO 设置后必须立即清理资源响应缓存，使后续公司视频列表重新按新配置生成 URL。
- 建立回归测试：先缓存带 A URL 的公司视频列表，再把 endpoint 改为 B，后续读取必须返回 B URL。
- 保持资源缓存的租户隔离和正常失效行为；不要求重启 Docker。

## Acceptance Criteria

- [x] 更新 MinIO endpoint 后，已有 `object_key` 视频的下一次资源列表响应使用新 endpoint。
- [x] MinIO 设置更新清理 `resources` 缓存命名空间；不会影响其它业务缓存命名空间或跨公司隔离。
- [x] 回归测试先证明旧实现会返回 A，再证明修复后返回 B。
- [x] 相关 Django 测试通过。

## Out of Scope

- 不迁移或复制 A 上的历史视频对象；B 必须已经具有相同 bucket 和对象键，才可成功播放。
- 不修改由用户手工填写的 `cloudUrl` 视频，因为它们不由 MinIO 设置管理。

