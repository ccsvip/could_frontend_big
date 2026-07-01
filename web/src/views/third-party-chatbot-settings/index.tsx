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
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  IconApi,
  IconEdit,
  IconPlus,
  IconRefresh,
  IconRobot,
  IconTrash,
} from '@tabler/icons-react';
import { fetchTenants, type TenantRecord } from '../../api/modules/tenants';
import {
  createPlatformThirdPartyChatbotApplication,
  createPlatformThirdPartyChatbotProvider,
  deletePlatformThirdPartyChatbotApplication,
  deletePlatformThirdPartyChatbotProvider,
  fetchPlatformThirdPartyChatbotApplications,
  fetchPlatformThirdPartyChatbotProviders,
  fetchTenantThirdPartyChatbotAuthorization,
  updatePlatformThirdPartyChatbotApplication,
  updatePlatformThirdPartyChatbotProvider,
  updateTenantThirdPartyChatbotAuthorization,
  type PlatformThirdPartyChatbotApplicationPayload,
  type PlatformThirdPartyChatbotApplicationRecord,
  type PlatformThirdPartyChatbotProviderPayload,
  type PlatformThirdPartyChatbotProviderRecord,
  type TenantThirdPartyChatbotAuthorization,
} from '../../api/modules/llm-settings';

type ProviderFormValues = Omit<PlatformThirdPartyChatbotProviderPayload, 'providerType' | 'isActive'>;
type ChatbotFormValues = Omit<PlatformThirdPartyChatbotApplicationPayload, 'isActive'>;

const effectiveGrantChatbotIds = (authorization: TenantThirdPartyChatbotAuthorization | null) => {
  if (!authorization) return [];
  return authorization.chatbots
    .filter((chatbot) => chatbot.providerIsActive && chatbot.isActive && chatbot.grantIsActive)
    .map((chatbot) => chatbot.id);
};

