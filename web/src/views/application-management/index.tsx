import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createAgentApplication,
  createAgentAnnotation,
  createAgentAnnotationFromMessage,
  createAgentApplicationConversation,
  deleteAgentAnnotation,
  deleteAgentApplication,
  fetchAgentAnnotations,
  fetchAgentApplication,
  fetchAgentApplicationStats,
  fetchAgentApplications,
  updateAgentAnnotation,
  type AgentAnnotationRecord,
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
import * as echarts from 'echarts';
import { 
  Select, 
  Spin, 
  message, 
  Button, 
  Card, 
  Input, 
  Slider, 
  Switch, 
  Avatar, 
  Badge, 
  Popover, 
  Checkbox, 
  Tooltip, 
  Modal, 
  Tag, 
  ConfigProvider, 
  theme,
  Empty,
  Pagination,
  Popconfirm
} from 'antd';

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
  BookmarkPlus,
  MessageSquare,
  Sparkles,
  ChevronDown,
  BarChart2,
  HelpCircle,
  RotateCcw,
  Mic,
  MicOff,
  Loader2,
  Pause,
  Play,
  Square,
  Volume2,
  GripVertical,
  ChevronUp,
  ChevronDown as ChevronDownIcon,
  Headphones,
  Languages,
  PenTool,
  FileQuestion,
  Zap,
  Copy,
} from 'lucide-react';

const PAGE_SIZE = 10;
const DEFAULT_TEMPERATURE = 0.7;
const DEFAULT_MAX_TOKENS = 1000;



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

const AGENT_TEMPLATES = [
  {
    key: 'customer_service',
    name: '智能客服助理',
    description: '提供 7x24 小时全天候客户服务，解答常见问题并引流至人工客服。',
    systemPrompt: '你是一个专业的智能客服助手。你要以礼貌、耐心和热情的态度回答用户关于产品、订单、退换货以及公司服务的咨询。如果遇到无法回答的问题，引导用户联系人工客服。',
    openingMessageEnabled: true,
    openingMessage: '您好！我是您的智能客服助手。请问今天有什么我可以帮您的？您可以询问关于订单、退换货或产品详情等问题。',
    suggestedQuestions: ['我们的退换货政策是怎样的？', '怎么联系人工客服？', '发货需要多久？'],
    temperature: 0.3,
    maxTokens: 1000,
    tag: '客户服务',
    gradient: 'from-emerald-500 to-teal-600',
    iconName: 'Headphones',
  },
  {
    key: 'copywriter',
    name: '营销文案大师',
    description: '撰写富有吸引力的社交媒体文案、产品描述、推广邮件和广告创意。',
    systemPrompt: '你是一个顶尖的营销文案策划师。擅长撰写吸引眼球、高转化率的社交媒体推文、小红书种草文、广告语和电子邮件文案。语气活泼、有创意、善用Emoji。',
    openingMessageEnabled: true,
    openingMessage: '嗨！我是您的营销文案专家。今天需要我帮您撰写什么文案？比如小红书文案、公众号推送、还是产品宣传片脚本？',
    suggestedQuestions: ['写一篇小红书风格的护肤品文案', '为新款智能手表写一句广告词', '写一封新品发布邮件给老客户'],
    temperature: 0.8,
    maxTokens: 1500,
    tag: '创意写作',
    gradient: 'from-purple-500 to-indigo-600',
    iconName: 'PenTool',
  },
  {
    key: 'data_analyst',
    name: '数据分析专家',
    description: '帮助您分析业务指标、解释复杂数据概念并编写数据处理代码。',
    systemPrompt: '你是一个资深的数据分析专家。擅长解释商业指标、数据科学概念，并能编写Python/SQL代码进行数据清洗和分析。回答要严谨、有条理，善于使用表格和列表。',
    openingMessageEnabled: true,
    openingMessage: '你好！我是您的专属数据分析专家。请提供您需要分析的数据概念或编写的代码需求，我会为您提供严谨专业的分析方案。',
    suggestedQuestions: ['如何分析上个季度的销售额下滑？', '请解释什么是留存率 and LTV', '写一段Python代码来清理缺失值'],
    temperature: 0.2,
    maxTokens: 2000,
    tag: '商业分析',
    gradient: 'from-blue-500 to-cyan-600',
    iconName: 'BarChart2',
  },
  {
    key: 'english_coach',
    name: '英语口语教练',
    description: '一对一口语日常对话练习，实时纠正语法错误并提供地道表达建议。',
    systemPrompt: 'You are an encouraging and friendly English Speaking Coach. Your goal is to help the user practice conversational English. Speak in clear, natural English, keep your sentences relatively short, and gently correct any major grammatical errors in the user\'s input with polite suggestions.',
    openingMessageEnabled: true,
    openingMessage: 'Hello! I\'m your English Speaking Coach. Let\'s practice speaking English together. What topic would you like to talk about today?',
    suggestedQuestions: ['Let\'s practice ordering food at a restaurant.', 'How can I say "辛苦了" in English?', 'Help me correct this sentence: "I goes to school yesterday."'],
    temperature: 0.6,
    maxTokens: 1000,
    tag: '语言学习',
    gradient: 'from-amber-500 to-orange-600',
    iconName: 'Languages',
  }
] as const;

const getTemplateIcon = (iconName: string) => {
  switch (iconName) {
    case 'Headphones':
      return <Headphones size={24} />;
    case 'PenTool':
      return <PenTool size={24} />;
    case 'BarChart2':
      return <BarChart2 size={24} />;
    case 'Languages':
      return <Languages size={24} />;
    default:
      return <Bot size={24} />;
  }
};

