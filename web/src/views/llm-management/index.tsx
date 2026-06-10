import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Button,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';
import {
  CloudOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ApiOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../store/auth';
import {
  fetchLLMProviders,
  createLLMProvider,
  updateLLMProvider,
  deleteLLMProvider,
  testLLMConnection,
  type LLMProviderRecord,
  type LLMProviderListQuery,
  type LLMModelItem,
} from '../../api/modules/llm-providers';

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

const PAGE_SIZE = 10;

export const LlmManagementPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('ai_models.llm.create');
  const canUpdate = hasPermission('ai_models.llm.update');
  const canDelete = hasPermission('ai_models.llm.delete');

  const [items, setItems] = useState<LLMProviderRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [searchKeyword, setSearchKeyword] = useState('');

  const [formVisible, setFormVisible] = useState(false);
  const [editingItem, setEditingItem] = useState<LLMProviderRecord | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const [avatarFile, setAvatarFile] = useState<UploadFile[]>([]);
  const [modelsList, setModelsList] = useState<LLMModelItem[]>([]);
  const [newModelName, setNewModelName] = useState('');

  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, { success: boolean; message: string; latencyMs: number }>>({});

  const query = useMemo<LLMProviderListQuery>(() => ({ page, keyword: searchKeyword }), [page, searchKeyword]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchLLMProviders(query);
      setItems(data.results);
      setTotal(data.count);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => { loadData(); }, [loadData]);

  const openCreateModal = () => {
    setEditingItem(null);
    form.resetFields();
    form.setFieldsValue({ providerType: 'openai', isActive: true });
    setAvatarFile([]);
    setModelsList([]);
    setNewModelName('');
    setFormVisible(true);
  };

  const openEditModal = (record: LLMProviderRecord) => {
    setEditingItem(record);
    form.setFieldsValue({
      name: record.name,
      providerType: record.providerType,
      apiBaseUrl: record.apiBaseUrl,
      apiKey: record.apiKey,
      isActive: record.isActive,
    });
    setAvatarFile(record.avatarUrl ? [{ uid: '-1', name: 'avatar', status: 'done', url: record.avatarUrl }] : []);
    setModelsList(record.modelsConfig || []);
    setNewModelName('');
    setFormVisible(true);
  };

  const handleAddModel = () => {
    const trimmed = newModelName.trim();
    if (!trimmed) return;
    if (modelsList.some((m) => m.name === trimmed)) {
      message.warning('该模型已存在');
      return;
    }
    const isFirst = modelsList.length === 0;
    setModelsList([...modelsList, { name: trimmed, isDefault: isFirst }]);
    setNewModelName('');
  };

  const handleRemoveModel = (name: string) => {
    const next = modelsList.filter((m) => m.name !== name);
    if (next.length > 0 && !next.some((m) => m.isDefault)) {
      next[0].isDefault = true;
    }
    setModelsList(next);
  };

  const handleSetDefaultModel = (name: string) => {
    setModelsList(modelsList.map((m) => ({ ...m, isDefault: m.name === name })));
  };

  const getErrorStatus = (error: unknown) => (
    error && typeof error === 'object' && 'response' in error
      ? (error as { response?: { status?: number } }).response?.status
      : undefined
  );

  const handleMissingProvider = (messageText: string, missingId?: number) => {
    message.warning(messageText);
    setEditingItem(null);
    setFormVisible(false);
    setTestResults((prev) => {
      const targetId = missingId ?? editingItem?.id;
      if (targetId === undefined) return prev;
      const next = { ...prev };
      delete next[targetId];
      return next;
    });
    loadData();
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const payload = {
        name: values.name,
        providerType: values.providerType,
        apiBaseUrl: values.apiBaseUrl,
        apiKey: values.apiKey,
        avatar: avatarFile[0]?.originFileObj as File | undefined,
        clearAvatar: avatarFile.length === 0 && editingItem?.avatarUrl ? true : undefined,
        modelsConfig: modelsList,
        isActive: values.isActive ?? true,
      };

      if (editingItem) {
        await updateLLMProvider(editingItem.id, payload);
        message.success('更新成功');
      } else {
        await createLLMProvider(payload as Required<typeof payload>);
        message.success('创建成功');
      }
      setFormVisible(false);
      setEditingItem(null);
      loadData();
    } catch (error) {
      if (getErrorStatus(error) === 404) {
        handleMissingProvider('该供应商记录已不存在，列表已刷新', editingItem?.id);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteLLMProvider(id);
      message.success('删除成功');
      if (items.length === 1 && page > 1) setPage(page - 1);
      else loadData();
    } catch (error) {
      if (getErrorStatus(error) === 404) {
        handleMissingProvider('该供应商记录已不存在，列表已刷新', id);
      }
    }
  };

  const handleTestConnection = async (id: number) => {
    setTestingId(id);
    try {
      const result = await testLLMConnection(id);
      setTestResults((prev) => ({ ...prev, [id]: result }));
      if (result.success) {
        message.success(`连接成功 (${result.latencyMs}ms)`);
      } else {
        message.error(result.message);
      }
    } catch (error) {
      if (getErrorStatus(error) === 404) {
        handleMissingProvider('该供应商记录已不存在，列表已刷新', id);
        return;
      }
      setTestResults((prev) => ({ ...prev, [id]: { success: false, message: '请求失败', latencyMs: 0 } }));
    } finally {
      setTestingId(null);
    }
  };

  const handleSearch = () => {
    setPage(1);
    setSearchKeyword(keyword);
  };

  const handleReset = () => {
    setKeyword('');
    setSearchKeyword('');
    setPage(1);
  };

  const columns: ColumnsType<LLMProviderRecord> = [
    {
      title: '供应商',
      key: 'name',
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={record.avatarUrl}
            icon={<CloudOutlined />}
            className="shadow-sm border border-slate-100 bg-brand-50 text-brand-600"
            size={36}
          />
          <div>
            <span className="font-semibold text-slate-800 text-sm hover:text-brand-600 transition-colors">
              {record.name}
            </span>
          </div>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'providerTypeLabel',
      width: 120,
      render: (value: string, record) => {
        const typeColors: Record<string, string> = {
          openai: 'purple',
          gemini: 'blue',
          claude: 'orange',
          kimi: 'green',
          doubao: 'cyan',
          deepseek: 'geekblue',
          qwen: 'red',
          zhipu: 'gold',
          other: 'magenta',
        };
        const color = typeColors[record.providerType] || 'default';
        return (
          <Tag color={color} className="font-semibold px-2.5 py-0.5 rounded-md border-0">
            {value || record.providerTypeLabel || record.providerType}
          </Tag>
        );
      },
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
      title: 'API 密钥',
      dataIndex: 'apiKey',
      width: 180,
      ellipsis: true,
      render: (key: string) => (
        <span className="font-mono text-xs text-slate-400 select-all tracking-wider">
          {key ? (key.length > 20 ? `${key.substring(0, 8)}...${key.substring(key.length - 8)}` : key) : '-'}
        </span>
      ),
    },
    {
      title: '模型数量',
      key: 'modelCount',
      width: 120,
      render: (_, record) => {
        const defaultModel = record.modelsConfig?.find((m) => m.isDefault);
        return (
          <Tooltip title={defaultModel ? `默认: ${defaultModel.name}` : '未设置默认模型'}>
            <Tag color="cyan" className="cursor-pointer border border-cyan-100 px-2 py-0.5 rounded-md">
              {record.modelsConfig?.length || 0} 个模型
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '状态',
      key: 'isActive',
      width: 90,
      render: (_, record) => (
        <Tag color={record.isActive ? 'success' : 'default'} className="px-2.5 py-0.5 rounded-md font-medium border-0">
          {record.isActive ? '启用中' : '已停用'}
        </Tag>
      ),
    },
    {
      title: '连通性',
      key: 'connection',
      width: 200,
      render: (_, record) => {
        const result = testResults[record.id];
        return (
          <div className="flex items-center gap-2">
            <Button
              size="small"
              icon={testingId === record.id ? <LoadingOutlined /> : <ApiOutlined />}
              loading={testingId === record.id}
              onClick={() => handleTestConnection(record.id)}
              className="border-slate-200 hover:border-brand-500 hover:text-brand-600 flex items-center transition-all rounded-md"
            >
              测试
            </Button>
            {result && (
              <Tag
                icon={result.success ? <CheckCircleOutlined className="text-emerald-500" /> : <CloseCircleOutlined className="text-rose-500" />}
                color={result.success ? 'success' : 'error'}
                className="m-0 font-mono px-2 py-0.5 rounded-md border-0"
              >
                {result.success ? `${result.latencyMs}ms` : '失败'}
              </Tag>
            )}
          </div>
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <div className="flex items-center gap-1">
          {canUpdate && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEditModal(record)}
              className="text-brand-600 hover:text-brand-700 hover:bg-brand-50 rounded-md"
            >
              编辑
            </Button>
          )}
          {canDelete && (
            <Popconfirm title="确定删除该供应商？" onConfirm={() => handleDelete(record.id)}>
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                className="hover:bg-rose-50 rounded-md"
              >
                删除
              </Button>
            </Popconfirm>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5 p-6">
      {/* 顶部 Page Hero */}
      <div className="page-hero">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <CloudOutlined className="text-brand-600" />
              <span>AI 模型供应商管理</span>
            </h1>
            <p className="text-slate-500 mt-1 text-sm">
              配置并接入第三方主流大语言模型服务（OpenAI、Claude、Gemini 等），实时监测模型响应延迟与连通状态。
            </p>
          </div>
          <div className="flex gap-3">
            <div className="bg-brand-50 border border-brand-100 rounded-lg px-4 py-1.5 text-center shadow-sm">
              <div className="text-xs text-brand-600 font-semibold mb-0.5">总供应商</div>
              <div className="text-lg font-bold text-brand-800">{total}</div>
            </div>
            <div className="bg-slate-50 border border-slate-200/60 rounded-lg px-4 py-1.5 text-center shadow-sm">
              <div className="text-xs text-slate-500 font-semibold mb-0.5">已启用</div>
              <div className="text-lg font-bold text-slate-700">
                {items.filter(item => item.isActive).length}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 搜索过滤控制中心 */}
      <div className="bg-white border border-slate-100 shadow-sm rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 transition-all hover:shadow-md duration-300">
        <div className="flex items-center gap-3">
          <Input
            placeholder="搜索供应商名称..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            allowClear
            className="w-64 rounded-lg hover:border-brand-500 focus:border-brand-500 py-1.5"
            prefix={<CloudOutlined className="text-slate-400 mr-1" />}
          />
          <Button
            type="primary"
            className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-lg px-4"
            onClick={handleSearch}
          >
            筛选
          </Button>
          <Button
            onClick={handleReset}
            className="hover:text-brand-600 hover:border-brand-600 rounded-lg px-4"
          >
            重置
          </Button>
        </div>
        {canCreate && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreateModal}
            className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 text-white shadow-sm hover:shadow-md transition-all rounded-lg px-4 py-1.5 h-auto flex items-center font-medium"
          >
            新建供应商
          </Button>
        )}
      </div>

      {/* 表格面板 */}
      <div className="bg-white border border-slate-100 shadow-sm rounded-xl p-4 transition-all hover:shadow-md duration-300">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showTotal: (t) => `共 ${t} 条`,
            onChange: setPage,
          }}
        />
      </div>

      {/* 创建 / 编辑 Modal */}
      <Modal
        title={
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <span className="p-1 bg-brand-50 text-brand-600 rounded">
              <CloudOutlined />
            </span>
            <span className="font-semibold">{editingItem ? '编辑供应商' : '新建供应商'}</span>
          </div>
        }
        open={formVisible}
        onCancel={() => setFormVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={640}
        destroyOnHidden
        forceRender
        className="custom-modal"
      >
        <Form form={form} layout="vertical" className="mt-5 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Form.Item name="name" label="供应商名称" rules={[{ required: true, message: '请输入供应商名称' }]}>
              <Input placeholder="例如：我的 OpenAI 账号" className="rounded-lg" />
            </Form.Item>

            <Form.Item name="providerType" label="供应商类型" rules={[{ required: true }]}>
              <Select options={PROVIDER_TYPE_OPTIONS} placeholder="选择供应商类型" className="rounded-lg" />
            </Form.Item>
          </div>

          <Form.Item name="apiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
            <Input placeholder="https://api.openai.com/v1" className="rounded-lg" />
          </Form.Item>

          <Form.Item
            name="apiKey"
            label="API 密钥"
            rules={[{ required: true, message: '请输入 API 密钥' }]}
          >
            <Input.TextArea placeholder="sk-..." rows={2} className="rounded-lg" />
          </Form.Item>

          <div className="grid gap-4 md:grid-cols-2">
            <Form.Item label="供应商头像">
              <Upload
                listType="picture-card"
                fileList={avatarFile}
                maxCount={1}
                beforeUpload={() => false}
                onChange={({ fileList }) => setAvatarFile(fileList)}
                className="avatar-uploader"
              >
                {avatarFile.length === 0 && (
                  <div className="text-slate-400">
                    <UploadOutlined className="text-lg mb-1" />
                    <div className="text-xs">上传头像</div>
                  </div>
                )}
              </Upload>
              <div className="text-slate-400 text-[11px] mt-1">
                支持 1:1 图片，建议不超过 1MB
              </div>
            </Form.Item>

            <Form.Item name="isActive" label="启用状态" valuePropName="checked">
              <div className="bg-slate-50 border border-slate-200/60 rounded-xl p-4 flex items-center justify-between mt-1">
                <span className="text-xs text-slate-500 font-medium">启用此供应商配置</span>
                <Switch checkedChildren="启用" unCheckedChildren="停用" className="shadow-sm" />
              </div>
            </Form.Item>
          </div>

          <Form.Item label="模型列表" className="border-t border-slate-100 pt-4">
            <div className="space-y-2 max-h-56 overflow-y-auto pr-1 custom-scrollbar">
              {modelsList.length === 0 ? (
                <div className="text-center py-6 border border-dashed border-slate-200 rounded-lg text-slate-400 text-xs">
                  暂无模型，请在下方添加
                </div>
              ) : (
                modelsList.map((model) => (
                  <div
                    key={model.name}
                    className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-100/60 px-3 py-2.5 transition-all duration-200"
                  >
                    <Radio
                      checked={model.isDefault}
                      onChange={() => handleSetDefaultModel(model.name)}
                      className="text-brand-600"
                    />
                    <span className="flex-1 text-sm font-semibold text-slate-700 font-mono">{model.name}</span>
                    {model.isDefault ? (
                      <Tag color="teal" className="m-0 border-0 px-2 py-0.5 rounded-md font-medium">默认</Tag>
                    ) : (
                      <Button
                        type="text"
                        size="small"
                        onClick={() => handleSetDefaultModel(model.name)}
                        className="text-xs text-slate-400 hover:text-brand-600 p-0 h-auto font-medium"
                      >
                        设为默认
                      </Button>
                    )}
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveModel(model.name)}
                      className="hover:bg-rose-50 text-slate-400 hover:text-rose-600 rounded-md"
                    />
                  </div>
                ))
              )}
            </div>
            <Space.Compact className="w-full mt-3">
              <Input
                placeholder="输入模型名称，如 gpt-4o"
                value={newModelName}
                onChange={(e) => setNewModelName(e.target.value)}
                onPressEnter={handleAddModel}
                className="rounded-l-lg py-1.5"
              />
              <Button
                type="primary"
                onClick={handleAddModel}
                icon={<PlusOutlined />}
                className="bg-brand-600 border-brand-600 hover:bg-brand-700 hover:border-brand-700 rounded-r-lg"
              >
                添加
              </Button>
            </Space.Compact>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
