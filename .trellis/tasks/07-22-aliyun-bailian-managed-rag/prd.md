# 接入阿里云百炼托管知识库解析与召回

## Goal

将知识库改为阿里云百炼托管 RAG：用户上传阿里云官方支持的文档格式后，由百炼完成文件解析、切片、Embedding 与索引；大模型对话和知识库命中测试通过百炼 Retrieve 召回内容，同时保持本地业务权限、知识库绑定和公司数据 100% 隔离。

## Confirmed Facts

- 当前实现会在本地解析文件、切片、调用 `/compatible-mode/v1/embeddings`，并从本地 `KnowledgeDocumentChunk` 召回。
- 官方托管流程为 `ApplyFileUploadLease → PUT → AddFile → DescribeFile → CreateIndex/SubmitIndexJob（或追加文档）→ Retrieve`。
- 百炼 `AddFile` 支持电子文档、智能文档、大模型文档、Qwen VL 和自动选择等解析器。
- 当前系统已有租户隔离的 `KnowledgeBase`、`KnowledgeDocument`、智能体绑定关系和 Celery 异步任务。
- 当前环境未配置百炼知识库所需的 AccessKey ID/Secret；现有 `MULTIMODAL_WORKSPACE_ID` 属于 ASR/VAD 配置，不能默认视为知识库授权。
- 用户已确认：百炼凭据和 Workspace 由超管统一配置，超管按公司授权；公司账号不配置、不查看密钥。
- 用户已确认：每个公司下的每个知识库映射独立百炼索引，默认解析器为 `AUTO_SELECT`，知识库管理员可选择其他官方解析器。
- 官方文档搜索支持 `doc/docx/wps/ppt/pptx/xls/xlsx/md/txt/pdf/epub/mobi`；图片、音频、视频属于不同知识库类型，不进入本次文档搜索入口。

## Requirements

1. 上传阿里云文档搜索知识库官方支持的文件后，保存本地文档记录并异步上传至百炼。
2. 百炼负责解析、切片、Embedding、向量存储与检索；不再使用本地 `KnowledgeDocumentChunk` 作为主索引或召回来源。
3. 本地持久化百炼 `fileId`、`indexId`、解析/索引任务 ID、阶段状态、错误和同步时间，用于幂等、重试和前端展示。
4. 每个本地知识库映射到独立的百炼索引；任何远端调用必须从租户范围内的本地映射取得 ID，禁止接受客户端传入任意远端 ID。
5. 上传、删除、重建索引与知识库删除必须同步百炼远端状态；远端失败要保留可重试状态，不得伪装成功。
6. 知识库命中测试、HTTP 对话、语音/WebSocket 对话统一通过百炼 Retrieve 召回，并沿用现有上下文注入契约。
7. 官方凭据与 Workspace 配置只能由平台管理员维护，响应中必须脱敏，日志不得输出 AccessKey Secret 或预签名上传 URL。
8. 前端展示上传、解析、索引、就绪、失败状态和明确错误，并支持人工重试。
9. 对既有文档提供可控的重新同步路径；上线与回滚不能删除本地原文件或已有业务绑定。
10. 文档上传白名单与阿里云文档搜索官方格式保持一致；服务端实际限制或错误必须原样归类为可定位的业务错误。
11. 平台凭据使用专用配置模型；AccessKey Secret 必须加密存储、仅支持覆盖写入且永不回传明文。
12. 知识库解析器默认 `AUTO_SELECT`，允许选择 `DOCMIND`、`DOCMIND_DIGITAL`、`DOCMIND_LLM_VERSION`；图片专用 Qwen VL、音视频解析不在本次入口暴露。

## Acceptance Criteria

- [ ] 上传至少 PDF、DOCX 及一种其他官方支持格式后，百炼状态依次完成解析与索引，本地最终为 ready。
- [ ] 文件内容、切片和向量由百炼托管，本地索引流程不调用文本 Embedding API、不写入新的 `KnowledgeDocumentChunk`。
- [ ] 对话询问文档内信息时，Retrieve 返回的切片被注入大模型上下文，并能追溯到本地知识库/文档。
- [ ] A 公司无法通过 API 参数、智能体绑定或远端 ID 召回 B 公司知识。
- [ ] 重复执行同一索引任务不会重复创建远端文件/索引；中断后可安全重试。
- [ ] 删除文档、删除知识库、重新索引均有远端同步和失败处理测试。
- [ ] 现有非知识库对话、设备统一 WebSocket 和媒体素材能力不被破坏。
- [ ] 超管可保存/更新百炼凭据、测试配置状态并按公司授权；公司端永远看不到密钥或 Workspace ID。
- [ ] `wps/epub/mobi` 等新增官方格式可上传，非白名单格式在进入远端流程前返回明确校验错误。

## Out of Scope

- 不自行实现 PDF/OCR/Office 解析器。
- 不自行实现向量相似度检索或维护新的本地 pgvector 索引。
- 本阶段不迁移到用户自购 ADB-PG，使用百炼内置向量库。

## Product Decisions

- 平台统一一套 AccessKey 和一个专用 Workspace，由超管配置并按公司授权。
- 每个本地知识库对应独立百炼 index；同一 Workspace 内通过后端租户映射强制隔离。
- 默认解析器为 `AUTO_SELECT`；知识库级可切换到其他文档解析器。
- 保留本地原文件用于下载与故障重试；百炼是解析、切片、向量与召回的唯一事实源。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
