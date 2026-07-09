import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Button, Card, Input, Select, Slider, Space, Spin, Switch, Tag, Tooltip, Typography, message } from 'antd';
import {
  IconCheck,
  IconHeadphones,
  IconPlayerPlay,
  IconRefresh,
  IconVolume,
  IconDeviceFloppy,
} from '@tabler/icons-react';
import {
  fetchCompanyTtsOptions,
  updateCompanyDefaultTtsVoice,
  type CompanyTtsOptions,
  type TtsSessionConfig,
  type TtsVoiceRecord,
} from '../../api/modules/tts';
import { useAuthStore } from '../../store/auth';
import { playRealtimeTts } from '../tts-realtime-playback';
import {
  getTtsInstructionDisabledReason,
  getTtsModelCapability,
  isTtsVoiceSupportedByModel,
} from '../tts-settings/tts-voice-capabilities';

const DEFAULT_TTS_SESSION_CONFIG: TtsSessionConfig = {
  mode: 'server_commit',
  language_type: 'Auto',
  response_format: 'pcm',
  sample_rate: 24000,
  speech_rate: 1,
  volume: 50,
  pitch_rate: 1,
  bit_rate: 128,
  instructions: '',
  optimize_instructions: false,
};
const OPTIMIZE_INSTRUCTIONS_TOOLTIP = '开启后会在有指令控制文本时自动优化表达，让语气、情绪和播报风格更清晰；不支持该能力的播报风格或音色不会生效。';

const normalizeTtsSessionConfig = (config?: Partial<TtsSessionConfig> | null): TtsSessionConfig => ({
  ...DEFAULT_TTS_SESSION_CONFIG,
  ...(config || {}),
  mode: 'server_commit',
  language_type: DEFAULT_TTS_SESSION_CONFIG.language_type,
  response_format: DEFAULT_TTS_SESSION_CONFIG.response_format,
  sample_rate: DEFAULT_TTS_SESSION_CONFIG.sample_rate,
  bit_rate: config?.bit_rate ?? DEFAULT_TTS_SESSION_CONFIG.bit_rate,
  instructions: (config?.instructions || '').trim(),
});

