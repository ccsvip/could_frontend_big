import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ApiOutlined,
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloudOutlined,
  CustomerServiceOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RightOutlined,
  SaveOutlined,
  SoundOutlined,
} from '@ant-design/icons';
import {
  fetchTtsProviders,
  fetchTtsSettings,
  testPlatformTts,
  updateTtsSettings,
  type TtsProviderSummary,
  type TtsSettings,
  type TtsSettingsPayload,
  type TtsVoiceRecord,
} from '../../api/modules/tts';

type TtsSettingsFormValues = {
  apiKey?: string;
  baseUrl: string;
  model: string;
  sampleRate: number;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
};

const SAMPLE_RATE_OPTIONS = [
  { label: '24kHz PCM 单声道', value: 24000 },
  { label: '16kHz PCM 单声道', value: 16000 },
];

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
    () => settings?.voices.map((voice) => ({ label: `${voice.displayName} (${voice.voiceCode})`, value: voice.id })) ?? [],
    [settings?.voices],
  );

  const handleSave = async () => {
    if (!activeProviderCode) {
      return;
    }
    const values = await form.validateFields();
    const payload: TtsSettingsPayload = { ...values };
    if (!payload.apiKey?.trim()) {
      delete payload.apiKey;
    }

    setSaving(true);
    try {
      const data = await updateTtsSettings(payload, activeProviderCode);
      setSettings(data);
      form.setFieldsValue({ ...values, apiKey: '' });
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
    const voiceId = form.getFieldValue('defaultVoiceId');
    setTesting(true);
    try {
      const blob = await testPlatformTts({ text: testText, voiceId }, activeProviderCode);
      setAudioBlob(blob);
      message.success('TTS 测试音频已生成');
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
          <Avatar src={record.avatarPath} icon={<CustomerServiceOutlined />} size={40} />
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
      title: '默认',
      dataIndex: 'isDefault',
      width: 96,
      render: (value: boolean, record) => (
        value ? (
          <Tag color="success" className="m-0 border-0 rounded-md">默认</Tag>
        ) : (
          <Button size="small" className="rounded-md" onClick={() => void handleDefaultVoice(record.id)}>
            设为默认
          </Button>
        )
      ),
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
                <SoundOutlined className="text-xl" />
              </div>
              <div>
                <Typography.Title level={3} className="!m-0 !text-lg !tracking-normal !text-slate-900">
                  TTS 设置
                </Typography.Title>
                <div className="mt-1 text-xs text-slate-500 font-mono">供应商 {providers.length} 个</div>
              </div>
            </div>
            <Button icon={<ReloadOutlined />} loading={providersLoading} className="rounded-md" onClick={() => void loadProviders()}>
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
                      <CloudOutlined className="text-lg" />
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
                  <RightOutlined className="mt-3 shrink-0 text-slate-300" />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Tag color={provider.isActive ? 'success' : 'default'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {provider.isActive ? '已启用' : '已停用'}
                  </Tag>
                  <Tag color={provider.configured ? 'cyan' : 'warning'} className="m-0 border-0 rounded-md px-2 py-0.5">
                    {provider.configured ? '配置完整' : '配置缺失'}
                  </Tag>
                  {provider.defaultVoiceName ? (
                    <Tag icon={<CheckCircleOutlined />} color="processing" className="m-0 border-0 rounded-md px-2 py-0.5">
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
              <SoundOutlined className="text-xl" />
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
                {settings?.code || activeProviderCode || '-'} · {settings?.sampleRate || 24000}Hz · PCM 单声道
              </div>
            </div>
          </div>
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />} className="rounded-md" onClick={() => navigate('/settings/tts')}>
              返回供应商
            </Button>
            <Button icon={<ReloadOutlined />} className="rounded-md" loading={loading} onClick={() => void loadSettings()}>
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
              <Form.Item name="model" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
                <Input placeholder="qwen3-tts-flash-realtime" className="font-mono rounded-lg" />
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

            <Form.Item name="defaultTestText" label="默认测试文本" rules={[{ required: true, message: '请输入默认测试文本' }]}>
              <Input.TextArea rows={4} showCount maxLength={500} className="rounded-lg" />
            </Form.Item>

            <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <Form.Item name="isActive" valuePropName="checked" noStyle>
                <Switch checkedChildren="启用" unCheckedChildren="停用" className="shadow-sm" />
              </Form.Item>
              <Space wrap>
                <Button type="primary" icon={<SaveOutlined />} className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-md" loading={saving} onClick={() => void handleSave()}>
                  保存设置
                </Button>
                <Button icon={<ApiOutlined />} className="rounded-md" loading={testing} onClick={() => void handleTest()}>
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
              icon={<PlayCircleOutlined />}
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
