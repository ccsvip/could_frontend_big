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
import {
  ApiOutlined,
  CustomerServiceOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  SoundOutlined,
} from '@ant-design/icons';
import {
  fetchTtsSettings,
  testPlatformTts,
  updateTtsSettings,
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

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTtsSettings();
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
  }, [form]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const voiceOptions = useMemo(
    () => settings?.voices.map((voice) => ({ label: `${voice.displayName} (${voice.voiceCode})`, value: voice.id })) ?? [],
    [settings?.voices],
  );

  const handleSave = async () => {
    const values = await form.validateFields();
    const payload: TtsSettingsPayload = { ...values };
    if (!payload.apiKey?.trim()) {
      delete payload.apiKey;
    }

    setSaving(true);
    try {
      const data = await updateTtsSettings(payload);
      setSettings(data);
      form.setFieldsValue({ ...values, apiKey: '' });
      message.success('TTS 设置已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleVoicePatch = async (voiceId: number, patch: Partial<TtsVoiceRecord>) => {
    const data = await updateTtsSettings({ voices: [{ id: voiceId, ...patch }] });
    setSettings(data);
  };

  const handleDefaultVoice = async (voiceId: number) => {
    const data = await updateTtsSettings({ defaultVoiceId: voiceId });
    setSettings(data);
    form.setFieldsValue({ defaultVoiceId: voiceId });
    message.success('默认音色已更新');
  };

  const handleTest = async () => {
    const voiceId = form.getFieldValue('defaultVoiceId');
    setTesting(true);
    try {
      const blob = await testPlatformTts({ text: testText, voiceId });
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
            <div className="truncate text-sm font-semibold text-slate-800">{value}</div>
            <code className="text-xs text-slate-500">{record.voiceCode}</code>
          </div>
        </div>
      ),
    },
    {
      title: '性别',
      dataIndex: 'gender',
      width: 100,
      render: (value: string) => <Tag color={value === 'female' ? 'magenta' : 'blue'}>{value || '-'}</Tag>,
    },
    {
      title: '默认',
      dataIndex: 'isDefault',
      width: 96,
      render: (value: boolean, record) => (
        value ? (
          <Tag color="success" className="m-0">默认</Tag>
        ) : (
          <Button size="small" onClick={() => void handleDefaultVoice(record.id)}>
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

  return (
    <div className="space-y-5">
      <div className="page-hero">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-teal-100 bg-teal-50 text-teal-700">
              <SoundOutlined className="text-xl" />
            </div>
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <Typography.Title level={3} className="!m-0 !text-lg !tracking-normal !text-slate-900">
                  TTS 设置
                </Typography.Title>
                <Tag color={settings?.isActive ? 'success' : 'default'} className="m-0">
                  {settings?.isActive ? '已启用' : '已停用'}
                </Tag>
                <Tag color={settings?.configured ? 'blue' : 'warning'} className="m-0">
                  {settings?.configured ? '配置完整' : '配置缺失'}
                </Tag>
              </div>
              <div className="text-xs text-slate-500">
                {settings?.name || '阿里云 TTS'} · {settings?.sampleRate || 24000}Hz · PCM 单声道
              </div>
            </div>
          </div>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadSettings()}>
            同步状态
          </Button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card title="阿里云 TTS" loading={loading} className="shadow-sm">
          <Form form={form} layout="vertical" requiredMark="optional">
            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item name="apiKey" label="API Key" tooltip="留空表示不修改当前密钥">
                <Input.Password
                  autoComplete="new-password"
                  placeholder={settings?.apiKeyConfigured ? settings.apiKeyMasked : '请输入 DashScope API Key'}
                />
              </Form.Item>
              <Form.Item name="model" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
                <Input placeholder="qwen3-tts-flash-realtime" />
              </Form.Item>
            </div>

            <Form.Item name="baseUrl" label="WebSocket URL" rules={[{ required: true, message: '请输入 WebSocket URL' }]}>
              <Input placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime" />
            </Form.Item>

            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item name="sampleRate" label="返回采样率" rules={[{ required: true, message: '请选择采样率' }]}>
                <Select options={SAMPLE_RATE_OPTIONS} />
              </Form.Item>
              <Form.Item name="defaultVoiceId" label="平台默认音色">
                <Select options={voiceOptions} placeholder="请选择默认音色" showSearch optionFilterProp="label" />
              </Form.Item>
            </div>

            <Form.Item name="defaultTestText" label="默认测试文本" rules={[{ required: true, message: '请输入默认测试文本' }]}>
              <Input.TextArea rows={4} showCount maxLength={500} />
            </Form.Item>

            <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <Form.Item name="isActive" valuePropName="checked" noStyle>
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Space wrap>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>
                  保存设置
                </Button>
                <Button icon={<ApiOutlined />} loading={testing} onClick={() => void handleTest()}>
                  测试 TTS
                </Button>
              </Space>
            </div>
          </Form>
        </Card>

        <Card title="测试播放" className="shadow-sm">
          <div className="space-y-4">
            <Input.TextArea
              rows={6}
              value={testText}
              maxLength={500}
              showCount
              onChange={(event) => setTestText(event.target.value)}
              placeholder={settings?.defaultTestText || '留空时使用默认测试文本'}
            />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={testing}
              block
              onClick={() => void handleTest()}
            >
              生成测试音频
            </Button>
            {audioUrl ? (
              <audio controls src={audioUrl} className="w-full" />
            ) : (
              <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-xs text-slate-400">
                暂无测试音频
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card title="内置音色目录" className="shadow-sm">
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
