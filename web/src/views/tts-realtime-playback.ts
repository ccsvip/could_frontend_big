import { type TtsRealtimeMessage, type TtsTestPayload } from '../api/modules/tts';
import type { TtsSessionConfig } from '../api/modules/tts';
import {
  buildRealtimeWebSocketUrl,
  buildTtsSessionCancelCommand,
  buildTtsSessionStartCommand,
  createRealtimeCommandId,
  encodeRealtimeCommand,
} from '../api/realtime';
import type { RealtimeError } from '../api/realtime';

type PlayRealtimeTtsOptions = TtsTestPayload & {
  token: string;
  tenantId?: number | null;
  providerCode?: string;
  sessionConfig?: TtsSessionConfig;
  filterPunctuation?: string;
  filterEmoji?: boolean;
  signal?: AbortSignal;
  excludePatterns?: string[];
  jitterBufferMs?: number;
  interruptSignal?: AbortSignal;
};

type PlayRealtimeTtsResult = {
  blob: Blob;
  sampleRate: number;
};

type WebAudioWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

type TtsRealtimeSocketMessage = TtsRealtimeMessage & {
  error?: RealtimeError;
};
type TtsStreamToken = {
  text: string;
  boundary: boolean;
};

export type TtsTextFilterRules = {
  filterPunctuation?: string;
  filterEmoji?: boolean;
  excludePatterns?: string[];
};

const TTS_SEGMENT_BOUNDARIES: Record<string, true> = {
  '。': true,
  '！': true,
  '!': true,
  '？': true,
  '?': true,
  '；': true,
  ';': true,
  '，': true,
  ',': true,
  '：': true,
  ':': true,
  '、': true,
  '\r': true,
  '\n': true,
};
const TTS_EMOJI_PATTERN = /[\u{1F000}-\u{1FAFF}\u2600-\u27BF\uFE0F]/u;

class LiteralExclusionStage {
  private pending: TtsStreamToken[] = [];
  private readonly patternLength: number;

  constructor(private readonly pattern: string) {
    this.patternLength = Array.from(pattern).length;
  }

  feed(tokens: TtsStreamToken[]) {
    const emitted: TtsStreamToken[] = [];
    tokens.forEach((token) => {
      this.pending.push(token);
      emitted.push(...this.drainSafePrefix());
    });
    return emitted;
  }

  finish() {
    const pending = this.pending;
    this.pending = [];
    return pending;
  }

  private drainSafePrefix() {
    const characterPositions = this.pending
      .map((token, index) => token.text ? index : -1)
      .filter((index) => index >= 0);
    const visibleCharacters = characterPositions.map((index) => this.pending[index].text);
    const visible = visibleCharacters.join('');
    if (visible.endsWith(this.pattern)) {
      const boundary = this.pending.some((token) => token.boundary);
      this.pending = [];
      return boundary ? [{ text: '', boundary: true }] : [];
    }

    const maxPrefixLength = Math.min(visibleCharacters.length, this.patternLength - 1);
    let heldCharacters = 0;
    for (let length = maxPrefixLength; length > 0; length -= 1) {
      if (this.pattern.startsWith(visibleCharacters.slice(-length).join(''))) {
        heldCharacters = length;
        break;
      }
    }
    if (heldCharacters > 0) {
      const heldFrom = characterPositions[characterPositions.length - heldCharacters];
      const emitted = this.pending.slice(0, heldFrom);
      this.pending = this.pending.slice(heldFrom);
      return emitted;
    }

    const emitted = this.pending;
    this.pending = [];
    return emitted;
  }
}

export class TtsStreamingTextProcessor {
  private readonly exclusionStages: LiteralExclusionStage[];
  private readonly filteredCharacters: Set<string>;
  private readonly filterEmoji: boolean;
  private segmentCharacters: string[] = [];
  private finished = false;

  constructor(rules: TtsTextFilterRules = {}) {
    const patterns = Array.from(new Set(rules.excludePatterns ?? [])).filter(Boolean);
    this.exclusionStages = patterns.map((pattern) => new LiteralExclusionStage(pattern));
    this.filteredCharacters = new Set(Array.from(rules.filterPunctuation ?? ''));
    this.filterEmoji = Boolean(rules.filterEmoji);
  }

  feed(text: string) {
    if (this.finished) {
      throw new Error('TTS text processor is already finished.');
    }
    const tokens = Array.from(text).map((character) => ({
      text: character,
      boundary: character in TTS_SEGMENT_BOUNDARIES,
    }));
    return this.consume(this.applyRules(tokens));
  }

