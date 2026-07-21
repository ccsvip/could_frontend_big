# 图片 Hash 去重上传 - 实施计划

## Implementation

- [x] 为 `Resource` 增加 `content_hash` 与图片 tenant 级条件唯一约束，生成迁移。
- [x] 增加分块 SHA-256 计算、重复查询和统一冲突错误，接入图片 Serializer 的创建、替换与清空路径。
- [x] 将 multipart 批量上传改为部分成功契约，覆盖请求内重复、数据库重复与正常项混合场景。
- [x] 扩展图片 presign 与资源创建请求的 `contentHash`，在签发前拦截当前 tenant 已有摘要，并处理并发冲突后的 object key 清理。
- [x] 在前端增加 Web Crypto 摘要计算和批内去重，普通/R2 单图与批量路径同步新契约和跳过提示。
- [x] 增加对象存储流式读取能力与幂等历史回填 management command，保留并报告历史重复项。
- [x] 补充 Django 测试：摘要记录、同 tenant 拒绝、跨 tenant 允许、同批部分成功、并发约束、presign 拦截、对象清理、历史回填。

## Validation

```powershell
docker compose exec backend python manage.py makemigrations --check
docker compose exec backend python manage.py test apps.resources.tests.test_resource_api apps.resources.tests.test_minio_video_api apps.resources.tests.test_minio_client --keepdb
docker compose exec backend python manage.py backfill_image_content_hashes --help
cd web
npm run build
cd ..
node scripts/check-tailwind-tokens.js
git diff --check
```

## Review Gates

- 所有重复查询必须基于当前 tenant；错误不得泄露其他 tenant 的 ID、名称或 Hash。
- 数据库约束必须覆盖并发创建，不能只依赖前端或 Serializer 的先查后写。
- multipart 与 R2 失败路径必须清理本次新增的文件/object key，不能删除既有资源对象。
- 批量上传必须保持部分成功，重复项不回滚正常项。
- 历史回填必须幂等、流式读取、逐项容错，不得在 schema/data migration 中访问远程存储。
- API 字段保持 camelCase，HTTP 重复冲突使用 409，批量结果保持结构化。

## Rollback Points

- 数据模型迁移与后端去重测试通过后再接入前端，避免客户端发送服务端不识别的摘要。
- presign 变更保留视频请求兼容性，只有图片要求 `contentHash`。
- 回填命令独立于迁移；出现对象存储读取问题时可停止并重跑，不影响已完成记录。
