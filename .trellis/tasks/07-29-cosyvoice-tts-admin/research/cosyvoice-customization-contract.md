# CosyVoice customization contract and 502 diagnostic

**Research-only note, 2026-07-29.** No request was sent, no credential was read or disclosed, and this note does not change configuration or source. All API facts below are from Alibaba Model Studio primary documentation.

## Required endpoint and headers

For a Beijing workspace, the exact HTTP endpoint is:

```text
POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization
```

Required headers:

```text
Authorization: Bearer <server-side API Key>
Content-Type: application/json
```

Source: [Voice-clone HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api), [Voice-design HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references).

## Exact CosyVoice request bodies

CosyVoice voice cloning and voice design share the outer `model` and action:

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "create_voice",
    "target_model": "cosyvoice-v3.5-plus"
  }
}
```

`qwen-voice-enrollment`, `qwen-voice-design`, `voice`, and `create` apply to the separate Qwen API variants, not CosyVoice.

### Clone

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "create_voice",
    "target_model": "cosyvoice-v3.5-plus",
    "prefix": "myvoice",
    "url": "https://publicly-reachable.example/reference.wav",
    "language_hints": ["zh"]
  }
}
```

- `url` is required and must be publicly reachable.
- `prefix` is required; ASCII letters/digits only, maximum 10 characters.
- `language_hints` is optional but, when present, is an array. Current documentation says only its first value is processed. `cosyvoice-v3.5-plus` supports it.
- `max_prompt_audio_length` and `enable_preprocess` are optional for `cosyvoice-v3.5-plus`.

Source: [Voice-clone HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api).

### Design

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "create_voice",
    "target_model": "cosyvoice-v3.5-plus",
    "voice_prompt": "沉稳的中年男性，音色低沉浑厚",
    "preview_text": "各位听众朋友，大家好",
    "prefix": "announcer",
    "language_hints": ["zh"]
  },
  "parameters": {
    "sample_rate": 24000,
    "response_format": "wav"
  }
}
```

- `voice_prompt`: required, Chinese or English only, at most 500 characters.
- `preview_text`: required, Chinese or English only, at most 200 characters.
- `prefix`: required, ASCII letters/digits only, maximum 10 characters.
- `language_hints`: optional **array**; valid CosyVoice values are `zh` and `en`, and it must match `preview_text` when supplied.
- `parameters` are optional; CosyVoice accepts sample rates 16000, 24000, or 48000 and formats `pcm`, `wav`, or `mp3`.

Source: [Voice-design HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references).

## Exact CosyVoice response and management fields

A successful CosyVoice clone/design create returns `output.voice_id`; it does **not** return `output.voice` (the latter belongs to Qwen). Design also returns a Base64 `output.preview_audio` object.

```json
{
  "output": {
    "voice_id": "cosyvoice-v3.5-plus-vd-announcer-..."
  },
  "usage": {"count": 1},
  "request_id": "..."
}
```

For CosyVoice read/delete operations, retain the same outer `model: "voice-enrollment"`:

- list: `input.action: "list_voice"`; optional `prefix`, `page_size`, `page_index`
- detail: `input.action: "query_voice"`, `input.voice_id: "..."`
- delete: `input.action: "delete_voice"`, `input.voice_id: "..."`

The API returns a `voice_list` whose ID field is `voice_id`. Voice status is `DEPLOYING`, `OK`, or `UNDEPLOYED`; only `OK` is documented as usable.

Sources: [Voice-clone HTTP API](https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api), [Voice-design HTTP API](https://help.aliyun.com/zh/model-studio/voice-design-api-references).

## Comparison with the repository at inspection time

`backend/apps/ai_models/services/cosyvoice.py` currently has the correct Beijing endpoint shape, outer model, action, target model, and prefix constraint. It differs from the official CosyVoice contract in three material fields:

| Local behavior | Official CosyVoice contract | Impact |
| --- | --- | --- |
| design creates `language_hints: language` (a string) | `language_hints` is `array[string]`, e.g. `["zh"]` | Invalid body shape; credible cause of a rejected or failing design request |
| `_remote_voice_id()` requires `output.voice` | Create response uses `output.voice_id` | A successful upstream create will be reported locally as failure and no local voice will be recorded |
| delete sends `input.voice` | Delete requires `input.voice_id` | Remote deletion cannot use the documented CosyVoice field |

For clone, the current body correctly uses `voice-enrollment`, `create_voice`, and `cosyvoice-v3.5-plus`. However, its local `https://` check is only syntactic; it cannot establish the official required condition that Alibaba can retrieve the supplied URL publicly. A private URL, expired signed URL, blocked origin, unsupported remote response, or failing upstream fetch may cause an upstream error even if the submitted URL begins with `https://`.

### What the observed HTTP 502 establishes

An HTTP 502 establishes only that the application received an upstream error response and mapped it to a bad-gateway-style local result. It does **not** identify a provider cause without the redacted upstream error body/request ID.

**[Inference]** The scalar `language_hints` is the clearest documented body discrepancy for design. For cloning, the documented model/action/target-model combination is already correct; the most important unverified external precondition is public retrievability of the source audio URL. Neither inference justifies retrying a create request automatically, because creation mutates remote state.
