import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Card, Space, Tag, Typography, message } from 'antd';
import { AudioOutlined, LoadingOutlined, PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { buildAsrRealtimeWebSocketUrl, fetchAsrStatus } from '../../api/modules/asr';
import { useAuthStore } from '../../store/auth';

type TestPhase = 'idle' | 'connecting' | 'listening' | 'finishing' | 'done' | 'error';

type AsrSocketMessage = {
  type?: string;
  text?: string;
  final?: boolean;
  message?: string;
};

type WebAudioWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext;
};

const TARGET_SAMPLE_RATE = 16000;

const phaseMeta: Record<TestPhase, { label: string; color: string }> = {
  idle: { label: '待测试', color: 'default' },
  connecting: { label: '准备中', color: 'processing' },
  listening: { label: '正在聆听', color: 'success' },
  finishing: { label: '整理结果', color: 'processing' },
  done: { label: '测试完成', color: 'blue' },
  error: { label: '测试异常', color: 'error' },
};

const downsampleBuffer = (buffer: Float32Array, inputSampleRate: number) => {
  if (inputSampleRate === TARGET_SAMPLE_RATE) {
    return buffer;
  }
  const sampleRateRatio = inputSampleRate / TARGET_SAMPLE_RATE;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }

  return result;
};

const encodePCM16 = (samples: Float32Array) => {
  const output = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return output.buffer;
};

