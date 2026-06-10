import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import {
  createPlatformLLMModel,
  createPlatformLLMProvider,
  deletePlatformLLMModel,
  deletePlatformLLMProvider,
  fetchPlatformLLMModels,
  fetchPlatformLLMProviders,
  fetchPlatformLLMTestSettings,
  fetchTenantLLMAuthorization,
  testPlatformLLMModel,
  updatePlatformLLMModel,
  updatePlatformLLMProvider,
  updatePlatformLLMTestSettings,
  updateTenantLLMAuthorization,
  type LLMTestSettings,
  type PlatformLLMModelPayload,
  type PlatformLLMModelRecord,
  type PlatformLLMProviderPayload,
  type PlatformLLMProviderRecord,
  type TenantLLMAuthorization,
} from '../../api/modules/llm-settings';

const PROVIDER_TYPE_OPTIONS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'Claude', value: 'claude' },
  { label: 'Kimi', value: 'kimi' },
  { label: '豆包', value: 'doubao' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: '通义千问', value: 'qwen' },
  { label: '智谱', value: 'zhipu' },
  { label: '其他', value: 'other' },
];

type ProviderFormValues = PlatformLLMProviderPayload;
type ModelFormValues = PlatformLLMModelPayload;

const DEFAULT_TEST_SETTINGS: LLMTestSettings = {
  testPrompt: '请用一句中文回复：连接测试成功。',
  testCooldownSeconds: 10,
  testTimeoutSeconds: 15,
  testMaxTokens: 64,
};

const effectiveGrantModelIds = (authorization: TenantLLMAuthorization | null) => {
  if (!authorization) return [];
  return authorization.providers.flatMap((provider) =>
    provider.models
      .filter((model) => provider.isActive && model.isActive && model.grantIsActive)
      .map((model) => model.id),
  );
};

