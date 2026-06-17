import { buildTtsRealtimeWebSocketUrl, type TtsRealtimeMessage, type TtsTestPayload } from '../api/modules/tts';

type PlayRealtimeTtsOptions = TtsTestPayload & {
  token: string;
  tenantId?: number | null;
  providerCode?: string;
  signal?: AbortSignal;
};

type PlayRealtimeTtsResult = {
  blob: Blob;
  sampleRate: number;
};

type WebAudioWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

export const playRealtimeTts = async (options: PlayRealtimeTtsOptions): Promise<PlayRealtimeTtsResult> => {
  const AudioContextClass = window.AudioContext || (window as WebAudioWindow).webkitAudioContext;
  if (!AudioContextClass) {
    throw new Error('当前浏览器不支持音频播放');
  }

  const audioContext = new AudioContextClass();
  const gain = audioContext.createGain();
  gain.connect(audioContext.destination);

  let sampleRate = 24000;
  let nextStartTime = audioContext.currentTime + 0.05;
  const chunks: ArrayBuffer[] = [];
  const scheduledSources: AudioBufferSourceNode[] = [];

  const closeAudio = () => {
    scheduledSources.forEach((source) => {
      try {
        source.stop();
      } catch {
        // Source may already have ended.
      }
      source.disconnect();
    });
    gain.disconnect();
    void audioContext.close();
  };

  return new Promise((resolve, reject) => {
    let settled = false;
    let completing = false;
    let completionTimer: number | null = null;
    const socket = new WebSocket(buildTtsRealtimeWebSocketUrl(options.token, options.tenantId));
    socket.binaryType = 'arraybuffer';

    const finish = () => {
      if (settled || completing) {
        return;
      }
      completing = true;
      const playbackTailMs = Math.max(0, (nextStartTime - audioContext.currentTime) * 1000);
      completionTimer = window.setTimeout(() => {
        settled = true;
        closeAudio();
        resolve({ blob: pcmToWav(chunks, sampleRate), sampleRate });
      }, playbackTailMs + 50);
    };

    const fail = (error: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      if (completionTimer !== null) {
        window.clearTimeout(completionTimer);
        completionTimer = null;
      }
      closeAudio();
      reject(error);
    };

    const abort = () => {
      socket.close();
      fail(new DOMException('TTS playback was cancelled', 'AbortError'));
    };

    if (options.signal?.aborted) {
      abort();
      return;
    }
    options.signal?.addEventListener('abort', abort, { once: true });

    socket.onopen = () => {
      if (audioContext.state === 'suspended') {
        void audioContext.resume();
      }
      socket.send(JSON.stringify({
        type: 'tts.start',
        text: options.text || '',
        voiceId: options.voiceId ?? null,
        providerCode: options.providerCode,
      }));
    };

    socket.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (typeof event.data !== 'string') {
        const pcm = event.data.slice(0);
        chunks.push(pcm);
        schedulePcmChunk(
          audioContext,
          gain,
          scheduledSources,
          pcm,
          sampleRate,
          () => nextStartTime,
          (value) => {
            nextStartTime = value;
          },
        );
        return;
      }

      let payload: TtsRealtimeMessage;
      try {
        payload = JSON.parse(event.data) as TtsRealtimeMessage;
      } catch {
        return;
      }
      if (payload.type === 'tts.ready' && payload.sampleRate) {
        sampleRate = payload.sampleRate;
        return;
      }
      if (payload.type === 'tts.done') {
        socket.close();
        finish();
        return;
      }
      if (payload.type === 'tts.error') {
        socket.close();
        fail(new Error(payload.message || '语音合成失败'));
      }
    };

    socket.onerror = () => {
      fail(new Error('TTS WebSocket 连接异常'));
    };

    socket.onclose = () => {
      options.signal?.removeEventListener('abort', abort);
      if (!settled && !completing && chunks.length > 0) {
        finish();
      } else if (!settled && !completing) {
        fail(new Error('TTS WebSocket 已关闭'));
      }
    };
  });
};

const schedulePcmChunk = (
  audioContext: AudioContext,
  output: AudioNode,
  scheduledSources: AudioBufferSourceNode[],
  pcm: ArrayBuffer,
  sampleRate: number,
  getNextStartTime: () => number,
  setNextStartTime: (value: number) => void,
) => {
  const samples = pcm16ToFloat32(pcm);
  if (samples.length === 0) {
    return;
  }
  const audioBuffer = audioContext.createBuffer(1, samples.length, sampleRate);
  audioBuffer.copyToChannel(samples, 0);
  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(output);
  const startAt = Math.max(audioContext.currentTime + 0.02, getNextStartTime());
  source.start(startAt);
  setNextStartTime(startAt + audioBuffer.duration);
  scheduledSources.push(source);
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
