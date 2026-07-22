# Technical Design

## Architecture Decision

采用阿里云百炼托管 RAG，停止本地文档解析、文本 Embedding、`KnowledgeDocumentChunk` 写入与本地关键词/向量召回。保留现有本地知识库、文档、智能体绑定和文件下载能力；本地仅维护业务元数据、远端映射与异步状态。

```text
Web upload
  → Django 保存租户范围内的 KnowledgeDocument 与原文件
  → Celery 同步任务
  → ApplyFileUploadLease → 预签名 URL PUT → AddFile
  → DescribeFile 轮询解析状态
  → 首文档 CreateIndex + SubmitIndexJob
     后续文档 SubmitIndexAddDocumentsJob
  → 轮询索引任务 → 本地 ready

对话 / 命中测试
  → 从本地智能体绑定解析 tenant + KnowledgeBase
  → 读取该租户下本地保存的 bailian_index_id
  → 百炼 Retrieve
  → 标准化为现有 recall result / system context
  → 调用现有 LLM 对话链路
```

## Platform Configuration and Authorization

- 新增平台单例配置，保存 AccessKey ID、加密后的 AccessKey Secret、Workspace ID、Category ID、endpoint、启用状态和更新时间。
- Secret 使用部署环境提供的 Fernet 主密钥加密；API 仅返回 `configured` 和掩码，不返回密文或明文。
- 扩展现有公司知识库授权记录，增加托管 RAG 启用状态。只有超管可配置平台凭据和公司授权。
- 公司账号只能消费授权能力；未授权、平台配置不完整或停用时，上传索引返回明确状态/错误。

## Tenant Isolation

- 每个 `KnowledgeBase` 对应一个独立百炼 index。
- 所有远端 ID 均从已通过 `request_tenant`/智能体 tenant 过滤的本地对象读取；HTTP payload 不接受 Workspace ID、index ID 或 file ID。
- 文档、知识库、智能体绑定三者 tenant 必须一致；跨租户对象按现有策略返回 404/权限错误。
- 远端 Retrieve 按一个或多个已授权本地知识库分别调用，再在应用层合并排序；不使用共享 index + metadata filter 作为隔离边界。

## Data Model

### Platform / tenant

- 平台百炼配置：凭据、Workspace、Category、endpoint、enabled。
- 公司知识库授权：`managed_rag_enabled`，保留既有 embedding/rerank 字段以兼容媒体素材能力。

### KnowledgeBase

- `bailian_index_id`
- `bailian_index_status` / `bailian_index_error`
- `bailian_index_job_id`
- `parser`（默认 `AUTO_SELECT`）
- `bailian_synced_at`

### KnowledgeDocument

- `content_md5`
- `bailian_file_id`
- `bailian_parse_status`
- `bailian_index_job_id`
- `sync_attempt` / `bailian_synced_at`
- 继续复用用户可见的 `index_status/index_error/indexed_at`，但含义改为远端同步总状态。

远端 lease 和预签名 URL 为短期敏感数据，不持久化、不记录日志。Job ID 可持久化以支持轮询恢复。

## State Machine and Idempotency

```text
pending → uploading → parsing → indexing → ready
                    ↘ failed ←───────────↗
delete_pending → deleted / failed
```

- Celery 任务以本地文档 ID 为入口，先加数据库锁并检查当前远端映射。
- 已有 `bailian_file_id` 时不重复申请租约；已有运行中的 job 时恢复轮询；ready 且 MD5 未变化时直接返回。
- 外部传输错误使用 Celery 有界指数退避；业务失败保存百炼 request ID/错误摘要并停止自动无限重试。
- 首个 ready 文档负责创建 KB index；并发上传通过知识库行锁保证只创建一次。

## Delete and Reindex

- 删除文档先标记 `delete_pending` 并异步移除百炼索引文档/文件；远端成功后删除本地记录和文件。远端失败保留记录供重试，避免孤儿远端数据。
- 删除知识库先删除/停用远端 index，再执行现有本地删除流程。
- “重新索引”对失败/历史文档执行幂等同步；不再重建本地 chunks。
- 历史本地 ready 文档不自动批量产生远端费用；管理员通过现有知识库“重建索引”动作显式迁移。

## Retrieval Contract

- 新建百炼客户端模块封装 SDK，业务层不散落响应路径或签名逻辑。
- `retrieve_knowledge_chunks` 保持现有返回结构：`mode/chunks/mediaAssets`，将 Retrieve 的 score、content、file metadata 映射到本地文档与知识库。
- 召回失败不回退本地 keyword/pgvector，返回空召回并记录结构化告警；主对话仍可在无知识上下文时继续。
- 媒体素材 `KnowledgeMediaAsset` 的现有独立链路保持不变，本阶段不并入文档搜索知识库。

## API and Frontend

- 保持现有 REST 路径；上传仍返回 201 + pending 文档。
- Serializer 增加解析器、远端阶段状态、是否可重试和同步时间；远端 ID 仅后端内部使用。
- 超管知识库设置页新增百炼托管配置；公司授权页新增托管 RAG 授权开关。
- 知识库页面更新格式 accept、状态标签和错误展示；保留重新索引操作。

## Compatibility and Rollback

- 保留 `KnowledgeDocumentChunk` 表但新链路不再读写，避免破坏历史迁移；后续独立清理。
- 功能开关控制托管 RAG 是否启用；回滚只停止新同步/召回，不删除远端 index 或本地文件。
- 保留旧字段和接口响应兼容字段，前端逐步切换。

## Security

- 不记录 AccessKey Secret、预签名 URL、上传 headers 或完整外部错误响应。
- 超管写入 Secret 时空值表示保留旧值；显式清除使用独立动作而非空字符串覆盖。
- 请求超时、最大文件大小和文件名长度按官方 API 约束处理；官方 100MB/150MB 口径不一致时以实际 API 响应为准并输出明确错误。
