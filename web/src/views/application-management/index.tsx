import {
  AppstoreOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  BookOutlined,
  DeleteOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SaveOutlined,
  SearchOutlined,
  SendOutlined,
} from '@ant-design/icons';
import {
  Avatar,
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Slider,
  Spin,
  Switch,
  Typography,
  message,
} from 'antd';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createAgentApplication,
  createAgentApplicationConversation,
  deleteAgentApplication,
  fetchAgentApplication,
  fetchAgentApplications,
  updateAgentApplication,
  type AgentApplicationPayload,
  type AgentApplicationRecord,
} from '../../api/modules/applications';
import { fetchConversation, sendMessageStream, updateConversationConfig, type ChatConversationDetail, type ChatMessage } from '../../api/modules/chat';
import { fetchKnowledgeDocuments, type KnowledgeDocumentRecord } from '../../api/modules/knowledge-base';
import { fetchLLMProviders, type LLMProviderRecord } from '../../api/modules/llm-providers';
import { ChatMarkdown } from '../../components/chat-markdown';
import { useAuthStore } from '../../store/auth';

const PAGE_SIZE = 10;
const DEFAULT_TEMPERATURE = 0.7;
const DEFAULT_MAX_TOKENS = 1000;

type CreateFormValues = {
  name: string;
  description?: string;
};

type ConfigFormValues = {
  name: string;
  description?: string;
  llmProviderId?: number | null;
  modelName?: string;
  systemPrompt?: string;
  knowledgeDocumentIds?: number[];
  temperature: number;
  maxTokens: number;
  isActive: boolean;
};

const normalizePageCount = (count: number, pageSize: number) => Math.max(1, Math.ceil(count / pageSize));

const fetchAllKnowledgeDocuments = async () => {
  const firstPage = await fetchKnowledgeDocuments({ page: 1 });
  const documents = [...firstPage.results];
  let page = 2;
  while (firstPage.next && documents.length < firstPage.count) {
    const nextPage = await fetchKnowledgeDocuments({ page });
    documents.push(...nextPage.results);
    if (!nextPage.next) break;
    page += 1;
  }
  return documents;
};

const fetchAllActiveProviders = async () => {
  const firstPage = await fetchLLMProviders({ page: 1, isActive: 'active' });
  const providers = [...firstPage.results];
  let page = 2;
  while (firstPage.next && providers.length < firstPage.count) {
    const nextPage = await fetchLLMProviders({ page, isActive: 'active' });
    providers.push(...nextPage.results);
    if (!nextPage.next) break;
    page += 1;
  }
  return providers.filter((provider) => provider.isActive);
};

const buildApplicationPayload = (values: ConfigFormValues): AgentApplicationPayload => ({
  name: values.name.trim(),
  description: values.description?.trim() || '',
  llmProviderId: values.llmProviderId ?? null,
  modelName: values.modelName || '',
  systemPrompt: values.systemPrompt || '',
  knowledgeDocumentIds: values.knowledgeDocumentIds || [],
  temperature: values.temperature,
  maxTokens: values.maxTokens,
  isActive: values.isActive,
});

