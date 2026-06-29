import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  AutoComplete,
  Button,
  Card,
  Form,
  Input,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams } from 'react-router-dom';
import {
  IconApi,
  IconArrowLeft,
  IconCheck,
  IconChevronRight,
  IconCloud,
  IconHeadphones,
  IconPlayerPlay,
  IconRefresh,
  IconVolume,
  IconDeviceFloppy,
} from '@tabler/icons-react';
import {
  fetchTtsProviders,
  fetchTtsSettings,
  updateTtsSettings,
  type TtsProviderSummary,
  type TtsSettings,
  type TtsSettingsPayload,
  type TtsSessionConfig,
  type TtsVoiceRecord,
} from '../../api/modules/tts';
import { useAuthStore } from '../../store/auth';
import { playRealtimeTts } from '../tts-realtime-playback';
import {
  DEFAULT_TTS_MODEL_OPTIONS,
  getTtsInstructionDisabledReason,
  getTtsModelCapability,
  isTtsVoiceSupportedByModel,
} from './tts-voice-capabilities';

type TtsSettingsFormValues = {
  apiKey?: string;
  baseUrl: string;
  model: string;
  sampleRate: number;
  ttsSessionConfig: TtsSessionConfig;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
};

const SAMPLE_RATE_OPTIONS = [
  { label: '24kHz PCM 单声道', value: 24000 },
  { label: '16kHz PCM 单声道', value: 16000 },
];
const TTS_LANGUAGE_OPTIONS = [
  { label: '自动识别', value: 'Auto' },
  { label: '中文', value: 'Chinese' },
  { label: '英语', value: 'English' },
  { label: '德语', value: 'German' },
  { label: '意大利语', value: 'Italian' },
  { label: '葡萄牙语', value: 'Portuguese' },
  { label: '西班牙语', value: 'Spanish' },
  { label: '日语', value: 'Japanese' },
  { label: '韩语', value: 'Korean' },
  { label: '法语', value: 'French' },
  { label: '俄语', value: 'Russian' },
] satisfies Array<{ label: string; value: TtsSessionConfig['language_type'] }>;
const TTS_RESPONSE_FORMAT_OPTIONS = [
  { label: 'PCM', value: 'pcm' },
  { label: 'WAV', value: 'wav' },
  { label: 'MP3', value: 'mp3' },
  { label: 'OPUS', value: 'opus' },
] satisfies Array<{ label: string; value: TtsSessionConfig['response_format'] }>;
const TTS_SAMPLE_RATE_VALUES: TtsSessionConfig['sample_rate'][] = [8000, 16000, 24000, 48000];
const TTS_SAMPLE_RATE_OPTIONS: Array<{ label: string; value: TtsSessionConfig['sample_rate'] }> = TTS_SAMPLE_RATE_VALUES.map((value) => ({ label: `${value} Hz`, value }));
const OPTIMIZE_INSTRUCTIONS_TOOLTIP = '开启后会在有指令控制文本时自动优化表达，让语气、情绪和播报风格更清晰；不支持指令控制的模型或音色不会生效。';

const normalizeTtsSessionConfig = (config?: Partial<TtsSessionConfig> | null): TtsSessionConfig => ({
  mode: 'server_commit',
  language_type: config?.language_type ?? 'Auto',
  response_format: config?.response_format ?? 'pcm',
  sample_rate: config?.sample_rate ?? 24000,
  speech_rate: config?.speech_rate ?? 1,
  volume: config?.volume ?? 50,
  pitch_rate: config?.pitch_rate ?? 1,
  bit_rate: config?.bit_rate ?? 128,
  instructions: (config?.instructions || '').trim(),
  optimize_instructions: Boolean(config?.optimize_instructions),
});

