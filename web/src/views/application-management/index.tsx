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
      {/* Header Banner */}
      <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="relative flex-1 overflow-hidden rounded-2xl bg-gradient-to-r from-slate-950 to-slate-900 border border-slate-800 p-6 md:p-8 text-white shadow-card">
          <div className="relative z-10">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight mb-2 flex items-center gap-2">
              应用工作室 <span className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400 border border-brand-500/20">Studio</span>
            </h1>
            <p className="text-slate-400 text-sm md:text-base max-w-xl">
              在这里构建、部署和管理您的专属智能体，连接底层大语言模型与专属知识资产。
            </p>
          </div>
          <div className="absolute -right-8 -bottom-10 opacity-5 pointer-events-none flex items-center justify-center">
            <RobotOutlined className="text-[180px] text-white" />
          </div>
        </div>
      </div>

      {/* Filter and Create Toolbar */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between bg-white/60 backdrop-blur border border-slate-200/50 p-4 rounded-2xl shadow-sm">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            size="large"
            allowClear
            prefix={<SearchOutlined className="text-slate-400" />}
            placeholder="搜索应用名称或描述..."
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            onPressEnter={handleSearch}
            className="max-w-md !rounded-xl border-slate-200/80 hover:border-brand-500 focus:border-brand-500 shadow-soft"
          />
          <Typography.Text className="text-slate-400 text-sm pl-2">共 {applicationTotal} 个应用</Typography.Text>
        </div>
        <Button
          type="primary"
          size="large"
          icon={<PlusOutlined />}
          disabled={!canCreate}
          onClick={() => setCreateOpen(true)}
          className="!h-11 !rounded-xl bg-gradient-to-r from-brand-500 to-teal-600 hover:from-brand-600 hover:to-teal-700 border-0 shadow-sm shadow-brand-500/20"
        >
          创建应用
        </Button>
      </div>

      {/* Applications Grid */}
      <Spin spinning={listLoading}>
        {applications.length > 0 ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {applications.map((application) => (
              <div
                key={application.id}
                className="group relative flex min-h-[280px] flex-col rounded-2xl border border-slate-200/60 bg-white p-6 shadow-card transition-all duration-300 hover:shadow-card-hover hover:-translate-y-1 hover:border-brand-200 overflow-hidden"
              >
                {/* Accent line shown on hover */}
                <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-brand-400 to-teal-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                
                <div className="mb-6 flex items-start justify-between gap-3">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-brand-50 text-2xl text-brand-600 transition-all duration-300 group-hover:bg-brand-500 group-hover:text-white shadow-sm">
                    <AppstoreOutlined />
                  </div>
                  {canDelete && (
                    <Popconfirm
                      title="删除应用"
                      description="确定要删除该应用吗？删除后不可恢复。"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => void handleDelete(application)}
                    >
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:!bg-red-50"
                      />
                    </Popconfirm>
                  )}
                </div>

                <Typography.Title level={4} className="!mb-2.5 !text-slate-900 group-hover:text-brand-600 transition-colors duration-200">
                  {application.name}
                </Typography.Title>

                <Typography.Paragraph ellipsis={{ rows: 2 }} className="!mb-6 !text-slate-500 text-sm leading-relaxed">
                  {application.description || '暂无描述'}
                </Typography.Paragraph>

                <div className="mt-auto border-t border-slate-100/80 pt-4 flex flex-col gap-3">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-slate-50 border border-slate-100 px-2.5 py-0.5 font-mono text-slate-600">
                      Temp: {application.temperature}
                    </span>
                    <span className="rounded-full bg-brand-50 border border-brand-100/50 px-2.5 py-0.5 text-brand-700 font-medium">
                      {application.knowledgeDocumentIds.length} 个知识库
                    </span>
                  </div>

                  <div className="flex justify-between items-center mt-1">
                    <Button
                      type="link"
                      className="!px-0 !font-semibold !text-slate-500 group-hover:!text-brand-600 flex items-center gap-1 transition-all duration-200"
                      onClick={() => navigate(`${application.id}`)}
                    >
                      <span>去编排</span>
                      <ArrowRightOutlined className="transition-transform duration-200 group-hover:translate-x-1" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white py-16">
            <Empty description="暂无应用" />
          </div>
        )}
      </Spin>

      {applicationTotal > PAGE_SIZE && (
        <div className="flex justify-center items-center gap-4 mt-8">
          <Button
            disabled={applicationPage <= 1}
            onClick={() => setApplicationPage((page) => page - 1)}
            className="!rounded-lg hover:!border-brand-500 hover:!text-brand-500"
          >
            上一页
          </Button>
          <Typography.Text className="text-slate-500 font-medium">
            {applicationPage} / {normalizePageCount(applicationTotal, PAGE_SIZE)}
          </Typography.Text>
          <Button
            disabled={applicationPage >= normalizePageCount(applicationTotal, PAGE_SIZE)}
            onClick={() => setApplicationPage((page) => page + 1)}
            className="!rounded-lg hover:!border-brand-500 hover:!text-brand-500"
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
      <div key={chatMessage.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
        <div className={`flex max-w-[85%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <Avatar
            size={36}
            icon={isUser ? <MessageOutlined /> : <RobotOutlined />}
            className={isUser ? '!bg-brand-600 shadow-sm border border-brand-500/20' : '!bg-emerald-600 shadow-sm border border-emerald-500/20'}
          />
          <div
            className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-soft ${
              isUser
                ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-tr-none'
                : 'bg-white border border-slate-100 text-slate-800 rounded-tl-none'
            }`}
          >
            {isUser ? (
              <span className="whitespace-pre-wrap break-words">{chatMessage.content}</span>
            ) : (
              <ChatMarkdown content={chatMessage.content} className="chat-markdown" />
            )}
            {chatMessage.id === -1 && (
              <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-brand-400 align-middle" />
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderApplicationWorkspace = () => (
    <div className="flex min-h-[calc(100vh-150px)] flex-col gap-4">
      {/* Workspace Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between bg-white/60 backdrop-blur border border-slate-200/50 p-4 rounded-2xl shadow-sm">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigateToApplicationList()}
            className="!rounded-full hover:!border-brand-500 hover:!text-brand-500 flex items-center justify-center h-9 w-9"
          />
          <div className="min-w-0">
            <Typography.Title level={4} className="!mb-0.5 truncate !text-slate-900 !font-bold">
              {selectedApplication?.name || '应用编排'}
            </Typography.Title>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
              <Typography.Text className="text-slate-400 text-xs font-medium">
                {selectedApplication?.llmProviderName || '未选择模型供应商'}
              </Typography.Text>
            </div>
          </div>
        </div>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          loading={configSaving}
          disabled={!canUpdate}
          onClick={() => void handleSaveConfig()}
          className="!h-10 !rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 border-0 shadow-sm shadow-brand-500/20 px-5"
        >
          保存配置
        </Button>
      </div>

      <Spin spinning={detailLoading || optionsLoading}>
        <div className="grid min-h-[calc(100vh-230px)] gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
          {/* Left panel - Config */}
          <div className="flex min-h-0 flex-col rounded-2xl border border-slate-200/60 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4 bg-slate-50/50 flex items-center justify-between">
              <Typography.Text className="text-slate-900 font-bold text-sm">应用配置</Typography.Text>
              <span className="text-xs text-slate-400 font-medium">Configuration</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              <Form
                form={configForm}
                layout="vertical"
                initialValues={{ temperature: DEFAULT_TEMPERATURE, maxTokens: DEFAULT_MAX_TOKENS, isActive: true }}
                className="space-y-4"
              >
                <Form.Item name="name" label={<span className="text-slate-700 font-semibold text-xs">应用名称</span>} rules={[{ required: true, message: '请输入应用名称' }]}>
                  <Input disabled={!canUpdate} maxLength={128} className="!rounded-lg" />
                </Form.Item>
                <Form.Item name="description" label={<span className="text-slate-700 font-semibold text-xs">应用描述</span>}>
                  <Input.TextArea disabled={!canUpdate} rows={2} maxLength={255} className="!rounded-lg" />
                </Form.Item>
                <Form.Item name="llmProviderId" label={<span className="text-slate-700 font-semibold text-xs">模型供应商</span>}>
                  <Select
                    allowClear
                    disabled={!canUpdate}
                    options={providers.map((provider) => ({ label: provider.name, value: provider.id }))}
                    onChange={handleProviderChange}
                    className="!rounded-lg"
                  />
                </Form.Item>
                <Form.Item name="modelName" label={<span className="text-slate-700 font-semibold text-xs">模型</span>}>
                  <Select allowClear disabled={!canUpdate || !selectedProviderId} options={modelOptions} className="!rounded-lg" />
                </Form.Item>
                <Form.Item name="systemPrompt" label={<span className="text-slate-700 font-semibold text-xs">系统提示词</span>}>
                  <Input.TextArea disabled={!canUpdate} rows={6} className="!rounded-lg font-mono text-xs" />
                </Form.Item>
                <Form.Item name="knowledgeDocumentIds" label={<span className="text-slate-700 font-semibold text-xs">知识库</span>}>
                  <Select
                    mode="multiple"
                    allowClear
                    disabled={!canUpdate}
                    optionFilterProp="label"
                    options={knowledgeDocuments.map((document) => ({
                      label: document.title || document.fileName,
                      value: document.id,
                    }))}
                    className="!rounded-lg"
                  />
                </Form.Item>
                <Form.Item name="temperature" label={<span className="text-slate-700 font-semibold text-xs">Temperature</span>}>
                  <Slider disabled={!canUpdate} min={0} max={2} step={0.1} marks={{ 0: '0', 1: '1', 2: '2' }} />
                </Form.Item>
                <Form.Item name="maxTokens" label={<span className="text-slate-700 font-semibold text-xs">最大输出 Tokens</span>} rules={[{ required: true, message: '请输入最大输出 Tokens' }]}>
                  <InputNumber disabled={!canUpdate} min={1} max={320000} className="!w-full !rounded-lg" />
                </Form.Item>
                <Form.Item name="isActive" label={<span className="text-slate-700 font-semibold text-xs">启用状态</span>} valuePropName="checked">
                  <Switch disabled={!canUpdate} />
                </Form.Item>
              </Form>
            </div>
          </div>

          {/* Right panel - Debug Chat */}
          <div className="flex min-h-0 flex-col rounded-2xl border border-slate-200/60 bg-white shadow-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <RobotOutlined className="text-brand-500" />
                <Typography.Text className="text-slate-900 font-bold text-sm">调试对话</Typography.Text>
              </div>
              {conversation ? (
                <span className="bg-brand-50 border border-brand-100 text-brand-700 px-2 py-0.5 rounded-full font-mono text-xs">
                  会话ID: #{conversation.id}
                </span>
              ) : (
                <span className="bg-slate-100 border border-slate-200 text-slate-500 px-2 py-0.5 rounded-full font-mono text-xs">
                  未开始
                </span>
              )}
            </div>
            
            <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/30 px-6 py-5">
              {chatLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Spin />
                </div>
              ) : displayedMessages.length > 0 ? (
                <div className="space-y-2">
                  {displayedMessages.map(renderChatMessage)}
                  <div ref={messagesEndRef} />
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-slate-400 gap-3">
                  <BookOutlined className="text-4xl text-slate-300" />
                  <span className="text-sm">暂无调试消息，输入下方消息即可开始</span>
                </div>
              )}
            </div>
            
            <div className="border-t border-slate-100 px-6 py-5 bg-white">
              <div className="flex gap-2">
                <Input
                  size="large"
                  value={inputValue}
                  placeholder="输入消息，与智能体开始对话..."
                  disabled={!canChat || streaming || !selectedApplication}
                  onChange={(event) => setInputValue(event.target.value)}
                  onPressEnter={() => void handleSend()}
                  className="!rounded-xl border-slate-200 hover:border-brand-500 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/10 shadow-inner bg-slate-50/30"
                />
                {streaming ? (
                  <Button size="large" danger onClick={handleStopStreaming} className="!rounded-xl px-5">
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    size="large"
                    icon={<SendOutlined />}
                    disabled={!inputValue.trim() || !canChat || !selectedApplication}
                    onClick={() => void handleSend()}
                    className={`!rounded-xl px-5 ${inputValue.trim() ? 'bg-gradient-to-r from-brand-500 to-teal-600 hover:from-brand-600 hover:to-teal-700 border-0 text-white' : ''}`}
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
    <div className="relative min-h-full bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:16px_16px] bg-slate-50/50 px-5 py-6 text-slate-900 lg:px-8">
      {selectedApplicationId ? renderApplicationWorkspace() : renderApplicationList()}
      <Modal
        title={<span className="text-slate-900 font-bold">创建应用</span>}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void handleCreate()}
        okText="创建"
        cancelText="取消"
        confirmLoading={createSaving}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical" className="mt-4">
          <Form.Item name="name" label={<span className="text-slate-700 font-medium">应用名称</span>} rules={[{ required: true, message: '请输入应用名称' }]}>
            <Input maxLength={128} className="!rounded-lg" placeholder="给您的智能体起个名字..." />
          </Form.Item>
          <Form.Item name="description" label={<span className="text-slate-700 font-medium">应用描述</span>}>
            <Input.TextArea rows={3} maxLength={255} className="!rounded-lg" placeholder="描述该智能体的用途..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
