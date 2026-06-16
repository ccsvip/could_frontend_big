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
  fetchAgentApplicationStats,
  fetchAgentApplications,
  updateAgentApplication,
  type AgentApplicationPayload,
  type AgentApplicationRecord,
  type AgentApplicationStats,
} from '../../api/modules/applications';
import {
  fetchConversation,
  fetchConversations,
  sendMessageStream,
  updateConversationConfig,
  type ChatConversationDetail,
  type ChatMessage,
  type ChatConversationRecord,
} from '../../api/modules/chat';
import { fetchKnowledgeDocuments, type KnowledgeDocumentRecord } from '../../api/modules/knowledge-base';
import { fetchCompanyLLMOptions, type CompanyLLMOptions } from '../../api/modules/llm-settings';
import { ChatMarkdown } from '../../components/chat-markdown';
import { useAuthStore } from '../../store/auth';
import dayjs from 'dayjs';

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
  llmModelId?: number | null;
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

const buildApplicationPayload = (values: ConfigFormValues): AgentApplicationPayload => ({
  name: values.name.trim(),
  description: values.description?.trim() || '',
  llmModelId: values.llmModelId ?? null,
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
  const [llmOptions, setLlmOptions] = useState<CompanyLLMOptions | null>(null);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentRecord[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  
  // Tab control state
  const [activeTab, setActiveTab] = useState<'orchestrate' | 'logs' | 'monitor'>('orchestrate');

  // Debug session state (Orchestration Tab)
  const [conversation, setConversation] = useState<ChatConversationDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // History & Log state (Logs Tab)
  const [logConversations, setLogConversations] = useState<ChatConversationRecord[]>([]);
  const [logConversationsLoading, setLogConversationsLoading] = useState(false);
  const [selectedLogConversation, setSelectedLogConversation] = useState<ChatConversationDetail | null>(null);
  const [selectedLogConversationLoading, setSelectedLogConversationLoading] = useState(false);

  // Monitor stats state (Monitor Tab)
  const [stats, setStats] = useState<AgentApplicationStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const selectedApplicationId = useMemo(() => {
    if (!applicationId) return null;
    const parsed = Number(applicationId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [applicationId]);

  const modelOptions = useMemo(
    () =>
      (llmOptions?.providers || []).map((provider) => ({
        label: provider.name,
        options: provider.models.map((model) => ({
          label: model.displayName || model.name,
          value: model.id,
        })),
      })),
    [llmOptions],
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
      const [nextOptions, nextDocuments] = await Promise.all([
        fetchCompanyLLMOptions(),
        fetchAllKnowledgeDocuments(),
      ]);
      setLlmOptions(nextOptions);
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
        llmModelId: detail.llmModelId,
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

  // Reset Detail page state when application ID changes
  useEffect(() => {
    setActiveTab('orchestrate');
    setSelectedLogConversation(null);
    setLogConversations([]);
    setStats(null);
  }, [selectedApplicationId]);

  // Fetch Log Sessions
  const loadLogConversations = useCallback(async () => {
    if (!selectedApplicationId) return;
    setLogConversationsLoading(true);
    try {
      const data = await fetchConversations({ application: selectedApplicationId });
      setLogConversations(data.results);
      if (data.results.length > 0 && !selectedLogConversation) {
        void loadSelectedLogConversation(data.results[0].id);
      }
    } catch {
      message.error('日志会话加载失败');
    } finally {
      setLogConversationsLoading(false);
    }
  }, [selectedApplicationId, selectedLogConversation]);

  const loadSelectedLogConversation = async (conversationId: number) => {
    setSelectedLogConversationLoading(true);
    try {
      const detail = await fetchConversation(conversationId);
      setSelectedLogConversation(detail);
    } catch {
      message.error('日志详情加载失败');
    } finally {
      setSelectedLogConversationLoading(false);
    }
  };

  // Fetch Monitor Statistics
  const loadStats = useCallback(async () => {
    if (!selectedApplicationId) return;
    setStatsLoading(true);
    try {
      const data = await fetchAgentApplicationStats(selectedApplicationId);
      setStats(data);
    } catch {
      message.error('监测数据加载失败');
    } finally {
      setStatsLoading(false);
    }
  }, [selectedApplicationId]);

  // Load tab-specific data
  useEffect(() => {
    if (activeTab === 'logs') {
      void loadLogConversations();
    } else if (activeTab === 'monitor') {
      void loadStats();
    }
  }, [activeTab, loadLogConversations, loadStats]);

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
          llmModelId: payload.llmModelId,
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
              智能体工作室 <span className="inline-flex items-center rounded-full bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400 border border-brand-500/20">Studio</span>
            </h1>
            <p className="text-slate-400 text-sm md:text-base max-w-xl">
              在这里构建、部署和管理您的专属智能体，连接大语言模型与知识库。
            </p>
          </div>
          <div className="absolute -right-8 -bottom-10 opacity-5 pointer-events-none flex items-center justify-center">
            <RobotOutlined className="text-[180px] text-white" />
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
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
      </div>

      {/* Applications Grid */}
      <Spin spinning={listLoading}>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {/* Create Agent Card (Fixed First Card) */}
          {canCreate && (
            <div
              onClick={() => setCreateOpen(true)}
              className="group flex min-h-[280px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white p-6 cursor-pointer hover:border-brand-500 hover:bg-brand-50/5 transition-all duration-300 shadow-soft"
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-50 border border-slate-100 text-2xl text-slate-400 group-hover:bg-brand-500 group-hover:text-white group-hover:border-brand-500 transition-all duration-300 mb-4 shadow-sm">
                <PlusOutlined />
              </div>
              <span className="text-slate-800 font-bold text-base group-hover:text-brand-600 transition-colors duration-200">
                创建智能体
              </span>
              <span className="text-slate-400 text-xs mt-2 max-w-[180px] text-center leading-relaxed">
                构建全新大模型智能助手，连接知识库与指令
              </span>
            </div>
          )}

          {applications.map((application) => (
            <div
              key={application.id}
              className="group relative flex min-h-[280px] flex-col rounded-2xl border border-slate-200/60 bg-white p-6 shadow-card transition-all duration-300 hover:shadow-card-hover hover:-translate-y-1 hover:border-brand-200 overflow-hidden"
            >
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
                  <span className="rounded-full bg-slate-50 border border-slate-100 px-2.5 py-0.5 font-sans text-slate-600">
                    模型: {application.llmModelDisplayName || application.llmModelName || '未设置'}
                  </span>
                  <span className="rounded-full bg-brand-50 border border-brand-100/50 px-2.5 py-0.5 text-brand-700 font-medium">
                    {application.knowledgeDocumentIds.length} 个知识库
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>更新时间: {dayjs(application.updated_at).format('YYYY-MM-DD HH:mm')}</span>
                </div>

                <div className="flex justify-between items-center mt-1">
                  <div className="flex items-center gap-2">
                    <Switch
                      size="small"
                      checked={application.isActive}
                      disabled={!canUpdate}
                      onChange={async (checked) => {
                        try {
                          await updateAgentApplication(application.id, { isActive: checked });
                          message.success(`应用已${checked ? '启用' : '停用'}`);
                          await loadApplications();
                        } catch {
                          message.error('状态修改失败');
                        }
                      }}
                    />
                    <span className="text-xs text-slate-500">{application.isActive ? '已启用' : '已停用'}</span>
                  </div>

                  <Button
                    type="link"
                    className="!px-0 !font-semibold !text-slate-500 group-hover:!text-brand-600 flex items-center gap-1 transition-all duration-200"
                    onClick={() => navigate(`${application.id}`)}
                  >
                    <span>进入</span>
                    <ArrowRightOutlined className="transition-transform duration-200 group-hover:translate-x-1" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
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

  const renderOrchestrateTab = () => (
    <Spin spinning={detailLoading || optionsLoading}>
      <div className="grid gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        {/* Left panel - Config */}
        <div className="flex min-h-0 flex-col rounded-2xl border border-slate-200/60 bg-white shadow-card overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4 bg-slate-50/50 flex items-center justify-between">
            <Typography.Text className="text-slate-900 font-bold text-sm">智能体编排</Typography.Text>
            <span className="text-xs text-slate-400 font-medium">Configuration</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            <Form
              form={configForm}
              layout="vertical"
              initialValues={{ temperature: DEFAULT_TEMPERATURE, maxTokens: DEFAULT_MAX_TOKENS, isActive: true }}
              className="space-y-4"
            >
              <Form.Item name="name" label={<span className="text-slate-700 font-semibold text-xs">智能体名称</span>} rules={[{ required: true, message: '请输入智能体名称' }]}>
                <Input disabled={!canUpdate} maxLength={128} className="!rounded-lg" />
              </Form.Item>
              <Form.Item name="description" label={<span className="text-slate-700 font-semibold text-xs">描述说明</span>}>
                <Input.TextArea disabled={!canUpdate} rows={2} maxLength={255} className="!rounded-lg" />
              </Form.Item>
              <Form.Item name="llmModelId" label={<span className="text-slate-700 font-semibold text-xs">选用模型</span>}>
                <Select
                  allowClear
                  disabled={!canUpdate || modelOptions.length === 0}
                  options={modelOptions}
                  placeholder={modelOptions.length === 0 ? '暂无可用模型' : '请选择模型'}
                  className="!rounded-lg"
                />
              </Form.Item>
              <Form.Item name="systemPrompt" label={<span className="text-slate-700 font-semibold text-xs">系统提示词 (System Prompt)</span>}>
                <Input.TextArea disabled={!canUpdate} rows={6} className="!rounded-lg font-mono text-xs" />
              </Form.Item>
              <Form.Item name="knowledgeDocumentIds" label={<span className="text-slate-700 font-semibold text-xs">绑定知识库文档</span>}>
                <Select
                  mode="multiple"
                  allowClear
                  disabled={!canUpdate}
                  optionFilterProp="label"
                  options={knowledgeDocuments.map((document) => {
                    const isTxtOrMd = ['txt', 'md'].includes(document.fileExtension?.toLowerCase() || '');
                    return {
                      label: `${document.title || document.fileName}${isTxtOrMd ? '' : ' (暂不参与检索)'}`,
                      value: document.id,
                    };
                  })}
                  className="!rounded-lg"
                />
              </Form.Item>
              <Form.Item name="temperature" label={<span className="text-slate-700 font-semibold text-xs">多样性温度 (Temperature)</span>}>
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
              <Typography.Text className="text-slate-900 font-bold text-sm">调试预览</Typography.Text>
            </div>
            {conversation ? (
              <span className="bg-brand-50 border border-brand-100 text-brand-700 px-2 py-0.5 rounded-full font-mono text-xs">
                调试会话ID: #{conversation.id}
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
                <span className="text-sm">发送消息开始智能体调试预览</span>
              </div>
            )}
          </div>
          
          <div className="border-t border-slate-100 px-6 py-5 bg-white">
            <div className="flex gap-2">
              <Input
                size="large"
                value={inputValue}
                placeholder="输入消息，与调试智能体对话..."
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
  );

  const renderLogsTab = () => (
    <Spin spinning={logConversationsLoading}>
      <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)] min-h-[calc(100vh-230px)]">
        {/* Left Side: Session List */}
        <div className="flex flex-col bg-white border border-slate-200/60 rounded-2xl shadow-card overflow-hidden">
          <div className="border-b border-slate-100 px-5 py-4 bg-slate-50/50 flex items-center justify-between">
            <Typography.Text className="text-slate-900 font-bold text-sm">历史会话记录</Typography.Text>
            <span className="text-xs text-slate-400 font-medium">{logConversations.length} 个历史会话</span>
          </div>
          
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-[calc(100vh-320px)]">
            {logConversations.length > 0 ? (
              logConversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => void loadSelectedLogConversation(conv.id)}
                  className={`px-5 py-4 cursor-pointer transition-colors duration-150 hover:bg-slate-50/80 ${
                    selectedLogConversation?.id === conv.id ? 'bg-brand-50/30 border-l-4 border-brand-500' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <Typography.Text className="font-semibold text-slate-950 truncate max-w-[190px]">
                      {conv.title}
                    </Typography.Text>
                    <Typography.Text className="text-slate-400 text-xs shrink-0 font-mono">
                      {dayjs(conv.updated_at).format('MM-DD HH:mm')}
                    </Typography.Text>
                  </div>
                  <Typography.Paragraph className="text-slate-500 text-xs !mb-2 truncate">
                    {conv.summary || conv.lastMessage || '暂无内容'}
                  </Typography.Paragraph>
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="bg-slate-50 border border-slate-100 px-2 py-0.5 rounded font-mono text-slate-500">
                      {conv.llmModelDisplayName || conv.llmModelName || '未知模型'}
                    </span>
                    <span className="flex items-center gap-1 font-medium text-slate-400">
                      <MessageOutlined className="text-xs" /> {conv.messageCount} 条消息
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex h-full items-center justify-center py-20">
                <Empty description="暂无历史会话" />
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Message Details */}
        <div className="flex flex-col bg-white border border-slate-200/60 rounded-2xl shadow-card overflow-hidden min-h-[400px]">
          {selectedLogConversation ? (
            <Spin spinning={selectedLogConversationLoading} className="flex-1 flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 bg-slate-50/50">
                <div className="min-w-0">
                  <Typography.Text className="text-slate-900 font-bold text-sm block truncate">
                    {selectedLogConversation.title}
                  </Typography.Text>
                  <Typography.Text className="text-slate-400 text-xs">
                    会话ID: #{selectedLogConversation.id} • 创建时间: {dayjs(selectedLogConversation.created_at).format('YYYY-MM-DD HH:mm:ss')}
                  </Typography.Text>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-6 bg-slate-50/20 max-h-[calc(100vh-360px)]">
                {selectedLogConversation.messages.length > 0 ? (
                  selectedLogConversation.messages.map((msg) => {
                    const isUser = msg.role === 'user';
                    return (
                      <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-5`}>
                        <div className={`flex max-w-[85%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                          <Avatar
                            size={36}
                            icon={isUser ? <MessageOutlined /> : <RobotOutlined />}
                            className={isUser ? '!bg-brand-600 shadow-sm border border-brand-500/20' : '!bg-emerald-600 shadow-sm border border-emerald-500/20'}
                          />
                          <div className="flex flex-col gap-1">
                            <div
                              className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-soft ${
                                isUser
                                  ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-tr-none'
                                  : 'bg-white border border-slate-100 text-slate-800 rounded-tl-none'
                              }`}
                            >
                              {isUser ? (
                                <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                              ) : (
                                <ChatMarkdown content={msg.content} className="chat-markdown" />
                              )}
                            </div>
                            <div className={`text-[10px] text-slate-400 flex items-center gap-2 px-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
                              <span>{dayjs(msg.created_at).format('HH:mm:ss')}</span>
                              {!isUser && msg.feedback !== 'none' && (
                                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${
                                  msg.feedback === 'up' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
                                }`}>
                                  {msg.feedback === 'up' ? '已点赞' : '已点踩'}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-400 py-20">
                    <span>无会话消息记录</span>
                  </div>
                )}
              </div>
            </Spin>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3 py-20">
              <MessageOutlined className="text-4xl text-slate-300" />
              <span className="text-sm">选择左侧历史会话查看消息详情</span>
            </div>
          )}
        </div>
      </div>
    </Spin>
  );

  const renderMonitorTab = () => {
    if (statsLoading) {
      return (
        <div className="flex h-64 items-center justify-center bg-white border border-slate-200/60 rounded-2xl">
          <Spin size="large" />
        </div>
      );
    }

    if (!stats) {
      return (
        <div className="flex h-64 flex-col items-center justify-center bg-white border border-slate-200/60 rounded-2xl text-slate-400 gap-3">
          <Empty description="暂无监测数据" />
        </div>
      );
    }

    const maxTrendCount = Math.max(1, ...stats.dailyTrends.map((d) => d.count));

    return (
      <div className="space-y-6">
        {/* Metric Cards Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="bg-white border border-slate-200/60 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow duration-150">
            <Typography.Text className="text-slate-400 text-xs font-semibold block mb-1">会话总数</Typography.Text>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 font-mono">{stats.conversationCount}</span>
              <span className="text-slate-400 text-xs">次</span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400">
              在该智能体下开启的调试与交互会话
            </div>
          </div>

          <div className="bg-white border border-slate-200/60 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow duration-150">
            <Typography.Text className="text-slate-400 text-xs font-semibold block mb-1">消息总量</Typography.Text>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 font-mono">{stats.messageCount}</span>
              <span className="text-slate-400 text-xs">条</span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between">
              <span>用户: <b className="text-slate-700 font-mono">{stats.userMessageCount}</b></span>
              <span>助手: <b className="text-slate-700 font-mono">{stats.assistantMessageCount}</b></span>
            </div>
          </div>

          <div className="bg-white border border-slate-200/60 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow duration-150">
            <Typography.Text className="text-slate-400 text-xs font-semibold block mb-1">用户好评度</Typography.Text>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 font-mono">
                {(stats.upCount + stats.downCount) > 0 ? `${Math.round((stats.upCount / (stats.upCount + stats.downCount)) * 100)}%` : '--'}
              </span>
              <span className="text-slate-400 text-xs">满意率</span>
            </div>
            <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between">
              <span className="text-emerald-600 font-medium">点赞: <b className="font-mono">{stats.upCount}</b></span>
              <span className="text-red-500 font-medium">点踩: <b className="font-mono">{stats.downCount}</b></span>
            </div>
          </div>

          <div className="bg-white border border-slate-200/60 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow duration-150">
            <Typography.Text className="text-slate-400 text-xs font-semibold block mb-1">最近配置修改</Typography.Text>
            <div className="text-sm font-semibold text-slate-900 mt-2 truncate">
              {dayjs(stats.updatedAt).format('YYYY-MM-DD')}
            </div>
            <div className="mt-2 text-[11px] text-slate-400">
              {dayjs(stats.updatedAt).format('HH:mm:ss')} (最近保存)
            </div>
          </div>
        </div>

        {/* 7-Day Trend Chart */}
        <div className="bg-white border border-slate-200/60 rounded-2xl p-6 shadow-sm">
          <Typography.Title level={5} className="!text-slate-900 !font-bold !mb-6">
            最近 7 天会话数趋势
          </Typography.Title>
          
          <div className="flex items-end justify-between h-48 pt-4 px-4 border-b border-slate-100">
            {stats.dailyTrends.map((trend) => {
              const pct = (trend.count / maxTrendCount) * 100;
              return (
                <div key={trend.date} className="flex flex-col items-center flex-1 group">
                  <div className="opacity-0 group-hover:opacity-100 bg-slate-800 text-white text-[10px] font-semibold px-2 py-0.5 rounded shadow-sm mb-1.5 transition-opacity duration-150 pointer-events-none tabular-nums">
                    {trend.count} 次
                  </div>
                  <div
                    className="w-8 sm:w-12 bg-gradient-to-t from-brand-500 to-teal-500 rounded-t-lg transition-all duration-300 hover:from-brand-600 hover:to-teal-600"
                    style={{ height: `${Math.max(4, pct)}%` }}
                  />
                  <span className="text-[11px] text-slate-400 mt-3 font-medium font-mono">
                    {trend.date}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  const renderApplicationWorkspace = () => {
    return (
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
                {selectedApplication?.name || '智能体工作室'}
              </Typography.Title>
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
                <Typography.Text className="text-slate-400 text-xs font-medium">
                  {selectedApplication?.llmProviderName
                    ? `${selectedApplication.llmProviderName} / ${selectedApplication.llmModelDisplayName || selectedApplication.llmModelName}`
                    : '未选择模型'}
                </Typography.Text>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {activeTab === 'orchestrate' && (
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
            )}
          </div>
        </div>

        {/* Tab Sidebars */}
        <div className="flex flex-col lg:flex-row gap-5 min-h-[calc(100vh-230px)]">
          <div className="w-full lg:w-56 shrink-0 flex flex-row lg:flex-col gap-1 bg-white border border-slate-200/60 p-2 rounded-2xl shadow-sm h-fit">
            <button
              onClick={() => setActiveTab('orchestrate')}
              className={`flex-1 lg:flex-initial flex items-center gap-2.5 px-4 py-3 text-sm font-semibold rounded-xl transition-all duration-200 ${
                activeTab === 'orchestrate'
                  ? 'bg-brand-50 text-brand-600 shadow-sm border border-brand-100/50'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <AppstoreOutlined className="text-base" />
              <span>编排</span>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex-1 lg:flex-initial flex items-center gap-2.5 px-4 py-3 text-sm font-semibold rounded-xl transition-all duration-200 ${
                activeTab === 'logs'
                  ? 'bg-brand-50 text-brand-600 shadow-sm border border-brand-100/50'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <BookOutlined className="text-base" />
              <span>日志与标注</span>
            </button>
            <button
              onClick={() => setActiveTab('monitor')}
              className={`flex-1 lg:flex-initial flex items-center gap-2.5 px-4 py-3 text-sm font-semibold rounded-xl transition-all duration-200 ${
                activeTab === 'monitor'
                  ? 'bg-brand-50 text-brand-600 shadow-sm border border-brand-100/50'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <RobotOutlined className="text-base" />
              <span>监测</span>
            </button>
          </div>

          <div className="flex-1 min-w-0">
            {activeTab === 'orchestrate' && renderOrchestrateTab()}
            {activeTab === 'logs' && renderLogsTab()}
            {activeTab === 'monitor' && renderMonitorTab()}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="relative min-h-full bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:16px_16px] bg-slate-50/50 px-5 py-6 text-slate-900 lg:px-8">
      {selectedApplicationId ? renderApplicationWorkspace() : renderApplicationList()}
      <Modal
        title={<span className="text-slate-900 font-bold">创建智能体</span>}
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void handleCreate()}
        okText="创建"
        cancelText="取消"
        confirmLoading={createSaving}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical" className="mt-4">
          <Form.Item name="name" label={<span className="text-slate-700 font-medium">智能体名称</span>} rules={[{ required: true, message: '请输入智能体名称' }]}>
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