  finish() {
    if (this.finished) {
      return [];
    }
    this.finished = true;
    const tokens: TtsStreamToken[] = [];
    this.exclusionStages.forEach((stage, index) => {
      let stageOutput = stage.finish();
      this.exclusionStages.slice(index + 1).forEach((downstream) => {
        stageOutput = downstream.feed(stageOutput);
      });
      tokens.push(...stageOutput);
    });
    const segments = this.consume(this.applyCharacterRules(tokens));
    if (this.segmentCharacters.length > 0) {
      segments.push(this.segmentCharacters.join(''));
      this.segmentCharacters = [];
    }
    return segments;
  }

  private applyRules(tokens: TtsStreamToken[]) {
    this.exclusionStages.forEach((stage) => {
      tokens = stage.feed(tokens);
    });
    return this.applyCharacterRules(tokens);
  }

  private applyCharacterRules(tokens: TtsStreamToken[]) {
    const filtered: TtsStreamToken[] = [];
    tokens.forEach((token) => {
      const removeCharacter = Boolean(token.text) && (
        (this.filterEmoji && TTS_EMOJI_PATTERN.test(token.text))
        || this.filteredCharacters.has(token.text)
      );
      if (removeCharacter) {
        if (token.boundary) {
          filtered.push({ text: '', boundary: true });
        }
        return;
      }
      filtered.push(token);
    });
    return filtered;
  }

  private consume(tokens: TtsStreamToken[]) {
    const segments: string[] = [];
    tokens.forEach((token) => {
      if (token.text) {
        this.segmentCharacters.push(token.text);
      }
      if (token.boundary && this.segmentCharacters.length > 0) {
        segments.push(this.segmentCharacters.join(''));
        this.segmentCharacters = [];
      }
    });
    return segments;
  }
}

