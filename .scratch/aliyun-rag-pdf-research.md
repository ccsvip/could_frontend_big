# 阿里云百炼 RAG 知识库 PDF 处理调研

调研时间：2026-07-22。以下结论均来自阿里云官方文档。

## 结论摘要

上传 PDF 后，PDF 的解析、切片、向量化和写入向量库应由阿里云百炼知识库服务完成，不需要在本地部署 pgvector 或自行实现 PDF 向量化。业务系统只需调用文件上传/添加、状态查询、创建或提交索引等 API，并等待异步状态完成。

## 官方 API 流程

官方《使用 API 操作知识库》示例的顺序是：

1. `ApplyFileUploadLease`：按文件名、MD5、大小申请上传租约和预签名 URL。
2. 使用预签名 URL `PUT` 上传文件。
3. `AddFile`：携带租约 ID、类目 ID 和解析器 `parser` 将已上传文件登记到百炼。
4. `DescribeFile` 轮询解析状态：`INIT`（待解析）→ `PARSING`（解析中）→ `PARSE_SUCCESS`（解析成功）。
5. `CreateIndex`：以 `structureType=unstructured`、`sourceType=DATA_CENTER_FILE`、`sinkType=DEFAULT` 和 `documentIds` 创建文档搜索类知识库索引。
6. `SubmitIndexJob`（首次创建）或 `SubmitIndexAddDocumentsJob`（向已有索引追加文件）提交索引任务，再查询任务状态。
7. 索引完成后通过 `Retrieve` 检索文本切片；向量生成和向量存储由知识库托管。

来源：[知识库 API 指南](https://help.aliyun.com/zh/model-studio/rag-knowledge-base-api-guide)

## PDF 解析器与“对应模型”

`AddFile` 官方 API 的 `Parser` 参数列出：`DOCMIND`（文档智能解析）、`DOCMIND_DIGITAL`（电子文档解析）、`DOCMIND_LLM_VERSION`（大模型文档解析）、`DASH_QWEN_VL_PARSER`（Qwen VL 解析）、`DOCMIND_LLM_VERSION_MEDIA`（音视频解析）和 `AUTO_SELECT`（自动选择）。当类目类型为 `UNSTRUCTURED` 时，也可由类目解析设置决定解析器；Qwen VL 解析才需要额外的 `ParserConfig`。

来源：[AddFile API 参数说明](https://help.aliyun.com/zh/model-studio/api-bailian-2023-12-29-addfile)

知识库产品文档进一步说明本地上传的“解析方式”：

- **电子文档解析**：不解析插图/图表，速度最快，适合纯文本 PDF。
- **文档智能解析**：识别并提取插图内容、生成文本摘要；摘要与其他内容一起切分并向量化。
- **大模型文档解析**：调用千问 VL 模型深度理解插图和图表，适合需要图表问答的 PDF。
- **Qwen VL 解析**：专用于图片文件，可指定千问 VL 模型和 Prompt。

来源：[知识库产品说明（解析方式）](https://help.aliyun.com/zh/model-studio/rag-knowledge-base)；[文档理解产品概览](https://help.aliyun.com/zh/document-mind/product-overview/overview-of-document-understanding)

如果创建知识库类型选择“视觉理解（富文本文档）”，系统对 PDF/图片做视觉级理解并保留原始版面；向量模型会自动切换为 **qwen3 多模态向量（qwen3-vl-embedding）**，不可更改。该模式支持纯文字、纯图片、图文组合命中测试。

来源：[知识库产品说明（知识库类型与视觉理解）](https://help.aliyun.com/zh/model-studio/rag-knowledge-base)

## 切片与向量化

文档解析后，知识库将内容切分为文本切片，再通过向量模型将每个切片转换为向量，以键值对形式写入向量数据库。支持智能切分（默认，按分句和语义完整性切分）、按长度切分（可设置重叠字符）和按页切分（适合页面主题独立的文件，如部分 PDF）。创建后可查看、编辑、增删切片。

基础文档问答默认使用 `text-embedding-v4`（官方向量 v4，512 维）；也可使用 `text-embedding-v3`（512 维）。视觉理解知识库使用 qwen3-vl-embedding。向量模型用于把查询 Prompt 和切片转换为数值向量，以计算语义相似度。

来源：[知识库产品说明（切片方式、向量模型）](https://help.aliyun.com/zh/model-studio/rag-knowledge-base)；[文本与多模态向量化](https://help.aliyun.com/zh/model-studio/embedding)

## 对当前报错的含义

`could not access file "$libdir/vector"` 是本地 PostgreSQL/pgvector 依赖错误，发生在应用查询本地向量表时；它不是阿里云 PDF 解析或阿里云 Embedding API 的正常返回。若目标架构是“上传后由阿里云百炼知识库自动解析和向量化”，应用侧不应在上传流程中自行写入 PostgreSQL `vector` 列或调用本地 Embedding。应核对当前实现是否误把阿里云知识库流程与本地向量库流程混用，并以百炼返回的 `fileId`、`indexId`、解析/索引任务状态作为业务状态来源。

