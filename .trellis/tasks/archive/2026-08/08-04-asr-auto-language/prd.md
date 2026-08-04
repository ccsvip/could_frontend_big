# ASR 自动识别语言

## Goal

让所有实时 ASR 会话按输入音频自动识别源语言，而非将识别语言固定为中文。

## Background

- 当前三个 `session.update` 构造点都发送 `input_audio_transcription.language: 'zh'`：
  - `backend/apps/ai_models/services/asr.py:181-194`：设备 PCM 转写。
  - `backend/apps/ai_models/services/asr.py:228-273`：ASR 连通性测试。
  - `backend/apps/ai_models/realtime_asr.py:208-221`：统一实时 WebSocket 的普通 ASR 与智能体 ASR 上游会话。
- 阿里云 Qwen-ASR Realtime 文档将 `session.input_audio_transcription.language` 标为可选字段；Qwen-ASR 文档规定语种不确定或混合时不要指定该参数。自动识别应省略该字段，而非传递未文档化的 `auto` 值。

## Requirements

1. 所有 ASR `session.update` 事件保留 `input_audio_transcription` 对象，但不得包含 `language` 键。
2. 设备 PCM 转写、统一实时 WebSocket 转写和 ASR 连通性测试必须采用相同的自动语言识别行为。
3. 不新增语言选择 UI、API 字段、数据库迁移或每租户语言覆盖配置。

## Acceptance Criteria

- [ ] 设备 PCM 转写发出的 `session.update` 中，`input_audio_transcription` 为 `{}`。
- [ ] 普通与智能体实时 ASR 共用的上游 `session.update` 中，`input_audio_transcription` 为 `{}`。
- [ ] ASR 连通性测试请求中，`input_audio_transcription` 为 `{}`。
- [ ] 回归测试断言以上请求载荷，并通过 `docker compose exec backend python manage.py test apps.ai_models.tests.test_asr_api apps.ai_models.tests.test_asr_realtime --keepdb`。

## Out of Scope

- 将识别文本翻译为中文或其他目标语言。
- 恢复固定语种或新增可配置语种。
- 修改 TTS 的独立 `language_type` 配置。

## Decisions and Risks

- 决定：省略 `language`，保留空的 `input_audio_transcription` 对象；前者启用自动语言识别，后者保留 ASR 转写配置边界。
- 影响：GitNexus 对设备转写构造器评为 LOW；唯一直接调用者是 `transcribe_pcm_audio`。实时构造器的图谱索引未包含 `config/realtime.py` 的两个源码调用点，已通过源码核对覆盖。
- 外部依据：[Qwen-ASR Realtime WebSocket 客户端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-client-events)；[Qwen-ASR API 参考](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)。