const TrendChart = ({ dailyTrends }: { dailyTrends: { date: string; count: number }[] }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    const chartDom = chartRef.current;
    const myChart = echarts.init(chartDom);
    
    const option = {
      grid: {
        top: '12%',
        left: '2%',
        right: '2%',
        bottom: '4%',
        containLabel: true,
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow',
        },
        backgroundColor: '#1e293b',
        borderWidth: 0,
        borderRadius: 8,
        padding: [8, 12],
        textStyle: {
          color: '#ffffff',
          fontSize: 12,
        },
        formatter: (params: any) => {
          const item = params[0];
          return `<div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;">${item.name}</div>
            <div style="font-weight: bold; font-size: 14px; color: #38bdf8;">${item.value} <span style="font-size: 11px; font-weight: normal; color: #cbd5e1;">次会话</span></div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: dailyTrends.map((d) => d.date),
        axisLine: {
          lineStyle: {
            color: '#e2e8f0',
          },
        },
        axisLabel: {
          color: '#64748b',
          fontSize: 11,
          fontFamily: 'monospace',
        },
        axisTick: {
          show: false,
        },
      },
      yAxis: {
        type: 'value',
        splitLine: {
          lineStyle: {
            color: '#f1f5f9',
          },
        },
        axisLabel: {
          color: '#64748b',
          fontSize: 11,
          fontFamily: 'monospace',
        },
      },
      series: [
        {
          name: '会话数',
          type: 'bar',
          data: dailyTrends.map((d) => d.count),
          barWidth: '30%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#0d9488' },
              { offset: 1, color: '#0f766e' },
            ]),
            borderRadius: [4, 4, 0, 0],
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#0f766e' },
                { offset: 1, color: '#115e59' },
              ]),
            },
          },
        },
      ],
    };

    myChart.setOption(option);

    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      myChart.dispose();
    };
  }, [dailyTrends]);

  return <div ref={chartRef} className="w-full h-full min-h-[240px] flex-1" />;
};

export const ApplicationManagementPage = () => {
  const { token } = theme.useToken();
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
  const [maxTokensUnlimited, setMaxTokensUnlimited] = useState(false);
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

  const [selectedTemplate, setSelectedTemplate] = useState<typeof AGENT_TEMPLATES[number] | null>(null);

  // Tab control state
  const [activeTab, setActiveTab] = useState<'orchestrate' | 'conversation' | 'annotations' | 'logs' | 'monitor'>('orchestrate');

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

  // Annotation state
  const [annotations, setAnnotations] = useState<AgentAnnotationRecord[]>([]);
  const [annotationsLoading, setAnnotationsLoading] = useState(false);
  const [annotationKeyword, setAnnotationKeyword] = useState('');
  const [annotationSearchValue, setAnnotationSearchValue] = useState('');
  const [annotationDialogOpen, setAnnotationDialogOpen] = useState(false);
  const [editingAnnotation, setEditingAnnotation] = useState<AgentAnnotationRecord | null>(null);
  const [annotationQuestion, setAnnotationQuestion] = useState('');
  const [annotationAnswer, setAnnotationAnswer] = useState('');
  const [annotationSaving, setAnnotationSaving] = useState(false);
  const [annotationsEnabled, setAnnotationsEnabled] = useState(true);

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
    if (maxTokensUnlimited !== selectedApplication.maxTokensUnlimited) return true;
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
    maxTokensUnlimited,
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
      const [llmResult, documentsResult] = await Promise.allSettled([
        fetchCompanyLLMOptions(),
        fetchAllKnowledgeDocuments(),
      ]);
      if (llmResult.status === 'fulfilled') {
        setLlmOptions(llmResult.value);
      }
      if (documentsResult.status === 'fulfilled') {
        setKnowledgeDocuments(documentsResult.value);
      }
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
      setMaxTokensUnlimited(detail.maxTokensUnlimited);
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
  const llmModelOptions = useMemo(
    () => [
      { label: '无模型', value: 'none' },
      ...((llmOptions?.providers || [])
        .filter((provider) => (provider.models || []).length > 0)
        .map((provider) => ({
          label: provider.name,
          options: provider.models.map((model) => ({
            label: model.displayName || model.name,
            value: String(model.id),
          })),
        }))),
    ],
    [llmOptions],
  );
  const hasAvailableLlmModels = llmModelOptions.length > 1;
  const isOpeningPlaybackPending = agentAudio.pendingPlaybackKey === 'opening-message';
  const isOpeningPlaybackPlaying = agentAudio.playingKey === 'opening-message' && !agentAudio.paused;

  // Reset states when switching applications
  useEffect(() => {
    setActiveTab('orchestrate');
    setSelectedLogConversation(null);
    setLogConversations([]);
    setAnnotations([]);
    setAnnotationKeyword('');
    setAnnotationSearchValue('');
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

  const loadAnnotations = useCallback(async () => {
    if (!selectedApplicationId) return;
    setAnnotationsLoading(true);
    try {
      const data = await fetchAgentAnnotations(selectedApplicationId, annotationKeyword);
      setAnnotations(data);
      setAnnotationsEnabled(data.some((item) => item.isActive) || data.length === 0);
    } catch {
      message.error('标注列表加载失败');
    } finally {
      setAnnotationsLoading(false);
    }
  }, [annotationKeyword, selectedApplicationId]);

  const openAnnotationDialog = (annotation?: AgentAnnotationRecord) => {
    setEditingAnnotation(annotation || null);
    setAnnotationQuestion(annotation?.question || '');
    setAnnotationAnswer(annotation?.answer || '');
    setAnnotationDialogOpen(true);
  };

  const closeAnnotationDialog = () => {
    setAnnotationDialogOpen(false);
    setEditingAnnotation(null);
    setAnnotationQuestion('');
    setAnnotationAnswer('');
  };

  const saveAnnotation = async () => {
    if (!selectedApplicationId) return;
    const question = annotationQuestion.trim();
    const answer = annotationAnswer.trim();
    if (!question || !answer) {
      message.warning('请填写问题和标准回复');
      return;
    }
    setAnnotationSaving(true);
    try {
      if (editingAnnotation) {
        await updateAgentAnnotation(selectedApplicationId, editingAnnotation.id, { question, answer });
        message.success('标注已更新');
      } else {
        await createAgentAnnotation(selectedApplicationId, { question, answer });
        message.success('标注已创建');
      }
      closeAnnotationDialog();
      await loadAnnotations();
    } catch {
      message.error('标注保存失败');
    } finally {
      setAnnotationSaving(false);
    }
  };

  const toggleAnnotation = async (annotation: AgentAnnotationRecord, checked: boolean, silent = false) => {
    if (!selectedApplicationId) return;
    try {
      await updateAgentAnnotation(selectedApplicationId, annotation.id, { isActive: checked });
      setAnnotations((current) => current.map((item) => (item.id === annotation.id ? { ...item, isActive: checked } : item)));
      if (!silent) {
        message.success(checked ? '标注已启用' : '标注已停用');
      }
    } catch {
      if (silent) {
        throw new Error('annotation status update failed');
      }
      if (!silent) {
        message.error('标注状态更新失败');
      }
    }
  };

  const removeAnnotation = async (annotationId: number) => {
    if (!selectedApplicationId) return;
    try {
      await deleteAgentAnnotation(selectedApplicationId, annotationId);
      setAnnotations((current) => current.filter((item) => item.id !== annotationId));
      message.success('标注已删除');
    } catch {
      message.error('标注删除失败');
    }
  };

  const createAnnotationFromAssistantMessage = async (assistantMessage: ChatMessage) => {
    if (!selectedApplicationId || assistantMessage.role !== 'assistant') return;
    const assistantIndex = messages.findIndex((item) => item.id === assistantMessage.id);
    const searchMessages = assistantIndex >= 0 ? messages.slice(0, assistantIndex) : messages;
    const previousUserMessage = [...searchMessages].reverse().find((item) => item.role === 'user');
    if (!previousUserMessage) {
      message.warning('未找到对应的问题');
      return;
    }
    try {
      await createAgentAnnotationFromMessage(selectedApplicationId, {
        messageId: assistantMessage.id,
        question: previousUserMessage.content,
        answer: assistantMessage.content,
      });
      message.success('已添加到标注');
      if (activeTab === 'annotations') {
        await loadAnnotations();
      }
    } catch {
      message.error('添加标注失败');
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
    if (activeTab === 'annotations') {
      void loadAnnotations();
    } else if (activeTab === 'logs') {
      void loadLogConversations();
    } else if (activeTab === 'monitor') {
      void loadStats();
    }
  }, [activeTab, loadAnnotations, loadLogConversations, loadStats]);

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
      const payload: AgentApplicationPayload = {
        name: createName.trim(),
        description: createDescription.trim(),
        temperature: selectedTemplate ? selectedTemplate.temperature : DEFAULT_TEMPERATURE,
        maxTokens: selectedTemplate ? selectedTemplate.maxTokens : DEFAULT_MAX_TOKENS,
        systemPrompt: selectedTemplate ? selectedTemplate.systemPrompt : '',
        openingMessageEnabled: selectedTemplate ? selectedTemplate.openingMessageEnabled : true,
        openingMessage: selectedTemplate ? selectedTemplate.openingMessage : '',
        suggestedQuestions: selectedTemplate ? [...selectedTemplate.suggestedQuestions] : [],
        isActive: true,
      };
      const created = await createAgentApplication(payload);
      message.success('智能体已创建');
      setCreateName('');
      setCreateDescription('');
      setSelectedTemplate(null);
      setCreateOpen(false);
      await loadApplications();
      navigate(`${created.id}`);
    } catch {
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
        maxTokensUnlimited,
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
          maxTokensUnlimited: payload.maxTokensUnlimited,
        });
        setConversation(nextConversation);
      }
      message.success('智能体配置已保存');
      await loadApplications();
    } catch {
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
    maxTokensUnlimited,
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
    if (replyPlaybackEnabled && ttsReady) {
      agentAudio.startStreamPlayback();
    }

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      setStreaming(false);
      abortRef.current = null;
      if (replyPlaybackEnabled && ttsReady) {
        agentAudio.finishStreamPlayback();
      }
      void refreshConversation(activeConversation.id)
        .then(() => undefined)
        .catch(() => {
          message.error('会话刷新失败');
        });
    };

    const controller = await sendMessageStream(
      activeConversation.id,
      content,
      true,
      null,
      (text) => {
        setStreamingContent((current) => current + text);
        if (replyPlaybackEnabled && ttsReady) {
          agentAudio.appendStreamPlaybackText(text);
        }
      },
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
    agentAudio.stopPlayback();
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

  const applicationOverview = useMemo(() => {
    const activeCount = applications.filter((app) => app.isActive).length;
    const configuredModelCount = applications.filter((app) => app.llmModelId).length;
    const knowledgeReferenceCount = applications.reduce(
      (total, app) => total + (app.knowledgeDocumentIds?.length || app.knowledgeDocuments?.length || 0),
      0,
    );

    return {
      activeCount,
      inactiveCount: applications.length - activeCount,
      configuredModelCount,
      knowledgeReferenceCount,
    };
  }, [applications]);

  const clearApplicationSearch = () => {
    setSearchValue('');
    setKeyword('');
    setApplicationPage(1);
  };

  const renderApplicationList = () => (
    <div className="flex flex-col gap-5 px-1 py-1">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-stretch md:items-center gap-4">
        <div style={{ minWidth: 0 }}>
          <div className="text-xl font-bold text-slate-800 tracking-tight">智能体控制台</div>
          <span className="text-sm text-slate-500">
            查看您已创建的智能体并进行配置，或通过下方的预设模板一键初始化新角色。
          </span>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-2.5 w-full md:w-auto shrink-0">
          <Input
            placeholder="搜索智能体名称或描述..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{ width: '100%', minWidth: 260 }}
            prefix={<Search size={16} className="text-slate-400" />}
          />
          <Button type="primary" onClick={handleSearch} className="w-full sm:w-auto cursor-pointer flex items-center justify-center gap-1">
            <Search size={14} />
            搜索
          </Button>
          {(keyword || searchValue) && (
            <Button type="text" onClick={clearApplicationSearch} className="w-full sm:w-auto cursor-pointer">
              清空
            </Button>
          )}
          {canCreate && (
            <Button type="primary" onClick={() => {
              setSelectedTemplate(null);
              setCreateName('');
              setCreateDescription('');
              setCreateOpen(true);
            }} className="w-full sm:w-auto cursor-pointer flex items-center justify-center gap-1">
              <Plus size={16} />
              创建智能体
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Section */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card variant="borderless" className="bg-white border border-slate-200/60 shadow-sm hover:shadow-md transition-all duration-300 rounded-2xl">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-medium">智能体总数</span>
            <span className="text-2xl font-bold font-mono leading-none text-slate-800">{applicationTotal}</span>
            <span className="text-xs text-slate-400 mt-1">所有已注册的智能体</span>
          </div>
        </Card>
        <Card variant="borderless" className="bg-white border border-slate-200/60 shadow-sm hover:shadow-md transition-all duration-300 rounded-2xl">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-medium">正常运行中</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono leading-none text-emerald-600">{applicationOverview.activeCount}</span>
              <span className="text-xs text-slate-400">停用 {applicationOverview.inactiveCount}</span>
            </div>
            <span className="text-xs text-slate-400 mt-1">可对外提供对话服务</span>
          </div>
        </Card>
        <Card variant="borderless" className="bg-white border border-slate-200/60 shadow-sm hover:shadow-md transition-all duration-300 rounded-2xl">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-medium">模型绑定率</span>
            <span className="text-2xl font-bold font-mono leading-none text-teal-600">{applicationOverview.configuredModelCount}</span>
            <span className="text-xs text-slate-400 mt-1">已绑定大语言模型</span>
          </div>
        </Card>
        <Card variant="borderless" className="bg-white border border-slate-200/60 shadow-sm hover:shadow-md transition-all duration-300 rounded-2xl">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-medium">知识库引用数</span>
            <span className="text-2xl font-bold font-mono leading-none text-blue-600">{applicationOverview.knowledgeReferenceCount}</span>
            <span className="text-xs text-slate-400 mt-1">文档关联引用次数</span>
          </div>
        </Card>
      </div>

      {/* Templates Section */}
      {!keyword && (
        <div className="bg-slate-50/50 border border-slate-200/40 rounded-2xl p-5 mt-1">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <Sparkles size={20} className="text-teal-600" />
            <div className="text-base font-bold text-slate-800">选用推荐模板一键初始化</div>
            <Tag color="cyan">开箱即用</Tag>
          </div>
          <span className="text-xs text-slate-500 block mb-4">
            为您预置了企业常见业务场景的角色人设，包含完整的系统提示词和常用开场白设定。
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {/* Blank Custom Card */}
            <Card variant="borderless" className="flex flex-col justify-between border-2 border-dashed border-slate-200 hover:border-teal-400 hover:bg-teal-50/10 cursor-pointer transition-all duration-300 rounded-2xl group min-h-[220px]" onClick={() => {
                setSelectedTemplate(null);
                setCreateName('');
                setCreateDescription('');
                setCreateOpen(true);
              }}
            >
              <div className="flex flex-col justify-center items-center gap-3 py-6" style={{ height: '100%' }}>
                <div className="p-4 bg-slate-100 rounded-full text-slate-500 group-hover:bg-teal-50/80 group-hover:text-teal-600 transition-colors duration-300">
                  <Plus size={28} />
                </div>
                <div className="text-center">
                  <span className="text-base font-bold text-slate-700 group-hover:text-teal-700 transition-colors duration-300 block mb-1">
                    新建空白智能体
                  </span>
                  <span className="text-xs text-slate-500 px-4 leading-relaxed block">
                    不预设行为人设，从零自由组装并调优您的专属应用。
                  </span>
                </div>
              </div>
            </Card>

            {/* Predefined templates */}
            {AGENT_TEMPLATES.map((tmpl) => (
              <Card variant="borderless" key={tmpl.key} className="flex flex-col justify-between bg-white border border-slate-200/60 hover:border-teal-300 hover:shadow-md cursor-pointer transition-all duration-300 rounded-2xl relative overflow-hidden group min-h-[220px]" onClick={() => {
                  setSelectedTemplate(tmpl);
                  setCreateName(tmpl.name);
                  setCreateDescription(tmpl.description);
                  setCreateOpen(true);
                }}
              >
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-teal-400 to-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <div className="flex flex-col gap-3 p-1 h-full justify-between">
                  <div className="flex justify-between items-center">
                    <div className={`p-2.5 bg-gradient-to-br ${tmpl.gradient} rounded-xl text-white shadow-sm`}>
                      {getTemplateIcon(tmpl.iconName)}
                    </div>
                    <Tag color="cyan" className="m-0 text-[10px]">
                      {tmpl.tag}
                    </Tag>
                  </div>

                  <div>
                    <span className="text-base font-bold text-slate-800 group-hover:text-teal-700 transition-colors duration-300 block mb-1">
                      {tmpl.name}
                    </span>
                    <span className="text-xs text-slate-500 line-clamp-3 leading-relaxed">
                      {tmpl.description}
                    </span>
                  </div>

                  <div className="border-t border-slate-100 mt-4 pt-3 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400">
                      含 {tmpl.suggestedQuestions.length} 条建议问题
                    </span>
                    <Button type="primary" size="small" className="group-hover:translate-x-0.5 transition-transform duration-200 cursor-pointer flex items-center gap-0.5">
                      使用模板 <ArrowRight size={10} />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Created Agents Section */}
      <div className="mt-2">
        <div className="flex items-center gap-2 mb-4">
          <Bot size={20} className="text-teal-600" />
          <div className="text-lg font-bold text-slate-800">
            {keyword ? '搜索筛选结果' : '我的智能体'}
          </div>
          <Badge count={applicationTotal} showZero color="#0f766e" />
          {keyword && (
            <span className="text-xs text-slate-400 ml-1">
              (筛选含有 "{keyword}" 的项)
            </span>
          )}
        </div>

        <Spin spinning={listLoading}>
          {applications.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {applications.map((app) => {
                const modelName = app.llmModelDisplayName || app.llmModelName;
                const knowledgeCount = app.knowledgeDocumentIds?.length || app.knowledgeDocuments?.length || 0;

                return (
                  <Card variant="borderless" key={app.id} className="flex flex-col justify-between bg-white border border-slate-200/60 hover:border-teal-200 hover:shadow-md transition-all duration-300 rounded-2xl relative overflow-hidden group min-h-[220px]">
                    <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-teal-500 to-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    
                    <div className="flex flex-col gap-3 p-1">
                      <div className="flex justify-between items-center">
                        <div className="p-2.5 bg-teal-50/80 rounded-xl text-teal-700">
                          <Bot size={20} />
                        </div>
                        <div className="flex items-center gap-2">
                          <Switch 
                            checked={app.isActive} 
                            disabled={!canUpdate} 
                            onChange={async (checked) => {
                              try {
                                await updateAgentApplication(app.id, { isActive: checked });
                                message.success(`智能体已${checked ? '启用' : '停用'}`);
                                await loadApplications();
                              } catch {
                                message.error('状态更新失败');
                              }
                            }}
                            className="cursor-pointer"
                            size="small"
                          />
                          <Tag color={app.isActive ? 'success' : 'default'} className="m-0">
                            {app.isActive ? '服务中' : '已停用'}
                          </Tag>
                        </div>
                      </div>

                      <div>
                        <span className="text-base font-bold text-slate-800 line-clamp-1 mb-1 block">
                          {app.name}
                        </span>
                        <span className="text-xs text-slate-500 line-clamp-2 h-9 leading-relaxed block">
                          {app.description || '暂无描述，点击配置开始进行详细编排设定。'}
                        </span>
                      </div>

                      <div className="flex gap-1.5 flex-wrap mt-1">
                        {modelName ? (
                          <Tag color="cyan" className="max-w-full truncate m-0">
                            {modelName}
                          </Tag>
                        ) : (
                          <Tag color="warning" className="m-0">未绑定模型</Tag>
                        )}
                        <Tag color={knowledgeCount > 0 ? 'blue' : 'default'} className="m-0 flex items-center gap-1">
                          <BookOpen size={10} className="shrink-0" />
                          {knowledgeCount} 文档
                        </Tag>
                      </div>
                    </div>

                    <div className="border-t border-slate-100 mt-4 pt-3 flex items-center justify-between">
                      <span className="text-xs text-slate-400 font-mono">
                        {dayjs(app.updated_at).format('YYYY-MM-DD')}
                      </span>
                      <div className="flex gap-2">
                        {canDelete && (
                          <Popconfirm
                            title="确认删除智能体"
                            description={`删除后将移除智能体配置、对话设置、关联会话和消息，且不可恢复。确定删除「${app.name}」吗？`}
                            onConfirm={() => void handleDelete(app.id)}
                            okText="确认删除"
                            cancelText="取消"
                            okButtonProps={{ danger: true, type: 'primary' }}
                            disabled={!canDelete}
                            placement="topRight"
                          >
                            <Button type="primary" danger size="small" className="rounded-lg cursor-pointer flex items-center justify-center p-1.5">
                              <Trash2 size={13} />
                            </Button>
                          </Popconfirm>
                        )}
                        <Button type="primary" size="small" onClick={() => navigate(`${app.id}`)} className="rounded-lg cursor-pointer flex items-center gap-0.5">
                          配置 <ArrowRight size={12} />
                        </Button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col justify-center items-center gap-3 bg-white rounded-2xl border border-slate-200/50 shadow-sm text-slate-400 py-12">
              <Bot size={40} className="text-slate-300" />
              <span className="text-sm text-slate-500 font-medium">
                {keyword ? '没有匹配的智能体' : '还没有已创建的智能体'}
              </span>
              {canCreate && !keyword && (
                <span className="text-xs text-slate-400 max-w-md px-4 leading-relaxed text-center block">
                  目前智能体列表为空。您可以在上方选择预置的业务模板一键初始化，或者点击“新建空白智能体”进行深度定制开发。
                </span>
              )}
            </div>
          )}
        </Spin>

        {/* Pagination Section */}
        {applicationTotal > PAGE_SIZE && (
          <div className="flex justify-end mt-6 border-t border-slate-200/30 pt-4">
            <Pagination
              current={applicationPage}
              pageSize={PAGE_SIZE}
              total={applicationTotal}
              onChange={(page) => setApplicationPage(page)}
              showSizeChanger={false}
              showTotal={(total) => `共 ${total} 个智能体`}
            />
          </div>
        )}
      </div>
    </div>
  );

  const renderChatMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'user';
    const playbackKey = `message-${msg.id}`;
    const isPlaybackPending = agentAudio.pendingPlaybackKey === playbackKey;
    const isPlaybackPlaying = agentAudio.playingKey === playbackKey && !agentAudio.paused;
    return (
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`} key={msg.id}>
        <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} gap-3`} style={{ maxWidth: '85%' }}>
          <Avatar
            size={36}
            icon={isUser ? <User size={16} /> : <Bot size={16} />}
            className={isUser ? '!bg-indigo-600 shrink-0' : '!bg-teal-600 shrink-0'}
          />
          <div className="flex flex-col gap-1">
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
              <div className="flex items-center gap-2 flex-wrap px-1">
                <Button 
                  type="text" 
                  size="small"
                  disabled={!ttsReady || isPlaybackPending} 
                  onClick={() => void agentAudio.playText(playbackKey, msg.content)}
                  className="flex items-center gap-1 text-slate-500 hover:text-teal-600 !px-1.5"
                >
                  {isPlaybackPending ? <Loader2 size={12} className="animate-spin" /> : isPlaybackPlaying ? <Pause size={12} /> : <Play size={12} />}
                  <span className="text-xs">{isPlaybackPending ? '生成中' : isPlaybackPlaying ? '暂停' : '播放'}</span>
                </Button>
                {agentAudio.playingKey === playbackKey && (
                  <Button 
                    type="text" 
                    danger 
                    size="small"
                    onClick={agentAudio.stopPlayback}
                    className="flex items-center gap-1 !px-1.5"
                  >
                    <Square size={12} />
                    <span className="text-xs">停止</span>
                  </Button>
                )}
                <Button 
                  type="text" 
                  size="small"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(msg.content);
                      message.success('已复制到剪贴板');
                    } catch {
                      message.error('复制失败');
                    }
                  }}
                  className="flex items-center gap-1 text-slate-500 hover:text-teal-600 !px-1.5"
                >
                  <Copy size={12} />
                  <span className="text-xs">复制</span>
                </Button>
                <Button 
                  type="text" 
                  size="small"
                  disabled={!canUpdate} 
                  onClick={() => void createAnnotationFromAssistantMessage(msg)}
                  className="flex items-center gap-1 text-slate-500 hover:text-teal-600 !px-1.5"
                >
                  <BookmarkPlus size={12} />
                  <span className="text-xs">添加到标注</span>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderOrchestrateTab = () => (
    <Spin spinning={detailLoading || optionsLoading} className="h-full" wrapperClassName="h-full-spin">
      <div className="grid grid-cols-1 xl:grid-cols-[390px_minmax(0,_1fr)] gap-4 h-full min-h-0">
        {/* Left Side: Config Panel */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden h-full" styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%', padding: '20px', overflow: 'hidden' } }}>
          <div className="text-lg font-bold shrink-0 mb-4">编排设置</div>
          
          <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-4 custom-scrollbar min-h-0">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-bold text-slate-700">智能体名称</span>
              <Input 
                disabled={!canUpdate}
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={128}
                placeholder="请输入智能体名称"
              />
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-sm font-bold text-slate-700">描述说明</span>
              <Input.TextArea
                disabled={!canUpdate}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={255}
                placeholder="输入描述以帮助团队了解它的用途"
                rows={2}
              />
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-slate-700">选用模型</span>
                <Tooltip title="选择为该智能体提供推理能力的大语言模型。需要先在服务提供商页面配置好 API 密钥。">
                  <HelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </div>
              <Select
                disabled={!canUpdate || !hasAvailableLlmModels}
                loading={optionsLoading}
                options={llmModelOptions}
                optionFilterProp="label"
                placeholder="请选择模型"
                showSearch
                value={llmModelId ? String(llmModelId) : 'none'}
                onChange={(val) => setLlmModelId(val === 'none' ? null : Number(val))}
              />
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-slate-700">系统提示词 (System Prompt)</span>
                <Tooltip title="设定智能体的角色人设、回复风格 and 行为约束，引导大模型产生符合预期的输出。">
                  <HelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </div>
              <Input.TextArea
                disabled={!canUpdate}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="您是大模型的引导者，在这里输入大模型的系统人设与行为提示..."
                rows={5}
                className="font-mono text-xs"
              />
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-sm font-bold text-slate-700">绑定知识库文档</span>
              <Popover
                placement="bottomLeft"
                trigger="click"
                styles={{ root: { width: 340 } }}
                content={
                  <div className="flex flex-col gap-2 max-h-[260px] overflow-y-auto pr-1 custom-scrollbar">
                    {knowledgeDocuments.length > 0 ? (
                      knowledgeDocuments.map((doc) => {
                        const isChecked = selectedDocs.includes(doc.id);
                        const isTxtOrMd = ['txt', 'md'].includes(doc.fileExtension?.toLowerCase() || '');
                        return (
                          <div className="text-sm flex items-start gap-2 hover:bg-slate-50 p-2 rounded-lg cursor-pointer" key={doc.id}
                            onClick={() => {
                              if (isChecked) {
                                setSelectedDocs(selectedDocs.filter((id) => id !== doc.id));
                              } else {
                                setSelectedDocs([...selectedDocs, doc.id]);
                              }
                            }}
                          >
                            <Checkbox
                              checked={isChecked}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedDocs([...selectedDocs, doc.id]);
                                } else {
                                  setSelectedDocs(selectedDocs.filter((id) => id !== doc.id));
                                }
                              }}
                            />
                            <div className="flex flex-col">
                              <span className="text-sm font-semibold text-slate-800">{doc.title || doc.fileName}</span>
                              {!isTxtOrMd && <span className="text-xs text-slate-400">暂不参与检索 (仅支持 txt/md)</span>}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-sm text-slate-400 text-center py-4">暂无可用知识库</div>
                    )}
                  </div>
                }
              >
                <Button type="default" style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="text-sm text-slate-505">选择关联知识库 ({selectedDocs.length} 个已选)</span>
                  <ChevronDown size={14} className="text-slate-400" />
                </Button>
              </Popover>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold text-slate-700">随机性温度 (Temperature)</span>
                  <Tooltip title="值越高回复越具创意 and 随机性；值越低回复越确定 and 保守。建议客服场景设为 0.2-0.5，创作场景设为 0.7-1.0。">
                    <HelpCircle size={14} className="text-slate-400 cursor-help" />
                  </Tooltip>
                </div>
                <Tag color="cyan">{temperature}</Tag>
              </div>
              <Slider
                disabled={!canUpdate}
                value={temperature}
                onChange={(val) => setTemperature(val)}
                min={0}
                max={2}
                step={0.1}
              />
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold text-slate-700">最大输出 Tokens</span>
                  <Tooltip title="单次模型回复生成的最大 Token 数量。开启不限制后，请求大模型时不会传递 max_tokens 参数。">
                    <HelpCircle size={14} className="text-slate-400 cursor-help" />
                  </Tooltip>
                </div>
                <Button
                  size="small"
                  type={maxTokensUnlimited ? 'primary' : 'default'}
                  disabled={!canUpdate}
                  onClick={() => setMaxTokensUnlimited((checked) => !checked)}
                >
                  不限制 Tokens
                </Button>
              </div>
              <Input 
                disabled={!canUpdate || maxTokensUnlimited}
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                min={1}
                max={320000}
              />
            </div>

            <div className="flex items-center gap-3 mt-2 mb-4">
              <span className="text-sm font-bold text-slate-700">启用此智能体</span>
              <Switch disabled={!canUpdate} checked={isActive} onChange={setIsActive} />
            </div>
          </div>
        </Card>

        {/* Right Side: Debug Chat */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden h-full" styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%', padding: '20px' } }}>
          {/* Chat Header */}
          <div className="flex justify-between items-center border-b border-slate-100 pb-3 mb-3 shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-teal-600" />
              <div className="text-lg font-bold">调试预览</div>
            </div>
            <div className="flex items-center gap-2">
              {conversation && (
                <Button type="text" size="small" onClick={async () => {
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
                  className="flex items-center gap-1 text-slate-500 hover:text-teal-600"
                >
                  <RotateCcw size={14} />
                  <span className="text-xs">新对话</span>
                </Button>
              )}
              {conversation ? (
                <Tag color="cyan" className="font-mono m-0">会话: #{conversation.id}</Tag>
              ) : (
                <Tag color="default" className="m-0">未开始</Tag>
              )}
            </div>
          </div>

          {/* Chat message content */}
          <div className="flex-1 overflow-y-auto bg-slate-50/40 p-4 rounded-xl border border-slate-100/50 min-h-0 custom-scrollbar">
            {chatLoading ? (
              <div className="flex justify-center items-center h-full">
                <Spin />
              </div>
            ) : displayedMessages.length > 0 ? (
              <div>
                {displayedMessages.map(renderChatMessage)}
                <div ref={messagesEndRef} />
              </div>
            ) : (
              <div className="flex flex-col justify-center items-center gap-4 h-full text-slate-400">
                <MessageSquare size={36} className="text-slate-300" />
                {openingMessageEnabled && openingMessage ? (
                  <div className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm max-w-xl text-slate-700 text-sm">
                    {openingMessage}
                  </div>
                ) : (
                  <span className="text-sm">输入消息并发送，开始与大模型进行调试对话</span>
                )}
                {suggestedQuestions.length > 0 && (
                  <div className="flex justify-center gap-2 flex-wrap max-w-lg mt-2">
                    {suggestedQuestions.map((question, index) => (
                      <Button 
                        type="dashed" 
                        size="small"
                        key={`${index}-${question}`} 
                        disabled={streaming || !canChat} 
                        onClick={() => void sendSuggestedQuestion(question)}
                        className="rounded-full flex items-center gap-1 text-xs text-slate-600 hover:text-teal-600 hover:border-teal-500"
                      >
                        <HelpCircle size={12} /> {question}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="flex gap-2 mt-3 pt-2 shrink-0">
            {voiceInputEnabled && (
              <Button 
                type="default" 
                disabled={!asrReady || agentAudio.transcribing} 
                onClick={() => {
                  if (agentAudio.recording) {
                    agentAudio.stopRecording();
                    return;
                  }
                  void agentAudio.startRecording((text) => setInputValue(text));
                }}
                className={`flex items-center justify-center ${agentAudio.recording ? 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100' : ''}`}
              >
                {agentAudio.recording ? <MicOff size={16} /> : <Mic size={16} />}
              </Button>
            )}
            <Input 
              value={inputValue}
              placeholder="发送调试消息..."
              disabled={!canChat || streaming || !selectedApplication}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
              style={{ flex: 1 }}
            />
            {streaming ? (
              <Button type="primary" danger onClick={handleStopStreaming} className="flex items-center gap-1">
                <Square size={14} /> 停止
              </Button>
            ) : (
              <Button type="primary" disabled={!inputValue.trim() || !canChat || !selectedApplication} onClick={() => void handleSend()} className="flex items-center justify-center">
                <Send size={16} />
              </Button>
            )}
          </div>
        </Card>
      </div>
    </Spin>
  );

  const renderConversationSettingsTab = () => (
    <Spin spinning={detailLoading} className="h-full" wrapperClassName="h-full-spin">
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(360px,_560px)_minmax(0,_1fr)] gap-4 h-full min-h-0">
        {/* Left Side: Settings Panel */}
        <div className="h-full flex flex-col gap-3 min-h-0">
          <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-3 custom-scrollbar min-h-0">
            {/* Opening Message */}
            <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm shrink-0" styles={{ body: { padding: '16px' } }}>
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-base font-bold text-slate-800">对话开场白</div>
                    <span className="text-xs text-slate-400">新对话进入时展示，且不写入聊天消息</span>
                  </div>
                  <Switch checked={openingMessageEnabled} disabled={!canUpdate} onChange={setOpeningMessageEnabled} />
                </div>
                <Input.TextArea
                  value={openingMessage}
                  disabled={!openingMessageEnabled || !canUpdate}
                  onChange={(event) => setOpeningMessage(event.target.value.slice(0, 200))}
                  rows={3}
                  placeholder="输入智能体开场白..."
                />
                <div className="flex justify-between text-xs text-slate-400">
                  <span>可在预览区播放开场白</span>
                  <span>{openingMessage.length}/200</span>
                </div>
              </div>
            </Card>

            {/* Suggested Questions */}
            <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm shrink-0" styles={{ body: { padding: '16px' } }}>
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-base font-bold text-slate-800">推荐建议问题</div>
                    <span className="text-xs text-slate-400">最多配置 10 条，引导用户开始对话</span>
                  </div>
                  <Tag color={suggestedQuestions.length >= 10 ? 'error' : 'default'}>{suggestedQuestions.length}/10</Tag>
                </div>
                {suggestedQuestions.length > 0 ? (
                  <div className="flex flex-col gap-2 max-h-[160px] overflow-y-auto pr-1 custom-scrollbar">
                    {suggestedQuestions.map((question, index) => (
                      <div className="flex items-center gap-1.5" key={`${index}-${question}`}>
                        <GripVertical size={14} className="text-slate-400 shrink-0 cursor-grab" />
                        <Input 
                          value={question}
                          onChange={(event) => updateSuggestedQuestion(index, event.target.value.slice(0, 120))}
                          disabled={!canUpdate}
                          style={{ flex: 1 }}
                        />
                        <Button 
                          type="default" 
                          size="small"
                          disabled={index === 0 || !canUpdate} 
                          onClick={() => moveSuggestedQuestion(index, -1)}
                          style={{ padding: '4px 8px' }}
                        >
                          <ChevronUp size={12} />
                        </Button>
                        <Button 
                          type="default" 
                          size="small"
                          disabled={index === suggestedQuestions.length - 1 || !canUpdate} 
                          onClick={() => moveSuggestedQuestion(index, 1)}
                          style={{ padding: '4px 8px' }}
                        >
                          <ChevronDownIcon size={12} />
                        </Button>
                        <Button 
                          type="primary" 
                          danger 
                          size="small"
                          disabled={!canUpdate} 
                          onClick={() => removeSuggestedQuestion(index)}
                          style={{ padding: '4px 8px' }}
                        >
                          <Trash2 size={12} />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-slate-400 rounded-xl border border-dashed border-slate-200 bg-slate-50/60 text-center py-4">
                    暂无建议问题，可在下方添加
                  </div>
                )}
                <div className="flex gap-2">
                  <Input 
                    value={newSuggestedQuestion}
                    onChange={(event) => setNewSuggestedQuestion(event.target.value.slice(0, 120))}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        addSuggestedQuestion();
                      }
                    }}
                    placeholder="添加建议问题，按 Enter 键确认..."
                    disabled={!canUpdate || suggestedQuestions.length >= 10}
                    style={{ flex: 1 }}
                  />
                  <Button disabled={!canUpdate || suggestedQuestions.length >= 10} onClick={addSuggestedQuestion} className="flex items-center gap-1">
                    <Plus size={14} /> 添加
                  </Button>
                </div>
              </div>
            </Card>

            {/* Voice Settings */}
            <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm shrink-0" styles={{ body: { padding: '16px' } }}>
              <div className="flex flex-col gap-4">
                <div className="flex justify-between items-center">
                  <div className="flex flex-col">
                    <span className="text-base font-bold text-slate-800">语音输入 (ASR)</span>
                    <span className="text-xs text-slate-400">
                      {asrReady ? '语音服务已就绪，可录制输入音频' : '语音服务未启用或尚未配置接口'}
                    </span>
                  </div>
                  <Switch checked={voiceInputEnabled} disabled={!canUpdate || !asrReady} onChange={setVoiceInputEnabled} />
                </div>
                <div className="flex justify-between items-center border-t border-slate-100 pt-4">
                  <div className="flex flex-col">
                    <span className="text-base font-bold text-slate-800">回复播报 (TTS)</span>
                    <span className="text-xs text-slate-400">
                      {ttsReady ? '使用默认音色在线语音播报开场白和回复' : '默认音色未设置或播报接口不可用'}
                    </span>
                  </div>
                  <Switch checked={replyPlaybackEnabled} disabled={!canUpdate || !ttsReady} onChange={setReplyPlaybackEnabled} />
                </div>
              </div>
            </Card>
          </div>

          <Button type="primary" size="large" disabled={!canUpdate || streaming} loading={configSaving} onClick={() => void handleSaveConfig()} className="shrink-0 w-full flex items-center justify-center gap-1.5">
            <Save size={16} /> 保存对话设置
          </Button>
        </div>

        {/* Right Side: Preview Panel */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden h-full" styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%', padding: '20px' } }}>
          <div className="flex justify-between items-center border-b border-slate-100 pb-3 mb-3 shrink-0">
            <div className="text-lg font-bold">调试预览</div>
            <Tag color="blue">实时同步</Tag>
          </div>
          
          <div className="flex-1 overflow-y-auto bg-slate-50/40 rounded-xl border border-slate-100/50 p-6 min-h-0 custom-scrollbar flex flex-col justify-center items-center gap-4">
            <Avatar 
              size={64} 
              icon={<Bot size={32} />} 
              className="!bg-teal-50 !text-teal-700 shadow-sm"
            />
            <div className="text-lg font-bold text-slate-800">开始与「{selectedApplication?.name || '智能体'}」对话</div>
            
            {openingMessageEnabled && openingMessage ? (
              <div className="flex flex-col items-center gap-3 w-full max-w-md">
                <div className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm text-sm text-slate-700 leading-relaxed text-center">
                  {openingMessage}
                </div>
                <div className="flex items-center gap-2">
                  <Button 
                    type="primary" 
                    size="small"
                    disabled={!ttsReady || isOpeningPlaybackPending} 
                    onClick={() => void agentAudio.playText('opening-message', openingMessage)}
                    className="flex items-center gap-1 rounded-full px-3"
                  >
                    {isOpeningPlaybackPending ? <Loader2 size={12} className="animate-spin" /> : isOpeningPlaybackPlaying ? <Pause size={12} /> : <Volume2 size={12} />}
                    <span>{isOpeningPlaybackPending ? '生成中' : isOpeningPlaybackPlaying ? '暂停开场白' : '播放开场白'}</span>
                  </Button>
                  {agentAudio.playingKey === 'opening-message' && (
                    <Button 
                      type="text" 
                      danger 
                      size="small"
                      onClick={agentAudio.stopPlayback}
                      className="flex items-center gap-1"
                    >
                      <Square size={12} />
                      <span>停止</span>
                    </Button>
                  )}
                </div>
              </div>
            ) : null}

            {suggestedQuestions.length > 0 ? (
              <div className="flex justify-center gap-2 flex-wrap max-w-md mt-2">
                {suggestedQuestions.map((question, index) => (
                  <Button 
                    type="dashed" 
                    size="small"
                    key={`${index}-${question}`} 
                    disabled={streaming || !canChat} 
                    onClick={() => void sendSuggestedQuestion(question)}
                    className="rounded-full flex items-center gap-1 text-xs text-slate-600 hover:text-teal-600 hover:border-teal-500"
                  >
                    <HelpCircle size={12} /> {question}
                  </Button>
                ))}
              </div>
            ) : (
              <span className="text-xs text-slate-400">暂无推荐的建议问题</span>
            )}
          </div>

          <div className="flex gap-2 mt-3 pt-2 shrink-0">
            {voiceInputEnabled && (
              <Button 
                type="default" 
                disabled={!asrReady || agentAudio.transcribing} 
                onClick={() => {
                  if (agentAudio.recording) {
                    agentAudio.stopRecording();
                    return;
                  }
                  void agentAudio.startRecording((text) => setInputValue(text));
                }}
                className={`flex items-center justify-center ${agentAudio.recording ? 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100' : ''}`}
              >
                {agentAudio.recording ? <MicOff size={16} /> : <Mic size={16} />}
              </Button>
            )}
            <Input 
              value={inputValue}
              placeholder="预览文本发送消息..."
              disabled={!canChat || streaming || !selectedApplication}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && void handleSend()}
              style={{ flex: 1 }}
            />
            <Button type="primary" disabled={!inputValue.trim() || !canChat || streaming} onClick={() => void handleSend()} className="flex items-center justify-center">
              <Send size={16} />
            </Button>
          </div>
        </Card>
      </div>
    </Spin>
  );

  const renderAnnotationsTab = () => (
    <Spin spinning={annotationsLoading} className="h-full" wrapperClassName="h-full-spin">
      <div className="flex flex-col gap-4 h-full min-h-0">
        {/* Banner Card */}
        <Card variant="borderless" className="bg-blue-50/50 border border-blue-100 shadow-sm shrink-0" styles={{ body: { padding: '16px' } }}>
          <div className="flex justify-between items-center gap-4">
            <div className="flex items-center gap-4" style={{ minWidth: 0 }}>
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm">
                <BookOpen size={22} />
              </div>
              <div className="flex flex-col gap-0.5" style={{ minWidth: 0 }}>
                <div className="text-base font-bold text-slate-800">精确命中标准问答</div>
                <span className="text-xs text-slate-500 max-w-2xl leading-relaxed truncate md:whitespace-normal">
                  配置标准问答。如果用户提问内容与所配的标注问题相符，智能体将绕过模型推理直接返回该标准回复，从而达到 100% 回复准确率。
                </span>
              </div>
            </div>
            <Switch 
              checked={annotationsEnabled} 
              onChange={async (checked) => {
                setAnnotationsEnabled(checked);
                const changedAnnotations = annotations.filter((annotation) => annotation.isActive !== checked);
                if (changedAnnotations.length === 0) return;
                try {
                  await Promise.all(changedAnnotations.map((annotation) => toggleAnnotation(annotation, checked, true)));
                  message.success(checked ? '已启用全部标注' : '已停用全部标注');
                } catch {
                  message.error('批量更新标注失败');
                }
              }}
              disabled={!canUpdate || annotations.length === 0}
            />
          </div>
        </Card>

        {/* Search & Create Actions */}
        <div className="flex flex-col sm:flex-row gap-3 shrink-0">
          <Input 
            value={annotationSearchValue}
            placeholder="搜索标准问题或答案内容..."
            onChange={(event) => setAnnotationSearchValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                setAnnotationKeyword(annotationSearchValue.trim());
              }
            }}
            style={{ flex: 1 }}
            prefix={<Search size={16} className="text-slate-400" />}
          />
          
          <Button type="default" onClick={() => setAnnotationKeyword(annotationSearchValue.trim())} className="flex items-center gap-1 justify-center">
            <Search size={14} /> 搜索
          </Button>
          <Button type="primary" disabled={!canUpdate} onClick={() => openAnnotationDialog()} className="flex items-center gap-1 justify-center shadow-sm">
            <Plus size={16} /> 新增标注
          </Button>
        </div>

        {/* List scrollable section */}
        <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-3 min-h-0 custom-scrollbar">
          {annotations.length > 0 ? (
            annotations.map((annotation) => (
              <Card variant="borderless" key={annotation.id} className="bg-white border border-slate-200/70 shadow-sm hover:shadow-md transition-shadow duration-300" styles={{ body: { padding: '16px' } }}>
                <div className="flex flex-col gap-3.5">
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex items-start gap-2.5" style={{ minWidth: 0 }}>
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 text-xs font-bold mt-0.5">
                        Q
                      </span>
                      <div className="text-base font-bold text-slate-800 break-all leading-normal">{annotation.question}</div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Switch 
                        checked={annotation.isActive} 
                        disabled={!canUpdate} 
                        onChange={(checked) => void toggleAnnotation(annotation, checked)} 
                        size="small"
                      />
                      <Button type="text" size="small" disabled={!canUpdate} onClick={() => openAnnotationDialog(annotation)} className="text-slate-500 hover:text-teal-600">
                        编辑
                      </Button>
                      <Popconfirm
                        title="删除标注？"
                        description="确定要删除这个标准回复吗？删除后该提问将不会直接匹配该答案。"
                        onConfirm={() => void removeAnnotation(annotation.id)}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true, type: 'primary' }}
                        placement="topRight"
                      >
                        <Button type="text" danger size="small" disabled={!canUpdate}>
                          删除
                        </Button>
                      </Popconfirm>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 rounded-xl bg-slate-50 p-3.5">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 text-xs font-bold mt-0.5">
                      A
                    </span>
                    <div className="flex-1 min-w-0">
                      <ChatMarkdown content={annotation.answer} className="chat-markdown text-sm leading-relaxed text-slate-700" />
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                    <span className="flex items-center gap-1 text-slate-500">
                      <Zap size={13} className="text-amber-500" /> 累计命中 <span className="font-semibold text-slate-700">{annotation.hitCount}</span> 次
                    </span>
                    <span>•</span>
                    <span>修改于: {annotation.lastHitAt ? dayjs(annotation.lastHitAt).format('M月D日 HH:mm') : dayjs(annotation.updated_at).format('M月D日 HH:mm')}</span>
                    {!annotation.isActive && <Tag color="default" className="m-0 py-0 px-1.5 text-[10px]">已停用</Tag>}
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <Card variant="borderless" className="bg-white border border-slate-200/70 shadow-sm flex-1 flex flex-col items-center justify-center min-h-[300px]" styles={{ body: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%' } }}>
              <Empty description="暂无匹配的标注数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </Card>
          )}
        </div>
      </div>
    </Spin>
  );

  const renderLogsTab = () => (
    <Spin spinning={logConversationsLoading} className="h-full" wrapperClassName="h-full-spin">
      <div className="grid grid-cols-1 xl:grid-cols-[380px_minmax(0,_1fr)] gap-4 h-full min-h-0">
        {/* Conversation List */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm h-full" styles={{ body: { padding: '16px', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}>
          <div className="flex justify-between items-center border-b border-slate-100 pb-3 mb-3 shrink-0">
            <div className="text-base font-bold text-slate-800">历史会话记录</div>
            <Tag color="default">{logConversations.length} 会话</Tag>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1.5 custom-scrollbar min-h-0">
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
                  <div className="flex justify-between items-start gap-2 mb-1">
                    <span className="text-sm font-bold text-slate-800 truncate max-w-[190px]">
                      {conv.title}
                    </span>
                    <span className="text-xs text-slate-400 shrink-0 font-mono">
                      {dayjs(conv.updated_at).format('MM-DD HH:mm')}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 line-clamp-1 block mb-2">
                    {conv.summary || conv.lastMessage || '暂无对话文本记录'}
                  </span>
                  <div className="flex justify-between items-center text-[10px]">
                    <Tag color="cyan" className="m-0 scale-90 origin-left">
                      {conv.llmModelDisplayName || conv.llmModelName || '未分配模型'}
                    </Tag>
                    <span className="flex items-center gap-1 text-slate-400">
                      <MessageSquare size={11} /> {conv.messageCount} 消息
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex-1 flex items-center justify-center py-12">
                <Empty description="暂无任何调试会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            )}
          </div>
        </Card>

        {/* Selected Conversation Detail */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden h-full" styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%', padding: '20px' } }}>
          {selectedLogConversation ? (
            <Spin spinning={selectedLogConversationLoading} className="flex-1 flex flex-col h-full min-h-0" wrapperClassName="h-full-spin flex-1">
              <div className="flex flex-col h-full min-h-0">
                <div className="flex flex-col border-b border-slate-100 pb-3 mb-3 shrink-0">
                  <div className="text-lg font-bold text-slate-800">{selectedLogConversation.title}</div>
                  <span className="text-xs text-slate-400 mt-1 font-mono">
                    会话 ID: #{selectedLogConversation.id} • 创建时间: {dayjs(selectedLogConversation.created_at).format('YYYY-MM-DD HH:mm:ss')}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto bg-slate-50/20 p-4 rounded-xl border border-slate-100/30 custom-scrollbar min-h-0">
                  {selectedLogConversation.messages.length > 0 ? (
                    selectedLogConversation.messages.map((msg) => {
                      const isUser = msg.role === 'user';
                      return (
                        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`} key={msg.id}>
                          <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} gap-3`} style={{ maxWidth: '85%' }}>
                            <Avatar
                              size={32}
                              icon={isUser ? <User size={14} /> : <Bot size={14} />}
                              className={isUser ? '!bg-indigo-600 shrink-0' : '!bg-teal-600 shrink-0'}
                            />
                            <div className="flex flex-col gap-1">
                              <div
                                className={`rounded-2xl px-4 py-2 text-sm leading-relaxed shadow-sm ${
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
                              <div className="flex items-center gap-2 text-[10px] text-slate-400 px-1 mt-0.5 justify-start">
                                <span className="font-mono">{dayjs(msg.created_at).format('HH:mm:ss')}</span>
                                {!isUser && msg.feedback !== 'none' && (
                                  <Tag color={msg.feedback === 'up' ? 'success' : 'error'} className="m-0 scale-90 transform-gpu py-0 px-1">
                                    {msg.feedback === 'up' ? '好评' : '差评'}
                                  </Tag>
                                )}
                                {!isUser && (
                                  <Button 
                                    type="text" 
                                    size="small"
                                    onClick={async () => {
                                      try {
                                        await navigator.clipboard.writeText(msg.content);
                                        message.success('已复制到剪贴板');
                                      } catch {
                                        message.error('复制失败');
                                      }
                                    }}
                                    className="flex items-center gap-1 text-slate-400 hover:text-teal-600 !p-0 !h-auto"
                                    style={{ fontSize: 10 }}
                                  >
                                    <Copy size={10} />
                                    <span>复制</span>
                                  </Button>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-slate-400 text-center py-12 text-sm">暂无会话消息记录</div>
                  )}
                </div>
              </div>
            </Spin>
          ) : (
            <div className="flex flex-col justify-center items-center gap-3 text-slate-400 h-full">
              <MessageSquare size={40} className="text-slate-300" />
              <span className="text-sm">选择左侧历史会话查看详细聊天明细</span>
            </div>
          )}
        </Card>
      </div>
    </Spin>
  );

  const renderMonitorTab = () => {
    if (statsLoading) {
      return (
        <Card variant="borderless" className="flex h-full items-center justify-center bg-white border border-slate-200/50 shadow-sm h-full">
          <Spin size="large" />
        </Card>
      );
    }

    if (!stats) {
      return (
        <Card variant="borderless" className="flex h-full flex-col items-center justify-center bg-white border border-slate-200/50 shadow-sm text-slate-400 h-full" styles={{ body: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%' } }}>
          <Empty description="暂无监测数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      );
    }



    return (
      <div className="flex flex-col gap-4 h-full min-h-0 overflow-y-auto pr-1 custom-scrollbar">
        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
          <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow rounded-2xl">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-slate-400 font-medium">调试会话总数</span>
              <div className="flex items-baseline gap-1 mt-1.5">
                <span className="text-3xl font-bold font-mono text-slate-800">{stats.conversationCount}</span>
                <span className="text-xs text-slate-500">次</span>
              </div>
              <span className="text-[10px] text-slate-400 mt-2">智能体开启的调试会话总计</span>
            </div>
          </Card>

          <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow rounded-2xl">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-slate-400 font-medium">交流消息总量</span>
              <div className="flex items-baseline gap-1 mt-1.5">
                <span className="text-3xl font-bold font-mono text-slate-800">{stats.messageCount}</span>
                <span className="text-xs text-slate-500">条</span>
              </div>
              <div className="flex justify-between items-center mt-2 text-[10px] text-slate-400 font-medium font-mono">
                <span>用户: <span className="font-bold text-slate-600">{stats.userMessageCount}</span></span>
                <span>助手: <span className="font-bold text-slate-600">{stats.assistantMessageCount}</span></span>
              </div>
            </div>
          </Card>

          <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow rounded-2xl">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-slate-400 font-medium">用户满意好评率</span>
              <div className="flex items-baseline gap-1 mt-1.5">
                <span className="text-3xl font-bold font-mono text-slate-800">
                  {(stats.upCount + stats.downCount) > 0 ? `${Math.round((stats.upCount / (stats.upCount + stats.downCount)) * 100)}%` : '--'}
                </span>
                <span className="text-xs text-slate-500">赞同比例</span>
              </div>
              <div className="flex justify-between items-center mt-2 text-[10px] font-mono">
                <span className="text-emerald-600 font-bold">点赞: {stats.upCount}</span>
                <span className="text-red-500 font-bold">点踩: {stats.downCount}</span>
              </div>
            </div>
          </Card>

          <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm hover:shadow transition-shadow rounded-2xl">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-slate-400 font-medium">统计最近更新</span>
              <span className="text-base font-bold text-slate-800 mt-2 truncate">
                {dayjs(stats.updatedAt).format('YYYY-MM-DD')}
              </span>
              <span className="text-[10px] text-slate-400 font-mono mt-1.5">
                {dayjs(stats.updatedAt).format('HH:mm:ss')} (最近更新时间)
              </span>
            </div>
          </Card>
        </div>

        {/* 7-Day Trend Chart */}
        <Card variant="borderless" className="bg-white border border-slate-200/50 shadow-sm flex-1 min-h-[340px] rounded-2xl" styles={{ body: { height: '100%', display: 'flex', flexDirection: 'column', padding: '20px 24px' } }}>
          <div className="flex flex-col gap-4 h-full flex-1">
            <div className="text-lg font-bold text-slate-800 shrink-0">最近 7 天会话数趋势</div>
            <div className="flex-1 min-h-0 w-full flex items-center justify-center">
              <TrendChart dailyTrends={stats.dailyTrends} />
            </div>
          </div>
        </Card>
      </div>
    );
  };

  const renderTabButton = (tabKey: typeof activeTab, icon: React.ReactNode, label: string, badgeCount = 0) => {
    const isActive = activeTab === tabKey;
    return (
      <Button
        type={isActive ? 'primary' : 'text'}
        onClick={() => setActiveTab(tabKey)}
        className="w-full transition-all duration-200 group flex items-center justify-start py-6 px-4 rounded-xl border border-transparent cursor-pointer"
        style={{
          backgroundColor: isActive ? token.colorPrimary : 'transparent',
          color: isActive ? '#ffffff' : '#475569',
          fontWeight: isActive ? 600 : 500,
          boxShadow: isActive ? `0 4px 12px ${token.colorPrimary}25` : 'none',
          textAlign: 'left',
          height: '46px',
        }}
      >
        <div className="flex items-center w-full justify-between">
          <div className="flex items-center min-w-0">
            <span className={`mr-2.5 flex items-center transition-transform duration-200 ${isActive ? 'scale-110 text-white' : 'text-slate-400 group-hover:text-teal-700'}`}>
              {icon}
            </span>
            <span className="truncate">{label}</span>
          </div>
          {badgeCount > 0 && (
            <Badge
              count={badgeCount}
              style={{
                backgroundColor: isActive ? '#ffffff' : token.colorPrimary,
                color: isActive ? token.colorPrimary : '#ffffff',
                boxShadow: 'none',
              }}
            />
          )}
        </div>
      </Button>
    );
  };

  const renderApplicationWorkspace = () => (
    <div className="flex flex-col h-[calc(100vh-160px)] lg:h-[calc(100vh-140px)] w-full gap-4 overflow-hidden">
      {/* Workspace Header */}
      <div className="shrink-0 flex justify-between items-center gap-3 bg-white/90 backdrop-blur px-5 py-3.5 rounded-2xl border border-slate-200/40 shadow-sm">
        <div className="flex items-center gap-3" style={{ minWidth: 0 }}>
          <Button 
            type="text" 
            onClick={handleBackClick} 
            style={{ width: 34, height: 34, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            className="rounded-full hover:bg-slate-100 text-slate-600"
          >
            <ArrowLeft size={16} />
          </Button>
          <div className="flex flex-col" style={{ minWidth: 0 }}>
            <div className="text-lg font-bold text-slate-800 truncate leading-tight">{selectedApplication?.name || '智能体'}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse" />
              <span className="text-xs text-slate-500 truncate">
                {selectedApplication?.llmProviderName
                  ? `${selectedApplication.llmProviderName} / ${selectedApplication.llmModelDisplayName || selectedApplication.llmModelName}`
                  : '未配置大语言模型'}
              </span>
            </div>
          </div>
        </div>

        {(activeTab === 'orchestrate' || activeTab === 'conversation') && (
          <div className="flex items-center gap-3">
            {isDirty && (
              <Tag color="warning" className="animate-pulse m-0 font-medium">
                未保存更改
              </Tag>
            )}
            <Button 
              type="primary"
              loading={configSaving} 
              disabled={!canUpdate || streaming} 
              onClick={() => void handleSaveConfig()}
              style={{ minWidth: 100 }}
              className="flex items-center gap-1 shadow-sm"
            >
              <Save size={14} /> 保存配置
            </Button>
          </div>
        )}
      </div>

      {/* Tab Navigation Layout */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        {/* Left Side Tab Navigation Menu */}
        <Card variant="borderless" className="w-full lg:w-56 shrink-0 bg-white border border-slate-200/50 shadow-sm flex flex-col" styles={{ body: { padding: '16px 12px', height: '100%', display: 'flex', flexDirection: 'column' } }}>
          <div className="flex flex-row lg:flex-col gap-1.5 flex-1 w-full">
            {renderTabButton('orchestrate', <Sparkles size={16} />, '编排')}
            {renderTabButton('conversation', <MessageSquare size={16} />, '对话设置')}
            {renderTabButton('annotations', <BookOpen size={16} />, '标注', annotations.length)}
            {renderTabButton('logs', <FileQuestion size={16} />, '日志')}
            {renderTabButton('monitor', <BarChart2 size={16} />, '监测')}
          </div>
        </Card>

        {/* Right Side Content Pane */}
        <div className="flex-1 min-w-0 h-full flex flex-col">
          {activeTab === 'orchestrate' && renderOrchestrateTab()}
          {activeTab === 'conversation' && renderConversationSettingsTab()}
          {activeTab === 'annotations' && renderAnnotationsTab()}
          {activeTab === 'logs' && renderLogsTab()}
          {activeTab === 'monitor' && renderMonitorTab()}
        </div>
      </div>
    </div>
  );

  return (
    <ConfigProvider theme={{ token: { colorPrimary: "#0f766e", borderRadius: 12 } }}>
      <div className="relative min-h-full bg-slate-50/20 px-4 py-4 text-slate-900">
        {selectedApplicationId ? renderApplicationWorkspace() : renderApplicationList()}
        
        <Modal
          open={annotationDialogOpen}
          title={editingAnnotation ? '编辑标注' : '新建标注'}
          onCancel={() => closeAnnotationDialog()}
          footer={[
            <Button key="cancel" onClick={() => closeAnnotationDialog()}>取消</Button>,
            <Button key="save" type="primary" loading={annotationSaving} onClick={() => void saveAnnotation()}>保存</Button>
          ]}
          width={560}
        >
          <div className="py-2 flex flex-col gap-4">
            <p className="text-slate-500 text-xs mb-2">
              配置精确匹配的问题和标准回复，命中后会跳过模型推理直接返回。
            </p>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold text-slate-700">问题</span>
              <Input.TextArea
                rows={3}
                value={annotationQuestion}
                onChange={(event) => setAnnotationQuestion(event.target.value)}
                placeholder="例如：营业时间"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold text-slate-700">标准回复</span>
              <Input.TextArea
                rows={5}
                value={annotationAnswer}
                onChange={(event) => setAnnotationAnswer(event.target.value)}
                placeholder="输入命中后要直接返回的标准答案"
              />
            </div>
          </div>
        </Modal>

        {/* Create Dialog */}
        <Modal
          open={createOpen}
          title={selectedTemplate ? `克隆模板: ${selectedTemplate.name}` : '创建智能体'}
          onCancel={() => {
            setCreateOpen(false);
            setSelectedTemplate(null);
            setCreateName('');
            setCreateDescription('');
          }}
          footer={[
            <Button key="cancel" onClick={() => {
              setCreateOpen(false);
              setSelectedTemplate(null);
              setCreateName('');
              setCreateDescription('');
            }}>取消</Button>,
            <Button key="create" type="primary" loading={createSaving} onClick={() => void handleCreate()}>
              {selectedTemplate ? '一键创建' : '创建智能体'}
            </Button>
          ]}
          width={450}
        >
          <div className="py-2 flex flex-col gap-4">
            <p className="text-slate-500 text-xs mb-2">
              {selectedTemplate ? '修改克隆智能体的名称与描述，点击“一键创建”即可初始化。' : '给智能体设定一个名字和简短描述以开始配置。'}
            </p>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold text-slate-700">智能体名称</span>
              <Input
                placeholder="给您的智能体起个名字..."
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-semibold text-slate-700">应用描述</span>
              <Input.TextArea
                placeholder="简要描述该智能体的职责与范围..."
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>
        </Modal>

        {/* Exit Confirmation Dialog */}
        <Modal
          open={showExitConfirm}
          title="确认放弃修改？"
          onCancel={() => setShowExitConfirm(false)}
          footer={[
            <Button key="cancel" onClick={() => setShowExitConfirm(false)}>取消</Button>,
            <Button key="exit" type="primary" danger onClick={() => {
              setShowExitConfirm(false);
              navigateToApplicationList();
            }}>
              放弃修改
            </Button>
          ]}
          width={400}
        >
          <p className="text-slate-500 text-sm py-2">
            您对智能体配置进行了修改，尚未保存。确定要放弃修改并返回列表吗？
          </p>
        </Modal>
      </div>
    </ConfigProvider>
  );
};
