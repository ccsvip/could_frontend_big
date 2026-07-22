# Technical Design — 知识库文档切片查看与编辑

## Architecture

```text
Web (KB detail document row)
  → Drawer: GET /knowledge-base/{id}/chunks/
  → Modal save: PATCH /knowledge-base/{id}/chunks/{chunkId}/
       ↓
KnowledgeDocumentViewSet (tenant scoped)
  → resolve document (tenant) + knowledge_base.bailian_index_id + document.bailian_file_id
  → bailian.list_chunks / bailian.update_chunk
       ↓
Aliyun Bailian ListChunks / UpdateChunk
```

- **真源**：百炼索引内切片；本地不缓存正文。
- **隔离**：所有远端 ID 仅从已租户过滤的本地对象读取；客户端不得传 Index/File/Workspace。
- **权限**：list/retrieve 用 `CanViewKnowledgeBase`；update 用 `CanUploadKnowledgeBase`。

## Backend

### `bailian.py` 新增

```python
def list_chunks(*, index_id: str, file_id: str, page_num: int = 1, page_size: int = 10) -> dict:
    # ListChunksRequest(index_id=..., file_id=..., page_num=..., page_size=...)
    # return { 'total': int, 'nodes': [ { 'chunk_id', 'title', 'content', 'is_displayed' } ] }

def update_chunk(
    *,
    index_id: str,
    file_id: str,
    chunk_id: str,
    content: str,
    title: str | None = None,
    is_displayed: bool = True,
) -> None:
    # UpdateChunkRequest(
    #   pipeline_id=index_id, data_id=file_id, chunk_id=...,
    #   content=..., title=..., is_displayed_chunk_content=is_displayed,
    # )
```

**List 映射规则**

| 响应字段 | 来源 |
|---------|------|
| `content` | `node.text`；若空则 `metadata.content` |
| `chunkId` | `metadata._id`（必需，缺则丢弃该节点并打日志） |
| `title` | `metadata.title` 或 `metadata.hier_title`，默认 `''` |
| `isDisplayed` | `metadata.is_displayed_chunk_content`，缺省 `True`（兼容 bool/str） |
| `count` | `data.total` |

不向 API 暴露：`workspace_id`、`pipeline_id`、`doc_id`、`file_path`、`image_url` 等。

**错误**：SDK 异常 → `BailianKnowledgeError`，view 层转 `ValidationError` 或 502 风格业务 message（与现有 delete/retrieve 一致，优先可读中文摘要，截断）。

### View / URL

挂在现有 `KnowledgeDocumentViewSet`（`/knowledge-base/`）：

| Method | path | action | permission |
|--------|------|--------|------------|
| GET | `{pk}/chunks/` | `chunks` | view；若 method 未来扩展 POST 则 upload |
| PATCH | `{pk}/chunks/{chunk_id}/` | `chunk_detail` | upload |

实现要点：

1. `get_object()` 已租户过滤。
2. 前置：`assert_managed_rag_available(request_tenant)`（与 upload/index 一致）。
3. 文档 `index_status != ready` 或缺少 `bailian_file_id` / `knowledge_base.bailian_index_id` → `ValidationError` 明确文案。
4. `page` 默认 1，`pageSize` 默认 10，上限 100（对齐百炼）。
5. PATCH：校验 content 长度 10–6000、title ≤50；`is_displayed` 使用请求体可选字段，**MVP 前端不传**，后端默认 `True`。  
   - 更稳妥：PATCH body 可带 `isDisplayed`（可选）；若不传则 **先不** 二次 List，直接 `True`（产品接受：MVP 不关停检索）。与 PRD D6 一致。
6. `chunk_id` 路径参数：URL 安全字符串，禁止注入 path 遍历；原样交给 SDK。
7. 不写本地 `KnowledgeDocumentChunk`，不改 `chunk_count`。

### Serializer（轻量）

- 列表响应手写 dict 即可，或小 Serializer：`KnowledgeDocumentChunkRemoteSerializer`（非 Model）。
- PATCH body：`content` required string；`title` optional string allow blank。

### Tests（`test_managed_rag.py` 或新建 `test_chunks_api.py`）

Mock `bailian.list_chunks` / `update_chunk`：

- happy list + update
- missing mapping / not ready
- tenant isolation（B 用户访问 A 的 document → 404）
- permission：无 upload 时 PATCH 403
- content too short rejected before remote（可选）

## Frontend

### API 模块 `knowledge-base.ts`

```ts
type KnowledgeDocumentChunkRecord = {
  chunkId: string;
  title: string;
  content: string;
  isDisplayed: boolean;
};

type KnowledgeDocumentChunkListResponse = {
  count: number;
  page: number;
  pageSize: number;
  results: KnowledgeDocumentChunkRecord[];
};

fetchDocumentChunks(documentId, { page?, pageSize? })
updateDocumentChunk(documentId, chunkId, { content, title? })
```

路径：`/knowledge-base/${id}/chunks/`、`/knowledge-base/${id}/chunks/${encodeURIComponent(chunkId)}/`。

### UI `knowledge-base/index.tsx`

1. 文档操作列增加「查看切片」（`IconStack2` 或现有图标）；`indexingStatus !== 'ready'` 时 `disabled`。
2. `Drawer`：`width` 约 560–640；标题「切片 · {document.title}」；`Table`/`List` + `Pagination`；loading / empty / error。
3. 行操作「编辑」或点正文 → `Modal`：`Input` title + `Input.TextArea` content；校验 10–6000 / title ≤50；保存调 PATCH 后 `message.success` 并 refetch 当前页。
4. 无 upload 权限：可打开 Drawer，隐藏/禁用编辑按钮。
5. **不**在文档表增加切片数列。

### 兼容与回滚

- 纯增量 API + UI；失败时仅该功能不可用，上传/召回不受影响。
- 回滚：去掉 actions 与前端入口即可；远端已编辑切片会保留（符合预期）。

## Trade-offs

| 选择 | 原因 | 代价 |
|------|------|------|
| 不落库缓存切片 | 避免与百炼双写不一致 | 每次打开 Drawer 调远端，受 10 QPS 限流 |
| 透传 chunkId | 实现简单，无编解码 | 响应含百炼内部 id；可接受（非跨租户密钥） |
| MVP 不改 isDisplayed | 降风险 | 无法从本产品关停单条切片 |
| 不回写 chunk_count | 少写路径 | 文档表仍无可靠切片数 |

## Security

- 不 log AccessKey、完整远端错误体；错误摘要有界。
- chunkId 仅作 opaque 字符串，不拼 SQL。
- 租户 scope 与现有 document destroy/download 一致。