export const TtsSettingsPage = () => {
  const [form] = Form.useForm<TtsSettingsFormValues>();
  const { providerCode } = useParams<{ providerCode?: string }>();
  const navigate = useNavigate();
  const activeProviderCode = providerCode?.trim();
  const isProviderListMode = !activeProviderCode;
  const [providers, setProviders] = useState<TtsProviderSummary[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [settings, setSettings] = useState<TtsSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [testText, setTestText] = useState('');
  const token = useAuthStore((state) => state.token);
  const selectedModel = Form.useWatch('model', form);
  const selectedDefaultVoiceId = Form.useWatch('defaultVoiceId', form);
  const selectedCapability = useMemo(() => getTtsModelCapability(selectedModel || settings?.model || ''), [selectedModel, settings?.model]);
  const selectedDefaultVoice = useMemo(
    () => settings?.voices.find((voice) => voice.id === selectedDefaultVoiceId) ?? null,
    [selectedDefaultVoiceId, settings?.voices],
  );
  const instructionDisabledReason = getTtsInstructionDisabledReason(selectedModel || settings?.model || '', selectedDefaultVoice?.voiceCode);

  const setAudioBlob = useCallback((blob: Blob) => {
    setAudioUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(blob);
    });
  }, []);

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  const loadProviders = useCallback(async () => {
    setProvidersLoading(true);
    try {
      const data = await fetchTtsProviders();
      setProviders(data);
    } finally {
      setProvidersLoading(false);
    }
  }, []);

  const loadSettings = useCallback(async () => {
    if (!activeProviderCode) {
      return;
    }
    setLoading(true);
    try {
      const data = await fetchTtsSettings(activeProviderCode);
      setSettings(data);
      form.setFieldsValue({
        apiKey: '',
        baseUrl: data.baseUrl,
        model: data.model,
        sampleRate: data.sampleRate,
        ttsSessionConfig: normalizeTtsSessionConfig(data.ttsSessionConfig),
        defaultVoiceId: data.defaultVoiceId,
        defaultTestText: data.defaultTestText,
        isActive: data.isActive,
      });
    } finally {
      setLoading(false);
    }
  }, [activeProviderCode, form]);

  useEffect(() => {
    if (isProviderListMode) {
      setSettings(null);
      void loadProviders();
      return;
    }
    void loadSettings();
  }, [isProviderListMode, loadProviders, loadSettings]);

  const voiceOptions = useMemo(
    () =>
      settings?.voices
        .filter((voice) => isTtsVoiceSupportedByModel(selectedModel || settings.model, voice.voiceCode))
        .map((voice) => ({ label: `${voice.displayName} (${voice.voiceCode})`, value: voice.id })) ?? [],
    [selectedModel, settings],
  );

  useEffect(() => {
    if (!settings || !selectedDefaultVoiceId) {
      return;
    }
    const selectedVoice = settings.voices.find((voice) => voice.id === selectedDefaultVoiceId);
    if (selectedVoice && !isTtsVoiceSupportedByModel(selectedModel || settings.model, selectedVoice.voiceCode)) {
      form.setFieldsValue({ defaultVoiceId: null });
    }
  }, [form, selectedDefaultVoiceId, selectedModel, settings]);

  const handleSave = async () => {
    if (!activeProviderCode) {
      return;
    }
    const values = await form.validateFields();
    const payload: TtsSettingsPayload = { ...values };
    payload.ttsSessionConfig = normalizeTtsSessionConfig(values.ttsSessionConfig);
    if (!payload.apiKey?.trim()) {
      delete payload.apiKey;
    }
    const selectedVoice = settings?.voices.find((voice) => voice.id === values.defaultVoiceId);
    const disabledReason = getTtsInstructionDisabledReason(values.model, selectedVoice?.voiceCode);
    if (disabledReason && payload.ttsSessionConfig) {
      payload.ttsSessionConfig = {
        ...payload.ttsSessionConfig,
        instructions: '',
        optimize_instructions: false,
      };
      form.setFieldValue(['ttsSessionConfig', 'instructions'], '');
      form.setFieldValue(['ttsSessionConfig', 'optimize_instructions'], false);
    }

    setSaving(true);
    try {
      const data = await updateTtsSettings(payload, activeProviderCode);
      setSettings(data);
      form.setFieldsValue({ ...values, ttsSessionConfig: normalizeTtsSessionConfig(data.ttsSessionConfig), apiKey: '' });
      message.success('TTS 设置已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleVoicePatch = async (voiceId: number, patch: Partial<TtsVoiceRecord>) => {
    if (!activeProviderCode) {
      return;
    }
    const data = await updateTtsSettings({ voices: [{ id: voiceId, ...patch }] }, activeProviderCode);
    setSettings(data);
  };

  const handleDefaultVoice = async (voiceId: number) => {
    if (!activeProviderCode) {
      return;
    }
    const data = await updateTtsSettings({ defaultVoiceId: voiceId }, activeProviderCode);
    setSettings(data);
    form.setFieldsValue({ defaultVoiceId: voiceId });
    message.success('默认音色已更新');
  };

  const handleTest = async () => {
    if (!activeProviderCode) {
      return;
    }
    if (!token) {
      message.error('登录状态已失效，请重新登录');
      return;
    }
    const voiceId = form.getFieldValue('defaultVoiceId');
    setTesting(true);
    try {
      const playbackText = testText.trim() || form.getFieldValue('defaultTestText') || settings?.defaultTestText || '';
      const sessionConfig = form.getFieldValue('ttsSessionConfig') || settings?.ttsSessionConfig;
      const { blob } = await playRealtimeTts({ text: playbackText, voiceId, token, providerCode: activeProviderCode, sessionConfig });
      if (blob.size <= 44) {
        message.error('TTS 未返回有效音频');
        return;
      }
      setAudioBlob(blob);
      message.success('TTS 测试音频已播放');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'TTS 测试失败');
    } finally {
      setTesting(false);
    }
  };

  const columns: ColumnsType<TtsVoiceRecord> = [
    {
      title: '音色',
      dataIndex: 'displayName',
      render: (value: string, record) => (
        <div className="flex items-center gap-3">
          <Avatar src={record.avatarPath} icon={<IconHeadphones size={20} />} size={40} />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-800 mb-1">{value}</div>
            <Typography.Text
              copyable={{ text: record.voiceCode }}
              className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded cursor-pointer"
            >
              {record.voiceCode}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: '性别',
      dataIndex: 'gender',
      width: 100,
      render: (value: string) => (
        <Tag color={value === 'female' ? 'magenta' : value === 'male' ? 'cyan' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
          {value === 'female' ? '女声' : value === 'male' ? '男声' : value || '-'}
        </Tag>
      ),
    },
    {
      title: '模型支持',
      width: 150,
      render: (_, record) => {
        const supported = isTtsVoiceSupportedByModel(selectedModel || settings?.model || '', record.voiceCode);
        return (
          <Space size={6} wrap>
            <Tag color={supported ? 'green' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
              {supported ? '当前模型可用' : '当前模型不可用'}
            </Tag>
            {supported && selectedCapability.supportsInstructionControl ? (
              <Tag color="blue" className="m-0 border-0 rounded-md px-2 py-0.5">支持指令</Tag>
            ) : (
              <Tooltip title={getTtsInstructionDisabledReason(selectedModel || settings?.model || '', record.voiceCode) || '当前音色不支持指令控制'}>
                <Tag color="orange" className="m-0 border-0 rounded-md px-2 py-0.5">不支持指令</Tag>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: '默认',
      dataIndex: 'isDefault',
      width: 96,
      render: (value: boolean, record) => {
        const supported = isTtsVoiceSupportedByModel(selectedModel || settings?.model || '', record.voiceCode);
        return value ? (
          <Tag color="success" className="m-0 border-0 rounded-md">默认</Tag>
        ) : (
          <Button size="small" className="rounded-md" disabled={!supported} onClick={() => void handleDefaultVoice(record.id)}>
            设为默认
          </Button>
        );
      },
    },
    {
      title: '启用',
      dataIndex: 'isActive',
      width: 96,
      render: (value: boolean | undefined, record) => (
        <Switch
          checked={Boolean(value)}
          size="small"
          onChange={(checked) => void handleVoicePatch(record.id, { isActive: checked })}
        />
      ),
    },
    {
      title: '公司可见',
      dataIndex: 'isVisible',
      width: 112,
      render: (value: boolean | undefined, record) => (
        <Switch
          checked={Boolean(value)}
          size="small"
          onChange={(checked) => void handleVoicePatch(record.id, { isVisible: checked })}
        />
      ),
    },
  ];

  if (isProviderListMode) {
    return (
      <div className="space-y-5">
        <div className="page-hero">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
                <IconVolume size={22} />
              </div>
              <div>
                <Typography.Title level={3} className="!m-0 !text-lg !tracking-normal !text-slate-900">
                  TTS 设置
                </Typography.Title>
                <div className="mt-1 text-xs text-slate-500 font-mono">供应商 {providers.length} 个</div>
              </div>
            </div>
            <Button icon={<IconRefresh size={16} />} loading={providersLoading} className="rounded-md" onClick={() => void loadProviders()}>
              同步状态
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {providersLoading && providers.length === 0 ? (
            <Card loading className="min-h-[180px] rounded-xl border border-slate-100 shadow-card" />
          ) : null}

          {providers.map((provider) => (
            <Card
              key={provider.code}
              hoverable
              className="rounded-xl border border-slate-100 shadow-card hover:shadow-card-hover transition-all duration-200"
              onClick={() => navigate(`/settings/tts/${provider.code}`)}
            >
              <div className="flex h-full flex-col gap-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
                      <IconCloud size={20} />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-base font-semibold text-slate-900 mb-1">{provider.name}</div>
                      <div onClick={(e) => e.stopPropagation()}>
                        <Typography.Text
                          copyable={{ text: provider.code }}
                          className="font-mono text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded cursor-pointer"
                        >
                          {provider.code}
                        </Typography.Text>
                      </div>
                    </div>
                  </div>
                  <IconChevronRight size={18} className="mt-3 shrink-0 text-slate-300" />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Tag color={provider.isActive ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {provider.isActive ? '已启用' : '已停用'}
                  </Tag>
                  <Tag color={provider.configured ? 'cyan' : 'warning'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {provider.configured ? '配置完整' : '配置缺失'}
                  </Tag>
                  {provider.defaultVoiceName ? (
                    <Tag icon={<IconCheck size={12} />} color="processing" className="m-0 border-0 rounded-md px-2 py-0.5">
                      {provider.defaultVoiceName}
                    </Tag>
                  ) : null}
                </div>

                <div className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                  <div>
                    <div className="font-medium text-slate-900">{provider.sampleRate}Hz</div>
                    <div>返回采样率</div>
                  </div>
                  <div>
                    <div className="font-medium text-slate-900">{provider.voiceCount}</div>
                    <div>内置音色</div>
                  </div>
                </div>
              </div>
            </Card>
          ))}

          {!providersLoading && providers.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-400">
              暂无 TTS 供应商
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-700">
              <IconVolume size={22} />
            </div>
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Typography.Title level={3} className="!m-0 !text-lg !tracking-normal !text-slate-900">
                  {settings?.name || 'TTS Provider'}
                </Typography.Title>
                <Tag color={settings?.isActive ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                  {settings?.isActive ? '已启用' : '已停用'}
                </Tag>
                <Tag color={settings?.configured ? 'cyan' : 'warning'} className="m-0 border-0 rounded-md px-2 py-0.5">
                  {settings?.configured ? '配置完整' : '配置缺失'}
                </Tag>
              </div>
              <div className="text-xs text-slate-500 font-mono">
                {settings?.code || activeProviderCode || '-'} · {settings?.ttsSessionConfig.sample_rate || settings?.sampleRate || 24000}Hz · {(settings?.ttsSessionConfig.response_format || 'pcm').toUpperCase()}
              </div>
            </div>
          </div>
          <Space wrap>
            <Button icon={<IconArrowLeft size={16} />} className="rounded-md" onClick={() => navigate('/settings/tts')}>
              返回供应商
            </Button>
            <Button icon={<IconRefresh size={16} />} className="rounded-md" loading={loading} onClick={() => void loadSettings()}>
              同步状态
            </Button>
          </Space>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card title={settings?.name || 'TTS Provider'} loading={loading} className="rounded-xl border border-slate-100 shadow-card">
          <Form form={form} layout="vertical" requiredMark="optional">
            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item name="apiKey" label="API Key" tooltip="留空表示不修改当前密钥">
                <Input.Password
                  autoComplete="new-password"
                  placeholder={settings?.apiKeyConfigured ? settings.apiKeyMasked : '请输入 DashScope API Key'}
                  className="font-mono rounded-lg"
                />
              </Form.Item>
              <Form.Item
                name="model"
                label="模型名称"
                rules={[{ required: true, message: '请输入模型名称' }]}
                tooltip="可从默认模型中选择，也可以直接编辑为新的模型名称。"
              >
                <AutoComplete
                  showSearch
                  allowClear
                  options={DEFAULT_TTS_MODEL_OPTIONS.map((option) => ({
                    label: (
                      <div className="flex flex-col gap-1 py-1">
                        <span className="font-mono text-xs">{option.value}</span>
                        <span className="text-[11px] text-slate-500">
                          {option.supportsInstructionControl ? '支持指令控制' : '不支持指令控制'}
                        </span>
                      </div>
                    ),
                    value: option.value,
                  }))}
                  placeholder="qwen3-tts-flash-realtime"
                  className="rounded-lg"
                  popupMatchSelectWidth={false}
                />
              </Form.Item>
            </div>

            <Form.Item name="baseUrl" label="WebSocket URL" rules={[{ required: true, message: '请输入 WebSocket URL' }]}>
              <Input placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime" className="font-mono rounded-lg" />
            </Form.Item>

            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item name="sampleRate" label="返回采样率" rules={[{ required: true, message: '请选择采样率' }]}>
                <Select options={SAMPLE_RATE_OPTIONS} className="rounded-lg" />
              </Form.Item>
              <Form.Item name="defaultVoiceId" label="平台默认音色">
                <Select options={voiceOptions} placeholder="请选择默认音色" showSearch optionFilterProp="label" className="rounded-lg" />
              </Form.Item>
            </div>

            <div className="mb-5 rounded-xl border border-slate-100 bg-slate-50/60 p-4">
              <div className="mb-4">
                <div className="text-sm font-semibold text-slate-800">Qwen TTS Realtime 参数</div>
                <div className="mt-1 text-xs text-slate-500">集中配置阿里云 session.update 参数，智能体和设备运行时会复用这里的 TTS 会话配置。</div>
              </div>
              <div className="grid gap-x-4 md:grid-cols-2">
                <Form.Item name={['ttsSessionConfig', 'language_type']} label="语种" rules={[{ required: true, message: '请选择语种' }]}>
                  <Select options={TTS_LANGUAGE_OPTIONS} className="rounded-lg" />
                </Form.Item>
                <Form.Item name={['ttsSessionConfig', 'response_format']} label="音频格式" rules={[{ required: true, message: '请选择音频格式' }]}>
                  <Select options={TTS_RESPONSE_FORMAT_OPTIONS} className="rounded-lg" />
                </Form.Item>
                <Form.Item name={['ttsSessionConfig', 'sample_rate']} label="会话采样率" rules={[{ required: true, message: '请选择会话采样率' }]}>
                  <Select options={TTS_SAMPLE_RATE_OPTIONS} className="rounded-lg" />
                </Form.Item>
              </div>
              <div className="mb-4 flex flex-wrap gap-2">
                <Tag color="processing" className="m-0 border-0 rounded-md px-2 py-0.5">
                  {selectedCapability.label}
                </Tag>
                <Tag color={selectedCapability.supportsInstructionControl ? 'blue' : 'orange'} className="m-0 border-0 rounded-md px-2 py-0.5">
                  {selectedCapability.supportsInstructionControl ? '模型支持指令控制' : '模型不支持指令控制'}
                </Tag>
                <Tag color="default" className="m-0 border-0 rounded-md px-2 py-0.5">
                  可用音色 {voiceOptions.length} 个
                </Tag>
              </div>
              <div className="grid gap-x-6 md:grid-cols-2">
                <Form.Item name={['ttsSessionConfig', 'speech_rate']} label="语速" rules={[{ required: true, message: '请设置语速' }]}>
                  <Slider min={0.5} max={2} step={0.05} />
                </Form.Item>
                <Form.Item name={['ttsSessionConfig', 'pitch_rate']} label="语调" rules={[{ required: true, message: '请设置语调' }]}>
                  <Slider min={0.5} max={2} step={0.05} />
                </Form.Item>
                <Form.Item name={['ttsSessionConfig', 'volume']} label="音量" rules={[{ required: true, message: '请设置音量' }]}>
                  <Slider min={0} max={100} step={1} />
                </Form.Item>
              </div>
              <Form.Item name={['ttsSessionConfig', 'instructions']} label="指令控制">
                <Input.TextArea
                  rows={3}
                  showCount
                  maxLength={4000}
                  disabled={Boolean(instructionDisabledReason)}
                  placeholder="例如：用温柔、自然、略带微笑的语气朗读。仅情感增强系列生效。"
                  className="rounded-lg"
                />
              </Form.Item>
              {instructionDisabledReason ? (
                <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {instructionDisabledReason}
                </div>
              ) : null}
              <Form.Item noStyle shouldUpdate={(prev, next) => prev.ttsSessionConfig?.instructions !== next.ttsSessionConfig?.instructions}>
                {({ getFieldValue }) => (
                  <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-3 py-2">
                    <Tooltip title={OPTIMIZE_INSTRUCTIONS_TOOLTIP}>
                      <span className="cursor-help text-sm font-medium text-slate-700">自动优化指令</span>
                    </Tooltip>
                    <Form.Item name={['ttsSessionConfig', 'optimize_instructions']} valuePropName="checked" noStyle>
                      <Switch disabled={Boolean(instructionDisabledReason) || !String(getFieldValue(['ttsSessionConfig', 'instructions']) || '').trim()} />
                    </Form.Item>
                  </div>
                )}
              </Form.Item>
            </div>

            <Form.Item name="defaultTestText" label="默认测试文本" rules={[{ required: true, message: '请输入默认测试文本' }]}>
              <Input.TextArea rows={4} showCount maxLength={500} className="rounded-lg" />
            </Form.Item>

            <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <Form.Item name="isActive" valuePropName="checked" noStyle>
                <Switch checkedChildren="启用" unCheckedChildren="停用" className="shadow-sm" />
              </Form.Item>
              <Space wrap>
                <Button type="primary" icon={<IconDeviceFloppy size={16} />} className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md" loading={saving} onClick={() => void handleSave()}>
                  保存设置
                </Button>
                <Button icon={<IconApi size={16} />} className="rounded-md" loading={testing} onClick={() => void handleTest()}>
                  测试 TTS
                </Button>
              </Space>
            </div>
          </Form>
        </Card>

        <Card title="测试播放" className="rounded-xl border border-slate-100 shadow-card">
          <div className="space-y-4">
            <Input.TextArea
              rows={6}
              value={testText}
              maxLength={500}
              showCount
              onChange={(event) => setTestText(event.target.value)}
              placeholder={settings?.defaultTestText || '留空时使用默认测试文本'}
              className="rounded-lg"
            />
            <Button
              type="primary"
              icon={<IconPlayerPlay size={16} />}
              loading={testing}
              block
              className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md"
              onClick={() => void handleTest()}
            >
              生成测试音频
            </Button>
            {audioUrl ? (
              <audio controls src={audioUrl} className="w-full mt-2" />
            ) : (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-400">
                暂无测试音频
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card title="内置音色目录" className="rounded-xl border border-slate-100 shadow-card">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={settings?.voices ?? []}
          loading={loading}
          pagination={{ pageSize: 12, showSizeChanger: false }}
          scroll={{ x: 'max-content' }}
        />
      </Card>
    </div>
  );
};
