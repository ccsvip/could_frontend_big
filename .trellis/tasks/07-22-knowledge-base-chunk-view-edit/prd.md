# 知识库文档切片查看与编辑

## Goal

在知识库详情的文档层，提供 Dify 风格的「查看 / 编辑切片」：文档索引就绪后，运营可浏览百炼托管知识库中该文档的文本切片，并修正正文与标题；保存后立即参与后续召回。不修改数据中心源文件。

## Background

- 文档 RAG 已切到 **阿里云百炼托管**（解析 / 切分 / 向量 / 检索在远端）。本地只维护 `KnowledgeDocument` / `KnowledgeBase` 元数据与 `bailian_file_id` / `bailian_index_id`。见 `.trellis/spec/backend/aliyun-bailian-managed-rag.md`。
- 本地 `KnowledgeDocumentChunk` 表仍在，但托管链路不再读写；**切片真相源是百炼**，不是本地 chunk 表。
- 百炼 OpenAPI + SDK（`alibabacloud_bailian20231229`）已提供：
  - `ListChunks`（`ListChunksRequest`：`index_id`, `file_id`, `page_num`, `page_size`）
  - `UpdateChunk`（`UpdateChunkRequest`：`pipeline_id`=index, `data_id`=file, `chunk_id`, `content`, `title`, `is_displayed_chunk_content`）
- 前端 `web/src/views/knowledge-base/index.tsx` 已有详情文档表与操作列，无切片入口；`web/src/api/modules/knowledge-base.ts` 无 chunk API。
- 后端 `backend/apps/knowledge_base/bailian.py` 尚未封装 List/Update Chunk。
- 权限现状：`knowledge_base.view` / `knowledge_base.upload` / download / bulk_download。

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| D1 | MVP 操作 | 查看列表 + 编辑 **content / title**。不含启用/禁用、删除、新增。 |
| D2 | 入口 UI | 文档行「查看切片」→ **右侧 Drawer**（分页列表）+ **编辑 Modal**。 |
| D3 | 权限 | 列表：`knowledge_base.view`；保存：`knowledge_base.upload`。 |
| D4 | 切片数 | 文档行 **不** 显示切片数；仅 Drawer 内展示 `total`。不回写 `chunk_count`。 |
| D5 | 切片 ID | 路径用本地 `documentId`；请求/响应携带百炼 `chunkId` 字符串。**永不**接收或返回 Workspace / Index / File ID。更新时后端用本地映射补齐 `pipeline_id`/`data_id`。 |
| D6 | Update 启停字段 | MVP 不改启停；调用 `UpdateChunk` 时从列表缓存的 `isDisplayed` 原样回传（默认 `true`），避免误关检索。 |

## Requirements

### Must

- **R1** 知识库详情 → 文档表操作列增加「查看切片」；`indexingStatus === 'ready'` 且业务上可拉切片时可用，否则禁用或点击后明确提示。
- **R2** Drawer 分页展示切片：页码、标题、正文预览（可展开）、字符数；底栏/标题显示 `total`。
- **R3** 编辑 Modal 可改 title（0–50 字）与 content（10–6000 字）；保存成功后刷新当前页列表。
- **R4** 后端仅接受本地 `document_id` + `chunkId`；租户作用域下解析 `bailian_index_id` / `bailian_file_id` 再调百炼。
- **R5** 未 ready、缺远端映射、平台未配置或租户未授权托管 RAG → 可读错误，不暴露跨租户信息。
- **R6** 前端基本校验 + 远端/后端错误 message 透出；无删除/新增/启停入口。

### Backlog（非本任务）

- 启用/禁用检索、删除切片、新增切片、关键词搜切片、召回结果跳转编辑。

## Acceptance Criteria

- [ ] **AC1** ready 文档打开 Drawer 能分页看到切片正文与 total。
- [ ] **AC2** 编辑 title/content 保存后列表与再次打开可见新内容（真源百炼）。
- [ ] **AC3** 跨租户 / 不存在 documentId → 404 语义，无远端 ID 泄漏。
- [ ] **AC4** 未 ready 或缺 `bailian_*` 映射 → 明确错误，不成功改远端。
- [ ] **AC5** content 过短/过长等：前端拦一层；后端/远端失败有 message。
- [ ] **AC6** UI 无删除/新增/启停切片；文档行无切片数列。
- [ ] **AC7** 列表需 view 权限；保存需 upload 权限（无 upload 仅可看）。

## Out of Scope

- 恢复本地 `KnowledgeDocumentChunk` 作为主数据源或本地切分/embedding。
- 修改百炼数据中心源文件。
- 导出切片、DeleteChunk / AddChunk、改 `IsDisplayedChunkContent` 产品入口。
- 回写/修复历史 `chunk_count` 字段语义（可另开任务）。

## API Sketch（契约摘要，细节见 design）

- `GET /api/v1/knowledge-base/{documentId}/chunks/?page=&pageSize=`
  - 200：`{ count, page, pageSize, results: [{ chunkId, title, content, isDisplayed }] }`
- `PATCH /api/v1/knowledge-base/{documentId}/chunks/{chunkId}/`
  - body：`{ content, title? }`
  - 200：更新后的切片对象（或 `{ ok: true }` + 前端 refetch）

## Notes

- 复杂任务：必须有 `design.md` + `implement.md`，且 `implement.jsonl` / `check.jsonl` 有真实条目后才能 `task.py start`。
- 切片编辑不改源文件，符合百炼产品语义。
