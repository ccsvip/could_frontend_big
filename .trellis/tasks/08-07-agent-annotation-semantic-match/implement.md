# 实现清单：智能体标注语义匹配

## 清单

### 1. 数据层

- [x] 迁移：`AgentAnnotationEmbedding` + 索引/约束
- [x] 迁移：`AgentApplication` 策略字段
- [x] 全局开关 `ANNOTATION_SEMANTIC_MATCH_ENABLED`（默认 True）

### 2. Embedding 运行时

- [x] `model_fingerprint` / `question_hash` / `embed_query(timeout=0.3)`
- [x] 复用租户 embedding 解析；不绑 managed_rag
- [x] cosine 复用 agent_knowledge

### 3. 索引

- [x] create/update 同步 `sync_annotation_embedding`
- [x] question 变更失效后重建
- [x] 管理命令 `reindex_annotation_embeddings`
- [x] 租户知识模型设置变更 / EmbeddingModel 字段变更触发 reindex

### 4. 匹配

- [x] `match_annotation`：exact → semantic；MVP 无 rerank
- [x] 双桶 prefer/fallback
- [x] Web / 设备 / 实时统一入口

### 5. 发布快照

- [x] `build_published_annotation_snapshot` 写入 embedding 块
- [x] 策略字段进入 `published_config`

### 6. 可观测

- [x] 日志记录 match_type / score / fingerprint / application_id

### 7. 测试

- [x] `apps.ai_models.tests.test_agent_annotation_semantic`（15 项）
- [x] 关联 API / 实时标注短路回归

### 8. 验证命令

```bash
docker compose exec backend python manage.py test apps.ai_models.tests.test_agent_annotation_semantic --keepdb
docker compose exec backend python manage.py test \
  apps.ai_models.tests.test_agent_application_api.AgentApplicationApiTests.test_publish_snapshots_annotation_blocks \
  apps.ai_models.tests.test_agent_application_api.AgentApplicationApiTests.test_create_annotation_from_assistant_message \
  apps.ai_models.tests.test_agent_application_api.AgentApplicationApiTests.test_create_annotation_accepts_media_reply_blocks \
  config.tests.test_realtime_websocket.RealtimeDeviceEventsTests.test_device_llm_session_skips_knowledge_retrieval_for_annotation_answer \
  --keepdb
```

### 9. 回滚点

- 全局开关 / 智能体 `annotation_semantic_enabled=False` → 仅精确匹配
- 匹配代码可回退，表可保留空转

### 10. 实现期非范围

- 别名 UI
- 真实 rerank 调用
- 前端阈值编辑器
- pgvector

## 风险文件

| 文件 | 风险 |
|---|---|
| `services/annotations.py` | 核心命中行为 |
| `services/annotation_embeddings.py` | 超时/换模型 |
| `services/reply_blocks.py` | 发布快照体积与相等比较 |
| `models.py` / migration 0056 | 数据模型 |
| `devices/views.py` / realtime | 语音延迟路径 |
| `views.py` 标注 CRUD | 保存时 embed 软失败 |

## 完成标准

PRD 验收项覆盖；Docker 内相关测试通过；无跨 fingerprint cosine；实时不调 rerank。

## 验证结果（2026-08-07）

- `test_agent_annotation_semantic`：15/15 OK
- 发布快照 / 从消息创建标注 / 媒体块 / 实时标注短路：OK
- 迁移 `0056_agent_annotation_semantic_match` 已应用
