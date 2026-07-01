# 第三方会话机器人 API 接入文档

## 1. 文档说明

本文档用于指导第三方系统接入华鹏 AI 平台的会话机器人接口。

当前已验证可用的机器人信息如下：

- 机器人名称：`售前`
- 机器人说明：`售前AI助手`
- 应用类型：`WORK_FLOW`
- 站点地址：`https://ai.ihuapeng.cn`
- API 基础地址：`https://ai.ihuapeng.cn/api`
- 在线聊天页：`https://ai.ihuapeng.cn/ui/chat/application-395f59649acf1838af64570ebe4ba89e`
- 应用 ID：`8d697146-f9a2-11ef-89c4-86dcb2923f74`
- 应用密钥：`application-395f59649acf1838af64570ebe4ba89e`

## 2. 鉴权方式

所有接口均通过请求头传递应用密钥。

请求头如下：

```http
AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e
```

注意事项：

- 请求头名称是 `AUTHORIZATION`
- 值直接填写应用密钥
- 不要添加 `Bearer ` 前缀
- `POST` 请求需增加 `Content-Type: application/json`

## 3. 接入流程

完整调用流程共 3 步：

1. 获取应用信息
2. 打开会话，获取 `chat_id`
3. 基于 `chat_id` 发送消息

### 3.1 获取应用信息

用于确认当前应用配置，并获取 `application_id`。

- 方法：`GET`
- 地址：`/application/profile`

完整请求：

```http
GET https://ai.ihuapeng.cn/api/application/profile
AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e
```

示例响应：

```json
{
  "code": 200,
  "message": "成功",
  "data": {
    "id": "8d697146-f9a2-11ef-89c4-86dcb2923f74",
    "name": "售前",
    "desc": "售前AI助手",
    "type": "WORK_FLOW"
  }
}
```

关键字段：

- `data.id`：应用 ID
- `data.name`：应用名称
- `data.type`：应用类型

### 3.2 打开会话

用于创建一个新的会话并获取 `chat_id`。

- 方法：`GET`
- 地址：`/application/{application_id}/chat/open`

当前机器人实际请求地址：

```http
GET https://ai.ihuapeng.cn/api/application/8d697146-f9a2-11ef-89c4-86dcb2923f74/chat/open
AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e
```

示例响应：

```json
{
  "code": 200,
  "message": "成功",
  "data": "b9ce2cd6-322c-11f1-b244-5622443d16c7"
}
```

关键字段：

- `data`：新建会话的 `chat_id`

说明：

- 如需开启新会话，请再次调用该接口
- 如需继续同一轮多轮对话，请复用同一个 `chat_id`

### 3.3 发送消息

用于向指定会话发送用户问题并获取机器人回复。

- 方法：`POST`
- 地址：`/application/chat_message/{chat_id}`

完整请求：

```http
POST https://ai.ihuapeng.cn/api/application/chat_message/{chat_id}
AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e
Content-Type: application/json
```

最小请求体：

```json
{
  "message": "你好",
  "stream": false
}
```

常用请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | `string` | 是 | 用户输入的问题 |
| `stream` | `boolean` | 否 | 是否流式输出，建议首次联调用 `false` |
| `re_chat` | `boolean` | 否 | 是否重新生成 |
| `form_data` | `object` | 否 | 表单扩展字段 |
| `image_list` | `array` | 否 | 图片输入列表 |
| `document_list` | `array` | 否 | 文档输入列表 |
| `audio_list` | `array` | 否 | 音频输入列表 |
| `runtime_node_id` | `string` | 否 | 高级运行参数 |
| `node_data` | `object` | 否 | 节点数据 |
| `chat_record_id` | `string` | 否 | 对话记录 ID |
| `child_node` | `string` | 否 | 子节点参数 |

示例响应：

```json
{
  "code": 200,
  "message": "成功",
  "data": {
    "chat_id": "b9ce2cd6-322c-11f1-b244-5622443d16c7",
    "id": "消息记录ID",
    "operate": true,
    "content": "您好！请问您想了解哪方面的内容？是关于时代安迅的产品、技术方案还是售后服务？如果需要详细资料，您可以直接拨打我的专线 18251914995 与我沟通。📥 点击下载《江苏华鹏产品手册》 https://docs.ihuapeng.cn/jshpdocs.pdf",
    "is_end": true,
    "reasoning_content": "",
    "answer_list": [
      {
        "content": "您好！请问您想了解哪方面的内容？是关于时代安迅的产品、技术方案还是售后服务？如果需要详细资料，您可以直接拨打我的专线 18251914995 与我沟通。📥 点击下载《江苏华鹏产品手册》 https://docs.ihuapeng.cn/jshpdocs.pdf",
        "reasoning_content": ""
      }
    ],
    "completion_tokens": 0,
    "prompt_tokens": 0
  }
}
```

