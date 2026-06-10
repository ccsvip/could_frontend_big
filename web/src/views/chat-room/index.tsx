import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Avatar,
  Button,
  Empty,
  Input,
  InputNumber,
  List,
  message,
  Popconfirm,
  Select,
  Spin,
  Switch,
  Typography,
} from 'antd';
import type { InputRef } from 'antd';
import {
  DislikeFilled,
  DislikeOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  LikeFilled,
  LikeOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../store/auth';
import {
  createConversation,
  deleteConversation,
  fetchConversation,
  fetchConversations,
  sendMessageStream,
  updateConversationConfig,
  updateMessageFeedback,
  updateConversationTitle,
  type ChatConversationListItem,
  type ChatConversationDetail,
  type ChatMessage as ChatMessageType,
} from '../../api/modules/chat';
import { fetchCompanyLLMOptions, type CompanyLLMOptions } from '../../api/modules/llm-settings';
import { ChatMarkdown } from '../../components/chat-markdown';

const PAGE_SIZE = 10;
const PROMPT_TEMPLATE_OPTIONS = [
  {
    label: '专业问答',
    value: 'professional_qa',
    prompt: '请使用专业、清晰、结构化的中文回答。优先使用二级标题、项目符号和 Markdown 表格，结论先行。',
  },
  {
    label: '文档整理',
    value: 'doc_structuring',
    prompt: '请把输出整理成易读的 Markdown 文档。需要时使用标题、列表、引用、代码块和总结小节。',
  },
  {
    label: '排障助手',
    value: 'debug_helper',
    prompt: '你是排障助手。请优先给出根因假设、验证步骤、修复建议和风险提示，回答要具体、可执行。',
  },
];

type DisplayAssistantMessage = {
  id: number;
  role: 'assistant';
  content: string;
  conversationId: number;
  created_at: string;
  feedback: 'none' | 'up' | 'down';
  isStreaming?: boolean;
};

export const ChatRoomPage = () => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('ai_models.chat.create');
  const canDelete = hasPermission('ai_models.chat.delete');

  const [conversations, setConversations] = useState<ChatConversationListItem[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [conversationTotal, setConversationTotal] = useState(0);
  const [conversationPage, setConversationPage] = useState(1);
  const [conversationKeyword, setConversationKeyword] = useState('');
  const [searchKeyword, setSearchKeyword] = useState('');

  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDetail, setActiveDetail] = useState<ChatConversationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [inputValue, setInputValue] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<InputRef>(null);
  const streamingContentRef = useRef('');

  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [editingTitleValue, setEditingTitleValue] = useState('');
  const [llmOptions, setLlmOptions] = useState<CompanyLLMOptions | null>(null);
  const [llmProvidersLoading, setLlmProvidersLoading] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  const [updatingConfig, setUpdatingConfig] = useState(false);
  const [useStreamEnabled, setUseStreamEnabled] = useState(true);
  const [systemPromptDraft, setSystemPromptDraft] = useState('');
  const [temperatureDraft, setTemperatureDraft] = useState(0.7);
  const [maxTokensDraft, setMaxTokensDraft] = useState(1000);
  const [selectedPromptTemplate, setSelectedPromptTemplate] = useState<string>();
  const [savingSystemPrompt, setSavingSystemPrompt] = useState(false);

  // --- Local optimistic messages (user msg before server confirms, + streaming assistant msg) ---
  const [pendingUserMsg, setPendingUserMsg] = useState<ChatMessageType | null>(null);

  const modelSelectOptions = useMemo(
    () =>
      (llmOptions?.providers || []).map((provider) => ({
        label: provider.name,
        options: provider.models.map((model) => ({
          label: model.isDefault ? `${model.displayName || model.name}（默认）` : model.displayName || model.name,
          value: model.id,
        })),
      })),
    [llmOptions],
  );

  const defaultModelId = useMemo(() => {
    if (llmOptions?.defaultModelId) return llmOptions.defaultModelId;
    return llmOptions?.providers[0]?.models[0]?.id ?? null;
  }, [llmOptions]);

  const findModelMeta = useCallback((modelId: number | null) => {
    if (!modelId) return null;
    for (const provider of llmOptions?.providers || []) {
      const model = provider.models.find((item) => item.id === modelId);
      if (model) return { provider, model };
    }
    return null;
  }, [llmOptions]);

  const syncConversationMeta = useCallback(
    (
      conversationId: number,
      modelId: number | null,
      nextSummary?: string,
      nextTitle?: string,
    ) => {
      const meta = findModelMeta(modelId);

      setConversations((prev) =>
        prev.map((item) =>
          item.id === conversationId
            ? {
                ...item,
                title: nextTitle ?? item.title,
                llmModelId: modelId,
                llmModelName: meta?.model.name || '',
                llmModelDisplayName: meta?.model.displayName || '',
                llmProviderName: meta?.provider.name ?? null,
                summary: nextSummary ?? item.summary,
              }
            : item,
        ),
      );
    },
    [findModelMeta],
  );

  const loadActiveProviders = useCallback(async () => {
    setLlmProvidersLoading(true);
    try {
      const response = await fetchCompanyLLMOptions();
      setLlmOptions(response);
    } finally {
      setLlmProvidersLoading(false);
    }
  }, []);

  // Load conversation list
  const loadConversations = useCallback(async () => {
    setConversationsLoading(true);
    try {
      const data = await fetchConversations(conversationPage, searchKeyword);
      setConversations(data.results);
      setConversationTotal(data.count);
    } finally {
      setConversationsLoading(false);
    }
  }, [conversationPage, searchKeyword]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    loadActiveProviders();
  }, [loadActiveProviders]);

  // Load active conversation detail
  const loadDetail = useCallback(async () => {
    if (!activeId) {
      setActiveDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const data = await fetchConversation(activeId);
      setActiveDetail(data);
      if (streamingContentRef.current) {
        const matchedAssistant = data.messages.some(
          (messageItem) =>
            messageItem.role === 'assistant'
            && messageItem.content === streamingContentRef.current,
        );
        if (matchedAssistant) {
          setStreamingContent('');
        }
      }
    } catch (err: unknown) {
      // If conversation was deleted (e.g., by admin), reset to empty state
      if (err && typeof err === 'object' && 'response' in err) {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) {
          setActiveId(null);
          setActiveDetail(null);
          loadConversations();
          return;
        }
      }
    } finally {
      setDetailLoading(false);
    }
  }, [activeId, loadConversations]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (activeDetail?.llmModelId) {
      setSelectedModelId(activeDetail.llmModelId);
      return;
    }

    setSelectedModelId((currentValue) => {
      if (currentValue && findModelMeta(currentValue)) {
        return currentValue;
      }
      return defaultModelId;
    });
  }, [activeDetail?.id, activeDetail?.llmModelId, defaultModelId, findModelMeta]);

  useEffect(() => {
    setSystemPromptDraft(activeDetail?.systemPrompt ?? '');
    setTemperatureDraft(activeDetail?.temperature ?? 0.7);
    setMaxTokensDraft(activeDetail?.maxTokens ?? 1000);
  }, [activeDetail?.id, activeDetail?.systemPrompt, activeDetail?.temperature, activeDetail?.maxTokens]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeDetail?.messages?.length, streamingContent, pendingUserMsg]);

  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  const finalizeStreaming = useCallback(() => {
    setStreaming(false);
    setPendingUserMsg(null);
    setTimeout(() => {
      loadDetail();
      loadConversations();
    }, 300);
  }, [loadConversations, loadDetail]);

  const handleNewConversation = async () => {
    if (!canCreate) return;
    try {
      const conv = await createConversation({
        title: '新对话',
        llmModelId: selectedModelId ?? defaultModelId,
        systemPrompt: systemPromptDraft,
        temperature: temperatureDraft,
        maxTokens: maxTokensDraft,
      });
      setConversations((prev) => [conv, ...prev]);
      setActiveId(conv.id);
      setInputValue('');
      inputRef.current?.focus();
    } catch {
      message.error('创建会话失败');
    }
  };

  const handleSelectConversation = (id: number) => {
    if (streaming) return;
    setActiveId(id);
    setActiveDetail(null);
    setPendingUserMsg(null);
    setStreamingContent('');
  };

  const handleDeleteConversation = async (id: number) => {
    if (!canDelete) return;
    try {
      await deleteConversation(id);
      if (activeId === id) {
        setActiveId(null);
        setActiveDetail(null);
      }
      loadConversations();
      message.success('已删除');
    } catch {
      message.error('删除失败');
    }
  };

  const handleStartEditTitle = (conv: ChatConversationListItem) => {
    setEditingTitleId(conv.id);
    setEditingTitleValue(conv.title);
  };

  const handleSaveTitle = async (id: number) => {
    const trimmed = editingTitleValue.trim();
    if (!trimmed) return;
    try {
      await updateConversationTitle(id, trimmed);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c)),
      );
      if (activeId === id && activeDetail) {
        setActiveDetail({ ...activeDetail, title: trimmed });
      }
    } catch {
      message.error('修改标题失败');
    }
    setEditingTitleId(null);
  };

  const handleModelChange = async (value: number) => {
    setSelectedModelId(value);
    if (!activeId || !activeDetail) {
      return;
    }

    if (activeDetail.llmModelId === value) {
      return;
    }

    const previousValue = activeDetail.llmModelId ?? defaultModelId;

    setUpdatingConfig(true);
    try {
      const nextDetail = await updateConversationConfig(activeId, {
        llmModelId: value,
        systemPrompt: systemPromptDraft,
        temperature: temperatureDraft,
        maxTokens: maxTokensDraft,
      });
      setActiveDetail(nextDetail);
      syncConversationMeta(
        activeId,
        value,
        nextDetail.summary,
        nextDetail.title,
      );
      message.success('已切换聊天模型');
    } catch {
      setSelectedModelId(previousValue);
      message.error('切换模型失败');
    } finally {
      setUpdatingConfig(false);
    }
  };

  const handleSend = useCallback(async () => {
    const content = inputValue.trim();
    if (!content || !activeId || streaming) return;

    // Optimistic user message
    const optimisticMsg: ChatMessageType = {
      id: -Date.now(),
      conversationId: activeId,
      role: 'user',
      content,
      feedback: 'none',
      created_at: new Date().toISOString(),
    };
    setPendingUserMsg(optimisticMsg);
    setInputValue('');
    setStreaming(true);
    setStreamingContent('');

    try {
      abortRef.current = await sendMessageStream(
        activeId,
        content,
        useStreamEnabled,
        null,
        // onChunk
        (text) => {
          setStreamingContent((prev) => prev + text);
        },
        // onTitle
        (title) => {
          setConversations((prev) =>
            prev.map((item) => (item.id === activeId ? { ...item, title } : item)),
          );
          setActiveDetail((prev) => (prev && prev.id === activeId ? { ...prev, title } : prev));
        },
        // onSummary
        (summary) => {
          setConversations((prev) =>
            prev.map((item) => (item.id === activeId ? { ...item, summary } : item)),
          );
          setActiveDetail((prev) => (prev && prev.id === activeId ? { ...prev, summary } : prev));
        },
        // onError
        (error) => {
          message.error(error);
        },
        // onDone
        () => {
          finalizeStreaming();
        },
      );
    } catch {
      finalizeStreaming();
      message.error('发送失败');
    }
  }, [activeId, finalizeStreaming, streaming, useStreamEnabled, inputValue]);

  const handleSaveSystemPrompt = async () => {
    if (!activeId || !activeDetail) {
      message.info('当前提示词会用于下一个新建会话');
      return;
    }

    const modelId = selectedModelId ?? activeDetail.llmModelId ?? defaultModelId;

    setSavingSystemPrompt(true);
    try {
      const nextDetail = await updateConversationConfig(activeId, {
        llmModelId: modelId,
        systemPrompt: systemPromptDraft,
        temperature: temperatureDraft,
        maxTokens: maxTokensDraft,
      });
      setActiveDetail(nextDetail);
      syncConversationMeta(activeId, modelId, nextDetail.summary, nextDetail.title);
      message.success('系统提示词已保存');
    } catch {
      message.error('保存系统提示词失败');
    } finally {
      setSavingSystemPrompt(false);
    }
  };

  const handleApplyPromptTemplate = (templateValue?: string) => {
    setSelectedPromptTemplate(templateValue);
    const template = PROMPT_TEMPLATE_OPTIONS.find((item) => item.value === templateValue);
    if (template) {
      setSystemPromptDraft(template.prompt);
    }
  };

  const handleSearchConversation = () => {
    setConversationPage(1);
    setSearchKeyword(conversationKeyword.trim());
  };

  const handleResetConversationSearch = () => {
    setConversationKeyword('');
    setSearchKeyword('');
    setConversationPage(1);
  };

  const latestAssistantMessageId = [...(activeDetail?.messages ?? [])]
    .reverse()
    .find((item) => item.role === 'assistant')?.id ?? null;

  const handleFeedback = async (messageId: number, feedback: 'up' | 'down') => {
    if (!activeId) return;
    const currentMessage = activeDetail?.messages.find((item) => item.id === messageId);
    const nextFeedback = currentMessage?.feedback === feedback ? 'none' : feedback;
    try {
      const updatedMessage = await updateMessageFeedback(activeId, messageId, nextFeedback);
      setActiveDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((item) => (item.id === messageId ? updatedMessage : item)),
        };
      });
    } catch {
      message.error('反馈提交失败');
    }
  };

  const handleRegenerateReply = async (assistantMessageId: number) => {
    if (!activeId || streaming) return;
    setStreaming(true);
    setStreamingContent('');
    try {
      abortRef.current = await sendMessageStream(
        activeId,
        '',
        useStreamEnabled,
        assistantMessageId,
        (text) => {
          setStreamingContent((prev) => prev + text);
        },
        (title) => {
          setConversations((prev) =>
            prev.map((item) => (item.id === activeId ? { ...item, title } : item)),
          );
          setActiveDetail((prev) => (prev && prev.id === activeId ? { ...prev, title } : prev));
        },
        (summary) => {
          setConversations((prev) =>
            prev.map((item) => (item.id === activeId ? { ...item, summary } : item)),
          );
          setActiveDetail((prev) => (prev && prev.id === activeId ? { ...prev, summary } : prev));
        },
        (error) => {
          message.error(error);
        },
        () => {
          finalizeStreaming();
        },
      );
    } catch {
      finalizeStreaming();
      message.error('重新生成失败');
    }
  };

  const handleStopStreaming = () => {
    abortRef.current?.abort();
    finalizeStreaming();
  };

  // Compute display messages
  const displayMessages: Array<ChatMessageType | DisplayAssistantMessage> = [
    ...(activeDetail?.messages || []),
  ];
  if (pendingUserMsg && activeDetail) {
    // Avoid duplicate if the detail already includes the optimistic msg
    const exists = displayMessages.some((m) => m.id === pendingUserMsg.id);
    if (!exists) displayMessages.push(pendingUserMsg);
  }
  const hasPersistedAssistantMatch = Boolean(
    streamingContent
    && activeDetail?.messages.some(
      (messageItem) =>
        messageItem.role === 'assistant' && messageItem.content === streamingContent,
    ),
  );
  if (streamingContent && (streaming || !hasPersistedAssistantMatch)) {
    displayMessages.push({
      id: -1,
      conversationId: activeId ?? 0,
      role: 'assistant',
      content: streamingContent,
      created_at: new Date().toISOString(),
      feedback: 'none',
      isStreaming: true,
    });
  }

  const handleCopyReply = async (replyContent: string) => {
    try {
      await navigator.clipboard.writeText(replyContent);
      message.success('已复制回复');
    } catch {
      message.error('复制失败，请检查浏览器权限');
    }
  };

  const renderModelSelector = (className?: string) => (
    <Select
      className={className}
      aria-label="聊天模型"
      popupMatchSelectWidth={false}
      showSearch
      optionFilterProp="label"
      placeholder={llmProvidersLoading ? '加载模型中...' : '请选择聊天模型'}
      value={selectedModelId ?? undefined}
      options={modelSelectOptions}
      onChange={handleModelChange}
      loading={llmProvidersLoading || updatingConfig}
      disabled={streaming || llmProvidersLoading || modelSelectOptions.length === 0}
      notFoundContent="暂无可用模型，请联系管理员配置 LLM 设置"
    />
  );

  return (
    <div className="flex h-[calc(100dvh-180px)] min-h-[560px] gap-0 overflow-hidden rounded-xl border border-slate-200/70 bg-white shadow-card">
      {/* Left sidebar: conversations list */}
      <div className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-slate-50/60 sm:flex md:w-64 lg:w-72">
        {/* Header */}
        <div className="space-y-3 border-b border-slate-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <Typography.Text strong className="text-sm">对话列表</Typography.Text>
            <Button
              type="primary"
              size="small"
              icon={<PlusOutlined />}
              onClick={handleNewConversation}
              disabled={!canCreate || modelSelectOptions.length === 0}
            >
              新对话
            </Button>
          </div>
          <div className="flex gap-2">
            <Input
              id="conversation-search"
              name="conversationSearch"
              aria-label="搜索对话"
              autoComplete="off"
              size="small"
              placeholder="搜索标题或消息内容"
              value={conversationKeyword}
              onChange={(event) => setConversationKeyword(event.target.value)}
              onPressEnter={handleSearchConversation}
            />
            <Button size="small" onClick={handleSearchConversation}>搜索</Button>
            <Button size="small" onClick={handleResetConversationSearch}>重置</Button>
          </div>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto">
          <List
            loading={conversationsLoading}
            dataSource={conversations}
            renderItem={(conv) => (
              <div
                key={conv.id}
                className={`group flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2.5 transition-colors hover:bg-teal-50/60 ${
                  activeId === conv.id ? 'bg-teal-50 border-l-2 border-l-teal-600' : ''
                }`}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <MessageOutlined className="text-slate-400 text-sm shrink-0" />
                <div className="min-w-0 flex-1">
                  {editingTitleId === conv.id ? (
                    <Input
                      size="small"
                      value={editingTitleValue}
                      onChange={(e) => setEditingTitleValue(e.target.value)}
                      onPressEnter={() => handleSaveTitle(conv.id)}
                      onBlur={() => handleSaveTitle(conv.id)}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                      className="!text-xs"
                    />
                  ) : (
                    <>
                      <Typography.Text
                        className="!text-xs block truncate"
                        ellipsis
                      >
                        {conv.title}
                      </Typography.Text>
                      {(conv.summary || conv.lastMessage) && (
                        <Typography.Text
                          type="secondary"
                          className="!text-[10px] block truncate"
                        >
                          {conv.summary || conv.lastMessage}
                        </Typography.Text>
                      )}
                    </>
                  )}
                </div>
                <div className="hidden shrink-0 group-hover:flex items-center gap-0.5">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleStartEditTitle(conv);
                    }}
                    className="!p-0 !h-5 !w-5 !text-slate-400 hover:!text-teal-600"
                  />
                  {canDelete && (
                    <Popconfirm
                      title="确定删除此对话？"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteConversation(conv.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                        className="!p-0 !h-5 !w-5 !text-slate-400 hover:!text-red-500"
                      />
                    </Popconfirm>
                  )}
                </div>
              </div>
            )}
            locale={{ emptyText: '暂无对话' }}
          />
          {conversationTotal > PAGE_SIZE && (
            <div className="flex justify-center gap-2 py-2">
              <Button
                size="small"
                disabled={conversationPage <= 1}
                onClick={() => setConversationPage((p) => p - 1)}
              >
                上一页
              </Button>
              <Typography.Text className="self-center text-xs text-slate-400">
                {conversationPage} / {Math.ceil(conversationTotal / PAGE_SIZE)}
              </Typography.Text>
              <Button
                size="small"
                disabled={conversationPage >= Math.ceil(conversationTotal / PAGE_SIZE)}
                onClick={() => setConversationPage((p) => p + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Right: chat area */}
      <div className="flex flex-1 min-w-0">
        <div className="flex min-w-0 flex-1 flex-col">
        {activeId && activeDetail ? (
          <>
            {/* Chat header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 bg-white">
              <div className="flex items-center gap-2 min-w-0">
                <RobotOutlined className="text-teal-600 text-lg shrink-0" />
                <Typography.Text strong className="truncate">
                  {activeDetail.title}
                </Typography.Text>
                {activeDetail.llmProviderName && (
                  <Typography.Text type="secondary" className="!text-xs shrink-0">
                    · {activeDetail.llmProviderName}
                    {activeDetail.llmModelName && ` / ${activeDetail.llmModelDisplayName || activeDetail.llmModelName}`}
                  </Typography.Text>
                )}
              </div>
              <Typography.Text type="secondary" className="!text-xs shrink-0">
                {useStreamEnabled ? '流式回复' : '非流式回复'}
              </Typography.Text>
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 bg-gradient-to-b from-slate-50/30 to-white">
              {detailLoading && (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-slate-500">
                  <Spin />
                  <span>加载消息中...</span>
                </div>
              )}
              {displayMessages.map((msg) => {
                const isUser = msg.role === 'user';
                const isStreamingMsg = 'isStreaming' in msg && msg.isStreaming;

                return (
                  <div
                    key={msg.id}
                    className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`flex gap-2.5 max-w-[75%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                      {/* Avatar */}
                      <Avatar
                        size={32}
                        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
                        className={
                          isUser
                            ? '!bg-gradient-to-br !from-teal-600 !to-teal-700 shrink-0'
                            : '!bg-emerald-500 shrink-0'
                        }
                      />
                      {/* Bubble */}
                      <div
                        className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                          isUser
                            ? 'bg-gradient-to-br from-teal-600 to-teal-700 text-white rounded-tr-md'
                            : 'bg-slate-100 text-slate-800 rounded-tl-md'
                        }`}
                      >
                        {isUser ? (
                          msg.content
                        ) : (
                          <div className="space-y-2">
                            <div className="flex justify-end">
                              {!isStreamingMsg && (
                                <>
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={msg.feedback === 'up' ? <LikeFilled /> : <LikeOutlined />}
                                    onClick={() => handleFeedback(msg.id, 'up')}
                                    className={`!h-6 !px-2 ${msg.feedback === 'up' ? '!text-teal-600' : '!text-slate-400 hover:!text-teal-600'}`}
                                  >
                                    点赞
                                  </Button>
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={msg.feedback === 'down' ? <DislikeFilled /> : <DislikeOutlined />}
                                    onClick={() => handleFeedback(msg.id, 'down')}
                                    className={`!h-6 !px-2 ${msg.feedback === 'down' ? '!text-red-500' : '!text-slate-400 hover:!text-red-500'}`}
                                  >
                                    点踩
                                  </Button>
                                </>
                              )}
                              {msg.id === latestAssistantMessageId && !streaming && (
                                <Button
                                  type="text"
                                  size="small"
                                  icon={<RobotOutlined />}
                                  onClick={() => handleRegenerateReply(msg.id)}
                                  className="!h-6 !px-2 !text-slate-400 hover:!text-emerald-500"
                                >
                                  重新生成
                                </Button>
                              )}
                              <Button
                                type="text"
                                size="small"
                                icon={<CopyOutlined />}
                                onClick={() => handleCopyReply(msg.content)}
                                className="!h-6 !px-2 !text-slate-400 hover:!text-teal-600"
                              >
                                复制
                              </Button>
                            </div>
                            <ChatMarkdown content={msg.content} className="chat-markdown" />
                          </div>
                        )}
                        {isStreamingMsg && (
                          <span className="inline-block w-0.5 h-4 ml-0.5 bg-slate-400 animate-pulse align-middle" />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              {streaming && !streamingContent && (
                <div className="flex justify-start">
                  <div className="flex gap-2.5 max-w-[75%]">
                    <Avatar size={32} icon={<RobotOutlined />} className="!bg-emerald-500 shrink-0" />
                    <div className="rounded-2xl rounded-tl-md bg-slate-100 px-4 py-2.5">
                      <Spin size="small" />
                      <Typography.Text type="secondary" className="ml-2 text-sm">思考中...</Typography.Text>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-slate-200 bg-white px-5 py-3">
              <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                <span>
                  当前模式：{useStreamEnabled ? '流式回复' : '非流式回复'}
                </span>
                {!useStreamEnabled && (
                  <span>关闭后会等待完整回答返回，再一次性展示。</span>
                )}
              </div>
              <div className="flex gap-2">
                <Input
                  id="chat-message-input"
                  name="chatMessage"
                  aria-label="聊天消息"
                  autoComplete="off"
                  ref={inputRef}
                  placeholder="输入消息，Enter 发送..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onPressEnter={handleSend}
                  disabled={!canCreate || streaming}
                  size="large"
                  className="flex-1"
                />
                {streaming ? (
                  <Button
                    danger
                    size="large"
                    onClick={handleStopStreaming}
                    className="shrink-0"
                  >
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    size="large"
                    icon={<SendOutlined />}
                    onClick={handleSend}
                    disabled={!inputValue.trim() || !canCreate}
                    className="shrink-0"
                  >
                    发送
                  </Button>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <Empty
              image={<MessageOutlined style={{ fontSize: 64, color: '#8c8c8c' }} />}
              description={
                <div className="space-y-3">
                  <Typography.Text type="secondary">选择一个对话开始聊天</Typography.Text>
                  <div className="flex items-center justify-center gap-2">
                    <Typography.Text type="secondary" className="!text-xs">
                      流式回复
                    </Typography.Text>
                    <Switch
                      size="small"
                      checked={useStreamEnabled}
                      onChange={setUseStreamEnabled}
                    />
                  </div>
                  <div>{renderModelSelector('min-w-[260px]')}</div>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleNewConversation}
                    disabled={!canCreate || modelSelectOptions.length === 0}
                    className="mt-3"
                  >
                    新建对话
                  </Button>
                </div>
              }
            />
          </div>
        )}
        </div>

        <div className="hidden w-72 shrink-0 flex-col border-l border-slate-200 bg-slate-50/70 xl:flex xl:w-80">
          <div className="border-b border-slate-200 px-4 py-3">
            <Typography.Text strong className="text-sm">会话配置</Typography.Text>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <div className="space-y-2">
              <Typography.Text type="secondary" className="!text-xs">
                聊天模型
              </Typography.Text>
              {renderModelSelector('w-full')}
            </div>

            <div className="space-y-2">
              <Typography.Text type="secondary" className="!text-xs">
                流式回复
              </Typography.Text>
              <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                <span className="text-sm text-slate-700">
                  {useStreamEnabled ? '开启，边生成边展示' : '关闭，完整回答后展示'}
                </span>
                <Switch
                  size="small"
                  checked={useStreamEnabled}
                  onChange={setUseStreamEnabled}
                  disabled={streaming}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Typography.Text type="secondary" className="!text-xs">
                系统提示词
              </Typography.Text>
              <Select
                value={selectedPromptTemplate}
                options={PROMPT_TEMPLATE_OPTIONS.map((item) => ({
                  label: item.label,
                  value: item.value,
                }))}
                placeholder="选择提示词模板"
                onChange={handleApplyPromptTemplate}
                allowClear
              />
              <Input.TextArea
                id="system-prompt-draft"
                name="systemPromptDraft"
                aria-label="系统提示词"
                value={systemPromptDraft}
                onChange={(event) => setSystemPromptDraft(event.target.value)}
                rows={12}
                placeholder="例如：请用结构化、专业但简洁的语气回答；遇到表格时优先输出 Markdown 表格。"
                className="resize-none"
              />
              <Typography.Text type="secondary" className="!text-[11px] block leading-5">
                {activeId
                  ? '保存后将作用于当前会话后续提问。'
                  : '当前填写的提示词会用于下一个新建会话。'}
              </Typography.Text>
              <Button
                type="primary"
                block
                onClick={handleSaveSystemPrompt}
                loading={savingSystemPrompt}
                disabled={streaming}
              >
                {activeId ? '保存到当前会话' : '提示词将在新建会话时生效'}
              </Button>
            </div>

            <div className="space-y-3">
              <Typography.Text type="secondary" className="!text-xs">
                推理参数
              </Typography.Text>
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
                <div className="space-y-1">
                  <Typography.Text type="secondary" className="!text-[11px]">
                    Temperature
                  </Typography.Text>
                  <InputNumber
                    id="temperature-draft"
                    name="temperatureDraft"
                    aria-label="Temperature"
                    min={0}
                    max={2}
                    step={0.1}
                    value={temperatureDraft}
                    onChange={(value) => setTemperatureDraft(typeof value === 'number' ? value : 0.7)}
                    className="w-full"
                  />
                </div>
                <div className="space-y-1">
                  <Typography.Text type="secondary" className="!text-[11px]">
                    Max Tokens
                  </Typography.Text>
                  <InputNumber
                    id="max-tokens-draft"
                    name="maxTokensDraft"
                    aria-label="Max Tokens"
                    min={1}
                    max={320000}
                    step={100}
                    value={maxTokensDraft}
                    onChange={(value) => setMaxTokensDraft(typeof value === 'number' ? value : 1000)}
                    className="w-full"
                  />
                </div>
              </div>
            </div>

            {activeDetail?.summary && (
              <div className="space-y-2">
                <Typography.Text type="secondary" className="!text-xs">
                  会话摘要
                </Typography.Text>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
                  {activeDetail.summary}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
