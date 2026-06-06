import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  AudioOutlined,
  DeleteOutlined,
  EditOutlined,
  LoadingOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import {
  buildAsrRealtimeWebSocketUrl,
  createAsrReplacementRule,
  deleteAsrReplacementRule,
  fetchAsrReplacementRules,
  fetchAsrStatus,
  updateAsrReplacementRule,
  type AsrReplacementRulePayload,
  type AsrReplacementRuleRecord,
} from '../../api/modules/asr';
import { useAuthStore } from '../../store/auth';
import { useTenantScopeStore } from '../../store/tenant-scope';

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

type ReplacementRuleFormValues = {
  sourceText: string;
  replacementText: string;
  isActive: boolean;
  sortOrder: number;
};

const TARGET_SAMPLE_RATE = 16000;
const RULE_PAGE_SIZE = 10;

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
  const tenantScopeId = useTenantScopeStore((state) => state.tenantId);
  const [phase, setPhase] = useState<TestPhase>('idle');
  const [serviceReady, setServiceReady] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [liveText, setLiveText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [errorText, setErrorText] = useState('');
  const [replacementRules, setReplacementRules] = useState<AsrReplacementRuleRecord[]>([]);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [rulesPage, setRulesPage] = useState(1);
  const [rulesTotal, setRulesTotal] = useState(0);
  const [ruleModalVisible, setRuleModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<AsrReplacementRuleRecord | null>(null);
  const [ruleSubmitting, setRuleSubmitting] = useState(false);
  const [ruleForm] = Form.useForm<ReplacementRuleFormValues>();

  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const ignoreTranscriptRef = useRef(false);

  const currentText = liveText || finalText;
  const canStart = serviceReady && phase !== 'connecting' && phase !== 'listening' && phase !== 'finishing';
  const canStop = phase === 'listening';
  const phaseInfo = phaseMeta[phase];

  const loadReplacementRules = useCallback(async (page = rulesPage) => {
    setRulesLoading(true);
    try {
      const data = await fetchAsrReplacementRules(page);
      setReplacementRules(data.results);
      setRulesTotal(data.count);
    } finally {
      setRulesLoading(false);
    }
  }, [rulesPage]);

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

  useEffect(() => {
    void loadReplacementRules();
  }, [loadReplacementRules]);

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
    ignoreTranscriptRef.current = false;
    setLiveText('');
    setFinalText('');
    setErrorText('');
  };

  const openCreateRuleModal = () => {
    setEditingRule(null);
    ruleForm.setFieldsValue({
      sourceText: '',
      replacementText: '',
      isActive: true,
      sortOrder: 0,
    });
    setRuleModalVisible(true);
  };

  const openEditRuleModal = (rule: AsrReplacementRuleRecord) => {
    setEditingRule(rule);
    ruleForm.setFieldsValue({
      sourceText: rule.sourceText,
      replacementText: rule.replacementText,
      isActive: rule.isActive,
      sortOrder: rule.sortOrder,
    });
    setRuleModalVisible(true);
  };

  const closeRuleModal = () => {
    setRuleModalVisible(false);
    setEditingRule(null);
    ruleForm.resetFields();
  };

  const buildRulePayload = (values: ReplacementRuleFormValues): AsrReplacementRulePayload => ({
    sourceText: values.sourceText.trim(),
    replacementText: values.replacementText.trim(),
    isActive: values.isActive ?? true,
    sortOrder: Number(values.sortOrder ?? 0),
  });

  const handleRuleSubmit = async () => {
    try {
      const values = await ruleForm.validateFields();
      setRuleSubmitting(true);
      const payload = buildRulePayload(values);
      if (editingRule) {
        await updateAsrReplacementRule(editingRule.id, payload);
        message.success('替换词已更新');
        closeRuleModal();
        await loadReplacementRules();
      } else {
        await createAsrReplacementRule(payload);
        message.success('替换词已创建');
        closeRuleModal();
        setRulesPage(1);
        await loadReplacementRules(1);
      }
    } finally {
      setRuleSubmitting(false);
    }
  };

  const handleRuleDelete = async (rule: AsrReplacementRuleRecord) => {
    await deleteAsrReplacementRule(rule.id);
    message.success('替换词已删除');
    const nextPage = replacementRules.length === 1 && rulesPage > 1 ? rulesPage - 1 : rulesPage;
    setRulesPage(nextPage);
    await loadReplacementRules(nextPage);
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
      if (ignoreTranscriptRef.current) {
        return;
      }
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

      const socket = new WebSocket(buildAsrRealtimeWebSocketUrl(token, tenantScopeId));
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
    ignoreTranscriptRef.current = true;
    setLiveText('');
    setFinalText('');
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
    if (!serviceReady) {
      return 'ASR 服务未就绪，请先检查 ASR 设置';
    }
    return '测试结果将在这里显示';
  }, [currentText, phase, serviceReady]);

  const replacementColumns: ColumnsType<AsrReplacementRuleRecord> = useMemo(
    () => [
      {
        title: '原词',
        dataIndex: 'sourceText',
        key: 'sourceText',
        width: 200,
        render: (value: string) => (
          <span className="font-medium text-slate-800 bg-slate-50 px-2.5 py-1 rounded border border-slate-100 text-xs">
            {value}
          </span>
        ),
      },
      {
        title: '替换词',
        dataIndex: 'replacementText',
        key: 'replacementText',
        width: 200,
        render: (value: string) => (
          <span className="font-medium text-teal-800 bg-teal-50/50 px-2.5 py-1 rounded border border-teal-100/50 text-xs">
            {value}
          </span>
        ),
      },
      {
        title: '状态',
        dataIndex: 'isActive',
        key: 'isActive',
        width: 100,
        render: (value: boolean) => (
          <Tag
            color={value ? 'success' : 'default'}
            className="px-2 py-0.5 rounded-full text-xs font-normal"
          >
            {value ? '● 已启用' : '○ 已停用'}
          </Tag>
        ),
      },
      {
        title: '排序',
        dataIndex: 'sortOrder',
        key: 'sortOrder',
        width: 90,
        render: (value: number) => (
          <span className="text-slate-500 font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">
            {value}
          </span>
        ),
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 190,
        render: (value: string) => <span className="text-slate-400 text-xs font-mono">{value}</span>,
      },
      {
        title: '操作',
        key: 'actions',
        width: 150,
        render: (_, rule) => (
          <div className="flex gap-2">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined className="text-teal-600" />}
              onClick={() => openEditRuleModal(rule)}
              className="text-teal-600 hover:bg-teal-50"
            >
              编辑
            </Button>
            <Popconfirm
              title="确认删除该替换词吗？"
              okText="确认"
              cancelText="取消"
              onConfirm={() => void handleRuleDelete(rule)}
            >
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                className="hover:bg-rose-50"
              >
                删除
              </Button>
            </Popconfirm>
          </div>
        ),
      },
    ],
    [handleRuleDelete],
  );

  return (
    <div className="space-y-4">
      <style>{`
        @keyframes pulse-ring {
          0% {
            transform: scale(0.95);
            opacity: 0.8;
          }
          50% {
            opacity: 0.4;
          }
          100% {
            transform: scale(1.3);
            opacity: 0;
          }
        }
        @keyframes pulse-ring-delayed {
          0% {
            transform: scale(0.95);
            opacity: 0;
          }
          30% {
            transform: scale(0.95);
            opacity: 0.8;
          }
          70% {
            opacity: 0.4;
          }
          100% {
            transform: scale(1.4);
            opacity: 0;
          }
        }
        @keyframes bar-grow-1 {
          0%, 100% { height: 8px; }
          50% { height: 28px; }
        }
        @keyframes bar-grow-2 {
          0%, 100% { height: 16px; }
          50% { height: 38px; }
        }
        @keyframes bar-grow-3 {
          0%, 100% { height: 6px; }
          50% { height: 22px; }
        }
        @keyframes bar-grow-4 {
          0%, 100% { height: 24px; }
          50% { height: 44px; }
        }
        @keyframes bar-grow-5 {
          0%, 100% { height: 12px; }
          50% { height: 32px; }
        }
        @keyframes typing-cursor {
          50% { border-color: transparent; opacity: 0; }
        }
      `}</style>

      {/* 顶部 Hero Banner */}
      <div className="page-hero">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700 shadow-sm">
              <AudioOutlined className="text-xl" />
            </div>
            <div>
              <Typography.Title level={4} className="!mb-0 !text-slate-900">
                ASR 语音识别管理
              </Typography.Title>
              <Typography.Text className="!text-slate-500 text-xs">
                配置与测试语音识别服务，维护特定专有名词的实时文本替换规则。
              </Typography.Text>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Tag
              color={serviceReady ? 'success' : 'warning'}
              className="flex items-center gap-1.5 px-2.5 py-1 border border-emerald-200/50"
            >
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${serviceReady ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
              {serviceReady ? '服务可用' : '服务未就绪'}
            </Tag>
            <Tag
              color={phaseInfo.color}
              className="px-2.5 py-1 font-medium"
            >
              {phaseInfo.label}
            </Tag>
            <Button
              icon={<ReloadOutlined />}
              loading={statusLoading}
              onClick={() => void loadStatus()}
              className="border-slate-200 hover:border-teal-500 hover:text-teal-600 flex items-center gap-1"
            >
              刷新状态
            </Button>
          </div>
        </div>
      </div>

      {/* 语音测试工作台 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* 左侧控制区 */}
        <div className="lg:col-span-4 flex flex-col">
          <Card className="flex-grow overflow-hidden relative border-slate-100 shadow-sm">
            <div className="p-6 h-full flex flex-col justify-between relative flex-grow min-h-[352px]">
              {/* 装饰性渐变背景 */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/5 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl pointer-events-none" />

              <div className="flex flex-col items-center justify-center py-6 flex-grow">
                {/* 麦克风录音控制按钮 */}
                <div className="relative flex items-center justify-center mb-6">
                  {/* 录音中的涟漪波动效果 */}
                  {phase === 'listening' && (
                    <>
                      <div className="absolute w-36 h-36 rounded-full bg-teal-500/10 border border-teal-500/20" style={{ animation: 'pulse-ring 2s infinite cubic-bezier(0.215, 0.610, 0.355, 1)' }} />
                      <div className="absolute w-44 h-44 rounded-full bg-teal-500/5 border border-teal-500/10" style={{ animation: 'pulse-ring-delayed 2.5s infinite cubic-bezier(0.215, 0.610, 0.355, 1)' }} />
                    </>
                  )}

                  <button
                    type="button"
                    disabled={!canStart && !canStop}
                    onClick={() => (canStop ? stopTest() : void startTest())}
                    style={{
                      boxShadow: canStop
                        ? '0 10px 25px -5px rgba(239, 68, 68, 0.3), inset 0 2px 4px rgba(255, 255, 255, 0.2)'
                        : !serviceReady
                          ? 'none'
                          : '0 10px 25px -5px rgba(13, 148, 136, 0.3), inset 0 2px 4px rgba(255, 255, 255, 0.2)'
                    }}
                    className={`relative z-10 flex h-24 w-24 items-center justify-center rounded-full border text-4xl transition-all duration-300 transform hover:scale-105 active:scale-95 ${
                      canStop
                        ? 'border-rose-500 bg-rose-500 text-white hover:bg-rose-600'
                        : !serviceReady
                          ? 'border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
                          : 'border-teal-600 bg-teal-600 text-white hover:bg-teal-700'
                    }`}
                    aria-label={canStop ? '停止 ASR 测试' : '开始 ASR 测试'}
                  >
                    {phase === 'connecting' || phase === 'finishing' ? (
                      <LoadingOutlined className="animate-spin text-3xl" />
                    ) : canStop ? (
                      <PauseCircleOutlined className="animate-pulse" />
                    ) : (
                      <PlayCircleOutlined />
                    )}
                  </button>
                </div>

                {/* 录音状态和辅助文字 */}
                <div className="text-center mb-6">
                  <div className={`font-semibold text-lg ${canStop ? 'text-teal-600' : 'text-slate-800'}`}>
                    {phase === 'listening' ? '录音测试中...' : phase === 'connecting' ? '正在连接服务...' : phase === 'finishing' ? '正在整理数据...' : phase === 'done' ? '测试已完成' : phase === 'error' ? '测试发生异常' : statusLoading ? '正在检查服务...' : serviceReady ? '准备就绪' : '服务未就绪'}
                  </div>
                  <div className="text-slate-400 text-xs mt-1">
                    {phase === 'listening' ? '请对着麦克风说话' : phase === 'connecting' ? '正在建立WebSocket连接' : phase === 'finishing' ? '正在等待最后一帧流式输出' : phase === 'done' ? '您可以重新启动测试' : statusLoading ? '正在读取 ASR 服务状态' : serviceReady ? '点击按钮开始实时语音识别' : '请先检查 ASR 设置'}
                  </div>
                </div>

                {/* 模拟音量声波 */}
                <div className="flex items-center gap-1.5 h-12 justify-center w-full px-4 mb-4">
                  {phase === 'listening' ? (
                    <>
                      <div className="w-1.5 bg-teal-500 rounded-full animate-[bar-grow-1_1.2s_infinite_ease-in-out]" style={{ height: '8px' }} />
                      <div className="w-1.5 bg-teal-500 rounded-full animate-[bar-grow-2_0.8s_infinite_ease-in-out]" style={{ height: '16px' }} />
                      <div className="w-1.5 bg-teal-600 rounded-full animate-[bar-grow-3_1.4s_infinite_ease-in-out]" style={{ height: '6px' }} />
                      <div className="w-1.5 bg-teal-500 rounded-full animate-[bar-grow-4_1s_infinite_ease-in-out]" style={{ height: '24px' }} />
                      <div className="w-1.5 bg-teal-400 rounded-full animate-[bar-grow-5_1.1s_infinite_ease-in-out]" style={{ height: '12px' }} />
                      <div className="w-1.5 bg-teal-500 rounded-full animate-[bar-grow-2_0.9s_infinite_ease-in-out]" style={{ height: '20px' }} />
                      <div className="w-1.5 bg-teal-600 rounded-full animate-[bar-grow-1_1.3s_infinite_ease-in-out]" style={{ height: '8px' }} />
                    </>
                  ) : (
                    <>
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                      <div className="w-1.5 h-1.5 bg-slate-300 rounded-full" />
                    </>
                  )}
                </div>
              </div>

              {/* 控制器底部标识与快捷清除 */}
              <div className="flex items-center justify-between border-t border-slate-100 pt-4 mt-auto">
                <span className="text-slate-400 text-xs">
                  音频采集: Mono PCM 16kHz
                </span>
                <Button
                  size="small"
                  danger
                  type="text"
                  disabled={!currentText && !errorText}
                  onClick={resetTest}
                  className="text-xs hover:bg-rose-50 flex items-center gap-1"
                >
                  <ReloadOutlined className="text-xs" /> 清空测试
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧识别面板 */}
        <div className="lg:col-span-8">
          <Card className="shadow-sm border-slate-100 overflow-hidden flex flex-col h-full">
            <div className="flex flex-col h-full flex-grow">
              {/* 模拟终端 Header */}
              <div className="flex items-center justify-between bg-slate-900 px-4 py-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                    <span className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                    <span className="w-3 h-3 rounded-full bg-[#27c93f]" />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {phase === 'listening' && (
                    <span className="flex items-center gap-1.5 text-xs text-rose-500 font-semibold animate-pulse">
                      <span className="h-2 w-2 rounded-full bg-rose-500" />
                      LIVE
                    </span>
                  )}
                  {Boolean(currentText) && (
                    <Button
                      size="small"
                      type="text"
                      onClick={() => {
                        if (currentText) {
                          navigator.clipboard.writeText(currentText);
                          message.success('已成功复制识别文本');
                        }
                      }}
                      className="text-slate-400 hover:text-white text-xs hover:bg-slate-800 border-none flex items-center gap-1"
                    >
                      复制文本
                    </Button>
                  )}
                </div>
              </div>

              {/* 模拟终端 Text Area */}
              <div className="bg-slate-950 p-6 min-h-[300px] flex-grow overflow-y-auto font-mono text-slate-100 custom-scrollbar select-text">
                {currentText.trim() ? (
                  <div className="whitespace-pre-wrap leading-8 text-[15px] relative">
                    {currentText}
                    {phase === 'listening' && (
                      <span className="inline-block w-2 h-4 bg-teal-400 ml-1 animate-[typing-cursor_0.8s_infinite]" />
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center min-h-[250px] text-center text-slate-500">
                    <AudioOutlined className="text-4xl text-slate-700 mb-3 animate-pulse" />
                    <div className="text-sm">{displayText}</div>
                    {phase === 'idle' && (
                      <div className="text-xs text-slate-600 mt-2 max-w-sm">
                        准备就绪后，点击左侧录音控制按钮，开启您的麦克风进行语音测试。
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 错误提示区域 */}
              {errorText ? (
                <div className="bg-rose-950/40 border-t border-rose-900/50 px-4 py-3 flex items-start gap-2 text-rose-300 text-xs font-mono">
                  <span className="text-rose-500 font-bold">[ERROR]</span>
                  <div className="flex-1">{errorText}</div>
                </div>
              ) : null}
            </div>
          </Card>
        </div>
      </div>

      {/* 替换词规则管理 */}
      <Card className="shadow-sm border-slate-100">
        <div className="p-6">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-teal-700 shadow-sm">
                <SwapOutlined className="text-lg" />
              </div>
              <div>
                <Typography.Title level={5} className="!mb-0 !text-slate-900">
                  替换词规则配置
                </Typography.Title>
                <Typography.Text className="!text-slate-500 text-xs block mt-0.5">
                  设置语音识别文本中的原词与替换词（例如公司名、专有名词），系统将在返回实时识别结果前自动应用规则进行修正。
                </Typography.Text>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                icon={<ReloadOutlined />}
                loading={rulesLoading}
                onClick={() => void loadReplacementRules()}
                className="border-slate-200 hover:border-teal-500 hover:text-teal-600 flex items-center gap-1"
              >
                刷新规则
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={openCreateRuleModal}
                className="bg-teal-700 hover:bg-teal-600 border-none flex items-center gap-1"
              >
                新建替换词
              </Button>
            </div>
          </div>

          <Table
            rowKey="id"
            columns={replacementColumns}
            dataSource={replacementRules}
            loading={rulesLoading}
            className="border border-slate-100 rounded-lg overflow-hidden"
            pagination={{
              current: rulesPage,
              pageSize: RULE_PAGE_SIZE,
              total: rulesTotal,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 条规则`,
              onChange: setRulesPage,
            }}
          />
        </div>
      </Card>

      {/* 规则表单模态框 */}
      <Modal
        title={
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-teal-50 text-teal-700">
              <SwapOutlined className="text-sm" />
            </span>
            <span className="font-semibold text-slate-800">{editingRule ? '编辑替换词' : '新建替换词'}</span>
          </div>
        }
        open={ruleModalVisible}
        onCancel={closeRuleModal}
        onOk={() => void handleRuleSubmit()}
        confirmLoading={ruleSubmitting}
        okText={editingRule ? '保存' : '创建'}
        cancelText="取消"
        destroyOnHidden
        forceRender
        className="rounded-xl overflow-hidden"
      >
        <Form<ReplacementRuleFormValues> form={ruleForm} layout="vertical" className="mt-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Form.Item
              label="原词"
              name="sourceText"
              rules={[{ required: true, whitespace: true, message: '请输入原词' }]}
              className="mb-4"
            >
              <Input placeholder="例如：小明" className="h-10 border-slate-200 focus:border-teal-500" />
            </Form.Item>

            <Form.Item
              label="替换为"
              name="replacementText"
              rules={[{ required: true, whitespace: true, message: '请输入替换词' }]}
              className="mb-4"
            >
              <Input placeholder="例如：小张" className="h-10 border-slate-200 focus:border-teal-500" />
            </Form.Item>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
            <Form.Item
              label="优先级排序 (越小越优先)"
              name="sortOrder"
              className="mb-4"
            >
              <InputNumber min={0} precision={0} className="!w-full h-10 flex items-center border-slate-200 focus:border-teal-500" />
            </Form.Item>

            <Form.Item
              label="启用状态"
              name="isActive"
              valuePropName="checked"
              className="mb-4"
            >
              <div className="h-10 flex items-center border border-slate-100 bg-slate-50/50 rounded px-3">
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
                <span className="text-slate-400 text-xs ml-3">启用后识别将自动生效</span>
              </div>
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
};