export const ThirdPartyChatbotSettingsPage = () => {
  const [providers, setProviders] = useState<PlatformThirdPartyChatbotProviderRecord[]>([]);
  const [chatbots, setChatbots] = useState<PlatformThirdPartyChatbotApplicationRecord[]>([]);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [authorization, setAuthorization] = useState<TenantThirdPartyChatbotAuthorization | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [savingAuth, setSavingAuth] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [chatbotModalOpen, setChatbotModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<PlatformThirdPartyChatbotProviderRecord | null>(null);
  const [editingChatbot, setEditingChatbot] = useState<PlatformThirdPartyChatbotApplicationRecord | null>(null);
  const [providerForm] = Form.useForm<ProviderFormValues>();
  const [chatbotForm] = Form.useForm<ChatbotFormValues>();

  const activeTenants = useMemo(() => tenants.filter((tenant) => tenant.isActive), [tenants]);
  const activeProviders = useMemo(() => providers.filter((provider) => provider.isActive), [providers]);
  const activeGrantIds = useMemo(() => effectiveGrantChatbotIds(authorization), [authorization]);
  const providerOptions = useMemo(
    () => activeProviders.map((provider) => ({ label: provider.name, value: provider.id })),
    [activeProviders],
  );

  const loadPlatformData = useCallback(async () => {
    setLoading(true);
    try {
      const [providerData, chatbotData, tenantData] = await Promise.all([
        fetchPlatformThirdPartyChatbotProviders(),
        fetchPlatformThirdPartyChatbotApplications(),
        fetchTenants({ page_size: 1000, include_hidden: true }),
      ]);
      const nextActiveTenants = tenantData.results.filter((tenant) => tenant.isActive);
      const selectedTenantStillActive = nextActiveTenants.some((tenant) => tenant.id === selectedTenantId);
      setProviders(providerData.results);
      setChatbots(chatbotData.results);
      setTenants(tenantData.results);
      if (!selectedTenantStillActive) {
        setSelectedTenantId(nextActiveTenants[0]?.id ?? null);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedTenantId]);

  const loadAuthorization = useCallback(async () => {
    if (!selectedTenantId) {
      setAuthorization(null);
      return;
    }
    setAuthLoading(true);
    try {
      const data = await fetchTenantThirdPartyChatbotAuthorization(selectedTenantId);
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
    setProviderModalOpen(true);
  };

  const openEditProvider = (record: PlatformThirdPartyChatbotProviderRecord) => {
    setEditingProvider(record);
    providerForm.setFieldsValue({
      name: record.name,
      apiBaseUrl: record.apiBaseUrl,
      sortOrder: record.sortOrder,
    });
    setProviderModalOpen(true);
  };

  const submitProvider = async () => {
    const values = await providerForm.validateFields();
    if (editingProvider) {
      await updatePlatformThirdPartyChatbotProvider(editingProvider.id, values);
      message.success('第三方供应商已更新');
    } else {
      await createPlatformThirdPartyChatbotProvider(values);
      message.success('第三方供应商已创建');
    }
    setProviderModalOpen(false);
    await loadPlatformData();
  };

  const openCreateChatbot = () => {
    setEditingChatbot(null);
    chatbotForm.resetFields();
    chatbotForm.setFieldsValue({ providerId: providerOptions[0]?.value, sortOrder: 0 });
    setChatbotModalOpen(true);
  };

  const openEditChatbot = (record: PlatformThirdPartyChatbotApplicationRecord) => {
    setEditingChatbot(record);
    chatbotForm.setFieldsValue({
      providerId: record.providerId,
      name: record.name,
      description: record.description,
      externalApplicationId: record.externalApplicationId,
      sortOrder: record.sortOrder,
    });
    setChatbotModalOpen(true);
  };

  const submitChatbot = async () => {
    const values = await chatbotForm.validateFields();
    if (editingChatbot) {
      await updatePlatformThirdPartyChatbotApplication(editingChatbot.id, values);
      message.success('第三方机器人已更新');
    } else {
      await createPlatformThirdPartyChatbotApplication(values);
      message.success('第三方机器人已创建');
    }
    setChatbotModalOpen(false);
    await loadPlatformData();
  };

  const toggleProvider = async (record: PlatformThirdPartyChatbotProviderRecord, checked: boolean) => {
    await updatePlatformThirdPartyChatbotProvider(record.id, { isActive: checked });
    message.success(`供应商已${checked ? '启用' : '停用'}`);
    await loadPlatformData();
  };

  const toggleChatbot = async (record: PlatformThirdPartyChatbotApplicationRecord, checked: boolean) => {
    await updatePlatformThirdPartyChatbotApplication(record.id, { isActive: checked });
    message.success(`机器人已${checked ? '启用' : '停用'}`);
    await loadPlatformData();
  };

  const removeProvider = async (record: PlatformThirdPartyChatbotProviderRecord) => {
    await deletePlatformThirdPartyChatbotProvider(record.id);
    message.success('第三方供应商已删除');
    await loadPlatformData();
  };

  const removeChatbot = async (record: PlatformThirdPartyChatbotApplicationRecord) => {
    await deletePlatformThirdPartyChatbotApplication(record.id);
    message.success('第三方机器人已删除');
    await loadPlatformData();
  };

  const updateGrant = (chatbotId: number, checked: boolean) => {
    if (!authorization) return;
    setAuthorization({
      ...authorization,
      chatbots: authorization.chatbots.map((chatbot) =>
        chatbot.id === chatbotId ? { ...chatbot, grantIsActive: checked } : chatbot,
      ),
    });
  };

  const saveAuthorization = async () => {
    if (!selectedTenantId || !authorization) return;
    setSavingAuth(true);
    try {
      const nextAuthorization = await updateTenantThirdPartyChatbotAuthorization(selectedTenantId, {
        chatbotGrants: authorization.chatbots.map((chatbot) => ({
          chatbotId: chatbot.id,
          isActive: chatbot.grantIsActive,
        })),
      });
      setAuthorization(nextAuthorization);
      message.success('公司第三方机器人授权已保存');
    } finally {
      setSavingAuth(false);
    }
  };

  const providerColumns: ColumnsType<PlatformThirdPartyChatbotProviderRecord> = [
    {
      title: '供应商',
      dataIndex: 'name',
      render: (_, record) => (
        <Space size="middle">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
            <IconApi size={18} />
          </span>
          <div>
            <div className="font-semibold text-slate-800">{record.name}</div>
            <div className="text-xs text-slate-400">{record.providerTypeLabel}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '接口地址',
      dataIndex: 'apiBaseUrl',
      ellipsis: true,
      render: (value: string) => <code className="text-xs text-slate-500">{value}</code>,
    },
    {
      title: '密钥',
      dataIndex: 'apiKeyMasked',
      width: 140,
      render: (_, record) => (
        <Tag color={record.apiKeyConfigured ? 'success' : 'warning'}>
          {record.apiKeyConfigured ? record.apiKeyMasked : '未配置'}
        </Tag>
      ),
    },
    {
      title: '启用',
      dataIndex: 'isActive',
      width: 90,
      render: (_, record) => (
        <Switch checked={record.isActive} onChange={(checked) => void toggleProvider(record, checked)} />
      ),
    },
    {
      title: '操作',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<IconEdit size={14} />} onClick={() => openEditProvider(record)} />
          <Popconfirm title="删除供应商" description="删除后其下机器人也会被移除。" onConfirm={() => void removeProvider(record)}>
            <Button size="small" danger icon={<IconTrash size={14} />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const chatbotColumns: ColumnsType<PlatformThirdPartyChatbotApplicationRecord> = [
    {
      title: '机器人',
      dataIndex: 'name',
      render: (_, record) => (
        <div>
          <div className="font-semibold text-slate-800">{record.name}</div>
          <div className="text-xs text-slate-400">{record.description || '无说明'}</div>
        </div>
      ),
    },
    {
      title: '供应商',
      dataIndex: 'providerName',
      width: 180,
      render: (value: string) => <Tag color="purple">{value}</Tag>,
    },
    {
      title: '第三方应用 ID',
      dataIndex: 'externalApplicationId',
      width: 180,
      render: (value: string) => <code className="text-xs text-slate-500">{value}</code>,
    },
    {
      title: '启用',
      dataIndex: 'isActive',
      width: 90,
      render: (_, record) => (
        <Switch checked={record.isActive} onChange={(checked) => void toggleChatbot(record, checked)} />
      ),
    },
    {
      title: '操作',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<IconEdit size={14} />} onClick={() => openEditChatbot(record)} />
          <Popconfirm title="删除机器人" description="删除后已绑定它的智能体将无法继续使用该后端。" onConfirm={() => void removeChatbot(record)}>
            <Button size="small" danger icon={<IconTrash size={14} />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const providersTab = (
    <div className="space-y-4">
      <div className="flex justify-end gap-2">
        <Button icon={<IconRefresh size={16} />} onClick={() => void loadPlatformData()}>
          刷新
        </Button>
        <Button type="primary" icon={<IconPlus size={16} />} onClick={openCreateProvider}>
          新增供应商
        </Button>
      </div>
      <Table rowKey="id" columns={providerColumns} dataSource={providers} pagination={false} />
    </div>
  );

  const chatbotsTab = (
    <div className="space-y-4">
      <div className="flex justify-end gap-2">
        <Button icon={<IconRefresh size={16} />} onClick={() => void loadPlatformData()}>
          刷新
        </Button>
        <Button type="primary" icon={<IconPlus size={16} />} disabled={providerOptions.length === 0} onClick={openCreateChatbot}>
          新增机器人
        </Button>
      </div>
      <Table rowKey="id" columns={chatbotColumns} dataSource={chatbots} pagination={false} />
    </div>
  );

  const authorizationTab = (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Space wrap>
          <span className="text-sm font-semibold text-slate-700">选择公司</span>
          <Select
            showSearch
            optionFilterProp="label"
            className="w-full sm:w-64"
            value={selectedTenantId ?? undefined}
            options={activeTenants.map((tenant) => ({ label: tenant.name, value: tenant.id }))}
            onChange={setSelectedTenantId}
          />
          <Tag color="purple">{activeGrantIds.length} 个已授权</Tag>
        </Space>
        <Button type="primary" loading={savingAuth} onClick={() => void saveAuthorization()}>
          保存授权
        </Button>
      </div>
      <Spin spinning={authLoading}>
        <Collapse
          items={(authorization?.chatbots || []).map((chatbot) => ({
            key: chatbot.id,
            label: (
              <div className="flex items-center justify-between gap-3 pr-4">
                <Space wrap>
                  <IconRobot size={18} className="text-violet-700" />
                  <span className="font-semibold text-slate-800">{chatbot.name}</span>
                  <Tag color="purple">{chatbot.providerName}</Tag>
                  <Tag color={chatbot.providerIsActive && chatbot.isActive ? 'success' : 'default'}>
                    {chatbot.providerIsActive && chatbot.isActive ? '全局可用' : '全局停用'}
                  </Tag>
                </Space>
                <Switch
                  checked={chatbot.grantIsActive}
                  disabled={!chatbot.providerIsActive || !chatbot.isActive}
                  onChange={(checked) => updateGrant(chatbot.id, checked)}
                />
              </div>
            ),
            children: (
              <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
                <div>第三方应用 ID：<code>{chatbot.externalApplicationId}</code></div>
                <div>{chatbot.description || '无说明'}</div>
              </div>
            ),
          }))}
        />
      </Spin>
    </div>
  );

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="page-hero">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold text-slate-900">
              <IconRobot size={24} className="text-violet-700" />
              <span>不规则 LLM 设置</span>
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              维护非 OpenAI 兼容的第三方会话机器人，并按公司单独授权。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:flex">
            <div className="rounded-lg border border-violet-100 bg-violet-50 px-4 py-1.5 text-center">
              <div className="text-xs font-semibold text-violet-700">供应商</div>
              <div className="text-lg font-bold text-violet-900">{providers.length} 个</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-1.5 text-center">
              <div className="text-xs font-semibold text-slate-500">机器人</div>
              <div className="text-lg font-bold text-slate-700">{chatbots.length} 个</div>
            </div>
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm sm:p-6">
          <Tabs
            items={[
              { key: 'providers', label: '第三方供应商', children: providersTab },
              { key: 'chatbots', label: '机器人应用', children: chatbotsTab },
              { key: 'authorization', label: '公司授权', children: authorizationTab },
            ]}
          />
        </div>
      </Spin>

      <Modal
        title={editingProvider ? '编辑第三方供应商' : '新增第三方供应商'}
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        onOk={() => void submitProvider()}
        destroyOnHidden
      >
        <Form form={providerForm} layout="vertical" className="pt-4">
          <Form.Item name="name" label="供应商名称" rules={[{ required: true, message: '请输入供应商名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="apiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
            <Input placeholder="https://example.com/api" />
          </Form.Item>
          <Form.Item
            name="apiKey"
            label="应用密钥"
            rules={editingProvider ? [] : [{ required: true, message: '请输入应用密钥' }]}
          >
            <Input.Password placeholder={editingProvider ? '留空表示不修改' : undefined} />
          </Form.Item>
          <Form.Item name="sortOrder" label="排序">
            <InputNumber min={0} className="!w-full" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingChatbot ? '编辑第三方机器人' : '新增第三方机器人'}
        open={chatbotModalOpen}
        onCancel={() => setChatbotModalOpen(false)}
        onOk={() => void submitChatbot()}
        destroyOnHidden
      >
        <Form form={chatbotForm} layout="vertical" className="pt-4">
          <Form.Item name="providerId" label="所属供应商" rules={[{ required: true, message: '请选择供应商' }]}>
            <Select options={providerOptions} />
          </Form.Item>
          <Form.Item name="name" label="机器人名称" rules={[{ required: true, message: '请输入机器人名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item
            name="externalApplicationId"
            label="第三方应用 ID"
            rules={[{ required: true, message: '请输入第三方应用 ID' }]}
          >
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} maxLength={255} showCount />
          </Form.Item>
          <Form.Item name="sortOrder" label="排序">
            <InputNumber min={0} className="!w-full" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
