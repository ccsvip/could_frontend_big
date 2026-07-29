---
name: device-chat
description: "Skill for the Device-chat area of could_frontend_big. 53 symbols across 1 files."
---

# Device-chat

53 symbols | 1 files | Cohesion: 85%

## When to Use

- Working with code in `device-chat/`
- Understanding how init, bindEvents, connectDevice work
- Modifying device-chat-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `device-chat/app.js` | init, bindEvents, connectDevice, buildActivationPayload, buildSessionPath (+48) |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `init` | Function | `device-chat/app.js` | 85 |
| `bindEvents` | Function | `device-chat/app.js` | 96 |
| `connectDevice` | Function | `device-chat/app.js` | 121 |
| `buildActivationPayload` | Function | `device-chat/app.js` | 174 |
| `buildSessionPath` | Function | `device-chat/app.js` | 191 |
| `normalizeSessionPayload` | Function | `device-chat/app.js` | 199 |
| `startRecording` | Function | `device-chat/app.js` | 217 |
| `uploadVoice` | Function | `device-chat/app.js` | 292 |
| `startRealtimeAsr` | Function | `device-chat/app.js` | 330 |
| `handleRealtimeAsrMessage` | Function | `device-chat/app.js` | 371 |
| `appendRealtimeTranscript` | Function | `device-chat/app.js` | 401 |
| `updateRealtimeQuestionText` | Function | `device-chat/app.js` | 417 |
| `getRealtimeTranscript` | Function | `device-chat/app.js` | 428 |
| `resetRealtimeTranscript` | Function | `device-chat/app.js` | 432 |
| `flushPendingRealtimeAudio` | Function | `device-chat/app.js` | 457 |
| `handleRealtimeAsrError` | Function | `device-chat/app.js` | 496 |
| `renderDevice` | Function | `device-chat/app.js` | 541 |
| `renderAnswer` | Function | `device-chat/app.js` | 548 |
| `buildAudioSource` | Function | `device-chat/app.js` | 580 |
| `setAudioSource` | Function | `device-chat/app.js` | 594 |

## How to Explore

1. `context({name: "init"})` — see callers and callees
2. `query({search_query: "device-chat"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
