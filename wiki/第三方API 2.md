# FlowMesh Open API

**Base URL:** `https://flowmesh-api.kmyszkj.com/api/open/v1`

---

## 认证

所有请求需在 Header 中携带对应类型的 API Key：

```
Authorization: Bearer <api-key>
sk-5wx1TnriRHYKSzIvido7rMbDruMiK_CeSBUe1QwYJU8
```

| API Key 前缀 | 适用范围 |
|---|---|
| `sk-` | 智能体 / 工作流 应用接口 |
| `fm-` | 知识库接口 |

---

## 通用响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

`code` 为 `0` 表示成功，非 `0` 为业务错误。HTTP 状态码 `401` / `403` / `500` 表示认证或系统级错误。

> **注意：** 所有 ID 字段均为字符串类型，以避免 JavaScript 大数精度丢失。

---

## 智能体 API

### 1. 获取应用信息

```
GET /apps/{slug}/info
```

**响应示例**

```json
{
  "code": 0,
  "data": {
    "id": "2062883145999032321",
    "name": "中医一附院问答助手",
    "description": "...",
    "type": "AGENT",
    "accessSlug": "zy-assistant"
  }
}
```

---

### 2. 创建会话

```
POST /apps/{slug}/sessions
```

**响应示例**

```json
{
  "code": 0,
  "data": {
    "sessionId": "2063100000000000001",
    "appId": "2062883145999032321",
    "slug": "zy-assistant"
  }
}
```

---

### 3. 会话列表

```
GET /apps/{slug}/sessions
```

**响应示例**

```json
{
  "code": 0,
  "data": [
    {
      "sessionId": "2063100000000000001",
      "appId": "2062883145999032321",
      "slug": "zy-assistant",
      "title": "关于1号楼科室分布的问题",
      "messageCount": 4,
      "status": "active",
      "createTime": "2026-06-05 10:00:00",
      "updateTime": "2026-06-05 10:05:00"
    }
  ]
}
```

---

### 4. 会话详情

```
GET /apps/{slug}/sessions/{sessionId}
```

**响应示例**

```json
{
  "code": 0,
  "data": {
    "session": {
      "sessionId": "2063100000000000001",
      "title": "关于1号楼科室分布的问题",
      "messageCount": 2
    },
    "messages": [
      {
        "id": "2063200000000000001",
        "role": "user",
        "content": "1号楼有哪些科室？",
        "status": "done",
        "createTime": "2026-06-05 10:00:00"
      },
      {
        "id": "2063200000000000002",
        "role": "assistant",
        "content": "1号楼设有内科、外科……",
        "status": "done",
        "inputTokens": 120,
        "outputTokens": 85,
        "createTime": "2026-06-05 10:00:03"
      }
    ]
  }
}
```

---

### 5. 删除会话

```
DELETE /apps/{slug}/sessions/{sessionId}
```

**响应示例**

```json
{ "code": 0, "data": null }
```

---

### 6. 流式对话（SSE）

```
POST /apps/{slug}/sessions/{sessionId}/chat
Content-Type: application/json
```

**请求体**

```json
{
  "query": "1号楼有哪些科室？",
  "history": [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "你好，有什么可以帮助你？" }
  ],
  "deepThinkingEnabled": false,
  "deepThinkingLevel": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | ✅ | 用户输入 |
| `history` | array | ❌ | 附加历史消息，补充本轮上下文 |
| `deepThinkingEnabled` | boolean | ❌ | 是否开启深度思考 |
| `deepThinkingLevel` | string | ❌ | 深度思考强度（`low` / `medium` / `high`） |

**响应**：`Content-Type: text/event-stream`，SSE 格式：

```
data: {"type":"delta","content":"1号楼设有"}

data: {"type":"delta","content":"内科、外科"}

