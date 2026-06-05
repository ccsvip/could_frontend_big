import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Form, Input, Space, Switch, Tag, Typography, message } from 'antd';
import { ApiOutlined, AudioOutlined, CheckCircleOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import {
  fetchAsrSettings,
  testAsrSettings,
  updateAsrSettings,
  type AsrSettingsPayload,
  type AsrSettingsRecord,
  type AsrTestResult,
} from '../../api/modules/asr';

const getEndpointHost = (baseUrl: string) => {
  try {
    return new URL(baseUrl).host || '-';
  } catch {
    return baseUrl || '-';
  }
};

export const AsrSettingsPage = () => {
  const [form] = Form.useForm<AsrSettingsPayload>();
  const [settings, setSettings] = useState<AsrSettingsRecord | null>(null);
  const [testResult, setTestResult] = useState<AsrTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAsrSettings();
      setSettings(data);
      form.setFieldsValue({
        workspaceId: data.workspaceId,
        apiKey: '',
        baseUrl: data.baseUrl,
        model: data.model,
        isActive: data.isActive,
      });
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const endpointHost = useMemo(() => getEndpointHost(settings?.baseUrl || ''), [settings?.baseUrl]);

  const handleSave = async () => {
    const values = await form.validateFields();
    const payload = { ...values };
    if (!payload.apiKey?.trim()) {
      delete payload.apiKey;
    }

    setSaving(true);
    try {
      const data = await updateAsrSettings(payload);
      setSettings(data);
      form.setFieldsValue({ ...payload, apiKey: '' });
      message.success('ASR 设置已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testAsrSettings();
      setTestResult(result);
      if (result.success) {
        message.success(`ASR 连接成功 (${result.latencyMs}ms)`);
      } else {
        message.error(result.message);
      }
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card size="small" loading={loading}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Space size={10} className="mb-2">
              <AudioOutlined className="text-lg text-teal-700" />
              <Typography.Title level={4} className="!mb-0 !text-slate-900">
                ASR 设置
              </Typography.Title>
              <Tag color={settings?.isActive ? 'success' : 'default'}>
                {settings?.isActive ? '已启用' : '已停用'}
              </Tag>
              <Tag color={settings?.configured ? 'blue' : 'warning'}>
                {settings?.configured ? '配置完整' : '配置缺失'}
              </Tag>
            </Space>
            <Typography.Text className="text-slate-500">
              平台级语音识别配置。密钥仅由后端保存和使用，不会下发到公司侧页面。
            </Typography.Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={() => void loadSettings()}>
            刷新
          </Button>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card size="small" title="连接参数">
          <Form form={form} layout="vertical" className="max-w-3xl">
            <Form.Item
              name="workspaceId"
              label="Workspace ID"
              rules={[{ required: true, message: '请输入 Workspace ID' }]}
            >
              <Input placeholder="llm-..." />
            </Form.Item>

            <Form.Item name="apiKey" label="API Key">
              <Input.Password placeholder={settings?.apiKey || '留空表示不修改当前密钥'} autoComplete="new-password" />
            </Form.Item>

            <Form.Item
              name="baseUrl"
              label="北京 WebSocket 地址"
              rules={[{ required: true, message: '请输入 WebSocket 地址' }]}
            >
              <Input placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime" />
            </Form.Item>

            <Form.Item name="model" label="模型" rules={[{ required: true, message: '请输入模型名称' }]}>
              <Input placeholder="qwen3-asr-flash-realtime" />
            </Form.Item>

            <Form.Item name="isActive" label="启用状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>

            <Space>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>
                保存设置
              </Button>
              <Button icon={<ApiOutlined />} loading={testing} onClick={() => void handleTest()}>
                测试连接
              </Button>
            </Space>
          </Form>
        </Card>

        <Card size="small" title="当前状态">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Endpoint">{endpointHost}</Descriptions.Item>
            <Descriptions.Item label="Model">{settings?.model || '-'}</Descriptions.Item>
            <Descriptions.Item label="Workspace">{settings?.workspaceId || '-'}</Descriptions.Item>
            <Descriptions.Item label="Updated">{settings?.updated_at || '-'}</Descriptions.Item>
          </Descriptions>

          {testResult ? (
            <Alert
              className="mt-4"
              type={testResult.success ? 'success' : 'error'}
              showIcon
              icon={testResult.success ? <CheckCircleOutlined /> : undefined}
              message={testResult.success ? `连接成功 (${testResult.latencyMs}ms)` : '连接失败'}
              description={testResult.message}
            />
          ) : null}
        </Card>
      </div>
    </div>
  );
};
