# Dify 知识库引用实现研究（最小版）

访问日期：2026-07-23  
研究基准：Dify 官方仓库提交 [`b56ac4af4d1470eedd68236d581174a0c29d57b2`](https://github.com/langgenius/dify/tree/b56ac4af4d1470eedd68236d581174a0c29d57b2)  
来源范围：仅 Dify 官方 GitHub 源码/API 契约。

## 结论

Dify 的实现不是让模型在答案正文里自行拼接来源，而是把“本轮实际召回的片段”作为结构化 `retriever_resources` 附着到 assistant message：流式响应在 `message_end.metadata.retriever_resources` 返回；历史消息接口则在消息对象的 `retriever_resources`（部分管理端日志映射来自 `metadata.retriever_resources`）中返回。前端把两条路径统一映射到消息的 `citation` 字段，再按文档聚合展示。

## 1. 数据与 SSE 契约

Dify 的内部召回来源模型 `RetrievalSourceMetadata` 包含：

- 定位：`dataset_id`、`document_id`、`segment_id`、`position`、`segment_position`
- 展示：`dataset_name`、`document_name`、`content`、`summary`、`title`
- 召回信息：`score`、`hit_count`、`word_count`、`index_node_hash`
- 其他：`data_source_type`、`retriever_from`、`page`、`doc_metadata`、`files`

来源：[citation_metadata.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/core/rag/entities/citation_metadata.py)

流式完成事件为：

```json
{
  "event": "message_end",
  "id": "message-id",
  "metadata": {
    "retriever_resources": [
      {
        "position": 1,
        "dataset_id": "...",
        "dataset_name": "...",
        "document_id": "...",
        "document_name": "...",
        "segment_id": "...",
        "segment_position": 3,
        "content": "实际召回切片正文",
        "score": 0.86
      }
    ]
  }
}
```

`MessageEndStreamResponse` 明确定义 `event=message_end` 与 `metadata`；响应转换器会将 `retriever_resources` 精简为可公开的来源字段。来源：[task_entities.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/core/app/entities/task_entities.py)、[base_app_generate_response_converter.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/core/app/apps/base_app_generate_response_converter.py)

## 2. 引用与召回切片的对应关系

每个引用条目就是一个实际召回片段，不是答案句子的精确行内归因。Dify 从检索记录构造来源，写入数据集、文档、切片 ID、切片正文与分数；启用开发态命中信息时额外提供切片序号、字符数、命中次数和向量哈希。来源：[dataset_retrieval.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/core/rag/retrieval/dataset_retrieval.py)

多次召回事件会被合并，Dify 当前按 `(dataset_id, document_id)` 去重并重新编号，因此它表达的是“回答使用/召回过哪些文档与片段”，并不证明答案中的某一句严格来自某个片段。来源：[message_cycle_manager.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/core/app/task_pipeline/message_cycle_manager.py)

## 3. 管理网页展示交互

- 即时聊天：收到 `message_end` 后，将 `metadata.retriever_resources` 写入当前回答的 `citation`。
- 历史聊天：加载历史消息时，将 `retriever_resources` 恢复到同一个 `citation` 字段。
- 回答仍在流式生成时不展示；完成后才在回答底部显示“引用”。
- 引用先按 `document_id` 聚合为文档胶囊；一行放不下时显示 `+ N` 展开。
- 点击文档胶囊弹出浮层，列出该文档下所有召回切片的序号和正文；管理调试态可显示字符数、召回次数、向量哈希、召回分数，并可跳转知识库文档。

来源：[chat hooks.ts](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/web/app/components/base/chat/chat/hooks.ts)、[answer/index.tsx](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/web/app/components/base/chat/chat/answer/index.tsx)、[citation/index.tsx](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/web/app/components/base/chat/chat/citation/index.tsx)、[citation/popup.tsx](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/web/app/components/base/chat/chat/citation/popup.tsx)

## 4. 持久化

Dify 使用独立的 `dataset_retriever_resources` 表，以 `message_id` 关联回答消息，并保存文档/切片定位、正文、分数、顺序和命中信息。历史消息序列化器把这些记录作为 `retriever_resources` 返回，因此刷新或进入日志页后仍能展示。来源：[model.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/models/model.py#L2628)、[message_fields.py](https://github.com/langgenius/dify/blob/b56ac4af4d1470eedd68236d581174a0c29d57b2/api/fields/message_fields.py)

## 5. 本项目可借鉴的最小方案

本项目边界已明确：引用只在管理网页查看。

1. 后端按 assistant message 持久化本轮实际召回切片快照；至少保存 `knowledgeBaseId/name`、`documentId/name`、`chunkId/index`、`content`、`score`、`position`。推荐独立引用表而不是只存临时 SSE 数据，便于历史查询和稳定审计。
2. 管理网页调试聊天：在回答完成事件中返回引用数组，前端收到后挂到当前 assistant message；历史加载接口返回同一 DTO，统一渲染。
3. 管理网页设备对话记录：后端从设备 HTTP/WebSocket 对话链路采集并持久化引用，历史接口返回；**不向设备 HTTP 或 WebSocket 响应增加引用字段**。
4. UI 复用 Dify 的轻量模式：回答底部显示“引用 2 个文档”；按文档聚合胶囊，点击浮层查看切片正文、召回分数和“查看知识库”链接。空数组不显示。
5. 不做首版行内 `[1]` 精确标注。现有召回信息只能可靠说明“本轮检索使用了哪些片段”，不能证明答案每句话与片段的逐字对应；这能避免制造虚假精确性。

### 建议统一 DTO

```ts
type KnowledgeCitation = {
  position: number
  knowledgeBaseId: string
  knowledgeBaseName: string
  documentId: string
  documentName: string
  chunkId: string
  chunkIndex?: number
  content: string
  score?: number
}
```

管理端即时事件与历史 API 使用相同字段，区别只在传输时机；设备端契约保持不变。
