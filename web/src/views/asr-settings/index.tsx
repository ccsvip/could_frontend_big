import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Form, Input, Space, Switch, Tag, message } from 'antd';
import {
  ApiOutlined,
  AudioOutlined,
  ReloadOutlined,
  SaveOutlined,
  DatabaseOutlined,
  KeyOutlined,
  LinkOutlined,
  SettingOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  InfoCircleOutlined,
} from '@ant-design/icons';
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
    <div className="space-y-6">
      {/* Top Hero Banner */}
      <div className="page-hero">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-teal-50 text-teal-700 shadow-sm border border-teal-100/50 flex-shrink-0">
              <AudioOutlined className="text-xl" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h1 className="text-lg font-semibold text-slate-900 m-0">
                  ASR 语音识别配置
                </h1>
                <Tag color={settings?.isActive ? 'success' : 'default'} className="m-0 rounded-full px-2.5 border-none shadow-sm text-xs font-semibold">
                  {settings?.isActive ? '已启用' : '已停用'}
                </Tag>
                <Tag color={settings?.configured ? 'blue' : 'warning'} className="m-0 rounded-full px-2.5 border-none shadow-sm text-xs font-semibold">
                  {settings?.configured ? '配置完整' : '配置缺失'}
                </Tag>
              </div>
              <p className="text-slate-500 text-xs m-0 leading-relaxed max-w-2xl">
                超级管理员平台级语音识别 (ASR) 配置。敏感的接口密钥 (API Key) 仅由后端加密保存并参与运算，不会下发给公司及终端租户。
              </p>
            </div>
          </div>
          <Button
            icon={<ReloadOutlined className={loading ? 'animate-spin' : ''} />}
            onClick={() => void loadSettings()}
            loading={loading}
            className="self-start md:self-center hover:border-teal-500 hover:text-teal-600 rounded-lg px-4 h-9"
          >
            同步状态
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* Left Side: Parameters Form */}
        <Card
          bordered
          title={
            <div className="flex items-center gap-2 py-0.5">
              <div className="w-1 h-4 bg-teal-600 rounded-full" />
              <span className="font-semibold text-slate-800">连接参数</span>
            </div>
          }
          className="shadow-sm hover:shadow-md transition-shadow duration-300"
          styles={{ body: { padding: '24px' } }}
        >
          <Form form={form} layout="vertical" requiredMark="optional">
            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item
                name="workspaceId"
                label={
                  <span className="flex items-center gap-1.5 font-medium text-slate-700">
                    <DatabaseOutlined className="text-slate-400" /> Workspace ID
                  </span>
                }
                rules={[{ required: true, message: '请输入 Workspace ID' }]}
                className="mb-5"
              >
                <Input placeholder="llm-..." className="h-10 rounded-lg border-slate-200" />
              </Form.Item>

              <Form.Item
                name="apiKey"
                label={
                  <span className="flex items-center gap-1.5 font-medium text-slate-700">
                    <KeyOutlined className="text-slate-400" /> API Key
                  </span>
                }
                className="mb-5"
                tooltip="留空表示不修改当前后端已保存的密钥"
              >
                <Input.Password
                  placeholder={settings?.apiKey || '留空表示不修改当前密钥'}
                  autoComplete="new-password"
                  className="h-10 rounded-lg border-slate-200"
                />
              </Form.Item>
            </div>

            <Form.Item
              name="baseUrl"
              label={
                <span className="flex items-center gap-1.5 font-medium text-slate-700">
                  <LinkOutlined className="text-slate-400" /> WebSocket 接口地址
                </span>
              }
              rules={[{ required: true, message: '请输入 WebSocket 地址' }]}
              className="mb-5"
              tooltip="DashScope 实时语音识别服务的 WebSocket 端点"
            >
              <Input placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime" className="h-10 rounded-lg border-slate-200" />
            </Form.Item>

            <div className="grid gap-x-4 md:grid-cols-2">
              <Form.Item
                name="model"
                label={
                  <span className="flex items-center gap-1.5 font-medium text-slate-700">
                    <SettingOutlined className="text-slate-400" /> 语音识别模型
                  </span>
                }
                rules={[{ required: true, message: '请输入模型名称' }]}
                className="mb-5"
              >
                <Input placeholder="qwen3-asr-flash-realtime" className="h-10 rounded-lg border-slate-200" />
              </Form.Item>

              <Form.Item
                label={
                  <span className="flex items-center gap-1.5 font-medium text-slate-700">
                    <InfoCircleOutlined className="text-slate-400" /> 启用服务状态
                  </span>
                }
                className="mb-5"
              >
                <div className="flex items-center h-10 px-3 border border-slate-200 rounded-lg bg-slate-50/50 justify-between">
                  <span className="text-xs text-slate-500">是否对全平台启用此 ASR 配置</span>
                  <Form.Item name="isActive" valuePropName="checked" noStyle>
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                  </Form.Item>
                </div>
              </Form.Item>
            </div>

            <div className="border-t border-slate-105 pt-5 mt-2">
              <Space size={12}>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={saving}
                  onClick={() => void handleSave()}
                  className="h-10 px-6 rounded-lg font-semibold"
                >
                  保存设置
                </Button>
                <Button
                  icon={<ApiOutlined />}
                  loading={testing}
                  onClick={() => void handleTest()}
                  className="h-10 px-5 rounded-lg border-slate-200 text-slate-600 hover:text-teal-600 hover:border-teal-300 font-semibold"
                >
                  测试连接
                </Button>
              </Space>
            </div>
          </Form>
        </Card>

        {/* Right Side: Monitor Panel */}
        <div className="flex flex-col gap-6">
          <Card
            bordered
            title={
              <div className="flex items-center gap-2 py-0.5">
                <div className="w-1 h-4 bg-sky-600 rounded-full" />
                <span className="font-semibold text-slate-800">当前状态</span>
              </div>
            }
            className="shadow-sm hover:shadow-md transition-shadow duration-300"
            styles={{ body: { padding: '20px' } }}
          >
            <div className="space-y-3.5">
              <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-100/80 bg-slate-50/30 hover:bg-slate-50 hover:border-slate-200/80 transition-all duration-200">
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-teal-50 text-teal-600 flex-shrink-0 border border-teal-100/50">
                    <GlobalOutlined className="text-base" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-medium">WebSocket 节点</div>
                    <div className="text-xs font-semibold text-slate-700 break-all select-all mt-1 max-w-[200px] sm:max-w-xs md:max-w-md xl:max-w-[210px] leading-normal">
                      {endpointHost}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-100/80 bg-slate-50/30 hover:bg-slate-50 hover:border-slate-200/80 transition-all duration-200">
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-sky-50 text-sky-600 flex-shrink-0 border border-sky-100/50">
                    <SettingOutlined className="text-base" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-medium">模型版本 (Model)</div>
                    <div className="text-xs font-semibold text-slate-700 mt-1 leading-normal break-all max-w-[200px] sm:max-w-xs md:max-w-md xl:max-w-[210px]">
                      {settings?.model || '-'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-100/80 bg-slate-50/30 hover:bg-slate-50 hover:border-slate-200/80 transition-all duration-200">
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex-shrink-0 border border-indigo-100/50">
                    <DatabaseOutlined className="text-base" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-medium">工作空间 (Workspace)</div>
                    <div className="text-xs font-semibold text-slate-700 select-all mt-1 break-all max-w-[200px] sm:max-w-xs md:max-w-md xl:max-w-[210px] leading-normal">
                      {settings?.workspaceId || '-'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-100/80 bg-slate-50/30 hover:bg-slate-50 hover:border-slate-200/80 transition-all duration-200">
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-slate-100 text-slate-600 flex-shrink-0 border border-slate-200/50">
                    <ClockCircleOutlined className="text-base" />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 font-medium">最近更新</div>
                    <div className="text-xs font-medium text-slate-600 mt-1 leading-normal">
                      {settings?.updated_at || '-'}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {testResult ? (
              <div
                className={`mt-5 p-4 rounded-xl border transition-all duration-300 ${
                  testResult.success
                    ? 'bg-emerald-50/40 border-emerald-100/70 text-emerald-950'
                    : 'bg-rose-50/40 border-rose-100/70 text-rose-950'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {testResult.success ? (
                    <CheckCircleFilled className="text-base text-emerald-500 mt-0.5 flex-shrink-0" />
                  ) : (
                    <CloseCircleFilled className="text-base text-rose-500 mt-0.5 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-bold text-xs text-slate-800">
                        {testResult.success ? '连接测试成功' : '连接测试失败'}
                      </span>
                      {testResult.success && testResult.latencyMs !== undefined && (
                        <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800 shadow-sm border border-emerald-200/30 flex-shrink-0">
                          {testResult.latencyMs}ms
                        </span>
                      )}
                    </div>
                    <div
                      className={`text-[11px] leading-relaxed break-words font-normal ${
                        testResult.success ? 'text-emerald-700' : 'text-rose-700'
                      }`}
                    >
                      {testResult.message || (testResult.success ? '服务节点连接建立成功。' : '节点连接超时，请检查端点和凭据配置。')}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-5 p-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/10 text-center">
                <p className="text-slate-400 text-xs m-0 leading-relaxed">
                  暂无连接测试结果。推荐在修改参数后点击“测试连接”确认状态。
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
