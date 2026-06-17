import { useCallback, useEffect, useRef, useState } from 'react';
import { message } from 'antd';

import { buildAsrRealtimeWebSocketUrl } from '../../api/modules/asr';
import { useAuthStore } from '../../store/auth';
import { useTenantScopeStore } from '../../store/tenant-scope';
import { playRealtimeTts } from '../tts-realtime-playback';
import { createPlaybackRequestGuard } from './playback-request-guard';
import {
  AUDIO_WORKLET_PROCESSOR_NAME,
  AUDIO_WORKLET_PROCESSOR_SOURCE,
  downsampleBuffer,
  encodePCM16,
} from './audio-utils';

type WebAudioWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

type AsrSocketMessage = {
  type?: string;
  text?: string;
  final?: boolean;
  message?: string;
};

export const useAgentAudio = () => {
  const token = useAuthStore((state) => state.token);
  const tenant = useAuthStore((state) => state.tenant);
  const tenantScopeId = useTenantScopeStore((state) => state.tenantId);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const [pendingPlaybackKey, setPendingPlaybackKey] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const transcriptRef = useRef('');
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const playbackRequestGuardRef = useRef(createPlaybackRequestGuard());
  const playbackKeyRef = useRef<string | null>(null);
  const playbackAbortRef = useRef<AbortController | null>(null);
  const streamPlaybackQueueRef = useRef<string[]>([]);
  const streamPlaybackBufferRef = useRef('');
  const streamPlaybackActiveRef = useRef(false);
  const streamPlaybackSessionRef = useRef(0);

  const stopRecording = useCallback(() => {
    workletNodeRef.current?.port.close();
    workletNodeRef.current?.disconnect();
    sourceRef.current?.disconnect();
    gainRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();

    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'asr.finish' }));
    } else {
      socket?.close();
    }

    workletNodeRef.current = null;
    sourceRef.current = null;
    gainRef.current = null;
    streamRef.current = null;
    audioContextRef.current = null;
    socketRef.current = null;
    setRecording(false);
    setTranscribing(false);
  }, []);

  const setupAudioStreaming = useCallback(async (stream: MediaStream, socket: WebSocket) => {
    const AudioContextClass = window.AudioContext || (window as WebAudioWindow).webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error('当前浏览器不支持音频采集');
    }
    const audioContext = new AudioContextClass();
    audioContextRef.current = audioContext;
    if (!audioContext.audioWorklet || typeof AudioWorkletNode === 'undefined') {
      throw new Error('当前浏览器不支持 AudioWorklet，无法进行实时音频采集');
    }

    const source = audioContext.createMediaStreamSource(stream);
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    const workletUrl = URL.createObjectURL(
      new Blob([AUDIO_WORKLET_PROCESSOR_SOURCE], { type: 'application/javascript' }),
    );

    try {
      await audioContext.audioWorklet.addModule(workletUrl);
    } finally {
      URL.revokeObjectURL(workletUrl);
    }

    const workletNode = new AudioWorkletNode(audioContext, AUDIO_WORKLET_PROCESSOR_NAME, {
      channelCount: 1,
      channelCountMode: 'explicit',
      channelInterpretation: 'speakers',
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });

    workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (socket.readyState !== WebSocket.OPEN) {
        return;
      }
      const pcm = encodePCM16(downsampleBuffer(event.data, audioContext.sampleRate));
      socket.send(pcm);
    };

    source.connect(workletNode);
    workletNode.connect(silentGain);
    silentGain.connect(audioContext.destination);

    sourceRef.current = source;
    workletNodeRef.current = workletNode;
    gainRef.current = silentGain;
  }, []);

  const startRecording = useCallback(async (onTranscript: (text: string) => void) => {
    if (!token) {
      message.error('登录状态已失效，请重新登录');
      return;
    }

    transcriptRef.current = '';
    setTranscribing(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const socket = new WebSocket(buildAsrRealtimeWebSocketUrl(token, tenantScopeId ?? tenant?.id ?? null));
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;

      socket.onopen = () => {
        void setupAudioStreaming(stream, socket).catch((error: unknown) => {
          message.error(error instanceof Error ? error.message : '无法打开麦克风');
          stopRecording();
        });
      };
      socket.onmessage = (event: MessageEvent<string>) => {
        let payload: AsrSocketMessage;
        try {
          payload = JSON.parse(event.data) as AsrSocketMessage;
        } catch {
          return;
        }
        if (payload.type === 'asr.ready') {
          setRecording(true);
          setTranscribing(false);
          return;
        }
        if (payload.type === 'asr.transcript' && payload.text) {
          const nextText = payload.final
            ? `${transcriptRef.current}${transcriptRef.current ? '\n' : ''}${payload.text}`
            : `${transcriptRef.current}${transcriptRef.current ? '\n' : ''}${payload.text}`;
          if (payload.final) {
            transcriptRef.current = nextText;
          }
          onTranscript(nextText);
          return;
        }
        if (payload.type === 'asr.done') {
          setRecording(false);
          setTranscribing(false);
          return;
        }
        if (payload.type === 'asr.error') {
          message.error(payload.message || '语音识别失败');
          stopRecording();
        }
      };
      socket.onerror = () => {
        message.error('ASR 连接异常');
        stopRecording();
      };
      socket.onclose = () => {
        setRecording(false);
        setTranscribing(false);
      };
    } catch (error) {
      message.error(error instanceof Error ? error.message : '无法打开麦克风');
      stopRecording();
    }
  }, [setupAudioStreaming, stopRecording, tenant?.id, tenantScopeId, token]);

  const revokeObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  const stopPlayback = useCallback(() => {
    playbackRequestGuardRef.current.cancel();
    playbackAbortRef.current?.abort();
    playbackAbortRef.current = null;
    streamPlaybackSessionRef.current += 1;
    streamPlaybackQueueRef.current = [];
    streamPlaybackBufferRef.current = '';
    streamPlaybackActiveRef.current = false;
    audioRef.current?.pause();
    audioRef.current = null;
    playbackKeyRef.current = null;
    revokeObjectUrl();
    setPlayingKey(null);
    setPendingPlaybackKey(null);
    setPaused(false);
  }, [revokeObjectUrl]);

  const playQueuedStreamSegments = useCallback(async (sessionId: number) => {
    if (streamPlaybackActiveRef.current) {
      return;
    }
    streamPlaybackActiveRef.current = true;
    setPlayingKey('streaming-reply');
    setPaused(false);

    while (streamPlaybackSessionRef.current === sessionId && streamPlaybackQueueRef.current.length > 0) {
      const segment = streamPlaybackQueueRef.current.shift();
      if (!segment || !token) {
        continue;
      }
      const abortController = new AbortController();
      playbackAbortRef.current = abortController;
      try {
        await playRealtimeTts({
          text: segment,
          token,
          tenantId: tenantScopeId ?? tenant?.id ?? null,
          signal: abortController.signal,
        });
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          message.error('语音合成失败');
        }
        break;
      } finally {
        if (playbackAbortRef.current === abortController) {
          playbackAbortRef.current = null;
        }
      }
    }

    if (streamPlaybackSessionRef.current === sessionId) {
      streamPlaybackActiveRef.current = false;
      setPlayingKey(null);
      setPendingPlaybackKey(null);
    }
  }, [tenant?.id, tenantScopeId, token]);

  const enqueueStreamPlaybackText = useCallback((text: string, force = false) => {
    const content = text.trim();
    if (!token || (!content && !force)) {
      return;
    }
    streamPlaybackBufferRef.current += text;
    const readySegments = extractReadyTtsSegments(streamPlaybackBufferRef.current, force);
    streamPlaybackBufferRef.current = readySegments.remainder;
    if (readySegments.segments.length === 0) {
      return;
    }
    streamPlaybackQueueRef.current.push(...readySegments.segments);
    const sessionId = streamPlaybackSessionRef.current;
    void playQueuedStreamSegments(sessionId);
  }, [playQueuedStreamSegments, token]);

  const startStreamPlayback = useCallback(() => {
    stopPlayback();
    streamPlaybackSessionRef.current += 1;
    streamPlaybackQueueRef.current = [];
    streamPlaybackBufferRef.current = '';
    streamPlaybackActiveRef.current = false;
    setPendingPlaybackKey('streaming-reply');
  }, [stopPlayback]);

  const appendStreamPlaybackText = useCallback((text: string) => {
    enqueueStreamPlaybackText(text, false);
  }, [enqueueStreamPlaybackText]);

  const finishStreamPlayback = useCallback(() => {
    enqueueStreamPlaybackText('', true);
  }, [enqueueStreamPlaybackText]);

  const playText = useCallback(async (key: string, text: string) => {
    const content = text.trim();
    if (!content) {
      return;
    }

    if (playbackKeyRef.current === key && audioRef.current) {
      if (audioRef.current.paused) {
        await audioRef.current.play();
        setPaused(false);
      } else {
        audioRef.current.pause();
        setPaused(true);
      }
      return;
    }
    if (playbackKeyRef.current === key) {
      stopPlayback();
      return;
    }

    const playbackRequestGuard = playbackRequestGuardRef.current;
    if (playbackRequestGuard.isPending(key, content)) {
      return;
    }

    stopPlayback();
    const playbackRequest = playbackRequestGuard.begin(key, content);
    setPendingPlaybackKey(key);
    setPlayingKey(key);
    setPaused(false);
    playbackKeyRef.current = key;
    const abortController = new AbortController();
    playbackAbortRef.current = abortController;

    try {
      if (!token) {
        message.error('登录状态已失效，请重新登录');
        stopPlayback();
        return;
      }
      await playRealtimeTts({
        text: content,
        token,
        tenantId: tenantScopeId ?? tenant?.id ?? null,
        signal: abortController.signal,
      });
      if (!playbackRequestGuard.isCurrent(playbackRequest)) {
        return;
      }

      playbackRequestGuard.complete(playbackRequest);
      setPendingPlaybackKey(null);
      playbackAbortRef.current = null;
      playbackKeyRef.current = null;
      setPlayingKey(null);
    } catch (error) {
      if (playbackRequestGuard.isCurrent(playbackRequest)) {
        stopPlayback();
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          message.error('语音合成失败');
        }
      }
    }
  }, [stopPlayback, tenant?.id, tenantScopeId, token]);

  useEffect(() => {
    return () => {
      stopRecording();
      stopPlayback();
    };
  }, [stopPlayback, stopRecording]);

  return {
    recording,
    transcribing,
    playingKey,
    pendingPlaybackKey,
    paused,
    startRecording,
    stopRecording,
    playText,
    stopPlayback,
    startStreamPlayback,
    appendStreamPlaybackText,
    finishStreamPlayback,
  };
};

const TTS_SEGMENT_PATTERN = /[。！？!?；;\n]/g;

const extractReadyTtsSegments = (text: string, force: boolean): { segments: string[]; remainder: string } => {
  const segments: string[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(TTS_SEGMENT_PATTERN)) {
    const endIndex = match.index + match[0].length;
    const segment = text.slice(lastIndex, endIndex).trim();
    if (segment) {
      segments.push(segment);
    }
    lastIndex = endIndex;
  }

  let remainder = text.slice(lastIndex);
  if (force && remainder.trim()) {
    segments.push(remainder.trim());
    remainder = '';
  } else if (remainder.length >= 80) {
    segments.push(remainder.trim());
    remainder = '';
  }

  return { segments, remainder };
};
