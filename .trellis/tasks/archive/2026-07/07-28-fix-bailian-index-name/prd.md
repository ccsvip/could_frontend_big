# 修复百炼索引名称长度校验

## Goal

确保任意合法的本地知识库名称都能创建百炼托管索引，不再因百炼 `name` 参数要求 1～20 字符而失败，同时保持远端索引名称稳定且全局唯一。

## Background

- `KnowledgeBase.name` 允许最多 128 字符（`backend/apps/knowledge_base/models.py:18`）。
- 首次索引当前发送 `${tenant_id}-${knowledge_base.name}`（`backend/apps/knowledge_base/managed_indexing.py:96`），可能超过百炼限制。
- `bailian.create_index` 当前只截断到 128 字符（`backend/apps/knowledge_base/bailian.py:152`），无法满足百炼的 20 字符契约。

## Requirements

- 远端索引名称必须与用户可编辑的知识库显示名称解耦。
- 名称必须非空且在 20 个 ASCII 字符以内。
- 名称必须由已持久化的 `KnowledgeBase` 主键确定，同一知识库重复计算结果不变，不同知识库结果不同。
- 使用 base36 表示数据库主键，并采用 `solin-k<base36_id>` 格式；对 Django 64 位正整数主键，最大长度为 20 个字符。
- 已存在 `bailian_index_id` 的知识库继续复用远端索引，不触发重建或改名。
- 用户可见的知识库名称长度和 API 契约保持不变。

## Acceptance Criteria

- [ ] 超长中文知识库名称首次索引时，传给 `bailian.create_index` 的 `name` 不超过 20 个字符。
- [ ] 最大 64 位正整数主键生成的索引名长度不超过 20，且只包含 ASCII 字母、数字和连字符。
- [ ] 两个不同知识库生成不同名称，同一知识库生成稳定名称。
- [ ] 现有百炼托管 RAG 目标测试通过。

## Out of Scope

- 不修改或迁移已经成功创建的远端索引。
- 不缩短或拒绝用户输入的知识库显示名称。
- 不改变上传、解析、检索和租户 Category 流程。