export const ApplicationManagementPage = () => {
  const { applicationId } = useParams<{ applicationId?: string }>();
  const navigate = useNavigate();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('agent_applications.create');
  const canUpdate = hasPermission('agent_applications.update');
  const canDelete = hasPermission('agent_applications.delete');
  const canChat = hasPermission('ai_models.chat.create');

  const [createForm] = Form.useForm<CreateFormValues>();
  const [configForm] = Form.useForm<ConfigFormValues>();
  const selectedProviderId = Form.useWatch('llmProviderId', configForm);

  const [applications, setApplications] = useState<AgentApplicationRecord[]>([]);
  const [applicationTotal, setApplicationTotal] = useState(0);
  const [applicationPage, setApplicationPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [listLoading, setListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [selectedApplication, setSelectedApplication] = useState<AgentApplicationRecord | null>(null);
  const [providers, setProviders] = useState<LLMProviderRecord[]>([]);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentRecord[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [conversation, setConversation] = useState<ChatConversationDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const selectedApplicationId = useMemo(() => {
    if (!applicationId) return null;
    const parsed = Number(applicationId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [applicationId]);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedProviderId) || null,
    [providers, selectedProviderId],
  );

  const modelOptions = useMemo(
    () =>
      selectedProvider?.modelsConfig
        .filter((model) => model.name)
        .map((model) => ({ label: model.name, value: model.name })) || [],
    [selectedProvider],
  );

  const loadApplications = useCallback(async () => {
    setListLoading(true);
    try {
      const response = await fetchAgentApplications({ page: applicationPage, keyword });
      setApplications(response.results);
      setApplicationTotal(response.count);
    } catch {
      message.error('应用列表加载失败');
    } finally {
      setListLoading(false);
    }
  }, [applicationPage, keyword]);

  const loadOptions = useCallback(async () => {
    setOptionsLoading(true);
    try {
      const [nextProviders, nextDocuments] = await Promise.all([
        fetchAllActiveProviders(),
        fetchAllKnowledgeDocuments(),
      ]);
      setProviders(nextProviders);
      setKnowledgeDocuments(nextDocuments);
    } catch {
      message.error('应用配置选项加载失败');
    } finally {
      setOptionsLoading(false);
    }
  }, []);

  const loadSelectedApplication = useCallback(async () => {
    if (!selectedApplicationId) {
      setSelectedApplication(null);
      setConversation(null);
      setMessages([]);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await fetchAgentApplication(selectedApplicationId);
      setSelectedApplication(detail);
      configForm.setFieldsValue({
        name: detail.name,
        description: detail.description,
        llmProviderId: detail.llmProviderId,
        modelName: detail.modelName,
        systemPrompt: detail.systemPrompt,
        knowledgeDocumentIds: detail.knowledgeDocumentIds,
        temperature: detail.temperature,
        maxTokens: detail.maxTokens,
        isActive: detail.isActive,
      });
      setConversation(null);
      setMessages([]);
      setStreamingContent('');
      setInputValue('');
    } catch {
      message.error('应用详情加载失败');
      navigate('..', { replace: true, relative: 'path' });
    } finally {
      setDetailLoading(false);
    }
  }, [configForm, navigate, selectedApplicationId]);

  useEffect(() => {
    void loadApplications();
  }, [loadApplications]);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  useEffect(() => {
    void loadSelectedApplication();
  }, [loadSelectedApplication]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, streamingContent]);

  const handleProviderChange = (providerId: number | null) => {
    const provider = providers.find((item) => item.id === providerId);
    const defaultModel = provider?.modelsConfig.find((model) => model.isDefault)?.name || provider?.modelsConfig[0]?.name || '';
    configForm.setFieldValue('modelName', defaultModel);
  };

  const handleSearch = () => {
    setApplicationPage(1);
    setKeyword(searchValue.trim());
  };

  const navigateToApplicationList = useCallback(
    (replace = false) => {
      navigate('..', { replace, relative: 'path' });
    },
    [navigate],
  );

  const handleCreate = async () => {
    const values = await createForm.validateFields();
    setCreateSaving(true);
    try {
      const created = await createAgentApplication({
        name: values.name.trim(),
        description: values.description?.trim() || '',
        temperature: DEFAULT_TEMPERATURE,
        maxTokens: DEFAULT_MAX_TOKENS,
        isActive: true,
      });
      message.success('应用已创建');
      createForm.resetFields();
      setCreateOpen(false);
      await loadApplications();
      navigate(`${created.id}`);
    } catch {
      message.error('应用创建失败');
    } finally {
      setCreateSaving(false);
    }
  };

  const handleSaveConfig = async () => {
    if (!selectedApplication || !canUpdate) return;
    const values = await configForm.validateFields();
    setConfigSaving(true);
    try {
      const payload = buildApplicationPayload(values);
      const updated = await updateAgentApplication(selectedApplication.id, payload);
      setSelectedApplication(updated);
      configForm.setFieldsValue({
        ...payload,
        knowledgeDocumentIds: updated.knowledgeDocumentIds,
      });
      if (conversation) {
        const nextConversation = await updateConversationConfig(conversation.id, {
          llmProviderId: payload.llmProviderId,
          modelName: payload.modelName,
          systemPrompt: payload.systemPrompt,
          temperature: payload.temperature,
          maxTokens: payload.maxTokens,
        });
        setConversation(nextConversation);
      }
      message.success('应用配置已保存');
      await loadApplications();
    } catch {
      message.error('应用配置保存失败');
    } finally {
      setConfigSaving(false);
    }
  };

  const handleDelete = async (application: AgentApplicationRecord) => {
    await deleteAgentApplication(application.id);
    message.success('应用已删除');
    if (selectedApplicationId === application.id) {
      navigateToApplicationList();
    }
    await loadApplications();
  };

  const ensureConversation = async () => {
    if (conversation) return conversation;
    if (!selectedApplication) return null;
    setChatLoading(true);
    try {
      const nextConversation = await createAgentApplicationConversation(selectedApplication.id);
      setConversation(nextConversation);
      setMessages(nextConversation.messages);
      return nextConversation;
    } finally {
      setChatLoading(false);
    }
  };

  const refreshConversation = async (conversationId: number) => {
    const nextConversation = await fetchConversation(conversationId);
    setConversation(nextConversation);
    setMessages(nextConversation.messages);
    setStreamingContent('');
  };

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || streaming || !canChat) return;
    const activeConversation = await ensureConversation();
    if (!activeConversation) return;

    const localUserMessage: ChatMessage = {
      id: -Date.now(),
      conversationId: activeConversation.id,
      role: 'user',
      content,
      feedback: 'none',
      created_at: new Date().toISOString(),
    };
    setInputValue('');
    setMessages((current) => [...current, localUserMessage]);
    setStreaming(true);
    setStreamingContent('');

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      setStreaming(false);
      abortRef.current = null;
      void refreshConversation(activeConversation.id).catch(() => {
        message.error('会话刷新失败');
      });
    };

    const controller = await sendMessageStream(
      activeConversation.id,
      content,
      true,
      null,
      (text) => setStreamingContent((current) => current + text),
      () => undefined,
      () => undefined,
      (error) => message.error(error),
      finish,
    );
    abortRef.current = controller;
  };

  const handleStopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  };

  const displayedMessages = useMemo(() => {
    if (!streamingContent) return messages;
    return [
      ...messages,
      {
        id: -1,
        conversationId: conversation?.id || 0,
        role: 'assistant' as const,
        content: streamingContent,
        feedback: 'none' as const,
        created_at: new Date().toISOString(),
      },
    ];
  }, [conversation?.id, messages, streamingContent]);

  const renderApplicationList = () => (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <Typography.Title level={2} className="!mb-1 !text-slate-950">
            应用工作室
          </Typography.Title>
          <Typography.Text className="text-slate-500">
            在这里构建、部署和管理您的 Gemini 专属智能体
          </Typography.Text>
        </div>
        <Button
          type="primary"
          size="large"
          icon={<PlusOutlined />}
          disabled={!canCreate}
          onClick={() => setCreateOpen(true)}
          className="!h-11 !rounded-lg"
        >
          创建应用
        </Button>
      </div>

      <div className="flex flex-col gap-3 border-b border-slate-200 pb-6 md:flex-row md:items-center md:justify-between">
        <Input
          size="large"
          allowClear
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder="搜索应用名称或描述..."
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
          onPressEnter={handleSearch}
          className="max-w-xl !rounded-lg"
        />
        <Typography.Text className="text-slate-500">共 {applicationTotal} 个应用</Typography.Text>
      </div>

      <Spin spinning={listLoading}>
        {applications.length > 0 ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {applications.map((application) => (
              <div
                key={application.id}
                className="group flex min-h-[260px] flex-col rounded-lg border border-slate-200 bg-white p-6 shadow-sm transition hover:border-indigo-200 hover:shadow-md"
              >
                <div className="mb-6 flex items-start justify-between gap-3">
                  <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-indigo-50 text-2xl text-indigo-600">
                    <AppstoreOutlined />
                  </div>
                  {canDelete && (
                    <Popconfirm
                      title="删除应用"
                      description="删除后不可恢复"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => void handleDelete(application)}
                    >
                      <Button type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  )}
                </div>
                <Typography.Title level={4} className="!mb-3 !text-slate-950">
                  {application.name}
                </Typography.Title>
                <Typography.Paragraph ellipsis={{ rows: 2 }} className="!mb-5 !text-slate-500">
                  {application.description || '暂无描述'}
                </Typography.Paragraph>
                <div className="mt-auto border-t border-slate-100 pt-4">
                  <div className="mb-4 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="rounded bg-slate-100 px-2 py-1 font-mono text-slate-700">
                      Temp: {application.temperature}
                    </span>
                    <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">
                      {application.knowledgeDocumentIds.length} 个知识库
                    </span>
                  </div>
                  <Button
                    type="link"
                    className="!px-0 !font-semibold !text-slate-600 group-hover:!text-indigo-600"
                    onClick={() => navigate(`${application.id}`)}
                  >
                    去编排 <ArrowRightOutlined />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-200 bg-white py-16">
            <Empty description="暂无应用" />
          </div>
        )}
      </Spin>

      {applicationTotal > PAGE_SIZE && (
        <div className="flex justify-center gap-3">
          <Button disabled={applicationPage <= 1} onClick={() => setApplicationPage((page) => page - 1)}>
            上一页
          </Button>
          <Typography.Text className="self-center text-slate-500">
            {applicationPage} / {normalizePageCount(applicationTotal, PAGE_SIZE)}
          </Typography.Text>
          <Button
            disabled={applicationPage >= normalizePageCount(applicationTotal, PAGE_SIZE)}
            onClick={() => setApplicationPage((page) => page + 1)}
          >
            下一页
          </Button>
        </div>
      )}
    </div>
  );

  const renderChatMessage = (chatMessage: ChatMessage) => {
    const isUser = chatMessage.role === 'user';
    return (
      <div key={chatMessage.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className={`flex max-w-[78%] gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <Avatar
            size={32}
            icon={isUser ? <MessageOutlined /> : <RobotOutlined />}
            className={isUser ? '!bg-indigo-600' : '!bg-emerald-500'}
          />
          <div
            className={`rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
              isUser ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-800'
            }`}
          >
            {isUser ? (
              <span className="whitespace-pre-wrap break-words">{chatMessage.content}</span>
            ) : (
              <ChatMarkdown content={chatMessage.content} className="chat-markdown" />
            )}
            {chatMessage.id === -1 && (
              <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-slate-400 align-middle" />
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderApplicationWorkspace = () => (
    <div className="flex min-h-[calc(100vh-150px)] flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigateToApplicationList()} />
          <div className="min-w-0">
            <Typography.Title level={3} className="!mb-0 truncate !text-slate-950">
              {selectedApplication?.name || '应用编排'}
            </Typography.Title>
            <Typography.Text className="text-slate-500">
              {selectedApplication?.llmProviderName || '未选择模型供应商'}
            </Typography.Text>
          </div>
        </div>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          loading={configSaving}
          disabled={!canUpdate}
          onClick={() => void handleSaveConfig()}
          className="!rounded-lg"
        >
          保存配置
        </Button>
      </div>

      <Spin spinning={detailLoading || optionsLoading}>
        <div className="grid min-h-[calc(100vh-220px)] gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
          <div className="flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-5 py-4">
              <Typography.Text strong>应用配置</Typography.Text>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              <Form form={configForm} layout="vertical" initialValues={{ temperature: DEFAULT_TEMPERATURE, maxTokens: DEFAULT_MAX_TOKENS, isActive: true }}>
                <Form.Item name="name" label="应用名称" rules={[{ required: true, message: '请输入应用名称' }]}>
                  <Input disabled={!canUpdate} maxLength={128} />
                </Form.Item>
                <Form.Item name="description" label="应用描述">
                  <Input.TextArea disabled={!canUpdate} rows={2} maxLength={255} />
                </Form.Item>
                <Form.Item name="llmProviderId" label="模型供应商">
                  <Select
                    allowClear
                    disabled={!canUpdate}
                    options={providers.map((provider) => ({ label: provider.name, value: provider.id }))}
                    onChange={handleProviderChange}
                  />
                </Form.Item>
                <Form.Item name="modelName" label="模型">
                  <Select allowClear disabled={!canUpdate || !selectedProviderId} options={modelOptions} />
                </Form.Item>
                <Form.Item name="systemPrompt" label="系统提示词">
                  <Input.TextArea disabled={!canUpdate} rows={8} />
                </Form.Item>
                <Form.Item name="knowledgeDocumentIds" label="知识库">
                  <Select
                    mode="multiple"
                    allowClear
                    disabled={!canUpdate}
                    optionFilterProp="label"
                    options={knowledgeDocuments.map((document) => ({
                      label: document.title || document.fileName,
                      value: document.id,
                    }))}
                  />
                </Form.Item>
                <Form.Item name="temperature" label="Temperature">
                  <Slider disabled={!canUpdate} min={0} max={2} step={0.1} marks={{ 0: '0', 1: '1', 2: '2' }} />
                </Form.Item>
                <Form.Item name="maxTokens" label="最大输出 Tokens" rules={[{ required: true, message: '请输入最大输出 Tokens' }]}>
                  <InputNumber disabled={!canUpdate} min={1} max={320000} className="!w-full" />
                </Form.Item>
                <Form.Item name="isActive" label="启用状态" valuePropName="checked">
                  <Switch disabled={!canUpdate} />
                </Form.Item>
              </Form>
            </div>
          </div>

          <div className="flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div className="flex items-center gap-2">
                <RobotOutlined className="text-emerald-600" />
                <Typography.Text strong>调试对话</Typography.Text>
              </div>
              <Typography.Text className="text-xs text-slate-400">
                {conversation ? `#${conversation.id}` : '未开始'}
              </Typography.Text>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/60 px-5 py-4">
              {chatLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Spin />
                </div>
              ) : displayedMessages.length > 0 ? (
                <div className="space-y-4">
                  {displayedMessages.map(renderChatMessage)}
                  <div ref={messagesEndRef} />
                </div>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Empty image={<BookOutlined className="text-5xl text-slate-300" />} description="暂无调试消息" />
                </div>
              )}
            </div>
            <div className="border-t border-slate-100 px-5 py-4">
              <div className="flex gap-2">
                <Input
                  size="large"
                  value={inputValue}
                  placeholder="输入消息..."
                  disabled={!canChat || streaming || !selectedApplication}
                  onChange={(event) => setInputValue(event.target.value)}
                  onPressEnter={() => void handleSend()}
                />
                {streaming ? (
                  <Button size="large" danger onClick={handleStopStreaming}>
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    size="large"
                    icon={<SendOutlined />}
                    disabled={!inputValue.trim() || !canChat || !selectedApplication}
                    onClick={() => void handleSend()}
                  >
                    发送
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </Spin>
    </div>
  );

  return (
    <div className="min-h-full bg-slate-50 px-5 py-6 text-slate-900 lg:px-8">
      {selectedApplicationId ? renderApplicationWorkspace() : renderApplicationList()}
      <Modal
        title="创建应用"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void handleCreate()}
        okText="创建"
        cancelText="取消"
        confirmLoading={createSaving}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="name" label="应用名称" rules={[{ required: true, message: '请输入应用名称' }]}>
            <Input maxLength={128} />
          </Form.Item>
          <Form.Item name="description" label="应用描述">
            <Input.TextArea rows={3} maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