export const LlmSettingsAdminPage = () => {
  const [providers, setProviders] = useState<PlatformLLMProviderRecord[]>([]);
  const [models, setModels] = useState<PlatformLLMModelRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [authorization, setAuthorization] = useState<TenantLLMAuthorization | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [savingAuth, setSavingAuth] = useState(false);
  const [testingModelId, setTestingModelId] = useState<number | null>(null);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<PlatformLLMProviderRecord | null>(null);
  const [editingModel, setEditingModel] = useState<PlatformLLMModelRecord | null>(null);
  const [providerForm] = Form.useForm<ProviderFormValues>();
  const [modelForm] = Form.useForm<ModelFormValues>();
  const [testSettingsForm] = Form.useForm<LLMTestSettings>();

  const modelByProvider = useMemo(() => {
    const grouped = new Map<number, PlatformLLMModelRecord[]>();
    models.forEach((model) => {
      grouped.set(model.providerId, [...(grouped.get(model.providerId) || []), model]);
    });
    return grouped;
  }, [models]);

  const activeGrantIds = useMemo(() => effectiveGrantModelIds(authorization), [authorization]);

  const loadPlatformData = useCallback(async () => {
    setLoading(true);
    try {
      const [providerData, modelData, tenantData, testSettings] = await Promise.all([
        fetchPlatformLLMProviders(),
        fetchPlatformLLMModels(),
        fetchTenants({ page_size: 1000, include_hidden: true }),
        fetchPlatformLLMTestSettings(),
      ]);
      setProviders(providerData.results);
      setModels(modelData.results);
      setTenants(tenantData.results);
      testSettingsForm.setFieldsValue(testSettings);
      if (!selectedTenantId && tenantData.results.length > 0) {
        setSelectedTenantId(tenantData.results[0].id);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedTenantId, testSettingsForm]);

  const loadAuthorization = useCallback(async () => {
    if (!selectedTenantId) {
      setAuthorization(null);
      return;
    }
    setAuthLoading(true);
    try {
      const data = await fetchTenantLLMAuthorization(selectedTenantId);
      setAuthorization(data);
    } finally {
      setAuthLoading(false);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    void loadPlatformData();
  }, [loadPlatformData]);

  useEffect(() => {
    void loadAuthorization();
  }, [loadAuthorization]);

  const openCreateProvider = () => {
    setEditingProvider(null);
    providerForm.resetFields();
    providerForm.setFieldsValue({ providerType: 'openai', isActive: true, sortOrder: 0 });
    setProviderModalOpen(true);
  };

  const openEditProvider = (record: PlatformLLMProviderRecord) => {
    setEditingProvider(record);
    providerForm.setFieldsValue({
      name: record.name,
      providerType: record.providerType,
      apiBaseUrl: record.apiBaseUrl,
      isActive: record.isActive,
      sortOrder: record.sortOrder,
    });
    setProviderModalOpen(true);
  };

  const submitProvider = async () => {
    const values = await providerForm.validateFields();
    if (editingProvider) {
      await updatePlatformLLMProvider(editingProvider.id, values);
      message.success('厂商已更新');
    } else {
      await createPlatformLLMProvider(values);
      message.success('厂商已创建');
    }
    setProviderModalOpen(false);
    await loadPlatformData();
  };

  const openCreateModel = (providerId?: number) => {
    setEditingModel(null);
    modelForm.resetFields();
    modelForm.setFieldsValue({ providerId, isActive: true, sortOrder: 0 });
    setModelModalOpen(true);
  };

  const openEditModel = (record: PlatformLLMModelRecord) => {
    setEditingModel(record);
    modelForm.setFieldsValue({
      providerId: record.providerId,
      name: record.name,
      displayName: record.displayName,
      isActive: record.isActive,
      sortOrder: record.sortOrder,
    });
    setModelModalOpen(true);
  };

  const submitModel = async () => {
    const values = await modelForm.validateFields();
    if (editingModel) {
      await updatePlatformLLMModel(editingModel.id, values);
      message.success('模型已更新');
    } else {
      await createPlatformLLMModel(values);
      message.success('模型已创建');
    }
    setModelModalOpen(false);
    await loadPlatformData();
    await loadAuthorization();
  };

  const handleTestModel = async (modelId: number) => {
    setTestingModelId(modelId);
    try {
      const result = await testPlatformLLMModel(modelId);
      if (result.success) {
        message.success(`连接成功，耗时 ${result.latencyMs}ms`);
      } else {
        message.error(result.message);
      }
    } finally {
      setTestingModelId(null);
    }
  };

  const updateGrant = (modelId: number, isActive: boolean) => {
    if (!authorization) return;
    setAuthorization({
      ...authorization,
      defaultModelId: isActive ? authorization.defaultModelId : authorization.defaultModelId === modelId ? null : authorization.defaultModelId,
      providers: authorization.providers.map((provider) => ({
        ...provider,
        models: provider.models.map((model) => (
          model.id === modelId ? { ...model, grantIsActive: isActive } : model
        )),
      })),
    });
  };

  const saveAuthorization = async () => {
    if (!authorization || !selectedTenantId) return;
    setSavingAuth(true);
    try {
      await updateTenantLLMAuthorization(selectedTenantId, {
        defaultModelId: authorization.defaultModelId,
        modelGrants: authorization.providers.flatMap((provider) =>
          provider.models.map((model) => ({ modelId: model.id, isActive: model.grantIsActive })),
        ),
      });
      message.success('授权已保存');
      await loadAuthorization();
    } finally {
      setSavingAuth(false);
    }
  };

  const saveTestSettings = async () => {
    const values = await testSettingsForm.validateFields();
    await updatePlatformLLMTestSettings(values);
    message.success('测试设置已保存');
  };

  const modelColumns: ColumnsType<PlatformLLMModelRecord> = [
    {
      title: '展示名称',
      dataIndex: 'displayName',
      render: (value: string, record) => value || record.name,
    },
    { title: '真实模型名称', dataIndex: 'name' },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 96,
      render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '排序',
      dataIndex: 'sortOrder',
      width: 80,
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<ExperimentOutlined />}
            loading={testingModelId === record.id}
            onClick={() => void handleTestModel(record.id)}
          >
            测试
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModel(record)}>
            编辑
          </Button>
          <Popconfirm title="删除模型" description="已授权或使用的模型不能删除，请停用。" onConfirm={() => deletePlatformLLMModel(record.id).then(loadPlatformData)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const providerColumns: ColumnsType<PlatformLLMProviderRecord> = [
    {
      title: '厂商',
      dataIndex: 'name',
      render: (value: string, record) => (
        <Space>
          <RobotOutlined className="text-brand-500" />
          <div>
            <div className="font-medium text-slate-900">{value}</div>
            <Typography.Text type="secondary" className="text-xs">{record.providerTypeLabel}</Typography.Text>
          </div>
        </Space>
      ),
    },
    { title: 'API 地址', dataIndex: 'apiBaseUrl', ellipsis: true },
    {
      title: '密钥',
      dataIndex: 'apiKeyMasked',
      width: 160,
      render: (value: string, record) => (
        <Tag color={record.apiKeyConfigured ? 'blue' : 'default'}>{record.apiKeyConfigured ? value : '未配置'}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 96,
      render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" icon={<PlusOutlined />} onClick={() => openCreateModel(record.id)}>
            模型
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditProvider(record)}>
            编辑
          </Button>
          <Popconfirm title="删除厂商" description="已授权或使用的厂商不能删除，请停用。" onConfirm={() => deletePlatformLLMProvider(record.id).then(loadPlatformData)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const providerModelTab = (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Typography.Text className="text-slate-500">平台统一维护厂商密钥与可授权模型。</Typography.Text>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void loadPlatformData()}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateProvider}>
            新增厂商
          </Button>
        </Space>
      </div>
      <Table
        rowKey="id"
        loading={loading}
        columns={providerColumns}
        dataSource={providers}
        expandable={{
          expandedRowRender: (provider) => (
            <Table
              rowKey="id"
              size="small"
              columns={modelColumns}
              dataSource={modelByProvider.get(provider.id) || []}
              pagination={false}
            />
          ),
        }}
      />
    </div>
  );

  const authorizationTab = (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Select
          showSearch
          className="min-w-[280px]"
          placeholder="选择公司"
          value={selectedTenantId ?? undefined}
          optionFilterProp="label"
          options={tenants.map((tenant) => ({ label: tenant.name, value: tenant.id }))}
          onChange={setSelectedTenantId}
        />
        <Space>
          <Select
            className="min-w-[260px]"
            placeholder="默认模型"
            allowClear
            value={authorization?.defaultModelId ?? undefined}
            options={authorization?.providers.flatMap((provider) =>
              provider.models
                .filter((model) => activeGrantIds.includes(model.id))
                .map((model) => ({
                  label: `${provider.name} / ${model.displayName || model.name}`,
                  value: model.id,
                })),
            )}
            onChange={(value) => authorization && setAuthorization({ ...authorization, defaultModelId: value ?? null })}
          />
          <Button type="primary" icon={<SaveOutlined />} loading={savingAuth} onClick={() => void saveAuthorization()}>
            保存授权
          </Button>
        </Space>
      </div>
      <Spin spinning={authLoading}>
        <Collapse
          items={(authorization?.providers || []).map((provider) => ({
            key: provider.id,
            label: (
              <Space>
                <ApiOutlined />
                <span>{provider.name}</span>
                <Tag color={provider.isActive ? 'green' : 'default'}>{provider.isActive ? '启用' : '停用'}</Tag>
              </Space>
            ),
            children: (
              <div className="divide-y divide-slate-100">
                {provider.models.map((model) => (
                  <div key={model.id} className="flex items-center justify-between gap-4 py-3">
                    <div>
                      <div className="font-medium text-slate-900">{model.displayName || model.name}</div>
                      <Typography.Text type="secondary" className="text-xs">{model.name}</Typography.Text>
                    </div>
                    <Space>
                      <Tag color={model.isActive && provider.isActive ? 'green' : 'default'}>
                        {model.isActive && provider.isActive ? '全局可用' : '全局停用'}
                      </Tag>
                      <Switch
                        checked={model.grantIsActive}
                        disabled={!model.isActive || !provider.isActive}
                        onChange={(checked) => updateGrant(model.id, checked)}
                      />
                    </Space>
                  </div>
                ))}
              </div>
            ),
          }))}
        />
      </Spin>
    </div>
  );

  const testSettingsTab = (
    <Form
      form={testSettingsForm}
      layout="vertical"
      initialValues={DEFAULT_TEST_SETTINGS}
      className="max-w-3xl"
    >
      <Form.Item
        name="testPrompt"
        label="测试提示词"
        rules={[
          { required: true, message: '请输入测试提示词' },
          { max: 2000, message: '测试提示词不能超过 2000 字符' },
        ]}
      >
        <Input.TextArea rows={6} showCount maxLength={2000} />
      </Form.Item>
      <div className="grid gap-4 md:grid-cols-3">
        <Form.Item name="testCooldownSeconds" label="冷却秒数" rules={[{ required: true }]}>
          <InputNumber min={0} max={3600} className="!w-full" />
        </Form.Item>
        <Form.Item name="testTimeoutSeconds" label="超时秒数" rules={[{ required: true }]}>
          <InputNumber min={1} max={60} className="!w-full" />
        </Form.Item>
        <Form.Item name="testMaxTokens" label="最大 Tokens" rules={[{ required: true }]}>
          <InputNumber min={1} max={512} className="!w-full" />
        </Form.Item>
      </div>
      <Button type="primary" icon={<SaveOutlined />} onClick={() => void saveTestSettings()}>
        保存测试设置
      </Button>
    </Form>
  );

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Typography.Title level={3} className="!mb-1">LLM设置</Typography.Title>
          <Typography.Text type="secondary">平台密钥、模型目录、公司授权与测速策略统一在这里维护。</Typography.Text>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <Tabs
          items={[
            { key: 'providers', label: '平台厂商与模型', children: providerModelTab },
            { key: 'authorization', label: '公司授权', children: authorizationTab },
            { key: 'test-settings', label: '测试设置', children: testSettingsTab },
          ]}
        />
      </div>

      <Modal
        title={editingProvider ? '编辑厂商' : '新增厂商'}
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        onOk={() => void submitProvider()}
        destroyOnHidden
      >
        <Form form={providerForm} layout="vertical" className="mt-4">
          <Form.Item name="name" label="厂商名称" rules={[{ required: true, message: '请输入厂商名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="providerType" label="厂商类型" rules={[{ required: true }]}>
            <Select options={PROVIDER_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="apiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="apiKey"
            label="API Key"
            rules={editingProvider ? [] : [{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder={editingProvider ? '留空表示不修改' : undefined} />
          </Form.Item>
          <div className="grid gap-4 md:grid-cols-2">
            <Form.Item name="sortOrder" label="排序">
              <InputNumber min={0} className="!w-full" />
            </Form.Item>
            <Form.Item name="isActive" label="启用状态" valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      <Modal
        title={editingModel ? '编辑模型' : '新增模型'}
        open={modelModalOpen}
        onCancel={() => setModelModalOpen(false)}
        onOk={() => void submitModel()}
        destroyOnHidden
      >
        <Form form={modelForm} layout="vertical" className="mt-4">
          <Form.Item name="providerId" label="所属厂商" rules={[{ required: true, message: '请选择厂商' }]}>
            <Select disabled={!!editingModel} options={providers.map((provider) => ({ label: provider.name, value: provider.id }))} />
          </Form.Item>
          <Form.Item name="name" label="真实模型名称" rules={[{ required: true, message: '请输入真实模型名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="displayName" label="展示名称">
            <Input maxLength={128} />
          </Form.Item>
          <div className="grid gap-4 md:grid-cols-2">
            <Form.Item name="sortOrder" label="排序">
              <InputNumber min={0} className="!w-full" />
            </Form.Item>
            <Form.Item name="isActive" label="启用状态" valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
};