export const playRealtimeTts = async (options: PlayRealtimeTtsOptions): Promise<PlayRealtimeTtsResult> => {
  const text = options.text || '';
  if (!text) {
    throw new Error('TTS 测试文本不能为空');
  }

  const AudioContextClass = window.AudioContext || (window as WebAudioWindow).webkitAudioContext;
  if (!AudioContextClass) {
    throw new Error('当前浏览器不支持音频播放');
  }

  const audioContext = new AudioContextClass();
  const gain = audioContext.createGain();
  gain.connect(audioContext.destination);
  const pcmPlayback = new PcmJitterBuffer(
    audioContext,
    gain,
    Math.max(0, options.jitterBufferMs ?? DEFAULT_PCM_JITTER_BUFFER_MS),
  );

  let sampleRate = 24000;
  let responseFormat: TtsRealtimeMessage['responseFormat'] = options.sessionConfig?.response_format || 'pcm';
  const chunks: ArrayBuffer[] = [];
  let audioClosed = false;
  let encodedAudio: HTMLAudioElement | null = null;
  let encodedAudioUrl: string | null = null;

  const closeEncodedAudio = () => {
    if (encodedAudio) {
      encodedAudio.pause();
      encodedAudio.src = '';
      encodedAudio.load();
      encodedAudio = null;
    }
    if (encodedAudioUrl) {
      URL.revokeObjectURL(encodedAudioUrl);
      encodedAudioUrl = null;
    }
  };

  const closeAudio = () => {
    closeEncodedAudio();
    if (audioClosed) {
      return;
    }
    audioClosed = true;
    pcmPlayback.stop();
    try {
      gain.gain.cancelScheduledValues(audioContext.currentTime);
      gain.gain.setValueAtTime(0, audioContext.currentTime);
    } catch {
      // Audio context may already be closing.
    }
    try {
      gain.disconnect();
    } catch {
      // Gain may already be disconnected.
    }
    void audioContext.close();
  };

  let resolve!: (result: PlayRealtimeTtsResult) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<PlayRealtimeTtsResult>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
    let settled = false;
    let completing = false;
    let interrupted = false;
    let cancelled = false;
    const socket = new WebSocket(buildRealtimeWebSocketUrl());
    socket.binaryType = 'arraybuffer';

    const removeAbortListeners = () => {
      options.signal?.removeEventListener('abort', abort);
      options.interruptSignal?.removeEventListener('abort', interruptPlayback);
    };

    const fail = (error: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      removeAbortListeners();
      closeAudio();
      reject(error);
    };

    const finish = async () => {
      if (settled || completing || cancelled) {
        return;
      }
      completing = true;
      if (chunks.length === 0) {
        fail(new Error('TTS 未返回有效音频'));
        return;
      }
      const blob = buildTtsAudioBlob(chunks, sampleRate, responseFormat);
      if (responseFormat === 'pcm') {
        try {
          await pcmPlayback.finish();
        } catch (error) {
          fail(error instanceof Error ? error : new Error('TTS PCM 音频格式无效'));
          return;
        }
        if (cancelled || settled) {
          return;
        }
        settled = true;
        removeAbortListeners();
        closeAudio();
        resolve({ blob, sampleRate });
        return;
      }

      const objectUrl = URL.createObjectURL(blob);
      const audio = new Audio(objectUrl);
      encodedAudioUrl = objectUrl;
      encodedAudio = audio;
      audio.onended = () => {
        if (settled) {
          return;
        }
        settled = true;
        removeAbortListeners();
        closeAudio();
        resolve({ blob, sampleRate });
      };
      audio.onerror = () => fail(new Error('当前浏览器无法播放该 TTS 音频格式'));
      void audio.play().catch(() => fail(new Error('当前浏览器无法播放该 TTS 音频格式')));
    };

    function abort() {
      if (settled) {
        return;
      }
      cancelled = true;
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(encodeRealtimeCommand(buildTtsSessionCancelCommand(createRealtimeCommandId('tts-cancel'))));
      }
      socket.close();
      fail(new DOMException('TTS playback was cancelled', 'AbortError'));
    }

    function interruptPlayback() {
      if (interrupted || settled) {
        return;
      }
      interrupted = true;
      cancelled = true;
      socket.close(1000, 'tts playback interrupted');
      fail(new DOMException('TTS playback was interrupted', 'AbortError'));
    }

    if (options.signal?.aborted) {
      abort();
      return promise;
    }
    options.signal?.addEventListener('abort', abort, { once: true });
    if (options.interruptSignal?.aborted) {
      interruptPlayback();
      return promise;
    }
    options.interruptSignal?.addEventListener('abort', interruptPlayback, { once: true });

    socket.onopen = () => {
      if (cancelled) {
        socket.close();
        return;
      }
      if (audioContext.state === 'suspended') {
        void audioContext.resume();
      }
      socket.send(encodeRealtimeCommand(buildTtsSessionStartCommand(createRealtimeCommandId('tts-session'), {
        token: options.token,
        tenantId: options.tenantId,
        text,
        voiceId: options.voiceId ?? null,
        providerCode: options.providerCode,
        sessionConfig: options.sessionConfig,
        filterPunctuation: options.filterPunctuation,
        filterEmoji: options.filterEmoji,
        excludePatterns: options.excludePatterns,
      })));
    };

    socket.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (cancelled || audioClosed) {
        return;
      }
      if (typeof event.data !== 'string') {
        const pcm = event.data.slice(0);
        chunks.push(pcm);
        if (responseFormat === 'pcm') {
          try {
            pcmPlayback.push(pcm, sampleRate);
          } catch (error) {
            fail(error instanceof Error ? error : new Error('TTS PCM 音频格式无效'));
          }
        }
        return;
      }

      let payload: TtsRealtimeSocketMessage;
      try {
        payload = JSON.parse(event.data) as TtsRealtimeSocketMessage;
      } catch {
        return;
      }
      if (payload.type === 'tts.ready' && payload.sampleRate) {
        sampleRate = payload.sampleRate;
        responseFormat = payload.responseFormat || responseFormat;
        return;
      }
      if (payload.type === 'tts.done') {
        socket.close();
        if (interrupted) {
          fail(new DOMException('TTS playback was interrupted', 'AbortError'));
          return;
        }
        void finish();
        return;
      }
      if (payload.type === 'tts.cancelled') {
        socket.close();
        fail(new DOMException('TTS playback was cancelled', 'AbortError'));
        return;
      }
      if (payload.type === 'tts.error') {
        socket.close();
        fail(new Error(payload.error?.message || '语音合成失败'));
      }
    };

    socket.onerror = () => fail(new Error('TTS WebSocket 连接异常'));

    socket.onclose = () => {
      removeAbortListeners();
      if (interrupted && !settled) {
        fail(new DOMException('TTS playback was interrupted', 'AbortError'));
        return;
      }
      if (!settled && !completing && chunks.length > 0) {
        void finish();
      } else if (!settled && !completing) {
        fail(new Error('TTS WebSocket 已关闭'));
      }
    };
  return promise;
};

const DEFAULT_PCM_JITTER_BUFFER_MS = 120;

type PendingPcmBuffer = {
  samples: Float32Array<ArrayBuffer>;
  sampleRate: number;
};

class PcmJitterBuffer {
  private readonly pending: PendingPcmBuffer[] = [];
  private readonly sources = new Set<AudioBufferSourceNode>();
  private pendingDuration = 0;
  private nextStartTime = 0;
  private trailingByte: number | null = null;
  private started = false;
  private finished = false;
  private finishResolver: (() => void) | null = null;

