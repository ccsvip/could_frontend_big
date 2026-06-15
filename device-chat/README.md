# 数字人语音问答测试页

根目录 `device-chat/` 是独立原生 HTML/CSS/JS demo，用设备码调用设备侧语音问答接口，不依赖后台管理登录态，也不暴露 ASR/TTS/LLM 密钥。

## 打开方式

直接打开：

```text
device-chat/index.html?deviceCode=DEVICE_001&apiBaseUrl=http://localhost:8880/api/v1
```

也可以不传 `deviceCode`，页面会展示设备码输入框。`apiBaseUrl` 不传时，如果通过 `file://` 打开，默认使用 `http://localhost:8880/api/v1`；如果部署在 Web 服务下，默认使用同源 `/api/v1`。

## 页面能力

- 从 URL `deviceCode` 自动连接设备，或手动输入设备码连接。
- 使用 `navigator.mediaDevices.getUserMedia` 与 `MediaRecorder` 录音。
- 录音结束后用 `multipart/form-data` 上传音频，并携带 `X-Device-Code`。
- 展示 ASR 问题文本、LLM 回答文本、`traceId`、`sessionId`。
- 支持 `audioUrl` 和 `audioBase64` 两种语音回复，自动播放失败时可手动播放。
- 支持请求超时、网络/CORS、设备码无效、ASR/LLM/TTS 失败等提示。

## 默认接口

页面默认按当前仓库已有运行时接口校验设备：

```http
GET /api/v1/device-runtime/config/?deviceCode=DEVICE_001
X-Device-Code: DEVICE_001
```

语音问答默认使用 PRD 约定接口：

```http
POST /api/v1/device/voice-chat
X-Device-Code: DEVICE_001
Content-Type: multipart/form-data
```

当前仓库已有设备运行时校验接口，但没有发现已落地的批量 `voice-chat` 后端接口；如果录音上传返回 404，需要后端补齐上述接口或通过 `voiceChatPath` 指向实际接口。

如果后端实际使用 PRD 中的设备会话接口，可以通过 URL 覆盖：

```text
device-chat/index.html?deviceCode=DEVICE_001&sessionPath=/device/session&voiceChatPath=/device/voice-chat
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

页面请求不携带 cookie，使用 `credentials: "omit"`，自定义请求头只有 `X-Device-Code`。后端 CORS 需要允许页面来源，并允许 `x-device-code` 请求头。当前仓库 `backend/config/settings/base.py` 已包含：

```py
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = (*default_headers, 'x-device-code')
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
优先同源代理部署；开发环境确认 `apiBaseUrl` 是浏览器可访问地址，并且后端允许页面 Origin 与 `x-device-code`。

**只有文本没有语音**
后端可以返回 `audioUrl` 或 `audioBase64`。如果 TTS 失败但 LLM 成功，页面会保留文本回答并提示语音合成失败。

**自动播放失败**
浏览器可能阻止非用户手势触发的音频播放，点击“播放语音回复”即可。
