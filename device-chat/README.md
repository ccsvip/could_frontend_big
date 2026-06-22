# 数字人语音问答测试页

根目录 `device-chat/` 是独立原生 HTML/CSS/JS demo，用设备码调用设备侧语音问答接口，不依赖后台管理登录态，也不暴露 ASR/TTS/LLM 密钥。

## 打开方式

直接打开：

```text
device-chat/index.html?deviceCode=DEVICE_001&apiBaseUrl=http://localhost:8880/api/v1
```

也可以不传 `deviceCode`，页面会展示设备码输入框。`apiBaseUrl` 不传时，如果通过 `file://` 打开，默认使用 `http://localhost:8880/api/v1`；如果部署在 Web 服务下，默认使用同源 `/api/v1`。

## 运行时接口控制台

如果需要按 Swagger 风格查看设备码运行时接口、请求头/体和原始响应，可以打开独立控制台：

```text
device-chat/runtime-api-console.html?deviceCode=DEVICE_001&apiBaseUrl=http://localhost:8880/api/v1
```

该页面不需要登录，不携带后台 JWT，只通过 `X-Device-Code`、`X-Request-ID`、`X-Trace-ID` 调用设备侧公开接口。左侧菜单会分别展示应用、AI 大模型/TTS 管理音色、资源管理背景图片、资源管理滚动文本、资源管理模型、资源管理视频、ASR、LLM、TTS；资源类数据通过 `POST /api/v1/device-runtime/resources/` 按 `resourceType` 单独获取。

设备码位置约定：

- 普通 HTTP 接口统一把设备码放在 `X-Device-Code` 请求头，请求体只放业务参数。
- WebSocket 浏览器握手不能自定义 `X-Device-Code` 请求头，因此统一实时通信命令在 payload 里携带 `deviceCode`。
- 资源切片接口除 `resourceType=application` 外，只返回当前资源列表 `items`；安卓端只需要消费 `items` 里的字段。

ASR WebSocket 能力测试会申请浏览器麦克风权限，收到 `asr.ready` 后把麦克风输入重采样为 16k mono `pcm_s16le`，并通过 `/ws/realtime/` 发送二进制分片；点击停止时发送 `asr.session.finish`。安卓端对接同样遵循 `asr.session.start` → 16k PCM bytes → `asr.session.finish` 的顺序。

ASR 替换词纠错由后端按设备所属公司自动应用。`asr.transcript` 事件里：

- `originalText` 是上游原始识别文本。
- `text` 是替换词纠错后的文本，安卓端应使用这个字段进入后续 LLM/TTS。
- `replacementApplied` 表示本次文本是否命中替换词。

### TTS HTTP 音频格式说明

`POST /api/v1/ai-models/tts/runtime/` 默认面向安卓设备返回 `audio/pcm` raw PCM，并通过响应头说明播放参数：

```http
Content-Type: audio/pcm
X-Audio-Source-Format: pcm_s16le
X-Audio-Sample-Rate: 16000
X-Audio-Channels: 1
X-TTS-Voice: Cherry
```

运行时接口控制台里的“TTS HTTP”和音色“测试”按钮是浏览器测试场景，会在请求体里额外传 `wrapWav: true`，让后端把同一段 PCM 包装成 `audio/wav`，方便 `<audio>` 直接播放。安卓端正常接入不需要传 `wrapWav`；如果安卓同学临时用浏览器或调试工具验证播放，也可以传：

```json
{
  "text": "你好，我是数字人设备。",
  "voiceId": 1,
  "wrapWav": true
}
```

## 页面能力

- 从 URL `deviceCode` 自动连接设备，或手动输入设备码连接。
- 使用 `navigator.mediaDevices.getUserMedia` 与 Web Audio 录音，上传 16k PCM。
- 录音过程中连接统一实时通信入口，并通过设备码启动实时语音识别会话，边说边展示识别文本。
- 录音结束后用 `multipart/form-data` 上传音频，并携带 `X-Device-Code`、`X-Request-ID`、`X-Trace-ID`。
- 展示 ASR 问题文本、LLM 回答文本、`traceId`、`sessionId`。
- 支持 `audioUrl` 和 `audioBase64` 两种语音回复，自动播放失败时可手动播放。
- 支持请求超时、网络/CORS、设备码无效、ASR/LLM/TTS 失败等提示。

## 默认接口

页面默认先按当前仓库已有设备激活接口上报设备：