export const AsrManagementPage = () => {
  const token = useAuthStore((state) => state.token);
  const [phase, setPhase] = useState<TestPhase>('idle');
  const [serviceReady, setServiceReady] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [liveText, setLiveText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [errorText, setErrorText] = useState('');

  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);

  const currentText = liveText || finalText;
  const canStart = serviceReady && phase !== 'connecting' && phase !== 'listening' && phase !== 'finishing';
  const canStop = phase === 'listening';
  const phaseInfo = phaseMeta[phase];

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const status = await fetchAsrStatus();
      setServiceReady(Boolean(status.configured && status.isActive));
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const stopAudio = useCallback(() => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    gainRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();
    processorRef.current = null;
    sourceRef.current = null;
    gainRef.current = null;
    streamRef.current = null;
    audioContextRef.current = null;
  }, []);

  const closeSocket = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  const resetTest = () => {
    setLiveText('');
    setFinalText('');
    setErrorText('');
  };

  const setupAudioStreaming = useCallback((stream: MediaStream, socket: WebSocket) => {
    const AudioContextClass = window.AudioContext || (window as WebAudioWindow).webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error('当前浏览器不支持音频采集');
    }
    const audioContext = new AudioContextClass();
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;

    processor.onaudioprocess = (event) => {
      if (socket.readyState !== WebSocket.OPEN) {
        return;
      }
      const channelData = event.inputBuffer.getChannelData(0);
      const pcm = encodePCM16(downsampleBuffer(channelData, audioContext.sampleRate));
      socket.send(pcm);
    };

    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(audioContext.destination);

    audioContextRef.current = audioContext;
    sourceRef.current = source;
    processorRef.current = processor;
    gainRef.current = silentGain;
  }, []);

  const handleSocketMessage = useCallback((event: MessageEvent<string>) => {
    let payload: AsrSocketMessage;
    try {
      payload = JSON.parse(event.data) as AsrSocketMessage;
    } catch {
      return;
    }

    if (payload.type === 'asr.ready') {
      setPhase('listening');
      return;
    }

    if (payload.type === 'asr.transcript' && payload.text) {
      if (payload.final) {
        setFinalText((previous) => `${previous}${previous ? '\n' : ''}${payload.text}`);
        setLiveText('');
      } else {
        setLiveText(payload.text);
      }
      return;
    }

    if (payload.type === 'asr.done') {
      setPhase('done');
      stopAudio();
      closeSocket();
      return;
    }

    if (payload.type === 'asr.error') {
      setErrorText(payload.message || 'ASR 测试失败');
      setPhase('error');
      stopAudio();
      closeSocket();
    }
  }, [closeSocket, stopAudio]);

  const startTest = async () => {
    if (!token) {
      message.error('登录状态已失效，请重新登录');
      return;
    }
    if (!serviceReady) {
      message.warning('ASR 服务未就绪');
      return;
    }

    resetTest();
    setPhase('connecting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const socket = new WebSocket(buildAsrRealtimeWebSocketUrl(token));
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;

      socket.onopen = () => {
        setupAudioStreaming(stream, socket);
      };
      socket.onmessage = handleSocketMessage;
      socket.onerror = () => {
        setErrorText('ASR 测试连接异常');
        setPhase('error');
        stopAudio();
      };
      socket.onclose = () => {
        stopAudio();
        setPhase((previous) => {
          if (previous === 'finishing') return 'done';
          if (previous === 'connecting' || previous === 'listening') return 'idle';
          return previous;
        });
      };
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : '无法打开麦克风');
      setPhase('error');
      stopAudio();
      closeSocket();
    }
  };

  const stopTest = () => {
    setPhase('finishing');
    stopAudio();
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'asr.finish' }));
    } else {
      setPhase(finalText || liveText ? 'done' : 'idle');
    }
  };

  useEffect(() => {
    return () => {
      stopAudio();
      closeSocket();
    };
  }, [closeSocket, stopAudio]);

  const displayText = useMemo(() => {
    if (currentText.trim()) {
      return currentText;
    }
    if (phase === 'listening') {
      return '正在等待语音输入';
    }
    return '测试结果将在这里显示';
  }, [currentText, phase]);

  return (
    <div className="space-y-4">
      <Card size="small">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Space size={10}>
            <AudioOutlined className="text-lg text-teal-700" />
            <Typography.Title level={4} className="!mb-0 !text-slate-900">
              ASR 测试
            </Typography.Title>
            <Tag color={serviceReady ? 'success' : 'warning'}>{serviceReady ? '服务可用' : '服务未就绪'}</Tag>
            <Tag color={phaseInfo.color}>{phaseInfo.label}</Tag>
          </Space>
          <Button icon={<ReloadOutlined />} loading={statusLoading} onClick={() => void loadStatus()}>
            刷新
          </Button>
        </div>
      </Card>

      <Card className="min-h-[420px]">
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-6 text-center">
          <button
            type="button"
            disabled={!canStart && !canStop}
            onClick={() => (canStop ? stopTest() : void startTest())}
            className={`flex h-28 w-28 items-center justify-center rounded-full border text-5xl shadow-sm transition ${
              canStop
                ? 'border-rose-200 bg-rose-50 text-rose-600 hover:border-rose-300 hover:bg-rose-100'
                : 'border-teal-200 bg-teal-50 text-teal-700 hover:border-teal-300 hover:bg-teal-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-300'
            }`}
            aria-label={canStop ? '停止 ASR 测试' : '开始 ASR 测试'}
          >
            {phase === 'connecting' || phase === 'finishing' ? (
              <LoadingOutlined />
            ) : canStop ? (
              <PauseCircleOutlined />
            ) : (
              <PlayCircleOutlined />
            )}
          </button>

          <div className="w-full max-w-4xl rounded-lg border border-slate-200 bg-slate-50 px-5 py-6 text-left">
            <div className="mb-3 text-xs font-medium uppercase text-slate-400">实时识别文本</div>
            <div className={`min-h-32 whitespace-pre-wrap text-lg leading-8 ${currentText ? 'text-slate-950' : 'text-slate-400'}`}>
              {displayText}
            </div>
          </div>

          {errorText ? (
            <Alert className="w-full max-w-4xl text-left" type="error" showIcon message="测试失败" description={errorText} />
          ) : null}
        </div>
      </Card>
    </div>
  );
};
