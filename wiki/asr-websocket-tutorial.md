# ASR WebSocket 最小接入教程

本文只说明如何用 WebSocket 接入阿里云 Qwen-ASR Realtime：`.env` 写哪些值、请求怎么发、响应怎么看。

参考文档：

- <https://help.aliyun.com/zh/model-studio/real-time-speech-recognition-user-guide>
- <https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-client-events>
- <https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events>

## 1. `.env` 需要写什么

最小配置：

```env
MULTIMODAL_API_KEY="你的 API Key"
MULTIMODAL_WORKSPACE_ID="你的 Workspace ID"
ASR_MODEL="qwen3-asr-flash-realtime"
ASR_REGION="cn-beijing"
ASR_BASE_URL=""
```

字段说明：

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `MULTIMODAL_API_KEY` | 是 | 阿里云 API Key，用于 WebSocket 鉴权 |
| `MULTIMODAL_WORKSPACE_ID` | 新加坡域名必填 | Workspace ID；新加坡 endpoint 会拼到域名里 |
| `ASR_MODEL` | 是 | ASR 模型名，例如 `qwen3-asr-flash-realtime` |
| `ASR_REGION` | 是 | 区域；北京用 `cn-beijing`，新加坡用 `ap-southeast-1` |
| `ASR_BASE_URL` | 否 | 自定义 WebSocket 地址；非空时覆盖 `ASR_REGION` 拼接逻辑 |

当前 demo 实测：这个 Key 连接北京 endpoint 成功，所以使用：

```env
ASR_REGION="cn-beijing"
```

## 2. WebSocket 地址

北京：

```text
wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=<ASR_MODEL>
```

新加坡：

```text
wss://<MULTIMODAL_WORKSPACE_ID>.ap-southeast-1.maas.aliyuncs.com/api-ws/v1/realtime?model=<ASR_MODEL>
```

如果设置了 `ASR_BASE_URL`，就直接使用：

```text
<ASR_BASE_URL>?model=<ASR_MODEL>
```

## 3. WebSocket 请求头

连接阿里云 ASR WebSocket 时，后端需要带这些 header：

```js
{
  Authorization: `Bearer ${process.env.MULTIMODAL_API_KEY}`,
  'OpenAI-Beta': 'realtime=v1',
  'X-DashScope-WorkSpace': process.env.MULTIMODAL_WORKSPACE_ID,
  'User-Agent': 'your-app-name/1.0'
}
```

注意：浏览器原生 `WebSocket` 不能自定义 `Authorization` header，所以通常要由后端发起到阿里云的 WebSocket 连接。

## 4. 最小请求流程

连接成功后，按顺序发送三个事件：

1. `session.update`
2. `input_audio_buffer.append`
3. `session.finish`

### 4.1 初始化会话：`session.update`

```json
{
  "event_id": "event_001",
  "type": "session.update",
  "session": {
    "input_audio_format": "pcm",
    "sample_rate": 16000,
    "input_audio_transcription": {
      "language": "zh"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.0,
      "silence_duration_ms": 400
    }
  }
}
```

含义：

| 字段 | 说明 |
| --- | --- |
| `input_audio_format` | 音频格式，当前用 `pcm` |
| `sample_rate` | 采样率，当前用 `16000` |
| `language` | 识别语言，中文用 `zh` |
| `turn_detection` | VAD 断句配置；设为 `null` 则切换 Manual 模式 |

### 4.2 追加音频：`input_audio_buffer.append`

音频要转成 Base64 后放进 `audio` 字段。

```json
{
  "event_id": "event_002",
  "type": "input_audio_buffer.append",
  "audio": "<base64 encoded pcm audio>"
}
```

当前最小格式要求：

```text
16kHz / mono / 16-bit PCM / Base64
```

可以连续发送多个 `input_audio_buffer.append`，每个事件是一小段音频。

### 4.3 结束会话：`session.finish`

```json
{
  "event_id": "event_003",
  "type": "session.finish"
}
```

发送后，服务端会返回剩余识别结果，最后返回 `session.finished`。

## 5. 最小响应流程

常见响应事件：

| 事件 | 说明 |
| --- | --- |
| `session.updated` | 会话配置已更新 |
| `input_audio_buffer.speech_started` | VAD 检测到开始说话 |
| `input_audio_buffer.speech_stopped` | VAD 检测到说话结束 |
| `conversation.item.input_audio_transcription.text` | 实时识别文本 |
| `conversation.item.input_audio_transcription.completed` | 最终识别文本 |
| `session.finished` | 会话结束 |

最关心的是这两个：

### 5.1 实时文本

```json
{
  "type": "conversation.item.input_audio_transcription.text",
  "text": "实时识别中的文字"
}
```

### 5.2 最终文本

```json
{
  "type": "conversation.item.input_audio_transcription.completed",
  "text": "最终识别结果"
}
```

字段名可能随模型或版本有差异。实际处理时可以兼容：

```js
const text = event.text || event.delta || event.transcript || event.content || '';
```

## 6. 最小代码骨架

```js
import WebSocket from 'ws';

const model = process.env.ASR_MODEL;
const apiKey = process.env.MULTIMODAL_API_KEY;
const workspaceId = process.env.MULTIMODAL_WORKSPACE_ID;

const url = `wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=${encodeURIComponent(model)}`;

const ws = new WebSocket(url, {
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'OpenAI-Beta': 'realtime=v1',
    'X-DashScope-WorkSpace': workspaceId
  }
});

ws.on('open', () => {
  ws.send(JSON.stringify({
    event_id: 'event_001',
    type: 'session.update',
    session: {
      input_audio_format: 'pcm',
      sample_rate: 16000,
      input_audio_transcription: {
        language: 'zh'
      },
      turn_detection: {
        type: 'server_vad',
        threshold: 0.0,
        silence_duration_ms: 400
      }
    }
  }));

  ws.send(JSON.stringify({
    event_id: 'event_002',
    type: 'input_audio_buffer.append',
    audio: '<base64 encoded pcm audio>'
  }));

  ws.send(JSON.stringify({
    event_id: 'event_003',
    type: 'session.finish'
  }));
});

ws.on('message', (data) => {
  const event = JSON.parse(data.toString());

  if (event.type === 'conversation.item.input_audio_transcription.text') {
    console.log('实时文本:', event.text || event.delta);
  }

  if (event.type === 'conversation.item.input_audio_transcription.completed') {
    console.log('最终文本:', event.text || event.transcript || event.content);
  }

  if (event.type === 'session.finished') {
    ws.close();
  }
});
```

## 7. 401 排查

如果 WebSocket 握手返回 `401`，优先检查：

1. `MULTIMODAL_API_KEY` 是否正确。
2. `Authorization` 是否是 `Bearer <API Key>`。
3. endpoint 区域是否和 API Key 匹配。
4. `MULTIMODAL_WORKSPACE_ID` 是否正确。

本 demo 中，同一个 Key：

- 北京 `wss://dashscope.aliyuncs.com/...` 握手成功。
- 新加坡 `wss://<WorkspaceId>.ap-southeast-1.maas.aliyuncs.com/...` 返回 `401`。

所以当前最小接入建议先使用：

```env
ASR_REGION="cn-beijing"
```