```http
POST /api/v1/device-auth/activate/
X-Device-Code: DEVICE_001
X-Request-ID: req-...
X-Trace-ID: trace-...
Content-Type: application/json

{
  "softwareVersion": "device-chat-html-demo",
  "systemVersion": "<browser user agent>",
  "mainboardInfo": "browser",
  "deviceInfo": {
    "source": "device-chat"
  }
}
```

如果设备不存在，后端会创建待绑定设备，超级管理员可在“设备请求”页面看到该设备。页面会停在“设备待授权”状态，不允许录音。

当激活接口返回 `bindingStatus: "bound"` 后，页面再拉取运行时配置：

```http
GET /api/v1/device-runtime/config/
X-Device-Code: DEVICE_001
X-Request-ID: req-...
X-Trace-ID: trace-...
```

录音开始后，页面会先打开统一实时通信入口：

```http
GET /ws/realtime/
```

连接建立后，页面发送 `asr.session.start` 命令，并在命令载荷里携带 `deviceCode`、`requestId`、`traceId` 完成设备身份解析与链路排查。收到 `asr.ready` 后页面持续发送 16k PCM 二进制分片，并根据 `asr.transcript` 事件实时刷新“我说的问题”；停止录音时发送 `asr.session.finish`。

语音问答默认使用 PRD 约定接口：

```http
POST /api/v1/device/voice-chat
X-Device-Code: DEVICE_001
X-Request-ID: req-...
X-Trace-ID: trace-...
Content-Type: multipart/form-data

audio=<16k pcm file>
deviceCode=DEVICE_001
format=pcm
sampleRate=16000
```

该接口会按 `deviceCode` 校验设备绑定状态，再执行 ASR → LLM → TTS。未绑定设备会返回 403，页面会提示先完成授权绑定。
实时 ASR 只负责录音过程中的即时文本展示；停止录音后仍会提交完整音频到该接口，用后端返回的最终 ASR/LLM/TTS 结果覆盖展示内容。

如果后端实际使用 PRD 中的设备会话接口，可以通过 URL 覆盖：

```text
device-chat/index.html?deviceCode=DEVICE_001&activatePath=/device-auth/activate/&sessionPath=/device/session&voiceChatPath=/device/voice-chat
```

## 语音问答响应格式

页面兼容包裹格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sessionId": "session_123456",
    "questionText": "今天有哪些注意事项？",
    "answerText": "今天需要注意设备电量、网络连接状态，以及保持麦克风正常工作。",
    "audioUrl": "https://example.com/media/tts/session_123456.mp3",
    "audioBase64": null,
    "traceId": "trace_abc123"
  }
}
```

也兼容直接返回 `data` 内字段的格式。`audioUrl` 如果返回容器内地址 `http://backend:8000/media/...`，页面会按当前 `apiBaseUrl` 的 origin 改写为浏览器可访问地址。

## 跨域处理

开发环境可直接把 `apiBaseUrl` 指向后端宿主端口：

```text
http://localhost:8880/api/v1
```

页面请求不携带 cookie，使用 `credentials: "omit"`，自定义请求头包括 `X-Device-Code`、`X-Request-ID`、`X-Trace-ID`。后端 CORS 需要允许页面来源，允许这些请求头，并暴露响应里的 trace 头。当前仓库 `backend/config/settings/base.py` 已包含：

```py
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = (*default_headers, 'x-device-code', 'x-request-id', 'x-trace-id')
CORS_EXPOSE_HEADERS = ('x-request-id', 'x-trace-id', ...)
```

生产或演示部署推荐同源代理，避免浏览器跨域限制：

```nginx
location /device-chat/ {
    root /var/www/solin;
}

location /api/v1/ {
    proxy_pass http://backend:8000/api/v1/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /media/ {
    proxy_pass http://backend:8000/media/;
}
```

同源部署后访问：

```text
https://example.com/device-chat/index.html?deviceCode=DEVICE_001
```

## 常见问题

**浏览器无法录音**
需要 HTTPS 或 `localhost` 环境，并允许麦克风权限。部分 iOS Safari 版本会限制录音和自动播放。

**设备码无效**
确认后台已登记并启用该设备码，设备已绑定公司和可用应用。

**请求跨域失败**
优先同源代理部署；开发环境确认 `apiBaseUrl` 是浏览器可访问地址，并且后端允许页面 Origin 与 `x-device-code`、`x-request-id`、`x-trace-id`。

**只有文本没有语音**
后端可以返回 `audioUrl` 或 `audioBase64`。如果 TTS 失败但 LLM 成功，页面会保留文本回答并提示语音合成失败。

**自动播放失败**
浏览器可能阻止非用户手势触发的音频播放，点击“播放语音回复”即可。
