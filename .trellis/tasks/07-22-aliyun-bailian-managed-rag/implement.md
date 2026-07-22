# Implementation Plan

## 1. Configuration and SDK

- [ ] 添加阿里云百炼官方 Python SDK 依赖与集中客户端封装。
- [ ] 增加平台百炼配置模型、Secret 加密工具、迁移、admin/API serializer。
- [ ] 扩展公司授权模型与超管设置/公司授权 API。
- [ ] 补配置脱敏、缺失加密主密钥、未授权与租户隔离测试。

## 2. Remote Mapping and State

- [ ] 扩展 KnowledgeBase/KnowledgeDocument 的远端映射、解析器和状态字段。
- [ ] 更新 serializers/admin/API 类型与前端状态展示。
- [ ] 将上传白名单同步为官方文档搜索格式。

## 3. Managed Indexing Workflow

- [ ] 实现 lease、PUT、AddFile、DescribeFile、CreateIndex、SubmitIndexJob、追加文档与状态查询封装。
- [ ] 重写 Celery 文档索引任务，加入行锁、MD5 幂等、有界重试和远端状态映射。
- [ ] 实现删除、重建和历史文档显式迁移路径。
- [ ] 停止文档链路对本地解析、文本 Embedding 和 KnowledgeDocumentChunk 的读写。

## 4. Managed Retrieval

- [ ] 实现 Retrieve 封装和远端结果标准化。
- [ ] 重写命中测试与对话召回，保持现有上下文注入接口。
- [ ] 验证 HTTP、语音、统一 WebSocket 和智能体发布绑定均使用相同召回入口。

## 5. Frontend

- [ ] 超管知识库设置页增加百炼凭据、Workspace、Category、endpoint 和连接状态。
- [ ] 公司授权页增加托管知识库开关。
- [ ] 知识库页增加解析器选择、官方格式 accept、远端阶段状态、错误与重试交互。
- [ ] 遵循 Tabler 图标、brand token、fluid text 与移动端规范。

## 6. Validation

- [ ] 单元测试 mock 所有百炼边界：成功、解析失败、索引失败、超时、重试、幂等和删除。
- [ ] 参数化验证官方文档格式；至少完成 PDF、DOCX、XLSX 三类端到端 mocked 流程。
- [ ] 覆盖跨租户 index/file 访问与智能体绑定隔离。
- [ ] 覆盖 Retrieve → context → LLM 对话注入。
- [ ] 运行相关 Django 测试、`makemigrations --check`、前端 `npm run build`、Compose 检查。
- [ ] 使用真实百炼测试凭据时仅做手工验收，不将凭据或响应敏感字段写入仓库/日志。

## Rollback Points

- 配置/模型迁移后：可关闭托管 RAG 开关，保留数据。
- 远端同步上线后：停止 Celery 新任务，不删除远端 index。
- 召回切换后：可关闭知识上下文注入，主对话继续工作；不恢复本地 pgvector 写入。
