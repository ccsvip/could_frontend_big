import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Button, Card, Empty, Input, Select, Slider, Space, Spin, Switch, Tag, Tooltip, Typography, message } from 'antd';
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
  type TtsCardSummary,
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
const ALIYUN_CARD_CODE = 'aliyun';

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

/** Find the card a voice belongs to, tolerating the pre-`providers` payload. */
const findCardForVoice = (options: CompanyTtsOptions | null, voice: TtsVoiceRecord | null): TtsCardSummary | null => {
  if (!options || !voice) return null;
  const cards = options.providers ?? [];
  return cards.find((card) => card.id === voice.providerId || card.code === voice.providerCode) ?? null;
};

/**
 * Only submit fields the selected card declares. Prevents one card's controls
 * (say Qwen's `instructions`) from being posted against another card, which the
 * backend rejects.
 */
const pickSchemaFields = (card: TtsCardSummary | null, config: TtsSessionConfig): Record<string, unknown> => {
  const names = card?.publicConfigSchema?.fields?.map((field) => field.name);
  if (!names || names.length === 0) {
    return { ...config };
  }
  const allowed: Record<string, unknown> = {};
  names.forEach((name) => {
    const value = (config as unknown as Record<string, unknown>)[name];
    if (value !== undefined) {
      allowed[name] = value;
    }
  });
  return allowed;
};

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

  const applyOptions = useCallback((data: CompanyTtsOptions) => {
    setOptions(data);
    setSelectedVoiceId(data.defaultVoiceId);
    setSelectedModelCode(data.provider.defaultModelCode || 'instructional');
    setTtsSessionConfig(normalizeTtsSessionConfig(data.ttsSessionConfig));
  }, []);

  const loadOptions = useCallback(async () => {
    setLoading(true);
    try {
      applyOptions(await fetchCompanyTtsOptions());
    } finally {
      setLoading(false);
    }
  }, [applyOptions]);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const selectedVoice = useMemo(
    () => options?.voices.find((voice) => voice.id === selectedVoiceId) ?? null,
    [options?.voices, selectedVoiceId],
  );
  const selectedCard = useMemo(() => findCardForVoice(options, selectedVoice), [options, selectedVoice]);
  const schemaFieldNames = useMemo(
    () => new Set((selectedCard?.publicConfigSchema?.fields ?? []).map((field) => field.name)),
    [selectedCard],
  );
  /** Cards that publish no schema are treated as the legacy Qwen shape. */
  const supportsField = useCallback(
    (name: keyof TtsSessionConfig) => schemaFieldNames.size === 0 || schemaFieldNames.has(name),
    [schemaFieldNames],
  );

  const isQwenCard = !selectedCard || selectedCard.code === ALIYUN_CARD_CODE;
  const modelCapability = useMemo(() => getTtsModelCapability(selectedModelCode), [selectedModelCode]);
  const instructionDisabledReason = isQwenCard
    ? getTtsInstructionDisabledReason(selectedModelCode, selectedVoice?.voiceCode)
    : '当前 TTS 卡片不支持指令控制';
  const instructionDisabledMessage = instructionDisabledReason ? '当前音色或播报风格不支持指令控制。' : '';
  const modelOptions = selectedCard?.modelOptions ?? options?.provider.modelOptions ?? [];

  /** Qwen narrows voices by playback profile; other cards do not share that vocabulary. */
  const isVoiceSelectable = useCallback(
    (voice: TtsVoiceRecord) => {
      const card = findCardForVoice(options, voice);
      if (card && card.code !== ALIYUN_CARD_CODE) return true;
      return isTtsVoiceSupportedByModel(selectedModelCode, voice.voiceCode);
    },
    [options, selectedModelCode],
  );

  const availableVoices = useMemo(
    () => (options?.voices ?? []).filter(isVoiceSelectable),
    [options?.voices, isVoiceSelectable],
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
    if (voice && !isVoiceSelectable(voice)) {
      setSelectedVoiceId(null);
    }
  }, [options, selectedVoiceId, isVoiceSelectable]);

  const saveDefaultVoice = async () => {
    if (!selectedVoiceId) {
      message.warning('请选择音色');
      return;
    }
    const normalized = normalizeTtsSessionConfig(ttsSessionConfig);
    if (isQwenCard) {
      normalized.model_code = selectedModelCode;
      if (instructionDisabledReason) {
        normalized.instructions = '';
        normalized.optimize_instructions = false;
        setTtsSessionConfig(normalized);
      }
    }
    setSaving(true);
    try {
      const data = await updateCompanyDefaultTtsVoice(
        selectedVoiceId,
        pickSchemaFields(selectedCard, normalized) as TtsSessionConfig,
        isQwenCard ? selectedModelCode : undefined,
      );
      applyOptions(data);
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
      const normalized = normalizeTtsSessionConfig(ttsSessionConfig);
      if (isQwenCard) {
        normalized.model_code = selectedModelCode;
      }
      if (instructionDisabledReason) {
        normalized.instructions = '';
        normalized.optimize_instructions = false;
      }
      const sessionConfig = {
        ...(pickSchemaFields(selectedCard, normalized) as TtsSessionConfig),
        response_format: 'pcm' as const,
      };
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
    const selectable = isVoiceSelectable(voice);
    const card = findCardForVoice(options, voice);
    const cardIsQwen = !card || card.code === ALIYUN_CARD_CODE;
    return (
      <div
        key={voice.id}
        role="button"
        tabIndex={0}
        aria-current={checked ? 'true' : undefined}
        aria-disabled={!selectable}
        className={`flex w-full items-center gap-3 rounded-lg border bg-white p-3 text-left transition duration-200 ${
          checked ? 'border-brand-500 bg-brand-50/50 ring-1 ring-brand-100' : 'border-slate-200'
        } ${selectable ? 'hover:border-brand-300' : 'cursor-not-allowed opacity-60'}`}
        onClick={() => {
          if (selectable) setSelectedVoiceId(voice.id);
        }}
        onKeyDown={(e) => {
          if (selectable && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            setSelectedVoiceId(voice.id);
          }
        }}
      >
        <Avatar src={voice.avatarPath} icon={<IconHeadphones size={20} />} size={40} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900">{voice.displayName}</span>
            {voice.providerName ? (
              <Tag className="m-0 border-0 rounded-md px-2 py-0.5">{voice.providerName}</Tag>
            ) : null}
            {voice.isDefault ? <Tag color="success" className="m-0 border-0 rounded-md px-2 py-0.5">当前默认</Tag> : null}
            <Tag color={selectable ? 'green' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
              {selectable ? '可用' : '当前风格不可用'}
            </Tag>
            {cardIsQwen && selectable && modelCapability.supportsInstructionControl ? (
              <Tag color="blue" className="m-0 border-0 rounded-md px-2 py-0.5">支持指令</Tag>
            ) : null}
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

  const voiceSelectGroups = useMemo(() => {
    const cards = options?.providers ?? [];
    if (cards.length > 0) {
      return cards
        .map((card) => ({
          label: card.name,
          options: card.voices.filter(isVoiceSelectable).map((voice) => ({
            label: `${voice.displayName} (${voice.voiceCode})`,
            value: voice.id,
          })),
        }))
        .filter((group) => group.options.length > 0);
    }
    // Migration window: the payload may predate `providers`.
    return [
      {
        label: options?.provider.name || '可用音色',
        options: availableVoices.map((voice) => ({
          label: `${voice.displayName} (${voice.voiceCode})`,
          value: voice.id,
        })),
      },
    ];
  }, [options?.providers, options?.provider.name, availableVoices, isVoiceSelectable]);

  const hasAuthorizedVoices = (options?.voices?.length ?? 0) > 0;

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
                  <Tag color={hasAuthorizedVoices ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {hasAuthorizedVoices ? `已授权 ${options?.providers?.length ?? 1} 张卡片` : '未分配 TTS 卡片'}
                  </Tag>
                  {selectedCard ? (
                    <Tag color="blue" className="m-0 border-0 rounded-md px-2 py-0.5">{selectedCard.name}</Tag>
                  ) : null}
                </div>
              </div>
            </div>
            <Space wrap>
              <Button icon={<IconRefresh size={16} />} className="rounded-md" loading={loading} onClick={() => void loadOptions()}>
                刷新
              </Button>
              <Button
                type="primary"
                icon={<IconDeviceFloppy size={16} />}
                className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md"
                loading={saving}
                disabled={!hasAuthorizedVoices}
                onClick={() => void saveDefaultVoice()}
              >
                保存 TTS 设置
              </Button>
            </Space>
          </div>
        </div>

        {!loading && !hasAuthorizedVoices ? (
          <Card className="rounded-xl border border-slate-100 shadow-card">
            <Empty description="当前公司还没有可用的 TTS 音色，请联系平台超管分配 TTS 卡片" />
          </Card>
        ) : (
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

              <Card
                title="播报参数"
                extra={selectedCard ? <Tag className="m-0 rounded-md border-0">{selectedCard.name} 配置</Tag> : null}
                className="rounded-xl border border-slate-100 shadow-card"
              >
                <div className="space-y-4">
                  {supportsField('model_code') && modelOptions.length > 0 ? (
                    <div className="grid gap-3">
                      <div className="flex flex-col gap-1.5">
                        <span className="text-xs font-medium text-slate-500">播报风格</span>
                        <Select
                          value={selectedModelCode}
                          options={modelOptions.map((item) => ({ label: item.label, value: item.code }))}
                          onChange={(value: string) => setSelectedModelCode(value)}
                        />
                      </div>
                    </div>
                  ) : null}
                  <div className="grid gap-4 md:grid-cols-2">
                    {supportsField('speech_rate') ? (
                      <div>
                        <div className="flex justify-between text-xs font-medium text-slate-500"><span>语速</span><span>{ttsSessionConfig.speech_rate.toFixed(2)}</span></div>
                        <Slider min={0.5} max={2} step={0.05} value={ttsSessionConfig.speech_rate} onChange={(value) => updateTtsSessionConfig('speech_rate', typeof value === 'number' ? value : ttsSessionConfig.speech_rate)} />
                      </div>
                    ) : null}
                    {supportsField('pitch_rate') ? (
                      <div>
                        <div className="flex justify-between text-xs font-medium text-slate-500"><span>语调</span><span>{ttsSessionConfig.pitch_rate.toFixed(2)}</span></div>
                        <Slider min={0.5} max={2} step={0.05} value={ttsSessionConfig.pitch_rate} onChange={(value) => updateTtsSessionConfig('pitch_rate', typeof value === 'number' ? value : ttsSessionConfig.pitch_rate)} />
                      </div>
                    ) : null}
                    {supportsField('volume') ? (
                      <div>
                        <div className="flex justify-between text-xs font-medium text-slate-500"><span>音量</span><span>{ttsSessionConfig.volume}</span></div>
                        <Slider min={0} max={100} step={1} value={ttsSessionConfig.volume} onChange={(value) => updateTtsSessionConfig('volume', typeof value === 'number' ? value : ttsSessionConfig.volume)} />
                      </div>
                    ) : null}
                  </div>
                  {supportsField('instructions') ? (
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
                  ) : null}
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
                    options={voiceSelectGroups}
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
        )}
      </div>
    </Spin>
  );
};
