# Implementation Plan — 知识库文档切片查看与编辑

## Ordered Checklist

### 1. Backend Bailian client

- [x] 在 `backend/apps/knowledge_base/bailian.py` 实现 `list_chunks` / `update_chunk`（SDK `ListChunksRequest` / `UpdateChunkRequest`）。
- [x] 统一 `_data` / `BailianKnowledgeError` 错误路径；metadata 安全解析。

**验证**：容器内可 import；单测 mock SDK 返回节点映射正确。

### 2. Backend API

- [x] `KnowledgeDocumentViewSet` 增加 `chunks`（GET list）与 `chunk_detail`（PATCH）。
- [x] `permission_map`（PATCH → upload）。
- [x] 前置：`assert_managed_rag_available`、ready、index_id、file_id。
- [x] 分页与 content/title 校验。

**验证**：

```bash
docker compose exec backend python manage.py test apps.knowledge_base.tests.test_chunks_api --keepdb
```

### 3. Frontend API

- [x] `web/src/api/modules/knowledge-base.ts` 增加类型与 `fetchDocumentChunks` / `updateDocumentChunk`。

**验证**：`cd web && npm run build`（tsc）。

### 4. Frontend UI

- [x] 文档操作列「查看切片」。
- [x] Drawer 列表 + Pagination + total。
- [x] 编辑 Modal + 校验 + 保存 refetch。
- [x] 权限：无 upload 只读。

**验证**：`npm run build`；手动：ready 文档打开切片 → 改一条 → 再开确认；未 ready 禁用。

### 5. Quality gate

- [x] 后端相关 test 绿（6 passed）。
- [x] 前端 build 过。
- [ ] 对照 PRD AC1–AC7（代码层完成；真连百炼需环境冒烟）。
- [x] 不触碰本地 `KnowledgeDocumentChunk` 写入路径。

## Risky points

| 风险 | 缓解 |
|------|------|
| UpdateChunk 字段名 `pipeline_id`/`data_id` 与 List 的 `index_id`/`file_id` 不一致 | 严格按 SDK 构造参数；对照容器内 `inspect.signature` |
| metadata `_id` 缺失 | 丢弃节点 + 日志；列表可空 |
| chunkId URL 特殊字符 | `encodeURIComponent` |
| 限流 10/s | 单文档分页，避免列表页批量拉 total |

## Rollback

- 回退 views actions + bailian 两函数 + 前端入口；已编辑远端切片无需回滚。

## Out of this implement pass

- DeleteChunk / AddChunk / isDisplayed UI
- chunk_count 回写
- 独立路由

## Suggested file touch list

- `backend/apps/knowledge_base/bailian.py`
- `backend/apps/knowledge_base/views.py`
- `backend/apps/knowledge_base/serializers.py`（可选）
- `backend/apps/knowledge_base/tests/test_chunks_api.py`（新建）或扩展 `test_managed_rag.py`
- `web/src/api/modules/knowledge-base.ts`
- `web/src/views/knowledge-base/index.tsx`