export const TtsManagementPage = () => {
  const [options, setOptions] = useState<CompanyTtsOptions | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState<number | null>(null);
  const [selectedModelCode, setSelectedModelCode] = useState<string>('instructional');
  const [ttsSessionConfig, setTtsSessionConfig] = useState<TtsSessionConfig>(DEFAULT_TTS_SESSION_CONFIG);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testText, setTestText] = useState('');
  const playbackAbortRef = useRef<AbortController | null>(null);
  const playbackInterruptRef = useRef<AbortController | null>(null);
  const token = useAuthStore((state) => state.token);

  const stopTestPlayback = useCallback(() => {
    playbackInterruptRef.current?.abort();
    playbackInterruptRef.current = null;
    playbackAbortRef.current?.abort();
    playbackAbortRef.current = null;
    setTesting(false);
  }, []);

  useEffect(() => () => {
    playbackInterruptRef.current?.abort();
    playbackAbortRef.current?.abort();
  }, []);

  const loadOptions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCompanyTtsOptions();
      setOptions(data);
      setSelectedVoiceId(data.defaultVoiceId);
      setSelectedModelCode(data.provider.defaultModelCode);
      setTtsSessionConfig(normalizeTtsSessionConfig(data.ttsSessionConfig));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const selectedVoice = useMemo(
    () => options?.voices.find((voice) => voice.id === selectedVoiceId) ?? null,
    [options?.voices, selectedVoiceId],
  );
  const modelCapability = useMemo(() => getTtsModelCapability(selectedModelCode), [selectedModelCode]);
  const instructionDisabledReason = getTtsInstructionDisabledReason(selectedModelCode, selectedVoice?.voiceCode);
  const instructionDisabledMessage = instructionDisabledReason ? '当前音色或播报风格不支持指令控制。' : '';
  const availableVoices = useMemo(
    () => (options?.voices ?? []).filter((voice) => isTtsVoiceSupportedByModel(selectedModelCode, voice.voiceCode)),
    [selectedModelCode, options?.voices],
  );

  const defaultVoice = useMemo(
    () => options?.voices.find((voice) => voice.id === options.defaultVoiceId) ?? null,
    [options?.defaultVoiceId, options?.voices],
  );

  useEffect(() => {
    if (!options || !selectedVoiceId) {
      return;
    }
    const voice = options.voices.find((item) => item.id === selectedVoiceId);
    if (voice && !isTtsVoiceSupportedByModel(selectedModelCode, voice.voiceCode)) {
      setSelectedVoiceId(null);
    }
  }, [options, selectedModelCode, selectedVoiceId]);

  const saveDefaultVoice = async () => {
    if (!selectedVoiceId) {
      message.warning('请选择音色');
      return;
    }
    const voice = options?.voices.find((item) => item.id === selectedVoiceId);
    const normalized = normalizeTtsSessionConfig(ttsSessionConfig);
    normalized.model_code = selectedModelCode;
    const disabledReason = getTtsInstructionDisabledReason(selectedModelCode, voice?.voiceCode);
    if (disabledReason) {
      normalized.instructions = '';
      normalized.optimize_instructions = false;
      setTtsSessionConfig(normalized);
    }
    setSaving(true);
    try {
      const data = await updateCompanyDefaultTtsVoice(selectedVoiceId, normalized, selectedModelCode);
      setOptions(data);
      setSelectedVoiceId(data.defaultVoiceId);
      setSelectedModelCode(data.provider.defaultModelCode);
      setTtsSessionConfig(normalizeTtsSessionConfig(data.ttsSessionConfig));
      message.success('TTS 管理设置已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!token) {
      message.error('登录状态已失效，请重新登录');
      return;
    }
    stopTestPlayback();
    const playbackAbort = new AbortController();
    const playbackInterrupt = new AbortController();
    playbackAbortRef.current = playbackAbort;
    playbackInterruptRef.current = playbackInterrupt;
    setTesting(true);
    try {
      const playbackText = testText.trim() || options?.defaultTestText || '';
      const sessionConfig = { ...normalizeTtsSessionConfig(ttsSessionConfig), model_code: selectedModelCode, response_format: 'pcm' as const };
      if (instructionDisabledReason) {
        sessionConfig.instructions = '';
        sessionConfig.optimize_instructions = false;
      }
      const { blob } = await playRealtimeTts({
        text: playbackText,
        voiceId: selectedVoiceId,
        token,
        sessionConfig,
        signal: playbackAbort.signal,
        interruptSignal: playbackInterrupt.signal,
      });
      if (blob.size <= 44) {
        message.error('TTS 未返回有效音频');
        return;
      }
      message.success('TTS 测试音频播放完成');
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      message.error(error instanceof Error ? error.message : 'TTS 测试失败');
    } finally {
      if (playbackAbortRef.current === playbackAbort) {
        playbackAbortRef.current = null;
      }
      if (playbackInterruptRef.current === playbackInterrupt) {
        playbackInterruptRef.current = null;
      }
      setTesting(false);
    }
  };

  const updateTtsSessionConfig = <TKey extends keyof TtsSessionConfig>(key: TKey, value: TtsSessionConfig[TKey]) => {
    setTtsSessionConfig((current) => ({ ...current, [key]: value }));
  };

  const renderVoice = (voice: TtsVoiceRecord) => {
    const checked = selectedVoiceId === voice.id;
    const supported = isTtsVoiceSupportedByModel(selectedModelCode, voice.voiceCode);
    return (
      <div
        key={voice.id}
        role="button"
        tabIndex={0}
        aria-current={checked ? 'true' : undefined}
        aria-disabled={!supported}
        className={`flex w-full items-center gap-3 rounded-lg border bg-white p-3 text-left transition duration-200 ${
          checked ? 'border-brand-500 bg-brand-50/50 ring-1 ring-brand-100' : 'border-slate-200'
        } ${supported ? 'hover:border-brand-300' : 'cursor-not-allowed opacity-60'}`}
        onClick={() => {
          if (supported) setSelectedVoiceId(voice.id);
        }}
        onKeyDown={(e) => {
          if (supported && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            setSelectedVoiceId(voice.id);
          }
        }}
      >
        <Avatar src={voice.avatarPath} icon={<IconHeadphones size={20} />} size={40} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900">{voice.displayName}</span>
            {voice.isDefault ? <Tag color="success" className="m-0 border-0 rounded-md px-2 py-0.5">当前默认</Tag> : null}
            <Tag color={supported ? 'green' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
              {supported ? '可用' : '当前风格不可用'}
            </Tag>
            {supported && modelCapability.supportsInstructionControl ? (
              <Tag color="blue" className="m-0 border-0 rounded-md px-2 py-0.5">支持指令</Tag>
            ) : (
              <Tooltip title="当前音色或播报风格不支持指令控制">
                <Tag color="orange" className="m-0 border-0 rounded-md px-2 py-0.5">不支持指令</Tag>
              </Tooltip>
            )}
          </div>
          <div className="mt-1" onClick={(e) => e.stopPropagation()}>
            <Typography.Text
              copyable={{ text: voice.voiceCode }}
              className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded inline-block"
            >
              {voice.voiceCode}
            </Typography.Text>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {voice.gender === 'female' ? '女声' : voice.gender === 'male' ? '男声' : voice.gender || '-'}
          </div>
        </div>
        <div className={`h-4 w-4 rounded-full border ${checked ? 'border-brand-600 bg-brand-600 shadow-[inset_0_0_0_3px_white]' : 'border-slate-300'}`} />
      </div>
    );
  };

  return (
    <Spin spinning={loading}>
      <div className="space-y-5">
        <div className="page-hero">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
                <IconVolume size={22} />
              </div>
              <div>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Typography.Title level={3} className="m-0 text-lg tracking-normal text-slate-900">
                    TTS 管理
                  </Typography.Title>
                  <Tag color={options?.provider.isActive ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {options?.provider.isActive ? '服务启用' : '服务停用'}
                  </Tag>
                  <Tag color={modelCapability.supportsInstructionControl ? 'blue' : 'orange'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {modelCapability.supportsInstructionControl ? '支持指令控制' : '不支持指令控制'}
                  </Tag>
                </div>
              </div>
            </div>
            <Space wrap>
              <Button icon={<IconRefresh size={16} />} className="rounded-md" loading={loading} onClick={() => void loadOptions()}>
                刷新
              </Button>
              <Button type="primary" icon={<IconDeviceFloppy size={16} />} className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md" loading={saving} onClick={() => void saveDefaultVoice()}>
                保存 TTS 设置
              </Button>
            </Space>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="space-y-4">
            <Card className="rounded-xl border border-slate-100 shadow-card">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <Avatar src={defaultVoice?.avatarPath} icon={<IconHeadphones size={22} />} size={48} />
                  <div>
                    <div className="text-sm font-semibold text-slate-900 mb-1">
                      {defaultVoice?.displayName || '未选择默认音色'}
                    </div>
                    {defaultVoice?.voiceCode ? (
                      <Typography.Text
                        copyable={{ text: defaultVoice.voiceCode }}
                        className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded cursor-pointer inline-block"
                      >
                        {defaultVoice.voiceCode}
                      </Typography.Text>
                    ) : (
                      <div className="text-xs text-slate-400">-</div>
                    )}
                  </div>
                </div>
                {selectedVoice ? (
                  <div className="flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-xs font-medium text-brand-700">
                    <IconCheck size={14} />
                    <span>已选择 {selectedVoice.displayName}</span>
                  </div>
                ) : null}
              </div>
            </Card>

            <Card title="播报参数" className="rounded-xl border border-slate-100 shadow-card">
              <div className="space-y-4">
                <div className="grid gap-3">
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium text-slate-500">播报风格</span>
                    <Select
                      value={selectedModelCode}
                      options={(options?.provider.modelOptions ?? []).map((item) => ({
                        label: item.label,
                        value: item.code,
                      }))}
                      onChange={(value: string) => setSelectedModelCode(value)}
                    />
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="flex justify-between text-xs font-medium text-slate-500"><span>语速</span><span>{ttsSessionConfig.speech_rate.toFixed(2)}</span></div>
                    <Slider min={0.5} max={2} step={0.05} value={ttsSessionConfig.speech_rate} onChange={(value) => updateTtsSessionConfig('speech_rate', typeof value === 'number' ? value : ttsSessionConfig.speech_rate)} />
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-medium text-slate-500"><span>语调</span><span>{ttsSessionConfig.pitch_rate.toFixed(2)}</span></div>
                    <Slider min={0.5} max={2} step={0.05} value={ttsSessionConfig.pitch_rate} onChange={(value) => updateTtsSessionConfig('pitch_rate', typeof value === 'number' ? value : ttsSessionConfig.pitch_rate)} />
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-medium text-slate-500"><span>音量</span><span>{ttsSessionConfig.volume}</span></div>
                    <Slider min={0} max={100} step={1} value={ttsSessionConfig.volume} onChange={(value) => updateTtsSessionConfig('volume', typeof value === 'number' ? value : ttsSessionConfig.volume)} />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-slate-500">指令控制</span>
                  <Input.TextArea
                    value={ttsSessionConfig.instructions}
                    rows={3}
                    maxLength={4000}
                    showCount
                    placeholder="例如：用温柔、自然、略带微笑的语气朗读。支持该能力的播报风格生效。"
                    disabled={Boolean(instructionDisabledReason)}
                    onChange={(event) => updateTtsSessionConfig('instructions', event.target.value)}
                  />
                  {instructionDisabledReason ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                      {instructionDisabledMessage}
                    </div>
                  ) : null}
                  <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
                    <Tooltip title={OPTIMIZE_INSTRUCTIONS_TOOLTIP}>
                      <span className="cursor-help text-sm font-medium text-slate-700">自动优化指令</span>
                    </Tooltip>
                    <Switch checked={ttsSessionConfig.optimize_instructions} disabled={Boolean(instructionDisabledReason) || !ttsSessionConfig.instructions.trim()} onChange={(checked) => updateTtsSessionConfig('optimize_instructions', checked)} />
                  </div>
                </div>
              </div>
            </Card>
          </div>

          <div className="space-y-4">
            <Card title="测试播放" className="rounded-xl border border-slate-100 shadow-card">
              <div className="space-y-4">
                <Input.TextArea
                  rows={5}
                  value={testText}
                  maxLength={500}
                  showCount
                  onChange={(event) => setTestText(event.target.value)}
                  placeholder={options?.defaultTestText || '留空时使用平台默认测试文本'}
                  className="rounded-lg"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="primary"
                    icon={<IconPlayerPlay size={16} />}
                    loading={testing}
                    disabled={testing}
                    className="min-w-[150px] bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md"
                    onClick={() => void handleTest()}
                  >
                    {testing ? '生成中' : '生成测试音频'}
                  </Button>
                  {testing ? (
                    <Button danger className="rounded-md" onClick={stopTestPlayback}>
                      停止
                    </Button>
                  ) : null}
                </div>
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-center text-xs text-slate-400">
                  点击后会按当前参数流式播放测试音频
                </div>
              </div>
            </Card>

            <Card
              title="音色目录"
              extra={<Tag className="m-0 rounded-md border-0">可用 {availableVoices.length} 个</Tag>}
              className="rounded-xl border border-slate-100 shadow-card"
            >
              <div className="space-y-3">
                <Select
                  value={selectedVoiceId ?? undefined}
                  options={availableVoices.map((voice) => ({
                    label: `${voice.displayName} (${voice.voiceCode})`,
                    value: voice.id,
                  }))}
                  placeholder="搜索并选择默认音色"
                  showSearch
                  optionFilterProp="label"
                  className="w-full"
                  onChange={setSelectedVoiceId}
                />
                <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                  {(options?.voices ?? []).map(renderVoice)}
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </Spin>
  );
};
