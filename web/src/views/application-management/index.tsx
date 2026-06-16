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
  type AgentApplicationRecord,
  type AgentApplicationStats,
  type AgentApplicationPayload,
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
import { fetchAsrStatus, type AsrStatusRecord } from '../../api/modules/asr';
import { fetchCompanyTtsOptions, type CompanyTtsOptions } from '../../api/modules/tts';
import { ChatMarkdown } from '../../components/chat-markdown';
import { useAuthStore } from '../../store/auth';
import { useAgentAudio } from './use-agent-audio';
import dayjs from 'dayjs';
import { Spin, message } from 'antd';

import {
  Theme,
  Button,
  Card,
  Flex,
  Grid,
  Heading,
  Text,
  TextField,
  TextArea,
  Select,
  Slider,
  Switch,
  Avatar,
  Box,
  Badge,
  Popover,
  Checkbox,
  Dialog,
  AlertDialog,
  Tooltip,
} from '@radix-ui/themes';
import {
  Bot,
  User,
  Plus,
  Trash2,
  Save,
  Search,
  Send,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  MessageSquare,
  Sparkles,
  ChevronDown,
  BarChart2,
  HelpCircle,
  RotateCcw,
  Mic,
  MicOff,
  Pause,
  Play,
  Square,
  Volume2,
  GripVertical,
  ChevronUp,
  ChevronDown as ChevronDownIcon,
} from 'lucide-react';

const PAGE_SIZE = 10;
const DEFAULT_TEMPERATURE = 0.7;
const DEFAULT_MAX_TOKENS = 1000;

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

