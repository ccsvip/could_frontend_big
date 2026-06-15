import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
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
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
  UploadOutlined,
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

type ProviderFormValues = Omit<PlatformLLMProviderPayload, 'avatar' | 'clearAvatar' | 'providerType' | 'isActive'>;
type ModelFormValues = Omit<PlatformLLMModelPayload, 'isActive'>;

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
  const [providerLogoFile, setProviderLogoFile] = useState<UploadFile[]>([]);
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
    providerForm.setFieldsValue({ sortOrder: 0 });
    setProviderLogoFile([]);
    setProviderModalOpen(true);
  };

  const openEditProvider = (record: PlatformLLMProviderRecord) => {
    setEditingProvider(record);
    providerForm.setFieldsValue({
      name: record.name,
      apiBaseUrl: record.apiBaseUrl,
      sortOrder: record.sortOrder,
    });
    setProviderLogoFile(record.avatarUrl ? [{ uid: '-1', name: 'logo', status: 'done', url: record.avatarUrl }] : []);
    setProviderModalOpen(true);
  };

  const submitProvider = async () => {
    const values = await providerForm.validateFields();
    const payload: PlatformLLMProviderPayload = {
      ...values,
      avatar: providerLogoFile[0]?.originFileObj,
      clearAvatar: providerLogoFile.length === 0 && !!editingProvider?.avatarUrl ? true : undefined,
    };
    if (editingProvider) {
      await updatePlatformLLMProvider(editingProvider.id, payload);
      message.success('厂商已更新');
    } else {
      await createPlatformLLMProvider(payload);
      message.success('厂商已创建');
    }
    setProviderModalOpen(false);
    await loadPlatformData();
  };

  const openCreateModel = (providerId?: number) => {
    setEditingModel(null);
    modelForm.resetFields();
    modelForm.setFieldsValue({ providerId, sortOrder: 0 });
    setModelModalOpen(true);
  };

  const openEditModel = (record: PlatformLLMModelRecord) => {
    setEditingModel(record);
    modelForm.setFieldsValue({
      providerId: record.providerId,
      name: record.name,
      displayName: record.displayName,
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
      render: (value: string, record) => (
        <span className="font-semibold text-slate-700">{value || record.name}</span>
      ),
    },
    {
      title: '真实模型名称',
      dataIndex: 'name',
      render: (value: string) => (
        <code className="text-xs font-mono text-slate-500 bg-slate-50 border border-slate-200/60 px-1.5 py-0.5 rounded">
          {value}
        </code>
      ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 96,
      render: (value: boolean) => (
        <Tag color={value ? 'success' : 'default'} className="px-2 py-0.5 rounded-md font-medium border-0">
          {value ? '启用' : '停用'}
        </Tag>
      ),
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
        <div className="flex items-center gap-1.5">
          <Button
            size="small"
            icon={<ExperimentOutlined />}
            loading={testingModelId === record.id}
            onClick={() => void handleTestModel(record.id)}
            className="border-slate-200 hover:border-brand-500 hover:text-brand-600 rounded-md"
          >
            测试
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditModel(record)}
            className="border-slate-200 hover:border-brand-500 hover:text-brand-600 rounded-md"
          >
            编辑
          </Button>
          <Popconfirm
            title="删除模型"
            description="仍有公司启用授权的模型不能删除，请先取消授权。"
            onConfirm={() => deletePlatformLLMModel(record.id).then(loadPlatformData)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} className="hover:bg-rose-50 rounded-md">
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  const providerColumns: ColumnsType<PlatformLLMProviderRecord> = [
    {
      title: '厂商',
      dataIndex: 'name',
      render: (value: string, record) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={record.avatarUrl}
            icon={<RobotOutlined />}
            className="shadow-sm border border-slate-100 bg-brand-50 text-brand-600"
            size={36}
          />
          <div>
            <span className="font-semibold text-slate-800 text-sm hover:text-brand-600 transition-colors">
              {value}
            </span>
          </div>
        </div>
      ),
    },
    {
      title: 'API 地址',
      dataIndex: 'apiBaseUrl',
      ellipsis: true,
      render: (url: string) => (
        <code className="text-xs text-slate-600 bg-slate-50 border border-slate-200/60 px-2 py-1 rounded select-all font-mono">
          {url}
        </code>
      ),
    },
    {
      title: '密钥',
      dataIndex: 'apiKeyMasked',
      width: 160,
      render: (value: string, record) => (
        <Tag color={record.apiKeyConfigured ? 'geekblue' : 'default'} className="px-2 py-0.5 font-mono rounded-md border-0">
          {record.apiKeyConfigured ? value : '未配置'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 96,
      render: (value: boolean) => (
        <Tag color={value ? 'success' : 'default'} className="px-2.5 py-0.5 rounded-md font-medium border-0">
          {value ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 260,
      render: (_, record) => (
        <div className="flex items-center gap-1.5">
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() => openCreateModel(record.id)}
            className="border-brand-100 hover:border-brand-500 text-brand-600 hover:text-brand-700 bg-brand-50/30 hover:bg-brand-50 rounded-md"
          >
            模型
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditProvider(record)}
            className="border-slate-200 hover:border-brand-500 hover:text-brand-600 rounded-md"
          >
            编辑
          </Button>
          <Popconfirm
            title="删除厂商"
            description="已授权或使用的厂商不能删除，请停用。"
            onConfirm={() => deletePlatformLLMProvider(record.id).then(loadPlatformData)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} className="hover:bg-rose-50 rounded-md">
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  const providerModelTab = (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
        <Typography.Text className="text-slate-500 text-xs sm:max-w-md md:max-w-lg">
          平台统一维护各模型供应商的密钥凭证与可用模型产品线。
        </Typography.Text>
        <div className="flex gap-2 w-full sm:w-auto">
          <Button icon={<ReloadOutlined />} onClick={() => void loadPlatformData()} className="rounded-lg flex-1 sm:flex-initial">
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreateProvider}
            className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-lg text-white flex-1 sm:flex-initial"
          >
            新增厂商
          </Button>
        </div>
      </div>
      <Table
        rowKey="id"
        loading={loading}
        columns={providerColumns}
        dataSource={providers}
        scroll={{ x: 'max-content' }}
        expandable={{
          expandedRowRender: (provider) => (
            <Table
              rowKey="id"
              size="small"
              columns={modelColumns}
              dataSource={modelByProvider.get(provider.id) || []}
              pagination={false}
              scroll={{ x: 'max-content' }}
            />
          ),
        }}
      />
    </div>
  );

  const authorizationTab = (
    <div className="space-y-4">
      <div className="bg-slate-50/50 border border-slate-100/80 rounded-xl p-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
          <span className="text-sm font-semibold text-slate-700 shrink-0">授权目标公司:</span>
          <Select
            showSearch
            className="w-full sm:w-[280px]"
            placeholder="请选择公司"
            value={selectedTenantId ?? undefined}
            optionFilterProp="label"
            options={tenants.map((tenant) => ({ label: tenant.name, value: tenant.id }))}
            onChange={setSelectedTenantId}
            size="large"
          />
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full lg:w-auto">
          <span className="text-sm font-semibold text-slate-700 shrink-0">租户默认模型:</span>
          <Select
            className="w-full sm:w-[280px] font-mono text-sm"
            placeholder="暂无默认模型"
            allowClear
            value={authorization?.defaultModelId ?? undefined}
            options={authorization?.providers.flatMap((provider) =>
              provider.models
                .filter((model) => activeGrantIds.includes(model.id))
                .map((model) => ({
                  label: `${provider.name} - ${model.displayName || model.name}`,
                  value: model.id,
                })),
            )}
            onChange={(value) => authorization && setAuthorization({ ...authorization, defaultModelId: value ?? null })}
            size="large"
          />
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={savingAuth}
            onClick={() => void saveAuthorization()}
            size="large"
            className="w-full sm:w-auto bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 text-white shadow-sm hover:shadow-md transition-all rounded-lg font-medium"
          >
            保存授权
          </Button>
        </div>
      </div>
      <Spin spinning={authLoading}>
        <Collapse
          className="custom-collapse border-slate-100 rounded-xl overflow-hidden shadow-sm bg-white"
          items={(authorization?.providers || []).map((provider) => ({
            key: provider.id,
            label: (
              <div className="flex items-center justify-between w-full pr-4">
                <Space size="middle" className="flex-wrap">
                  <ApiOutlined className="text-brand-600 text-base" />
                  <span className="font-semibold text-slate-800 text-sm">{provider.name}</span>
                  <Tag color={provider.isActive ? 'success' : 'default'} className="px-2 py-0.5 rounded-md border-0 text-xs">
                    {provider.isActive ? '启用中' : '已停用'}
                  </Tag>
                </Space>
                <span className="text-xs text-slate-400 font-medium shrink-0 ml-2">
                  {provider.models.filter(m => m.grantIsActive).length} / {provider.models.length} 已授权
                </span>
              </div>
            ),
            children: (
              <div className="divide-y divide-slate-100/80 px-2 bg-slate-50/20 rounded-lg">
                {provider.models.length === 0 ? (
                  <div className="text-center py-6 text-slate-400 text-xs">该厂商下未录入任何模型</div>
                ) : (
                  provider.models.map((model) => (
                    <div key={model.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 py-3.5 px-4 hover:bg-slate-50/60 rounded-lg transition-colors">
                      <div>
                        <div className="font-semibold text-slate-800 text-sm">{model.displayName || model.name}</div>
                        <code className="text-[11px] font-mono text-slate-400 mt-0.5 block">{model.name}</code>
                      </div>
                      <div className="flex items-center gap-3 self-end sm:self-auto">
                        <Tag
                          color={model.isActive && provider.isActive ? 'success' : 'default'}
                          className="m-0 px-2 py-0.5 rounded-md border-0 text-xs font-medium"
                        >
                          {model.isActive && provider.isActive ? '全局可用' : '全局停用'}
                        </Tag>
                        <div className="w-[1px] h-4 bg-slate-200" />
                        <span className="text-xs text-slate-500">租户授权</span>
                        <Switch
                          checked={model.grantIsActive}
                          disabled={!model.isActive || !provider.isActive}
                          onChange={(checked) => updateGrant(model.id, checked)}
                          className="shadow-sm"
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
            ),
          }))}
        />
      </Spin>
    </div>
  );

  const testSettingsTab = (
    <div className="max-w-3xl bg-slate-50/30 border border-slate-100 rounded-xl p-4 sm:p-6 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-1.5 mb-1">
          <ExperimentOutlined className="text-brand-600" />
          <span>可用性与测速配置</span>
        </h3>
        <p className="text-xs text-slate-400">
          当测试模型连通性时，系统将使用下方预设的提示词与超参数请求模型，以此评估平均响应延迟。
        </p>
      </div>
      <Form
        form={testSettingsForm}
        layout="vertical"
        initialValues={DEFAULT_TEST_SETTINGS}
      >
        <Form.Item
          name="testPrompt"
          label="测试提示词"
          rules={[
            { required: true, message: '请输入测试提示词' },
            { max: 2000, message: '测试提示词不能超过 2000 字符' },
          ]}
        >
          <Input.TextArea rows={5} showCount maxLength={2000} className="rounded-lg" />
        </Form.Item>
        <div className="grid gap-4 md:grid-cols-3 mb-4">
          <Form.Item name="testCooldownSeconds" label="冷却秒数" rules={[{ required: true }]}>
            <InputNumber min={0} max={3600} className="!w-full rounded-lg" />
          </Form.Item>
          <Form.Item name="testTimeoutSeconds" label="超时秒数" rules={[{ required: true }]}>
            <InputNumber min={1} max={60} className="!w-full rounded-lg" />
          </Form.Item>
          <Form.Item name="testMaxTokens" label="最大 Tokens" rules={[{ required: true }]}>
            <InputNumber min={1} max={512} className="!w-full rounded-lg" />
          </Form.Item>
        </div>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={() => void saveTestSettings()}
          className="w-full sm:w-auto bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 text-white shadow-sm hover:shadow-md transition-all rounded-lg px-4"
        >
          保存测试设置
        </Button>
      </Form>
    </div>
  );

  return (
    <div className="space-y-5 p-4 sm:p-6">
      {/* 顶部 Page Hero */}
      <div className="page-hero">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <RobotOutlined className="text-brand-600" />
              <span>LLM 平台全局设置</span>
            </h1>
            <p className="text-slate-500 mt-1 text-sm">
              在此统一维护各云厂商平台密钥、租户公司授权与全局测试测速策略。
            </p>
          </div>
          <div className="flex gap-3 w-full sm:w-auto justify-between sm:justify-start">
            <div className="flex-1 sm:flex-none bg-brand-50 border border-brand-100 rounded-lg px-4 py-1.5 text-center shadow-sm">
              <div className="text-xs text-brand-600 font-semibold mb-0.5">可用厂商</div>
              <div className="text-lg font-bold text-brand-800">{providers.length} 个</div>
            </div>
            <div className="flex-1 sm:flex-none bg-slate-50 border border-slate-200/60 rounded-lg px-4 py-1.5 text-center shadow-sm">
              <div className="text-xs text-slate-500 font-semibold mb-0.5">已录模型</div>
              <div className="text-lg font-bold text-slate-700">{models.length} 个</div>
            </div>
          </div>
        </div>
      </div>

      {/* 主 Tab 内容区域 */}
      <div className="bg-white border border-slate-100 shadow-sm rounded-xl p-4 sm:p-6 transition-all hover:shadow-md duration-300">
        <Tabs
          items={[
            { key: 'providers', label: '平台厂商与模型', children: providerModelTab },
            { key: 'authorization', label: '公司授权', children: authorizationTab },
            { key: 'test-settings', label: '测试设置', children: testSettingsTab },
          ]}
        />
      </div>

      {/* 厂商 Modal */}
      <Modal
        title={
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <span className="p-1 bg-brand-50 text-brand-600 rounded">
              <RobotOutlined />
            </span>
            <span className="font-semibold">{editingProvider ? '编辑厂商' : '新增厂商'}</span>
          </div>
        }
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        onOk={() => void submitProvider()}
        destroyOnHidden
        className="custom-modal"
      >
        <Form form={providerForm} layout="vertical" className="mt-5 space-y-4">
          <Form.Item name="name" label="厂商名称" rules={[{ required: true, message: '请输入厂商名称' }]}>
            <Input maxLength={128} className="rounded-lg" />
          </Form.Item>
          <Form.Item name="apiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
            <Input className="rounded-lg" />
          </Form.Item>
          <Form.Item
            name="apiKey"
            label="API Key"
            rules={editingProvider ? [] : [{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder={editingProvider ? '留空表示不修改' : undefined} className="rounded-lg" />
          </Form.Item>
          <div className="grid gap-4 md:grid-cols-2">
            <Form.Item label="厂商 Logo">
              <Upload
                listType="picture-card"
                fileList={providerLogoFile}
                maxCount={1}
                beforeUpload={() => false}
                onChange={({ fileList }) => setProviderLogoFile(fileList)}
              >
                {providerLogoFile.length === 0 && (
                  <div className="text-slate-400 text-center">
                    <UploadOutlined className="text-lg mb-1" />
                    <div className="text-xs">上传 Logo</div>
                  </div>
                )}
              </Upload>
              <div className="text-slate-400 text-[11px] mt-1">
                支持 1:1 图片，建议不超过 1MB
              </div>
            </Form.Item>
            <Form.Item name="sortOrder" label="排序">
              <InputNumber min={0} className="!w-full rounded-lg" />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      {/* 模型 Modal */}
      <Modal
        title={
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <span className="p-1 bg-brand-50 text-brand-600 rounded">
              <ExperimentOutlined />
            </span>
            <span className="font-semibold">{editingModel ? '编辑模型' : '新增模型'}</span>
          </div>
        }
        open={modelModalOpen}
        onCancel={() => setModelModalOpen(false)}
        onOk={() => void submitModel()}
        destroyOnHidden
        className="custom-modal"
      >
        <Form form={modelForm} layout="vertical" className="mt-5 space-y-4">
          <Form.Item name="providerId" label="所属厂商" rules={[{ required: true, message: '请选择厂商' }]}>
            <Select disabled={!!editingModel} options={providers.map((provider) => ({ label: provider.name, value: provider.id }))} className="rounded-lg" />
          </Form.Item>
          <Form.Item name="name" label="真实模型名称" rules={[{ required: true, message: '请输入真实模型名称' }]}>
            <Input maxLength={128} className="rounded-lg font-mono" placeholder="如 gpt-4o" />
          </Form.Item>
          <Form.Item name="displayName" label="展示名称">
            <Input maxLength={128} className="rounded-lg" placeholder="如 OpenAI GPT-4o" />
          </Form.Item>
          <Form.Item name="sortOrder" label="排序">
            <InputNumber min={0} className="!w-full rounded-lg" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
