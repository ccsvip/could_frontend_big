# 图片资源批量管理与删除 - 实施计划

## Implementation

- [x] 在资源 Serializer 层增加批量删除请求校验：非空、正整数、唯一、最多 100 项。
- [x] 为 `ImageResourceViewSet.bulk` 增加 DELETE method mapping 和删除权限映射。
- [x] 实现 tenant-scoped、仅图片、部分成功的批量删除响应，并复用单项删除保护逻辑。
- [x] 补充后端测试：权限拒绝、部分成功、引用保护、跨租户/视频/不存在 ID、缓存失效。
- [x] 在前端 resources API module 增加批量删除请求与响应类型。
- [x] 在图片资源页增加批量模式、当前页选择/全选、确认、结果反馈和分页回退。
- [x] 检查单项删除、批量上传、视频页面不受影响。

## Validation

```powershell
docker compose exec backend python manage.py test apps.resources.tests.test_resource_api --keepdb
cd web
npm run build
cd ..
node scripts/check-tailwind-tokens.js
git diff --check
```

## Review Gates

- API 路径保持 REST 集合语义，不新增动词式 URL。
- 任何提交的 ID 都不能绕过 tenant scope 或图片类型限制。
- 部分失败不回滚成功项，失败原因可定位。
- 无删除权限时前后端均不可执行批量删除。
- 前端图标仅使用 `@tabler/icons-react`，不新增硬编码颜色、Tailwind `!` 前缀或固定像素字号。

## Rollback Points

- 后端测试通过后再接前端；若前端交互失败，后端 DELETE action 可独立保留且不影响现有 POST 上传。
- 无模型或迁移变更，代码回退即可恢复原行为。
