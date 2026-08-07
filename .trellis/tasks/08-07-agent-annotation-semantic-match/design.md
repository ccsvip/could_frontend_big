# 设计：智能体标注语义匹配

## 1. 架构

```
用户问题
  → normalize + 精确匹配（现有）
  → 未命中且语义开启：
        解析租户 EmbeddingModel
        加载同 fingerprint 的 ready 向量
        embed 用户问句（超时 300ms）
        cosine Top1 >= 0.88 → 命中
  → 否则走 LLM / 知识库
```

统一匹配实现：`apps/ai_models/services/annotations.py`  
向量生命周期：`apps/ai_models/services/annotation_embeddings.py`  
复用：`agent_knowledge._embed_texts` / `_cosine_similarity` / `_embedding_model_for_tenant`

调用点：

| 路径 | 文件 |
|---|---|
| Web 会话 | `apps/ai_models/views.py` |
| 设备语音 HTTP | `apps/devices/views.py`（`_find_annotation`） |
| 实时 WS | `config/realtime.py`（经 device `_find_annotation`） |

## 2. 数据模型

### 2.1 `AgentAnnotationEmbedding`（新表）

| 字段 | 说明 |
|---|---|
| annotation | FK CASCADE |
| tenant / application | 冗余，便于按租户/智能体重建 |
| embedding_fingerprint | `code\|model\|dimensions` |
| embedding_model_name | 如 text-embedding-v4 |
| dimensions | 0 表示 default |
| question_hash | 归一化 question 的 sha256 |
| embedding | float 列表 |
| status | pending / ready / failed |
| error_message / embedded_at | 诊断用 |

约束：`(annotation, embedding_fingerprint)` 唯一；索引按 application/tenant + fingerprint + status。

### 2.2 智能体策略字段（`AgentApplication`）

| 字段 | 默认 | 说明 |
|---|---|---|
| annotation_semantic_enabled | True | 无 embedding 时运行时仍 no-op |
| annotation_cosine_threshold | 0.88 | |
| annotation_rerank_enabled | False | MVP 不调用 |
| annotation_rerank_threshold | 0.0 | 预留 |
| annotation_semantic_top_k | 3 | 预留 |

发布时写入 `published_config`，设备读已发布策略。

### 2.3 发布快照

每条标注增加：

```json
"embedding": {
  "fingerprint": "aliyun|text-embedding-v4|1024",
  "model": "text-embedding-v4",
  "dimensions": 1024,
  "vector": [/* floats */],
  "questionHash": "..."
}
```

无 ready 向量则为 `null`。

## 3. Fingerprint 与模型解析

```text
fingerprint = f"{code}|{model}|{dimensions or 'default'}"
```

运行时（草稿/未发布匹配）：

1. 优先当前租户 embedding 的 fingerprint，且存在 ready 向量
2. 否则回退到任一仍可调用模型的旧 fingerprint 桶
3. 都没有 → 仅精确匹配

已发布快照：

1. 使用快照内向量
2. 用与快照 fingerprint 匹配且可调用的模型 embed query
3. 解析不到模型 → 仅精确匹配

**不**依赖 `managed_rag_enabled`。

## 4. 匹配契约

```text
match_annotation(...)
  1) exact → match_type=exact, score=1.0
  2) semantic cosine Top1 ≥ threshold → match_type=semantic
  3) MVP 永不调用 rerank
  4) 失败/超时 → None（上层继续 LLM）
```

对外兼容：`find_matching_annotation` / `find_matching_published_annotation` 仍返回 annotation 或 None。

## 5. 索引生命周期

| 事件 | 动作 |
|---|---|
| 创建/更新标注 | 同步 embed 当前 fingerprint |
| 修改 question | 清空该标注所有桶后重建当前桶 |
| 删除标注 | CASCADE |
| 租户 embedding 变更 | 批量 reindex 新 fingerprint，保留旧桶 |
| EmbeddingModel.model/dimensions 变更 | 信号触发相关租户 reindex |
| 发布 | 快照拷贝当前 fingerprint 的 ready 向量 |
| 管理命令 | `reindex_annotation_embeddings` |

## 6. 延迟控制

| 控制项 | 值 |
|---|---|
| query embed 超时 | 300ms |
| 索引 embed 超时 | 30s（保存路径软失败） |
| rerank | 关闭 |
| 精确短路 | 始终最先 |

现网实测 embed ≈ 180ms p50，落在 300ms 预算内。

## 7. 全局开关

`settings.ANNOTATION_SEMANTIC_MATCH_ENABLED`（默认 True）作为紧急关闭。

## 8. 兼容与回滚

- 旧发布快照无 `embedding` 字段 → 仅精确匹配，直到重新 publish
- 迁移仅增量字段/新表
- 回滚：关全局开关或智能体 `annotation_semantic_enabled=False`

## 9. 安全与租户隔离

- 按 application + tenant 过滤
- 向量不跨租户
- 日志只记 match 元数据，遵循现有脱敏

## 10. 测试策略

Mock `embed_query`：

- 精确命中
- 语义过阈值命中 / 不过阈值未命中
- embed 异常降级
- 维度不一致跳过
- fingerprint 隔离
- 双桶回退
- 发布快照含向量
- 租户隔离
- 全局/应用关闭语义