关键字段：

- `data.content`：机器人主回复内容
- `data.chat_id`：当前会话 ID
- `data.is_end`：当前消息是否结束
- `data.answer_list`：候选回答列表

## 4. 一次完整调用示例

### 4.1 cURL 示例

#### 1）获取应用信息

```bash
curl -X GET "https://ai.ihuapeng.cn/api/application/profile" \
  -H "AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e"
```

#### 2）打开会话

```bash
curl -X GET "https://ai.ihuapeng.cn/api/application/8d697146-f9a2-11ef-89c4-86dcb2923f74/chat/open" \
  -H "AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e"
```

#### 3）发送消息

```bash
curl -X POST "https://ai.ihuapeng.cn/api/application/chat_message/{chat_id}" \
  -H "AUTHORIZATION: application-395f59649acf1838af64570ebe4ba89e" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "stream": false
  }'
```

### 4.2 JavaScript 示例

```js
const API_BASE = 'https://ai.ihuapeng.cn/api';
const APP_KEY = 'application-395f59649acf1838af64570ebe4ba89e';
const APPLICATION_ID = '8d697146-f9a2-11ef-89c4-86dcb2923f74';

const headers = {
  AUTHORIZATION: APP_KEY,
  'Content-Type': 'application/json',
};

async function openChat() {
  const response = await fetch(`${API_BASE}/application/${APPLICATION_ID}/chat/open`, {
    method: 'GET',
    headers: {
      AUTHORIZATION: APP_KEY,
    },
  });
  const result = await response.json();
  return result.data;
}

async function sendMessage(chatId, message) {
  const response = await fetch(`${API_BASE}/application/chat_message/${chatId}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      message,
      stream: false,
    }),
  });
  return response.json();
}

async function main() {
  const chatId = await openChat();
  const result = await sendMessage(chatId, '你好');
  console.log('chatId:', chatId);
  console.log('reply:', result.data.content);
}

main();
```

### 4.3 Python 示例

```python
import requests

API_BASE = "https://ai.ihuapeng.cn/api"
APP_KEY = "application-395f59649acf1838af64570ebe4ba89e"
APPLICATION_ID = "8d697146-f9a2-11ef-89c4-86dcb2923f74"

headers = {
    "AUTHORIZATION": APP_KEY,
}

open_resp = requests.get(
    f"{API_BASE}/application/{APPLICATION_ID}/chat/open",
    headers=headers,
    timeout=30,
)
open_resp.raise_for_status()
chat_id = open_resp.json()["data"]

message_resp = requests.post(
    f"{API_BASE}/application/chat_message/{chat_id}",
    headers={
        "AUTHORIZATION": APP_KEY,
        "Content-Type": "application/json",
    },
    json={
        "message": "你好",
        "stream": False,
    },
    timeout=60,
)
message_resp.raise_for_status()
result = message_resp.json()

print("chat_id:", chat_id)
print("reply:", result["data"]["content"])
```

## 5. 错误处理

常见返回格式：

```json
{
  "code": 1002,
  "message": "非法用户！认证信息不正确",
  "data": null
}
```

常见问题：

| 场景 | 原因 | 处理方式 |
| --- | --- | --- |
| `code != 200` | 鉴权失败 | 检查 `AUTHORIZATION` 是否正确，且不要加 `Bearer ` |
| 打开会话失败 | `application_id` 错误 | 使用当前文档给出的应用 ID |
| 回复为空或异常 | 模型或流程配置异常 | 联系平台管理方检查机器人配置 |
| 4xx/5xx HTTP 错误 | 请求格式错误或服务异常 | 检查 JSON、路径参数和请求头 |

建议第三方系统至少处理以下逻辑：

- 先判断 HTTP 状态码是否成功
- 再判断业务返回 `code` 是否为 `200`
- 失败时记录 `message`
- 超时场景建议增加重试与日志

## 6. 网页访问方式

如果第三方只需要直接打开机器人网页，而不需要自行对接 API，可直接访问：

```text
https://ai.ihuapeng.cn/ui/chat/application-395f59649acf1838af64570ebe4ba89e
```

## 7. 说明与建议

- 建议生产环境通过服务端调用该接口，不建议将密钥暴露在浏览器前端源码中
- 若第三方需要多轮对话，请保存并复用 `chat_id`
- 若第三方需要每次新咨询都独立开始，请每次先调用一次 `chat/open`
- 如后续更换机器人，仅需替换 `应用密钥` 和 `应用 ID`
- 官方接口文档页面：`https://ai.ihuapeng.cn/doc/chat/`