data: {"type":"done","content":""}
```

| 事件类型 | 说明 |
|---|---|
| `delta` | 增量文本片段 |
| `done` | 生成完毕 |
| `error` | 发生错误，`content` 为错误信息 |

---

### 7. 同步对话（便捷接口）

不需要预先创建会话，自动管理会话生命周期。

```
POST /apps/{slug}/chat
Content-Type: application/json
```

**请求体**

```json
{
  "query": "1号楼有哪些科室？",
  "sessionId": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | ✅ | 用户输入 |
| `sessionId` | string | ❌ | 传入则继续已有会话；不传则自动创建新会话 |

**响应示例**

```json
{
  "code": 0,
  "data": {
    "sessionId": "2063100000000000001",
    "answer": "1号楼设有内科、外科……",
    "version": "v3"
  }
}
```

---

### 8. 停止生成

```
POST /apps/{slug}/sessions/{sessionId}/stop
```

**响应示例**

```json
{
  "code": 0,
  "data": {
    "found": true,
    "stopped": true,
    "alreadyFinished": false
  }
}
```

---

## 工作流 API

### 1. 同步运行

等待工作流执行完成后返回全部输出。

```
POST /apps/{slug}/run
Content-Type: application/json
```

**请求体**

```json
{
  "inputs": {
    "question": "今天天气如何？",
    "language": "zh"
  }
}
```

`inputs` 键名与工作流定义的输入变量保持一致，不填则传空对象或省略 Body。

**响应示例**

```json
{
  "code": 0,
  "data": {
    "answer": "今天北京晴，气温 28℃。",
    "summary": "..."
  }
}
```

---

### 2. 流式运行（SSE）

```
POST /apps/{slug}/run/stream
Content-Type: application/json
```

**请求体**（同上 `inputs` 结构）

**响应**：`Content-Type: text/event-stream`，按节点粒度推送进度：

```
data: {"type":"node_start","nodeId":"llm_1","nodeName":"LLM 节点"}

data: {"type":"node_end","nodeId":"llm_1","outputs":{"answer":"..."}}

data: {"type":"workflow_end","outputs":{"answer":"..."}}
```

---

## 知识库 API

### 权限范围（Scope）

创建知识库 API Key 时需指定权限范围：

| Scope | 说明 |
|---|---|
| `KB_READ` | 查看知识库信息 |
| `KB_WRITE` | 创建 / 修改 / 删除知识库 |
| `DOC_READ` | 查看文档 |
| `DOC_WRITE` | 新增 / 修改 / 删除文档 |
| `CHUNK_READ` | 查看分片 |
| `CHUNK_WRITE` | 新增 / 修改 / 删除分片 |
| `RETRIEVAL` | 执行检索 |

---

### 知识库

#### 列出知识库

```
GET /datasets
```

返回当前 API Key 有权访问的知识库列表。所需 Scope：`KB_READ`

**响应示例**

```json
{
  "code": 0,
  "data": [
    {
      "id": "2062809131456737282",
      "name": "中医一附院",
      "description": "院内科室与就诊信息",
      "documentCount": 12,
      "createTime": "2026-05-01 09:00:00"
    }
  ]
}
```

---

#### 获取知识库详情

```
GET /datasets/{datasetId}
```

所需 Scope：`KB_READ`

---

#### 创建知识库

```
POST /datasets
Content-Type: application/json
```

所需 Scope：`KB_WRITE`

**请求体**

```json
{
  "name": "新知识库",
  "description": "用途说明"
}
```

---

#### 更新知识库

```
PATCH /datasets/{datasetId}
Content-Type: application/json
```

所需 Scope：`KB_WRITE`

**请求体**（仅传需要修改的字段）

```json
{
  "name": "新名称",
  "description": "新描述"
}
```

---

#### 删除知识库

```
DELETE /datasets/{datasetId}
```

所需 Scope：`KB_WRITE`

---

### 文档

#### 文档列表

```
GET /datasets/{datasetId}/documents?page=1&limit=20
```

所需 Scope：`DOC_READ`

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` | integer | 1 | 页码 |
| `limit` | integer | 20 | 每页条数 |

**响应示例**

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "list": [
      {
        "id": "2062827573593362433",
        "name": "1号楼及2号楼科室分布.pdf",
        "status": "completed",
        "chunkCount": 35,
        "characters": 12400,
        "createTime": "2026-05-10 14:00:00"
      }
    ]
  }
}
```

---

#### 获取文档详情

```
GET /datasets/{datasetId}/documents/{docId}
```

所需 Scope：`DOC_READ`

---

#### 新增文档

```
POST /datasets/{datasetId}/documents
Content-Type: application/json
```

所需 Scope：`DOC_WRITE`

**请求体**

```json
{
  "name": "文档名称",
  "sourceType": "TEXT",
  "content": "文档正文内容……"
}
```

---

#### 更新文档

```
PATCH /datasets/{datasetId}/documents/{docId}
Content-Type: application/json
```

所需 Scope：`DOC_WRITE`

---

#### 删除文档

```
DELETE /datasets/{datasetId}/documents/{docId}
```

所需 Scope：`DOC_WRITE`

---

### 分片（Segment）

#### 分片列表

```
GET /datasets/{datasetId}/documents/{docId}/segments?page=1&limit=20
```

所需 Scope：`CHUNK_READ`

**响应示例**

```json
{
  "code": 0,
  "data": {
    "total": 35,
    "list": [
      {
        "id": "2062900000000000001",
        "title": "内科（1101-1115）",
        "content": "内科位于1号楼11层……",
        "characters": 350,
        "enabled": 1,
        "position": 1,
        "hits": 12
      }
    ]
  }
}
```

---

#### 新增分片

```
POST /datasets/{datasetId}/documents/{docId}/segments
Content-Type: application/json
```

所需 Scope：`CHUNK_WRITE`

**请求体**

```json
{
  "content": "分片正文内容，不能为空",
  "title": "可选标题",
  "enabled": 1,
  "position": 0
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `content` | string | ✅ | 分片内容 |
| `title` | string | ❌ | 分片标题 |
| `enabled` | integer | ❌ | `1` 启用（默认），`0` 禁用 |
| `position` | integer | ❌ | 排序位置，默认 `0` |

---

#### 更新分片

```
PATCH /datasets/{datasetId}/documents/{docId}/segments/{chunkId}
Content-Type: application/json
```

所需 Scope：`CHUNK_WRITE`

**请求体**（仅传需要修改的字段）

---

#### 删除分片

```
DELETE /datasets/{datasetId}/documents/{docId}/segments/{chunkId}
```

所需 Scope：`CHUNK_WRITE`

---

### 检索

```
POST /datasets/{datasetId}/retrieve
Content-Type: application/json
```

所需 Scope：`RETRIEVAL`

**请求体**

```json
{
  "query": "1号楼内科在哪里",
  "retrievalMode": "hybrid",
  "topK": 5,
  "scoreThresholdEnabled": 1,
  "scoreThreshold": 0.5,
  "hybridStrategy": "rrf",
  "hybridSemanticWeight": 0.7,
  "rerankEnabled": 0,
  "filterDocumentIds": ["2062827573593362433"],
  "metadataFilter": {
    "department": "内科"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `query` | string | ✅ | 检索问题 |
| `retrievalMode` | string | ❌ | `semantic`（语义）/ `fulltext`（全文）/ `hybrid`（混合，默认） |
| `topK` | integer | ❌ | 返回条数，默认 5 |
| `scoreThresholdEnabled` | integer | ❌ | `1` 启用分数过滤，`0` 不过滤 |
| `scoreThreshold` | number | ❌ | 最低相似度分数，`0~1` |
| `hybridStrategy` | string | ❌ | 混合策略：`rrf`（倒数融合）/ `weighted`（加权） |
| `hybridSemanticWeight` | number | ❌ | 语义权重（仅 `weighted` 策略有效），`0~1` |
| `rerankEnabled` | integer | ❌ | `1` 启用重排序，`0` 不启用 |
| `filterDocumentIds` | array | ❌ | 限定检索的文档 ID 列表 |
| `metadataFilter` | object | ❌ | 元数据过滤条件，键值对 |

**响应示例**

```json
{
  "code": 0,
  "data": {
    "logId": "2063500000000000001",
    "records": [
      {
        "chunkId": "2062900000000000001",
        "documentId": "2062827573593362433",
        "documentName": "1号楼及2号楼科室分布.pdf",
        "title": "内科（1101-1115）",
        "content": "内科位于1号楼11层……",
        "score": 0.92,
        "rank": 1
      }
    ]
  }
}
```

---

## 错误码

| HTTP 状态码 | code | 说明 |
|---|---|---|
| 200 | 0 | 成功 |
| 200 | 非 0 | 业务错误，见 `message` 字段 |
| 401 | 401 | API Key 缺失、无效或已过期 |
| 403 | 403 | 无权访问该资源 |
| 500 | 500 | 服务器内部错误 |
