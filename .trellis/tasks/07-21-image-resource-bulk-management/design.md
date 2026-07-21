# 图片资源批量管理与删除 - 技术设计

## Boundaries

- 后端仅扩展 `ImageResourceViewSet`，不影响视频、模型或音色资源。
- 前端仅在 `ResourceManagementPage` 的 `resourceType === 'image'` 分支提供批量管理。
- 不新增模型或迁移；沿用 `Resource`、权限点、tenant scope 和业务缓存。

## HTTP Contract

复用现有图片资源集合路径，以 HTTP 方法区分批量上传与批量删除：

```http
DELETE /api/v1/resources/images/bulk/
Content-Type: application/json

{"ids": [12, 15, 19]}
```

请求约束：

- `ids` 必须是 1 到 100 个互不重复的正整数。
- action 使用 `CanDeleteImageResources`。
- 待删除对象只能来自 `ImageResourceViewSet.get_queryset()`，因此自动限制为当前 tenant scope 下的图片。

成功或部分成功统一返回 `200 OK`：

```json
{
  "deletedIds": [12, 15],
  "failures": [
    {"id": 19, "name": "产品图", "reason": "该资源被 1 个标注回复引用，不能删除"}
  ]
}
```

越权、不存在或非图片 ID 使用相同的不可见语义：`name` 为空，`reason` 为“图片不存在或无权访问”，避免泄露其他公司的资源信息。请求结构错误返回 `400`。

## Backend Flow

1. 使用专用 Serializer 校验和去重 `ids`。
2. 从 tenant-scoped 图片 queryset 一次查询可见资源并按请求 ID 建索引。
3. 按请求顺序处理：不可见 ID记录失败；可见资源调用现有 `perform_destroy()`。
4. 捕获现有引用保护产生的 `ValidationError`，转换为该项失败原因；其余项继续处理。
5. `perform_destroy()` 继续负责数据库删除、对象存储清理和缓存失效，保持单项与批量语义一致。

不包裹整批事务，因为产品决策明确要求部分成功。

## Frontend Flow

- 图片页且有删除权限时显示“批量管理”入口。
- 批量模式下，每张卡片显示 Checkbox；工具区提供当前页全选、已选数量、删除所选和退出。
- 选择仅限当前页；翻页、切换用途/分类、搜索或退出批量模式时清空。
- 确认后调用批量删除 API。成功删除的 ID 从选择中移除；失败项保留并通过结果弹窗逐项展示原因。
- 当前页全部可见项被删除且页码大于 1 时回退上一页，否则刷新当前页。

## Compatibility And Risk

- `/resources/images/bulk/` 现有 `POST` 批量上传保持不变，通过 DRF action method mapping 增加 `DELETE`。
- 请求上限 100 与后端分页最大值一致，限制单次操作成本。
- 不修改现有单项删除入口，便于回滚前端批量入口而不影响原流程。
- 回滚只需移除 DELETE mapping、前端 API 方法和批量 UI；无数据迁移。