  constructor(
    private readonly audioContext: AudioContext,
    private readonly output: AudioNode,
    private readonly startupBufferMs: number,
  ) {}

  push(pcm: ArrayBuffer, sampleRate: number) {
    if (this.finished) {
      throw new Error('TTS PCM 播放队列已经结束');
    }
    const alignedPcm = this.alignPcmFrames(pcm);
    if (alignedPcm.byteLength === 0) {
      return;
    }
    const samples = pcm16ToFloat32(alignedPcm);
    this.pending.push({ samples, sampleRate });
    this.pendingDuration += samples.length / sampleRate;
    if (!this.started && this.pendingDuration * 1000 >= this.startupBufferMs) {
      this.started = true;
    }
    if (this.started) {
      this.schedulePending();
    }
  }

  finish(): Promise<void> {
    if (this.trailingByte !== null) {
      return Promise.reject(new Error('TTS 返回了不完整的 PCM 采样帧'));
    }
    this.finished = true;
    this.started = true;
    this.schedulePending();
    if (this.sources.size === 0) {
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      this.finishResolver = resolve;
    });
  }

  stop() {
    this.pending.length = 0;
    this.pendingDuration = 0;
    this.trailingByte = null;
    this.sources.forEach((source) => {
      source.onended = null;
      try {
        source.stop(this.audioContext.currentTime);
      } catch {
        // Source may already have ended.
      }
      try {
        source.disconnect();
      } catch {
        // Source may already be disconnected.
      }
    });
    this.sources.clear();
    this.finishResolver?.();
    this.finishResolver = null;
  }

  private alignPcmFrames(pcm: ArrayBuffer) {
    const bytes = new Uint8Array(pcm);
    if (this.trailingByte === null && bytes.byteLength % 2 === 0) {
      return pcm;
    }

    const combined = new Uint8Array(bytes.byteLength + (this.trailingByte === null ? 0 : 1));
    let offset = 0;
    if (this.trailingByte !== null) {
      combined[0] = this.trailingByte;
      this.trailingByte = null;
      offset = 1;
    }
    combined.set(bytes, offset);
    const alignedLength = combined.byteLength - (combined.byteLength % 2);
    if (alignedLength < combined.byteLength) {
      this.trailingByte = combined[combined.byteLength - 1];
    }
    return combined.buffer.slice(0, alignedLength);
  }

  private schedulePending() {
    if (this.pending.length === 0) {
      return;
    }
    let startAt = Math.max(this.nextStartTime, this.audioContext.currentTime + 0.04);
    this.pending.forEach(({ samples, sampleRate }) => {
      const audioBuffer = this.audioContext.createBuffer(1, samples.length, sampleRate);
      audioBuffer.copyToChannel(samples, 0);
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.output);
      source.onended = () => {
        source.disconnect();
        this.sources.delete(source);
        if (this.finished && this.sources.size === 0) {
          this.finishResolver?.();
          this.finishResolver = null;
        }
      };
      this.sources.add(source);
      source.start(startAt);
      startAt += audioBuffer.duration;
    });
    this.pending.length = 0;
    this.pendingDuration = 0;
    this.nextStartTime = startAt;
  }
}

const buildTtsAudioBlob = (
  chunks: ArrayBuffer[],
  sampleRate: number,
  responseFormat: TtsRealtimeMessage['responseFormat'],
) => {
  if (responseFormat === 'wav') {
    return new Blob(chunks, { type: 'audio/wav' });
  }
  if (responseFormat === 'mp3') {
    return new Blob(chunks, { type: 'audio/mpeg' });
  }
  if (responseFormat === 'opus') {
    return new Blob(chunks, { type: 'audio/opus' });
  }
  return pcmToWav(chunks, sampleRate);
};


const pcm16ToFloat32 = (pcm: ArrayBuffer) => {
  const view = new DataView(pcm);
  const samples = new Float32Array(Math.floor(view.byteLength / 2));
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 32768;
  }
  return samples;
};

const pcmToWav = (chunks: ArrayBuffer[], sampleRate: number) => {
  const pcmBytes = concatChunks(chunks);
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + pcmBytes.byteLength, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, pcmBytes.byteLength, true);
  return new Blob([header, pcmBytes], { type: 'audio/wav' });
};

const concatChunks = (chunks: ArrayBuffer[]) => {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;
  chunks.forEach((chunk) => {
    output.set(new Uint8Array(chunk), offset);
    offset += chunk.byteLength;
  });
  return output;
};

const writeString = (view: DataView, offset: number, value: string) => {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
};
