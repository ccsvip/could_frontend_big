import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Button,
  Card,
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
        <Space>
          <Avatar src={record.avatarUrl} icon={<CloudOutlined />} />
          <span>{record.name}</span>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'providerTypeLabel',
      width: 120,
    },
    {
      title: 'API 地址',
      dataIndex: 'apiBaseUrl',
      ellipsis: true,
    },
    {
      title: 'API 密钥',
      dataIndex: 'apiKey',
      width: 180,
      ellipsis: true,
    },
    {
      title: '模型数量',
      key: 'modelCount',
      width: 100,
      render: (_, record) => {
        const defaultModel = record.modelsConfig?.find((m) => m.isDefault);
        return (
          <Tooltip title={defaultModel ? `默认: ${defaultModel.name}` : undefined}>
            <Tag color="blue">{record.modelsConfig?.length || 0} 个</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '状态',
      key: 'isActive',
      width: 80,
      render: (_, record) => (
        <Tag color={record.isActive ? 'green' : 'default'}>{record.isActive ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '连通性',
      key: 'connection',
      width: 200,
      render: (_, record) => {
        const result = testResults[record.id];
        return (
          <Space>
            <Button
              size="small"
              icon={testingId === record.id ? <LoadingOutlined /> : <ApiOutlined />}
              loading={testingId === record.id}
              onClick={() => handleTestConnection(record.id)}
            >
              测试
            </Button>
            {result && (
              <Tag
                icon={result.success ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                color={result.success ? 'success' : 'error'}
              >
                {result.success ? `${result.latencyMs}ms` : '失败'}
              </Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space>
          {canUpdate && (
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
              编辑
            </Button>
          )}
          {canDelete && (
            <Popconfirm title="确定删除该供应商？" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <Card size="small">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Space wrap>
            <Input
              placeholder="搜索供应商名称"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
              style={{ width: 220 }}
            />
            <Button type="primary" onClick={handleSearch}>筛选</Button>
            <Button onClick={handleReset}>重置</Button>
          </Space>
          {canCreate && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
              新建供应商
            </Button>
          )}
        </div>
      </Card>

      <Card size="small">
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
      </Card>

      <Modal
        title={editingItem ? '编辑供应商' : '新建供应商'}
        open={formVisible}
        onCancel={() => setFormVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={640}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="name" label="供应商名称" rules={[{ required: true, message: '请输入供应商名称' }]}>
            <Input placeholder="例如：我的 OpenAI 账号" />
          </Form.Item>

          <Form.Item name="providerType" label="供应商类型" rules={[{ required: true }]}>
            <Select options={PROVIDER_TYPE_OPTIONS} placeholder="选择供应商类型" />
          </Form.Item>

          <Form.Item name="apiBaseUrl" label="API 地址" rules={[{ required: true, message: '请输入 API 地址' }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item
            name="apiKey"
            label="API 密钥"
            rules={[{ required: true, message: '请输入 API 密钥' }]}
          >
            <Input.TextArea placeholder="sk-..." rows={2} />
          </Form.Item>

          <Form.Item label="供应商头像">
            <Upload
              listType="picture-card"
              fileList={avatarFile}
              maxCount={1}
              beforeUpload={() => false}
              onChange={({ fileList }) => setAvatarFile(fileList)}
            >
              {avatarFile.length === 0 && (
                <div>
                  <UploadOutlined />
                  <div className="mt-1 text-xs">上传头像</div>
                </div>
              )}
            </Upload>
          </Form.Item>

          <Form.Item label="模型列表">
            <div className="space-y-2">
              {modelsList.map((model) => (
                <div key={model.name} className="flex items-center gap-2 rounded border border-slate-200 px-3 py-2">
                  <Radio
                    checked={model.isDefault}
                    onChange={() => handleSetDefaultModel(model.name)}
                  />
                  <span className="flex-1 text-sm">{model.name}</span>
                  {model.isDefault && <Tag color="blue" className="!mr-0">默认</Tag>}
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveModel(model.name)}
                  />
                </div>
              ))}
              <Space.Compact className="w-full">
                <Input
                  placeholder="输入模型名称，如 gpt-4o"
                  value={newModelName}
                  onChange={(e) => setNewModelName(e.target.value)}
                  onPressEnter={handleAddModel}
                />
                <Button type="primary" onClick={handleAddModel} icon={<PlusOutlined />}>
                  添加
                </Button>
              </Space.Compact>
            </div>
          </Form.Item>

          <Form.Item name="isActive" label="启用状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
