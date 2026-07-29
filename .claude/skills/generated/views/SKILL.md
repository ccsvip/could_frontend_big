---
name: views
description: "Skill for the Views area of could_frontend_big. 30 symbols across 8 files."
---

# Views

30 symbols | 8 files | Cohesion: 81%

## When to Use

- Working with code in `web/`
- Understanding how buildAsrRealtimeWebSocketUrl, buildTtsRealtimeWebSocketUrl, buildRealtimeWebSocketUrl work
- Modifying views-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/src/views/tts-realtime-playback.ts` | playRealtimeTts, closeEncodedAudio, closeAudio, finish, fail (+8) |
| `web/src/api/realtime.ts` | buildRealtimeWebSocketUrl, createRealtimeCommandId, encodeRealtimeCommand, buildAsrSessionStartCommand, buildAsrSessionFinishCommand (+3) |
| `web/src/views/application-management/use-agent-audio.ts` | stopRecording, setupAudioStreaming, startRecording |
| `web/src/views/application-management/audio-utils.ts` | downsampleBuffer, encodePCM16 |
| `web/src/api/modules/asr.ts` | buildAsrRealtimeWebSocketUrl |
| `web/src/api/modules/tts.ts` | buildTtsRealtimeWebSocketUrl |
| `web/src/views/asr-management/index.tsx` | stopTest |
| `web/src/views/media-devices.ts` | requestMicrophoneStream |

## Entry Points

Start here when exploring this area:

- **`buildAsrRealtimeWebSocketUrl`** (Function) — `web/src/api/modules/asr.ts:140`
- **`buildTtsRealtimeWebSocketUrl`** (Function) — `web/src/api/modules/tts.ts:149`
- **`buildRealtimeWebSocketUrl`** (Function) — `web/src/api/realtime.ts:20`
- **`createRealtimeCommandId`** (Function) — `web/src/api/realtime.ts:30`
- **`encodeRealtimeCommand`** (Function) — `web/src/api/realtime.ts:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `buildAsrRealtimeWebSocketUrl` | Function | `web/src/api/modules/asr.ts` | 140 |
| `buildTtsRealtimeWebSocketUrl` | Function | `web/src/api/modules/tts.ts` | 149 |
| `buildRealtimeWebSocketUrl` | Function | `web/src/api/realtime.ts` | 20 |
| `createRealtimeCommandId` | Function | `web/src/api/realtime.ts` | 30 |
| `encodeRealtimeCommand` | Function | `web/src/api/realtime.ts` | 33 |
| `buildAsrSessionStartCommand` | Function | `web/src/api/realtime.ts` | 35 |
| `buildAsrSessionFinishCommand` | Function | `web/src/api/realtime.ts` | 50 |
| `buildAsrSessionCancelCommand` | Function | `web/src/api/realtime.ts` | 55 |
| `buildTtsSessionStartCommand` | Function | `web/src/api/realtime.ts` | 65 |
| `buildTtsSessionCancelCommand` | Function | `web/src/api/realtime.ts` | 88 |
| `downsampleBuffer` | Function | `web/src/views/application-management/audio-utils.ts` | 47 |
| `encodePCM16` | Function | `web/src/views/application-management/audio-utils.ts` | 77 |
| `stopRecording` | Function | `web/src/views/application-management/use-agent-audio.ts` | 84 |
| `setupAudioStreaming` | Function | `web/src/views/application-management/use-agent-audio.ts` | 117 |
| `startRecording` | Function | `web/src/views/application-management/use-agent-audio.ts` | 167 |
| `stopTest` | Function | `web/src/views/asr-management/index.tsx` | 610 |
| `requestMicrophoneStream` | Function | `web/src/views/media-devices.ts` | 2 |
| `playRealtimeTts` | Function | `web/src/views/tts-realtime-playback.ts` | 35 |
| `closeEncodedAudio` | Function | `web/src/views/tts-realtime-playback.ts` | 59 |
| `closeAudio` | Function | `web/src/views/tts-realtime-playback.ts` | 72 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ApplicationManagementPage → EncodeRealtimeCommand` | cross_community | 4 |
| `ApplicationManagementPage → BuildAsrSessionCancelCommand` | cross_community | 4 |
| `ApplicationManagementPage → CreateRealtimeCommandId` | cross_community | 4 |
| `ApplicationManagementPage → BuildAsrSessionFinishCommand` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Application-management | 1 calls |
| Asr-management | 1 calls |

## How to Explore

1. `context({name: "buildAsrRealtimeWebSocketUrl"})` — see callers and callees
2. `query({search_query: "views"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