export const ApplicationManagementPage = () => {
  const { applicationId } = useParams<{ applicationId?: string }>();
  const navigate = useNavigate();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('agent_applications.create');
  const canUpdate = hasPermission('agent_applications.update');
  const canDelete = hasPermission('agent_applications.delete');
  const canChat = hasPermission('ai_models.chat.create');

  // List view states
  const [applications, setApplications] = useState<AgentApplicationRecord[]>([]);
  const [applicationTotal, setApplicationTotal] = useState(0);
  const [applicationPage, setApplicationPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [listLoading, setListLoading] = useState(false);

  // Detail / Config form states
  const [selectedApplication, setSelectedApplication] = useState<AgentApplicationRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [llmOptions, setLlmOptions] = useState<CompanyLLMOptions | null>(null);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentRecord[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);

  // Form states (direct React states instead of AntD forms)
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [llmModelId, setLlmModelId] = useState<number | null>(null);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
  const [temperature, setTemperature] = useState(DEFAULT_TEMPERATURE);
  const [maxTokens, setMaxTokens] = useState(DEFAULT_MAX_TOKENS);
  const [isActive, setIsActive] = useState(true);
  const [openingMessageEnabled, setOpeningMessageEnabled] = useState(true);
  const [openingMessage, setOpeningMessage] = useState('');
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [newSuggestedQuestion, setNewSuggestedQuestion] = useState('');
  const [voiceInputEnabled, setVoiceInputEnabled] = useState(false);
  const [replyPlaybackEnabled, setReplyPlaybackEnabled] = useState(false);
  const [asrStatus, setAsrStatus] = useState<AsrStatusRecord | null>(null);
  const [ttsOptions, setTtsOptions] = useState<CompanyTtsOptions | null>(null);
  const agentAudio = useAgentAudio();

  // Create Popup states
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [createSaving, setCreateSaving] = useState(false);
  const [deleteApplicationId, setDeleteApplicationId] = useState<number | null>(null);

  // Tab control state
  const [activeTab, setActiveTab] = useState<'orchestrate' | 'conversation' | 'logs' | 'monitor'>('orchestrate');

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

  const [showExitConfirm, setShowExitConfirm] = useState(false);

  const isDirty = useMemo(() => {
    if (!selectedApplication) return false;
    if (name.trim() !== selectedApplication.name) return true;
    if (description.trim() !== (selectedApplication.description || '')) return true;
    if (llmModelId !== selectedApplication.llmModelId) return true;
    if (systemPrompt !== (selectedApplication.systemPrompt || '')) return true;
    if (temperature !== selectedApplication.temperature) return true;
    if (maxTokens !== selectedApplication.maxTokens) return true;
    if (isActive !== selectedApplication.isActive) return true;
    if (openingMessageEnabled !== selectedApplication.openingMessageEnabled) return true;
    if (openingMessage.trim() !== (selectedApplication.openingMessage || '')) return true;
    if (voiceInputEnabled !== selectedApplication.voiceInputEnabled) return true;
    if (replyPlaybackEnabled !== selectedApplication.replyPlaybackEnabled) return true;

    const previousQuestions = selectedApplication.suggestedQuestions || [];
    if (suggestedQuestions.length !== previousQuestions.length) return true;
    if (!previousQuestions.every((question, index) => question === suggestedQuestions[index])) return true;

    const prevDocs = selectedApplication.knowledgeDocumentIds || [];
    if (selectedDocs.length !== prevDocs.length) return true;
    const currentDocsSet = new Set(selectedDocs);
    return !prevDocs.every((id) => currentDocsSet.has(id));
  }, [
    selectedApplication,
    name,
    description,
    llmModelId,
    systemPrompt,
    selectedDocs,
    temperature,
    maxTokens,
    isActive,
    openingMessageEnabled,
    openingMessage,
    suggestedQuestions,
    voiceInputEnabled,
    replyPlaybackEnabled,
  ]);

  const handleBackClick = () => {
    if (isDirty) {
      setShowExitConfirm(true);
    } else {
      navigateToApplicationList();
    }
  };

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

  const loadConversationServiceStatus = useCallback(async () => {
    try {
      const [nextAsrStatus, nextTtsOptions] = await Promise.all([
        fetchAsrStatus(),
        fetchCompanyTtsOptions(),
      ]);
      setAsrStatus(nextAsrStatus);
      setTtsOptions(nextTtsOptions);
    } catch {
      message.warning('语音服务状态加载失败');
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
      
      // Populate local state values
      setName(detail.name);
      setDescription(detail.description || '');
      setLlmModelId(detail.llmModelId);
      setSystemPrompt(detail.systemPrompt || '');
      setSelectedDocs(detail.knowledgeDocumentIds || []);
      setTemperature(detail.temperature);
      setMaxTokens(detail.maxTokens);
      setIsActive(detail.isActive);
      setOpeningMessageEnabled(detail.openingMessageEnabled);
      setOpeningMessage(detail.openingMessage || '');
      setSuggestedQuestions(detail.suggestedQuestions || []);
      setNewSuggestedQuestion('');
      setVoiceInputEnabled(detail.voiceInputEnabled);
      setReplyPlaybackEnabled(detail.replyPlaybackEnabled);

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
  }, [navigate, selectedApplicationId]);

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
    if (selectedApplicationId) {
      void loadConversationServiceStatus();
    }
  }, [loadConversationServiceStatus, selectedApplicationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, streamingContent]);

  const asrReady = Boolean(asrStatus?.isActive && asrStatus.configured);
  const ttsReady = Boolean(ttsOptions?.provider.isActive && ttsOptions.defaultVoiceId);

  // Reset states when switching applications
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
    if (!createName.trim()) {
      message.error('请输入智能体名称');
      return;
    }
    setCreateSaving(true);
    try {
      const created = await createAgentApplication({
        name: createName.trim(),
        description: createDescription.trim(),
        temperature: DEFAULT_TEMPERATURE,
        maxTokens: DEFAULT_MAX_TOKENS,
        isActive: true,
      });
      message.success('智能体已创建');
      setCreateName('');
      setCreateDescription('');
      setCreateOpen(false);
      await loadApplications();
      navigate(`${created.id}`);
    } catch {
      message.error('智能体创建失败');
    } finally {
      setCreateSaving(false);
    }
  };

  const handleSaveConfig = useCallback(async () => {
    if (!selectedApplication || !canUpdate) return;
    if (!name.trim()) {
      message.error('请输入智能体名称');
      return;
    }
    const normalizedSuggestedQuestions = suggestedQuestions.map((question) => question.trim());
    if (normalizedSuggestedQuestions.some((question) => !question)) {
      message.error('建议问题不能为空');
      return;
    }
    setConfigSaving(true);
    try {
      const payload: AgentApplicationPayload = {
        name: name.trim(),
        description: description.trim(),
        llmModelId: llmModelId,
        systemPrompt: systemPrompt,
        knowledgeDocumentIds: selectedDocs,
        temperature: temperature,
        maxTokens: maxTokens,
        isActive: isActive,
        openingMessageEnabled,
        openingMessage: openingMessage.trim(),
        suggestedQuestions: normalizedSuggestedQuestions,
        voiceInputEnabled,
        replyPlaybackEnabled,
      };
      const updated = await updateAgentApplication(selectedApplication.id, payload);
      setSelectedApplication(updated);
      if (conversation) {
        const nextConversation = await updateConversationConfig(conversation.id, {
          llmModelId: payload.llmModelId,
          systemPrompt: payload.systemPrompt,
          temperature: payload.temperature,
          maxTokens: payload.maxTokens,
        });
        setConversation(nextConversation);
      }
      message.success('智能体配置已保存');
      await loadApplications();
    } catch {
      message.error('智能体配置保存失败');
    } finally {
      setConfigSaving(false);
    }
  }, [
    selectedApplication,
    canUpdate,
    name,
    description,
    llmModelId,
    systemPrompt,
    selectedDocs,
    temperature,
    maxTokens,
    isActive,
    openingMessageEnabled,
    openingMessage,
    suggestedQuestions,
    voiceInputEnabled,
    replyPlaybackEnabled,
    conversation,
    loadApplications,
  ]);

  // Keyboard Shortcuts (Alt+1/2/3 for switching tabs, Ctrl+S for saving)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedApplicationId) return;

      // Switch tabs: Alt + 1/2/3/4
      if (e.altKey && e.key === '1') {
        e.preventDefault();
        setActiveTab('orchestrate');
      } else if (e.altKey && e.key === '2') {
        e.preventDefault();
        setActiveTab('conversation');
      } else if (e.altKey && e.key === '3') {
        e.preventDefault();
        setActiveTab('logs');
      } else if (e.altKey && e.key === '4') {
        e.preventDefault();
        setActiveTab('monitor');
      }

      // Save config: Ctrl + S (or Cmd + S)
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        if ((activeTab === 'orchestrate' || activeTab === 'conversation') && isDirty && canUpdate && !configSaving && !streaming) {
          e.preventDefault();
          void handleSaveConfig();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedApplicationId, activeTab, isDirty, canUpdate, configSaving, streaming, handleSaveConfig]);

  const handleDelete = async (applicationId: number) => {
    try {
      await deleteAgentApplication(applicationId);
      message.success('智能体已删除');
      if (selectedApplicationId === applicationId) {
        navigateToApplicationList();
      }
      await loadApplications();
    } catch {
      message.error('智能体删除失败');
    }
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
    return nextConversation;
  };

  const sendChatContent = async (content: string) => {
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
      void refreshConversation(activeConversation.id)
        .then((nextConversation) => {
          if (!replyPlaybackEnabled || !ttsReady) return;
          const assistantMessage = [...nextConversation.messages]
            .reverse()
            .find((item) => item.role === 'assistant');
          if (assistantMessage) {
            void agentAudio.playText(`message-${assistantMessage.id}`, assistantMessage.content);
          }
        })
        .catch(() => {
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

  const handleSend = async () => {
    const content = inputValue.trim();
    await sendChatContent(content);
  };

  const handleStopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  };

  const addSuggestedQuestion = () => {
    const text = newSuggestedQuestion.trim();
    if (!text) {
      message.warning('请输入建议问题');
      return;
    }
    if (suggestedQuestions.length >= 10) {
      message.warning('建议问题最多 10 条');
      return;
    }
    setSuggestedQuestions((current) => [...current, text]);
    setNewSuggestedQuestion('');
  };

  const updateSuggestedQuestion = (index: number, value: string) => {
    setSuggestedQuestions((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)));
  };

  const removeSuggestedQuestion = (index: number) => {
    setSuggestedQuestions((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const moveSuggestedQuestion = (index: number, direction: -1 | 1) => {
    setSuggestedQuestions((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
  };

  const sendSuggestedQuestion = async (question: string) => {
    if (isDirty) {
      message.warning('请先保存对话设置，再发送建议问题');
      return;
    }
    await sendChatContent(question.trim());
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
    <Flex direction="column" gap="5">
      {/* Banner */}
      <Card size="3" style={{ background: 'linear-gradient(135deg, var(--slate-9) 0%, var(--slate-12) 100%)', color: 'white', border: 'none' }}>
        <Flex direction="column" gap="2" style={{ position: 'relative', overflow: 'hidden' }}>
          <Flex align="center" gap="2">
            <Heading size="6" weight="bold">智能体工作室</Heading>
            <Badge color="teal" variant="soft">Studio</Badge>
          </Flex>
          <Text color="gray" size="2" style={{ maxWidth: 500 }}>
            自主编排、测试和部署您的专属智能助手。自由组装大语言模型、私有知识库文档，并无缝介入指令系统。
          </Text>
          <div style={{ position: 'absolute', right: -20, bottom: -40, opacity: 0.08 }}>
            <Bot size={160} />
          </div>
        </Flex>
      </Card>

      {/* Filter and Create Toolbar */}
      <Flex gap="3" align="center" justify="between" className="bg-white/80 backdrop-blur p-4 rounded-2xl border border-slate-200/40 shadow-sm">
        <Flex align="center" gap="2" style={{ flex: 1 }}>
          <TextField.Root
            size="2"
            placeholder="搜索应用名称或描述..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{ width: '100%', maxWidth: 360 }}
          >
            <TextField.Slot>
              <Search size={16} />
            </TextField.Slot>
          </TextField.Root>
          <Text size="2" color="gray" style={{ marginLeft: 8 }}>共 {applicationTotal} 个应用</Text>
        </Flex>
      </Flex>

      {/* Applications Grid */}
      <Spin spinning={listLoading}>
        <Grid columns={{ initial: '1', md: '2', lg: '3' }} gap="4">
          {/* Create Agent Card */}
          {canCreate && (
            <Card
              size="2"
              className="group flex flex-col justify-center items-center cursor-pointer border-dashed border-2 hover:border-teal-500 hover:bg-teal-50/5 transition-all duration-300"
              style={{ minHeight: 280 }}
              onClick={() => setCreateOpen(true)}
            >
              <Flex direction="column" align="center" justify="center" gap="3" style={{ height: '100%' }}>
                <div
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500
                    group-hover:bg-teal-600 group-hover:text-white transition-colors"
                >
                  <Plus size={24} />
                </div>
                <Text weight="bold" size="3">创建智能体</Text>
                <Text size="1" color="gray" align="center" style={{ maxWidth: 200 }}>
                  构建全新大模型智能助手，连接知识库与指令
                </Text>
              </Flex>
            </Card>
          )}

          {applications.map((app) => (
            <Card key={app.id} size="2" className="flex flex-col relative overflow-hidden group hover:shadow-md transition-shadow">
              <Flex direction="column" gap="4" style={{ height: '100%' }}>
                <Flex align="start" justify="between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
                    <Bot size={24} />
                  </div>
                  
                  {canDelete && (
                    <AlertDialog.Root
                      open={deleteApplicationId === app.id}
                      onOpenChange={(open) => setDeleteApplicationId(open ? app.id : null)}
                    >
                      <AlertDialog.Trigger>
                        <Button
                          variant="ghost"
                          color="red"
                          size="1"
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 size={16} />
                        </Button>
                      </AlertDialog.Trigger>
                      <AlertDialog.Content style={{ maxWidth: 400 }}>
                        <AlertDialog.Title>确认删除智能体</AlertDialog.Title>
                        <AlertDialog.Description size="2">
                          删除后将移除智能体配置、对话设置、关联会话和消息，且不可恢复。绑定的知识库、模型、音色和 ASR/TTS 配置不会被删除。确定删除「{app.name}」吗？
                        </AlertDialog.Description>
                        <Flex gap="3" mt="4" justify="end">
                          <AlertDialog.Cancel>
                            <Button variant="soft" color="gray">取消</Button>
                          </AlertDialog.Cancel>
                          <AlertDialog.Action>
                            <Button variant="solid" color="red" onClick={() => void handleDelete(app.id)}>
                              确认删除
                            </Button>
                          </AlertDialog.Action>
                        </Flex>
                      </AlertDialog.Content>
                    </AlertDialog.Root>
                  )}
                </Flex>

                <Flex direction="column" gap="1">
                  <Heading size="3" className="truncate text-slate-900">{app.name}</Heading>
                  <Text size="2" color="gray" className="line-clamp-2 leading-relaxed" style={{ minHeight: 40 }}>
                    {app.description || '暂无描述'}
                  </Text>
                </Flex>

                <Flex direction="column" gap="3" className="mt-auto border-t border-slate-100 pt-3">
                  <Flex gap="2" wrap="wrap">
                    <Badge color="gray" variant="soft">
                      模型: {app.llmModelDisplayName || app.llmModelName || '未配置'}
                    </Badge>
                    <Badge color="teal" variant="soft">
                      {app.knowledgeDocumentIds.length} 个知识库
                    </Badge>
                  </Flex>

                  <Text size="1" color="gray" className="font-mono">
                    更新时间: {dayjs(app.updated_at).format('YYYY-MM-DD HH:mm')}
                  </Text>

                  <Flex align="center" justify="between" className="pt-1">
                    <Flex align="center" gap="2">
                      <Switch
                        size="1"
                        checked={app.isActive}
                        disabled={!canUpdate}
                        onCheckedChange={async (checked) => {
                          try {
                            await updateAgentApplication(app.id, { isActive: checked });
                            message.success(`智能体已${checked ? '启用' : '停用'}`);
                            await loadApplications();
                          } catch {
                            message.error('状态更新失败');
                          }
                        }}
                      />
                      <Text size="1" color="gray">{app.isActive ? '已启用' : '已停用'}</Text>
                    </Flex>

                    <Button
                      variant="ghost"
                      size="1"
                      className="font-semibold text-slate-600 hover:text-teal-600 flex items-center gap-1"
                      onClick={() => navigate(`${app.id}`)}
                    >
                      <span>配置</span>
                      <ArrowRight size={14} />
                    </Button>
                  </Flex>
                </Flex>
              </Flex>
            </Card>
          ))}
        </Grid>
      </Spin>

      {applicationTotal > PAGE_SIZE && (
        <Flex justify="center" align="center" gap="3" mt="4">
          <Button
            variant="outline"
            color="gray"
            disabled={applicationPage <= 1}
            onClick={() => setApplicationPage((page) => page - 1)}
          >
            上一页
          </Button>
          <Text size="2" color="gray" weight="bold">
            {applicationPage} / {normalizePageCount(applicationTotal, PAGE_SIZE)}
          </Text>
          <Button
            variant="outline"
            color="gray"
            disabled={applicationPage >= normalizePageCount(applicationTotal, PAGE_SIZE)}
            onClick={() => setApplicationPage((page) => page + 1)}
          >
            下一页
          </Button>
        </Flex>
      )}
    </Flex>
  );

  const renderChatMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'user';
    return (
      <Flex key={msg.id} justify={isUser ? 'end' : 'start'} className="mb-4">
        <Flex gap="3" style={{ maxWidth: '85%' }} direction={isUser ? 'row-reverse' : 'row'}>
          <Avatar
            size="2"
            fallback={isUser ? <User size={16} /> : <Bot size={16} />}
            color={isUser ? 'indigo' : 'teal'}
            variant="solid"
          />
          <Flex direction="column" gap="1">
            <div
              className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
                isUser
                  ? 'bg-slate-900 text-white rounded-tr-none'
                  : 'bg-white border border-slate-100 text-slate-800 rounded-tl-none'
              }`}
            >
              {isUser ? (
                <span className="whitespace-pre-wrap break-words">{msg.content}</span>
              ) : (
                <ChatMarkdown content={msg.content} className="chat-markdown" />
              )}
              {msg.id === -1 && (
                <span className="ml-1 inline-block h-4 w-0.5 bg-teal-500 animate-pulse align-middle" />
              )}
            </div>
            {!isUser && msg.id !== -1 && (
              <Flex align="center" gap="2" className="px-1">
                <Button
                  size="1"
                  variant="soft"
                  color="teal"
                  disabled={!ttsReady}
                  onClick={() => void agentAudio.playText(`message-${msg.id}`, msg.content)}
                >
                  {agentAudio.playingKey === `message-${msg.id}` && !agentAudio.paused ? <Pause size={12} /> : <Play size={12} />}
                  <Text size="1">{agentAudio.playingKey === `message-${msg.id}` && !agentAudio.paused ? '暂停' : '播放'}</Text>
                </Button>
                {agentAudio.playingKey === `message-${msg.id}` && (
                  <Button size="1" variant="ghost" color="red" onClick={agentAudio.stopPlayback}>
                    <Square size={12} />
                    <Text size="1">停止</Text>
                  </Button>
                )}
              </Flex>
            )}
          </Flex>
        </Flex>
      </Flex>
    );
  };

  const renderOrchestrateTab = () => (
    <Spin spinning={detailLoading || optionsLoading}>
      <Grid columns={{ initial: '1', xl: '390px minmax(0, 1fr)' }} gap="4">
        {/* Left Side: Config Panel */}
        <Card size="2" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden" style={{ maxHeight: 'calc(100vh - 250px)', overflowY: 'auto' }}>
          <Flex direction="column" gap="4">
            <Heading size="3">编排设置</Heading>
            
            <Flex direction="column" gap="1">
              <Text size="2" weight="bold">智能体名称</Text>
              <TextField.Root
                disabled={!canUpdate}
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={128}
                placeholder="名称不能为空"
              />
            </Flex>

            <Flex direction="column" gap="1">
              <Text size="2" weight="bold">描述说明</Text>
              <TextArea
                disabled={!canUpdate}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={255}
                placeholder="输入描述以帮助团队了解它的用途"
                rows={2}
              />
            </Flex>

            <Flex direction="column" gap="1">
              <Flex align="center" gap="1.5">
                <Text size="2" weight="bold">选用模型</Text>
                <Tooltip content="选择为该智能体提供推理能力的大语言模型。需要先在服务提供商页面配置好 API 密钥。">
                  <HelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </Flex>
              <Select.Root
                disabled={!canUpdate || !(llmOptions?.providers || []).some((p) => (p.models || []).length > 0)}
                value={llmModelId ? String(llmModelId) : 'none'}
                onValueChange={(val) => setLlmModelId(val === 'none' ? null : Number(val))}
              >
                <Select.Trigger placeholder="请选择模型" style={{ width: '100%' }} />
                <Select.Content>
                  <Select.Item value="none">无模型</Select.Item>
                  {(llmOptions?.providers || []).map((provider) => (
                    <Select.Group key={provider.id}>
                      <Select.Label>{provider.name}</Select.Label>
                      {provider.models.map((model) => (
                        <Select.Item key={model.id} value={String(model.id)}>
                          {model.displayName || model.name}
                        </Select.Item>
                      ))}
                    </Select.Group>
                  ))}
                </Select.Content>
              </Select.Root>
            </Flex>

            <Flex direction="column" gap="1">
              <Flex align="center" gap="1.5">
                <Text size="2" weight="bold">系统提示词 (System Prompt)</Text>
                <Tooltip content="设定智能体的角色人设、回复风格和行为约束，引导大模型产生符合预期的输出。">
                  <HelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </Flex>
              <TextArea
                disabled={!canUpdate}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="您是大模型的引导者，在这里输入大模型的系统人设与行为提示..."
                rows={5}
                className="font-mono text-xs"
              />
            </Flex>

            <Flex direction="column" gap="1">
              <Text size="2" weight="bold">绑定知识库文档</Text>
              <Popover.Root>
                <Popover.Trigger>
                  <Button variant="outline" color="gray" size="2" style={{ justifyContent: 'between', width: '100%' }}>
                    <Text size="2">选择关联知识库 ({selectedDocs.length} 个已选)</Text>
                    <ChevronDown size={14} />
                  </Button>
                </Popover.Trigger>
                <Popover.Content style={{ width: 340 }}>
                  <Flex direction="column" gap="3">
                    {knowledgeDocuments.length > 0 ? (
                      knowledgeDocuments.map((doc) => {
                        const isChecked = selectedDocs.includes(doc.id);
                        const isTxtOrMd = ['txt', 'md'].includes(doc.fileExtension?.toLowerCase() || '');
                        return (
                          <Text key={doc.id} as="label" size="2" className="flex items-start gap-2 hover:bg-slate-50 p-1.5 rounded cursor-pointer">
                            <Checkbox
                              checked={isChecked}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedDocs([...selectedDocs, doc.id]);
                                } else {
                                  setSelectedDocs(selectedDocs.filter((id) => id !== doc.id));
                                }
                              }}
                            />
                            <Flex direction="column">
                              <Text weight="bold" size="2">{doc.title || doc.fileName}</Text>
                              {!isTxtOrMd && <Text size="1" color="gray">暂不参与检索 (仅支持 txt/md)</Text>}
                            </Flex>
                          </Text>
                        );
                      })
                    ) : (
                      <Text size="2" color="gray" align="center">暂无可用知识库</Text>
                    )}
                  </Flex>
                </Popover.Content>
              </Popover.Root>
            </Flex>

            <Flex direction="column" gap="2" style={{ paddingBottom: 8 }}>
              <Flex align="center" justify="between">
                <Flex align="center" gap="1.5">
                  <Text size="2" weight="bold">随机性温度 (Temperature)</Text>
                  <Tooltip content="值越高回复越具创意和随机性；值越低回复越确定和保守。建议客服场景设为 0.2-0.5，创作场景设为 0.7-1.0。">
                    <HelpCircle size={14} className="text-slate-400 cursor-help" />
                  </Tooltip>
                </Flex>
                <Badge variant="soft" color="teal">{temperature}</Badge>
              </Flex>
              <Slider
                disabled={!canUpdate}
                value={[temperature]}
                onValueChange={([val]) => setTemperature(val)}
                min={0}
                max={2}
                step={0.1}
              />
            </Flex>

            <Flex direction="column" gap="1">
              <Flex align="center" gap="1.5">
                <Text size="2" weight="bold">最大输出 Tokens</Text>
                <Tooltip content="单次模型回复生成的最大 Token 数量。1 个 Token 大约对应 1.5 个汉字或 0.75 个英文单词。">
                  <HelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </Flex>
              <TextField.Root
                disabled={!canUpdate}
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                min={1}
                max={320000}
              />
            </Flex>

            <Flex align="center" gap="3" mt="2">
              <Text size="2" weight="bold">启用此智能体</Text>
              <Switch
                disabled={!canUpdate}
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </Flex>
          </Flex>
        </Card>

        {/* Right Side: Debug Chat */}
        <Card size="2" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden" style={{ height: 'calc(100vh - 250px)' }}>
          <Flex direction="column" style={{ height: '100%' }}>
            {/* Chat Header */}
            <Flex align="center" justify="between" className="border-b border-slate-100 pb-3 mb-3">
              <Flex align="center" gap="2">
                <Sparkles size={16} className="text-teal-600" />
                <Heading size="3">调试预览</Heading>
              </Flex>
              <Flex align="center" gap="2">
                {conversation && (
                  <Button
                    variant="ghost"
                    color="gray"
                    size="1"
                    onClick={async () => {
                      setChatLoading(true);
                      try {
                        const nextConversation = await createAgentApplicationConversation(selectedApplication!.id);
                        setConversation(nextConversation);
                        setMessages(nextConversation.messages);
                        setStreamingContent('');
                        setInputValue('');
                        message.success('调试会话已重置');
                      } catch {
                        message.error('重置会话失败');
                      } finally {
                        setChatLoading(false);
                      }
                    }}
                    title="重置当前调试会话"
                  >
                    <RotateCcw size={14} />
                    <Text size="1">新对话</Text>
                  </Button>
                )}
                {conversation ? (
                  <Badge color="teal" variant="soft" className="font-mono">会话: #{conversation.id}</Badge>
                ) : (
                  <Badge color="gray" variant="soft">未开始</Badge>
                )}
              </Flex>
            </Flex>

            {/* Chat message content */}
            <Box style={{ flex: 1, overflowY: 'auto' }} className="bg-slate-50/40 p-4 rounded-xl border border-slate-100/50">
              {chatLoading ? (
                <Flex align="center" justify="center" style={{ height: '100%' }}>
                  <Spin />
                </Flex>
              ) : displayedMessages.length > 0 ? (
                <div>
                  {displayedMessages.map(renderChatMessage)}
                  <div ref={messagesEndRef} />
                </div>
              ) : (
                <Flex direction="column" align="center" justify="center" gap="3" style={{ height: '100%' }} className="text-slate-400">
                  <MessageSquare size={36} className="text-slate-300" />
                  {openingMessageEnabled && openingMessage ? (
                    <Box className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm max-w-xl text-slate-700">
                      <Text size="2">{openingMessage}</Text>
                    </Box>
                  ) : (
                    <Text size="2">输入消息并发送，开始与大模型进行调试对话</Text>
                  )}
                  {suggestedQuestions.length > 0 && (
                    <Flex wrap="wrap" justify="center" gap="2">
                      {suggestedQuestions.map((question, index) => (
                        <Button
                          key={`${index}-${question}`}
                          size="1"
                          variant="soft"
                          color="gray"
                          disabled={streaming || !canChat}
                          onClick={() => void sendSuggestedQuestion(question)}
                        >
                          <HelpCircle size={12} /> {question}
                        </Button>
                      ))}
                    </Flex>
                  )}
                </Flex>
              )}
            </Box>

            {/* Input area */}
            <Flex gap="2" mt="3" className="pt-2">
              {voiceInputEnabled && (
                <Button
                  size="3"
                  variant="soft"
                  color={agentAudio.recording ? 'red' : 'teal'}
                  disabled={!asrReady || agentAudio.transcribing}
                  onClick={() => {
                    if (agentAudio.recording) {
                      agentAudio.stopRecording();
                      return;
                    }
                    void agentAudio.startRecording((text) => setInputValue(text));
                  }}
                >
                  {agentAudio.recording ? <MicOff size={16} /> : <Mic size={16} />}
                </Button>
              )}
              <TextField.Root
                size="3"
                value={inputValue}
                placeholder="发送调试消息..."
                disabled={!canChat || streaming || !selectedApplication}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
                style={{ flex: 1 }}
              />
              {streaming ? (
                <Button size="3" color="red" variant="soft" onClick={handleStopStreaming}>
                  <Text size="2" weight="bold">停止</Text>
                </Button>
              ) : (
                <Button
                  size="3"
                  color="teal"
                  disabled={!inputValue.trim() || !canChat || !selectedApplication}
                  onClick={() => void handleSend()}
                >
                  <Send size={16} />
                </Button>
              )}
            </Flex>
          </Flex>
        </Card>
      </Grid>
    </Spin>
  );

  const renderConversationSettingsTab = () => (
    <Spin spinning={detailLoading}>
      <Grid columns={{ initial: '1', xl: 'minmax(360px, 560px) minmax(0, 1fr)' }} gap="4">
        <Flex direction="column" gap="4">
          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm">
            <Flex direction="column" gap="3">
              <Flex align="center" justify="between">
                <Box>
                  <Heading size="3">开场白</Heading>
                  <Text size="1" color="gray">新对话进入时展示，且不写入聊天消息</Text>
                </Box>
                <Switch checked={openingMessageEnabled} onCheckedChange={setOpeningMessageEnabled} disabled={!canUpdate} />
              </Flex>
              <TextArea
                value={openingMessage}
                disabled={!openingMessageEnabled || !canUpdate}
                onChange={(event) => setOpeningMessage(event.target.value.slice(0, 200))}
                rows={4}
                placeholder="输入智能体开场白"
              />
              <Flex justify="between">
                <Text size="1" color="gray">可在预览区播放开场白</Text>
                <Text size="1" color="gray">{openingMessage.length}/200</Text>
              </Flex>
            </Flex>
          </Card>

          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm">
            <Flex direction="column" gap="3">
              <Flex align="center" justify="between">
                <Box>
                  <Heading size="3">建议问题</Heading>
                  <Text size="1" color="gray">最多 10 条，点击后直接发送</Text>
                </Box>
                <Badge color={suggestedQuestions.length >= 10 ? 'red' : 'gray'}>{suggestedQuestions.length}/10</Badge>
              </Flex>
              {suggestedQuestions.length > 0 ? (
                <Flex direction="column" gap="2">
                  {suggestedQuestions.map((question, index) => (
                    <Flex key={`${index}-${question}`} align="center" gap="2">
                      <GripVertical size={14} className="text-slate-400 shrink-0" />
                      <TextField.Root
                        value={question}
                        onChange={(event) => updateSuggestedQuestion(index, event.target.value.slice(0, 120))}
                        disabled={!canUpdate}
                        style={{ flex: 1 }}
                      />
                      <Button
                        size="1"
                        variant="soft"
                        color="gray"
                        disabled={index === 0 || !canUpdate}
                        onClick={() => moveSuggestedQuestion(index, -1)}
                      >
                        <ChevronUp size={12} />
                      </Button>
                      <Button
                        size="1"
                        variant="soft"
                        color="gray"
                        disabled={index === suggestedQuestions.length - 1 || !canUpdate}
                        onClick={() => moveSuggestedQuestion(index, 1)}
                      >
                        <ChevronDownIcon size={12} />
                      </Button>
                      <Button size="1" variant="soft" color="red" disabled={!canUpdate} onClick={() => removeSuggestedQuestion(index)}>
                        <Trash2 size={12} />
                      </Button>
                    </Flex>
                  ))}
                </Flex>
              ) : (
                <Text size="2" color="gray" className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-3 py-4">
                  暂无建议问题
                </Text>
              )}
              <Flex gap="2">
                <TextField.Root
                  value={newSuggestedQuestion}
                  onChange={(event) => setNewSuggestedQuestion(event.target.value.slice(0, 120))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addSuggestedQuestion();
                    }
                  }}
                  placeholder="添加一个建议问题，按 Enter 确认"
                  disabled={!canUpdate || suggestedQuestions.length >= 10}
                  style={{ flex: 1 }}
                />
                <Button disabled={!canUpdate || suggestedQuestions.length >= 10} onClick={addSuggestedQuestion}>
                  <Plus size={14} /> 添加
                </Button>
              </Flex>
            </Flex>
          </Card>

          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm">
            <Flex direction="column" gap="4">
              <Flex align="center" justify="between">
                <Box>
                  <Heading size="3">语音输入</Heading>
                  <Text size="1" color={asrReady ? 'gray' : 'red'}>
                    {asrReady ? 'ASR 服务可用，录音转写后填入输入框' : 'ASR 服务未就绪，请先检查 ASR 设置'}
                  </Text>
                </Box>
                <Switch checked={voiceInputEnabled} onCheckedChange={setVoiceInputEnabled} disabled={!canUpdate || !asrReady} />
              </Flex>
              <Flex align="center" justify="between">
                <Box>
                  <Heading size="3">回复播报</Heading>
                  <Text size="1" color={ttsReady ? 'gray' : 'red'}>
                    {ttsReady ? '使用公司默认 TTS 音色播报开场白和助手回复' : 'TTS 默认音色未配置或服务不可用'}
                  </Text>
                </Box>
                <Switch checked={replyPlaybackEnabled} onCheckedChange={setReplyPlaybackEnabled} disabled={!canUpdate || !ttsReady} />
              </Flex>
            </Flex>
          </Card>

          <Button
            size="3"
            color="teal"
            disabled={!canUpdate || streaming}
            loading={configSaving}
            onClick={() => void handleSaveConfig()}
          >
            <Save size={16} /> 保存对话设置
          </Button>
        </Flex>

        <Card size="2" className="bg-white border border-slate-200/50 shadow-sm">
          <Flex direction="column" gap="4" style={{ minHeight: 540 }}>
            <Flex align="center" justify="between">
              <Heading size="3">调试预览</Heading>
              <Badge color="blue" variant="soft">实时</Badge>
            </Flex>
            <Flex direction="column" align="center" justify="center" gap="3" style={{ flex: 1 }} className="bg-slate-50/40 rounded-xl border border-slate-100/50 p-4">
              <Avatar size="4" fallback={<Bot size={24} />} color="teal" variant="soft" />
              <Heading size="4" align="center">开始与 {selectedApplication?.name || '智能体'} 对话</Heading>
              {openingMessageEnabled && openingMessage ? (
                <Flex direction="column" align="center" gap="2" style={{ width: '100%' }}>
                  <Box className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm max-w-xl">
                    <Text size="2">{openingMessage}</Text>
                  </Box>
                  <Flex align="center" gap="2">
                    <Button
                      size="1"
                      variant="soft"
                      color="teal"
                      disabled={!ttsReady}
                      onClick={() => void agentAudio.playText('opening-message', openingMessage)}
                    >
                      {agentAudio.playingKey === 'opening-message' && !agentAudio.paused ? <Pause size={12} /> : <Volume2 size={12} />}
                      <Text size="1">{agentAudio.playingKey === 'opening-message' && !agentAudio.paused ? '暂停开场白' : '播放开场白'}</Text>
                    </Button>
                    {agentAudio.playingKey === 'opening-message' && (
                      <Button size="1" variant="ghost" color="red" onClick={agentAudio.stopPlayback}>
                        <Square size={12} />
                        <Text size="1">停止</Text>
                      </Button>
                    )}
                  </Flex>
                </Flex>
              ) : null}
              {suggestedQuestions.length > 0 ? (
                <Flex wrap="wrap" justify="center" gap="2">
                  {suggestedQuestions.map((question, index) => (
                    <Button
                      key={`${index}-${question}`}
                      size="2"
                      variant="soft"
                      color="gray"
                      disabled={streaming || !canChat}
                      onClick={() => void sendSuggestedQuestion(question)}
                    >
                      <HelpCircle size={14} /> {question}
                    </Button>
                  ))}
                </Flex>
              ) : (
                <Text size="2" color="gray">暂无建议问题</Text>
              )}
            </Flex>
            <Flex gap="2">
              {voiceInputEnabled && (
                <Button
                  size="3"
                  variant="soft"
                  color={agentAudio.recording ? 'red' : 'teal'}
                  disabled={!asrReady || agentAudio.transcribing}
                  onClick={() => {
                    if (agentAudio.recording) {
                      agentAudio.stopRecording();
                      return;
                    }
                    void agentAudio.startRecording((text) => setInputValue(text));
                  }}
                >
                  {agentAudio.recording ? <MicOff size={16} /> : <Mic size={16} />}
                </Button>
              )}
              <TextField.Root
                size="3"
                value={inputValue}
                placeholder="发送调试消息..."
                disabled={!canChat || streaming || !selectedApplication}
                onChange={(event) => setInputValue(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && void handleSend()}
                style={{ flex: 1 }}
              />
              <Button size="3" color="teal" disabled={!inputValue.trim() || !canChat || streaming} onClick={() => void handleSend()}>
                <Send size={16} />
              </Button>
            </Flex>
          </Flex>
        </Card>
      </Grid>
    </Spin>
  );

  const renderLogsTab = () => (
    <Spin spinning={logConversationsLoading}>
      <Grid columns={{ initial: '1', xl: '380px minmax(0, 1fr)' }} gap="4">
        {/* Conversation List */}
        <Card size="2" className="flex flex-col bg-white border border-slate-200/50 shadow-sm" style={{ maxHeight: 'calc(100vh - 250px)', overflowY: 'auto' }}>
          <Flex direction="column" gap="3">
            <Flex align="center" justify="between" className="border-b border-slate-100 pb-3">
              <Heading size="3">历史会话</Heading>
              <Badge color="gray">{logConversations.length} 会话</Badge>
            </Flex>

            <Flex direction="column" gap="1" className="divide-y divide-slate-100">
              {logConversations.length > 0 ? (
                logConversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => void loadSelectedLogConversation(conv.id)}
                    className={`py-3 px-3 cursor-pointer rounded-xl transition-all duration-200 border ${
                      selectedLogConversation?.id === conv.id
                        ? 'bg-teal-50/50 border-teal-200 shadow-sm'
                        : 'border-transparent hover:bg-slate-50'
                    }`}
                  >
                    <Flex justify="between" align="start" gap="2" mb="1">
                      <Text size="2" weight="bold" className="truncate max-w-[190px]">
                        {conv.title}
                      </Text>
                      <Text size="1" color="gray" className="shrink-0 font-mono">
                        {dayjs(conv.updated_at).format('MM-DD HH:mm')}
                      </Text>
                    </Flex>
                    <Text size="1" color="gray" className="line-clamp-1 block mb-2">
                      {conv.summary || conv.lastMessage || '暂无内容'}
                    </Text>
                    <Flex justify="between" align="center" className="text-[10px]">
                      <Badge color="gray" size="1">
                        {conv.llmModelDisplayName || conv.llmModelName || '未分配'}
                      </Badge>
                      <span className="flex items-center gap-1 text-slate-400">
                        <MessageSquare size={12} /> {conv.messageCount} 消息
                      </span>
                    </Flex>
                  </div>
                ))
              ) : (
                <Flex direction="column" align="center" justify="center" py="8" className="text-slate-400 py-12">
                  <MessageSquare size={32} className="text-slate-300 mb-2" />
                  <Text size="1">暂无调试会话历史</Text>
                </Flex>
              )}
            </Flex>
          </Flex>
        </Card>

        {/* Selected Conversation Detail */}
        <Card size="2" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden" style={{ height: 'calc(100vh - 250px)' }}>
          {selectedLogConversation ? (
            <Spin spinning={selectedLogConversationLoading} className="flex-1 flex flex-col" style={{ height: '100%' }}>
              <Flex direction="column" style={{ height: '100%' }}>
                <Flex direction="column" className="border-b border-slate-100 pb-3 mb-3">
                  <Heading size="3">{selectedLogConversation.title}</Heading>
                  <Text size="1" color="gray" className="mt-1">
                    会话 ID: #{selectedLogConversation.id} • 创建时间: {dayjs(selectedLogConversation.created_at).format('YYYY-MM-DD HH:mm:ss')}
                  </Text>
                </Flex>

                <Box style={{ flex: 1, overflowY: 'auto' }} className="bg-slate-50/20 p-4 rounded-xl border border-slate-100/30">
                  {selectedLogConversation.messages.length > 0 ? (
                    selectedLogConversation.messages.map((msg) => {
                      const isUser = msg.role === 'user';
                      return (
                        <Flex key={msg.id} justify={isUser ? 'end' : 'start'} className="mb-4">
                          <Flex gap="3" style={{ maxWidth: '85%' }} direction={isUser ? 'row-reverse' : 'row'}>
                            <Avatar
                              size="2"
                              fallback={isUser ? <User size={14} /> : <Bot size={14} />}
                              color={isUser ? 'indigo' : 'teal'}
                              variant="solid"
                            />
                            <Flex direction="column" gap="1">
                              <div
                                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
                                  isUser
                                    ? 'bg-slate-900 text-white rounded-tr-none'
                                    : 'bg-white border border-slate-100 text-slate-800 rounded-tl-none'
                                }`}
                              >
                                {isUser ? (
                                  <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                                ) : (
                                  <ChatMarkdown content={msg.content} className="chat-markdown" />
                                )}
                              </div>
                              <Flex align="center" gap="2" className="text-[10px] text-slate-400 px-1 mt-0.5">
                                <span>{dayjs(msg.created_at).format('HH:mm:ss')}</span>
                                {!isUser && msg.feedback !== 'none' && (
                                  <Badge color={msg.feedback === 'up' ? 'green' : 'red'} size="1">
                                    {msg.feedback === 'up' ? '好评' : '差评'}
                                  </Badge>
                                )}
                              </Flex>
                            </Flex>
                          </Flex>
                        </Flex>
                      );
                    })
                  ) : (
                    <Text size="2" color="gray" align="center">无会话消息记录</Text>
                  )}
                </Box>
              </Flex>
            </Spin>
          ) : (
            <Flex direction="column" align="center" justify="center" gap="3" style={{ height: '100%' }} className="text-slate-400">
              <MessageSquare size={40} className="text-slate-300" />
              <Text size="2">选择左侧历史会话查看详细聊天明细</Text>
            </Flex>
          )}
        </Card>
      </Grid>
    </Spin>
  );

  const renderMonitorTab = () => {
    if (statsLoading) {
      return (
        <Card size="2" className="flex h-64 items-center justify-center bg-white border border-slate-200/50 shadow-sm">
          <Spin size="large" />
        </Card>
      );
    }

    if (!stats) {
      return (
        <Card size="2" className="flex h-64 flex-col items-center justify-center bg-white border border-slate-200/50 shadow-sm text-slate-400">
          <BarChart2 size={36} className="text-slate-300 mb-2" />
          <Text size="2">暂无监测数据</Text>
        </Card>
      );
    }

    const maxTrendCount = Math.max(1, ...stats.dailyTrends.map((d) => d.count));

    return (
      <Flex direction="column" gap="5">
        {/* Metric Cards Grid */}
        <Grid columns={{ initial: '1', sm: '2', lg: '4' }} gap="4">
          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow">
            <Flex direction="column" gap="1">
              <Text size="1" weight="medium" color="gray">会话总数</Text>
              <Flex align="baseline" gap="2" mt="1">
                <Text size="7" weight="bold" className="font-mono">{stats.conversationCount}</Text>
                <Text size="1" color="gray">次</Text>
              </Flex>
              <Text size="1" color="gray" className="mt-2">智能体开启的调试会话总计</Text>
            </Flex>
          </Card>

          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow">
            <Flex direction="column" gap="1">
              <Text size="1" weight="medium" color="gray">消息总量</Text>
              <Flex align="baseline" gap="2" mt="1">
                <Text size="7" weight="bold" className="font-mono">{stats.messageCount}</Text>
                <Text size="1" color="gray">条</Text>
              </Flex>
              <Flex align="center" justify="between" className="mt-2 text-[10px] text-slate-500 font-medium">
                <span>用户: <span className="font-mono font-bold">{stats.userMessageCount}</span></span>
                <span>助手: <span className="font-mono font-bold">{stats.assistantMessageCount}</span></span>
              </Flex>
            </Flex>
          </Card>

          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow">
            <Flex direction="column" gap="1">
              <Text size="1" weight="medium" color="gray">好评率</Text>
              <Flex align="baseline" gap="2" mt="1">
                <Text size="7" weight="bold" className="font-mono">
                  {(stats.upCount + stats.downCount) > 0 ? `${Math.round((stats.upCount / (stats.upCount + stats.downCount)) * 100)}%` : '--'}
                </Text>
                <Text size="1" color="gray">好评百分比</Text>
              </Flex>
              <Flex align="center" justify="between" className="mt-2 text-[10px]">
                <Text color="teal" weight="bold" size="1">点赞: {stats.upCount}</Text>
                <Text color="red" weight="bold" size="1">点踩: {stats.downCount}</Text>
              </Flex>
            </Flex>
          </Card>

          <Card size="2" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow">
            <Flex direction="column" gap="1">
              <Text size="1" weight="medium" color="gray">更新时间</Text>
              <Text size="4" weight="bold" mt="2" className="truncate">
                {dayjs(stats.updatedAt).format('YYYY-MM-DD')}
              </Text>
              <Text size="1" color="gray" className="mt-2 font-mono">
                {dayjs(stats.updatedAt).format('HH:mm:ss')} (配置最新保存)
              </Text>
            </Flex>
          </Card>
        </Grid>

        {/* 7-Day Trend Chart */}
        <Card size="2" className="bg-white border border-slate-200/50 shadow-sm">
          <Flex direction="column" gap="4">
            <Heading size="3">最近 7 天会话数趋势</Heading>
            <div className="flex items-end justify-between h-48 pt-4 px-4 border-b border-slate-100">
              {stats.dailyTrends.map((trend) => {
                const pct = (trend.count / maxTrendCount) * 100;
                return (
                  <div key={trend.date} className="flex flex-col items-center flex-1 group">
                    <div className="opacity-0 group-hover:opacity-100 bg-slate-800 text-white text-[10px] font-semibold px-2 py-0.5 rounded shadow-sm mb-1.5 transition-opacity duration-150 pointer-events-none tabular-nums">
                      {trend.count} 次
                    </div>
                    <div
                      className="w-8 sm:w-12 bg-gradient-to-t from-teal-500 to-teal-700 rounded-t-lg transition-all duration-300 hover:from-teal-600 hover:to-teal-800"
                      style={{ height: `${Math.max(4, pct)}%` }}
                    />
                    <span className="text-[10px] text-slate-400 mt-2 font-medium font-mono">
                      {trend.date}
                    </span>
                  </div>
                );
              })}
            </div>
          </Flex>
        </Card>
      </Flex>
    );
  };

  const renderApplicationWorkspace = () => (
    <Flex direction="column" gap="4">
      {/* Workspace Header */}
      <Flex gap="3" align="center" justify="between" className="bg-white/80 backdrop-blur p-4 rounded-2xl border border-slate-200/40 shadow-sm">
        <Flex align="center" gap="3" style={{ minWidth: 0 }}>
          <Button
            variant="ghost"
            color="gray"
            radius="full"
            onClick={handleBackClick}
            style={{ width: 36, height: 36, padding: 0 }}
          >
            <ArrowLeft size={16} />
          </Button>
          <Flex direction="column" style={{ minWidth: 0 }}>
            <Heading size="4" className="truncate">{selectedApplication?.name || '智能体'}</Heading>
            <Flex align="center" gap="2" mt="1">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse" />
              <Text size="1" color="gray">
                {selectedApplication?.llmProviderName
                  ? `${selectedApplication.llmProviderName} / ${selectedApplication.llmModelDisplayName || selectedApplication.llmModelName}`
                  : '未选择模型'}
              </Text>
            </Flex>
          </Flex>
        </Flex>

        {(activeTab === 'orchestrate' || activeTab === 'conversation') && (
          <Flex align="center" gap="3">
            {isDirty && (
              <Badge color="orange" variant="soft" className="animate-pulse">
                未保存更改
              </Badge>
            )}
            <Button
              color={isDirty ? 'teal' : 'gray'}
              variant={isDirty ? 'solid' : 'soft'}
              size="2"
              loading={configSaving}
              disabled={!canUpdate || streaming}
              onClick={() => void handleSaveConfig()}
              style={{ minWidth: 100 }}
            >
              <Save size={14} /> 保存配置
            </Button>
          </Flex>
        )}
      </Flex>

      {/* Tab Navigation Layout */}
      <Flex gap="4" direction={{ initial: 'column', lg: 'row' }}>
        {/* Left tabs menu */}
        <Card size="1" className="w-full lg:w-56 shrink-0 bg-white border border-slate-200/50 shadow-sm" style={{ height: 'fit-content' }}>
          <Flex direction={{ initial: 'row', lg: 'column' }} gap="1">
            <Button
              variant={activeTab === 'orchestrate' ? 'soft' : 'ghost'}
              color={activeTab === 'orchestrate' ? 'teal' : 'gray'}
              onClick={() => setActiveTab('orchestrate')}
              style={{ justifyContent: 'start', flex: 1, padding: '12px 16px', borderRadius: '12px' }}
            >
              <Sparkles size={16} style={{ marginRight: 8 }} /> 编排
            </Button>
            <Button
              variant={activeTab === 'conversation' ? 'soft' : 'ghost'}
              color={activeTab === 'conversation' ? 'teal' : 'gray'}
              onClick={() => setActiveTab('conversation')}
              style={{ justifyContent: 'start', flex: 1, padding: '12px 16px', borderRadius: '12px' }}
            >
              <MessageSquare size={16} style={{ marginRight: 8 }} /> 对话设置
            </Button>
            <Button
              variant={activeTab === 'logs' ? 'soft' : 'ghost'}
              color={activeTab === 'logs' ? 'teal' : 'gray'}
              onClick={() => setActiveTab('logs')}
              style={{ justifyContent: 'start', flex: 1, padding: '12px 16px', borderRadius: '12px' }}
            >
              <BookOpen size={16} style={{ marginRight: 8 }} /> 日志与标注
            </Button>
            <Button
              variant={activeTab === 'monitor' ? 'soft' : 'ghost'}
              color={activeTab === 'monitor' ? 'teal' : 'gray'}
              onClick={() => setActiveTab('monitor')}
              style={{ justifyContent: 'start', flex: 1, padding: '12px 16px', borderRadius: '12px' }}
            >
              <BarChart2 size={16} style={{ marginRight: 8 }} /> 监测
            </Button>
          </Flex>
        </Card>

        {/* Right Tab Panel Content */}
        <Box style={{ flex: 1, minWidth: 0 }}>
          {activeTab === 'orchestrate' && renderOrchestrateTab()}
          {activeTab === 'conversation' && renderConversationSettingsTab()}
          {activeTab === 'logs' && renderLogsTab()}
          {activeTab === 'monitor' && renderMonitorTab()}
        </Box>
      </Flex>
    </Flex>
  );

  return (
    <Theme accentColor="teal" grayColor="slate" radius="medium" scaling="100%">
      <div className="relative min-h-full bg-slate-50/30 px-2 py-2 text-slate-900">
        {selectedApplicationId ? renderApplicationWorkspace() : renderApplicationList()}
        
        {/* Create Dialog */}
        <Dialog.Root open={createOpen} onOpenChange={setCreateOpen}>
          <Dialog.Content style={{ maxWidth: 450 }}>
            <Dialog.Title>创建智能体</Dialog.Title>
            <Dialog.Description size="2" mb="4">
              给智能体设定一个名字和简短描述以开始配置。
            </Dialog.Description>

            <Flex direction="column" gap="3">
              <label>
                <Text as="div" size="2" mb="1" weight="bold">智能体名称</Text>
                <TextField.Root
                  placeholder="给您的智能体起个名字..."
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                />
              </label>
              <label>
                <Text as="div" size="2" mb="1" weight="bold">应用描述</Text>
                <TextArea
                  placeholder="简要描述该智能体的职责与范围..."
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  rows={3}
                />
              </label>
            </Flex>

            <Flex gap="3" mt="4" justify="end">
              <Dialog.Close>
                <Button variant="soft" color="gray">取消</Button>
              </Dialog.Close>
              <Button onClick={() => void handleCreate()} loading={createSaving}>
                创建智能体
              </Button>
            </Flex>
          </Dialog.Content>
        </Dialog.Root>

        {/* Exit Confirmation Dialog */}
        <AlertDialog.Root open={showExitConfirm} onOpenChange={setShowExitConfirm}>
          <AlertDialog.Content style={{ maxWidth: 400 }}>
            <AlertDialog.Title>确认放弃修改？</AlertDialog.Title>
            <AlertDialog.Description size="2">
              您对智能体配置进行了修改，尚未保存。确定要放弃修改并返回列表吗？
            </AlertDialog.Description>
            <Flex gap="3" mt="4" justify="end">
              <AlertDialog.Cancel>
                <Button variant="soft" color="gray">取消</Button>
              </AlertDialog.Cancel>
              <AlertDialog.Action>
                <Button variant="solid" color="red" onClick={() => {
                  setShowExitConfirm(false);
                  navigateToApplicationList();
                }}>
                  放弃修改
                </Button>
              </AlertDialog.Action>
            </Flex>
          </AlertDialog.Content>
        </AlertDialog.Root>
      </div>
    </Theme>
  );
};
