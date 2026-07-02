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
  publishAgentApplication,
  updateAgentAnnotation,
  type AgentAnnotationRecord,
  type AgentReplyBlock,
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
import { fetchKnowledgeBases, type KnowledgeBaseRecord } from '../../api/modules/knowledge-base';
import {
  fetchCompanyLLMOptions,
  fetchCompanyThirdPartyChatbotOptions,
  type CompanyLLMOptions,
  type CompanyThirdPartyChatbotOptions,
} from '../../api/modules/llm-settings';
import { fetchAsrStatus, type AsrStatusRecord } from '../../api/modules/asr';
import { fetchCompanyTtsOptions, type CompanyTtsOptions } from '../../api/modules/tts';
import { fetchDeviceChatLogs, type DeviceChatLogRecord } from '../../api/modules/devices';
import { fetchImageResources, fetchVideoResources, type ResourceRecord, type ResourceType } from '../../api/modules/resources';
import { ChatMarkdown } from '../../components/chat-markdown';
import { normalizeMediaAssetUrl } from '../../api/client';
import { useAuthStore } from '../../store/auth';
import { useAgentAudio } from './use-agent-audio';
import dayjs from 'dayjs';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
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
  theme,
  Empty,
  Pagination,
  Popconfirm,
  Segmented
} from 'antd';

import {
  IconRobot,
  IconUser,
  IconPlus,
  IconTrash,
  IconDeviceFloppy,
  IconSearch,
  IconSend,
  IconArrowLeft,
  IconArrowRight,
  IconBook,
  IconBookmarkPlus,
  IconMessage,
  IconSparkles,
  IconChevronDown,
  IconChartBar,
  IconHelpCircle,
  IconRotate,
  IconMicrophone,
  IconMicrophoneOff,
  IconLoader2,
  IconPlayerPause,
  IconPlayerPlay,
  IconSquare,
  IconVolume2,
  IconGripVertical,
  IconChevronUp,
  IconHeadphones,
  IconLanguage,
  IconPencil,
  IconFileUnknown,
  IconBolt,
  IconCopy,
} from '@tabler/icons-react';

type RuntimeBackendType = 'platform_llm' | 'third_party_chatbot';

type LogConversationItem = {
  key: string;
  source: 'chat' | 'device';
  id: number;
  title: string;
  summary: string;
  lastMessage: string | null;
  messageCount: number;
  runtimeBackendType: RuntimeBackendType;
  llmModelName: string;
  llmModelDisplayName: string;
  llmProviderName: string | null;
  thirdPartyChatbotName: string;
  thirdPartyChatbotProviderName: string | null;
  created_at: string;
  updated_at: string;
  detail?: ChatConversationDetail;
};

type LogConversationCategory = 'chat' | 'device';

const PAGE_SIZE = 10;
const LOG_CONVERSATION_PAGE_SIZE = 100;
const DEFAULT_TEMPERATURE = 0.7;
const DEFAULT_MAX_TOKENS = 1000;
const DEFAULT_TTS_FILTER_PUNCTUATION = '。！？!?；;、';
const ANNOTATION_PUNCTUATION_PATTERN = /\p{P}/gu;
const ASR_BOUNDARY_PUNCTUATION_PATTERN = /^[\p{P}\s]+|[\p{P}\s]+$/gu;

const normalizeAnnotationQuestion = (value: string) => value.replace(ANNOTATION_PUNCTUATION_PATTERN, '').trim();
const normalizeAsrTranscript = (value: string) => value.replace(ASR_BOUNDARY_PUNCTUATION_PATTERN, '').trim();
const textBlock = (text: string): AgentReplyBlock => ({ type: 'text', text });
const blocksToText = (blocks: AgentReplyBlock[]) => blocks
  .filter((block): block is Extract<AgentReplyBlock, { type: 'text' }> => block.type === 'text')
  .map((block) => block.text.trim())
  .filter(Boolean)
  .join('\n');
type AgentMediaReplyBlock = Extract<AgentReplyBlock, { type: 'image' | 'video' }>;
const getEditorText = (blocks: AgentReplyBlock[]) => blocks.find((block): block is Extract<AgentReplyBlock, { type: 'text' }> => block.type === 'text')?.text || '';
const normalizeReplyBlocks = (blocks: AgentReplyBlock[] | undefined, fallbackText = '') => {
  const source = blocks && blocks.length > 0 ? blocks : [textBlock(fallbackText)];
  return source
    .map((block) => {
      if (block.type === 'text') {
        return textBlock(block.text || '');
      }
      return block;
    })
    .filter((block) => block.type !== 'text' || block.text.trim());
};
const normalizeAnnotationEditorBlocks = (blocks: AgentReplyBlock[] | undefined, fallbackText = '') => {
  const normalized = normalizeReplyBlocks(blocks, fallbackText);
  const text = blocksToText(normalized) || fallbackText.trim();
  const mediaBlocks = normalized.filter((block): block is AgentMediaReplyBlock => block.type !== 'text');
  return [textBlock(text), ...mediaBlocks];
};

const toDeviceChatConversationDetail = (logs: DeviceChatLogRecord[]): ChatConversationDetail => {
  const orderedLogs = [...logs].sort((a, b) => {
    const byTime = dayjs(a.createdAt).valueOf() - dayjs(b.createdAt).valueOf();
    return byTime || a.id - b.id;
  });
  const firstLog = orderedLogs[0];
  const lastLog = orderedLogs[orderedLogs.length - 1];
  const conversationId = firstLog.conversationId ? -firstLog.conversationId : -firstLog.id;
  const title = `${firstLog.deviceName || firstLog.code || '设备'} 设备运行时`;
  const messages = orderedLogs.flatMap<ChatMessage>((log) => [
    {
      id: log.id * 2,
      conversationId,
      role: 'user',
      content: log.questionText,
      contentBlocks: [textBlock(log.questionText)],
      feedback: 'none',
      created_at: log.createdAt,
    },
    {
      id: log.id * 2 + 1,
      conversationId,
      role: 'assistant',
      content: log.answerText,
      contentBlocks: [textBlock(log.answerText)],
      feedback: 'none',
      created_at: log.createdAt,
    },
  ]);

  return {
    id: conversationId,
    title,
    applicationId: firstLog.agentApplicationId,
    runtimeBackendType: 'platform_llm',
    llmModelId: null,
    llmModelName: lastLog.modelName,
    llmModelDisplayName: lastLog.modelName,
    llmProviderName: null,
    thirdPartyChatbotId: null,
    thirdPartyChatbotName: '',
    thirdPartyChatbotProviderName: null,
    summary: firstLog.questionText,
    systemPrompt: '',
    temperature: 0,
    maxTokens: 0,
    maxTokensUnlimited: false,
    messages,
    created_at: firstLog.createdAt,
    updated_at: lastLog.createdAt,
  };
};

const toDeviceChatLogItem = (logs: DeviceChatLogRecord[]): LogConversationItem => {
  const orderedLogs = [...logs].sort((a, b) => {
    const byTime = dayjs(a.createdAt).valueOf() - dayjs(b.createdAt).valueOf();
    return byTime || a.id - b.id;
  });
  const firstLog = orderedLogs[0];
  const lastLog = orderedLogs[orderedLogs.length - 1];
  const detail = toDeviceChatConversationDetail(orderedLogs);
  return {
    key: firstLog.conversationId ? `device-conversation-${firstLog.conversationId}` : `device-${firstLog.id}`,
    source: 'device',
    id: firstLog.conversationId ? -firstLog.conversationId : firstLog.id,
    title: detail.title,
    summary: firstLog.questionText,
    lastMessage: lastLog.answerText,
    messageCount: detail.messages.length,
    runtimeBackendType: 'platform_llm',
    llmModelName: lastLog.modelName,
    llmModelDisplayName: lastLog.modelName || '运行时设备',
    llmProviderName: null,
    thirdPartyChatbotName: '',
    thirdPartyChatbotProviderName: null,
    created_at: firstLog.createdAt,
    updated_at: lastLog.createdAt,
    detail,
  };
};

const toDeviceChatLogItems = (logs: DeviceChatLogRecord[]): LogConversationItem[] => {
  const groups = new Map<string, DeviceChatLogRecord[]>();
  for (const log of logs) {
    const key = log.conversationId ? `conversation-${log.conversationId}` : `log-${log.id}`;
    const group = groups.get(key) || [];
    group.push(log);
    groups.set(key, group);
  }
  return Array.from(groups.values()).map(toDeviceChatLogItem);
};

const toChatConversationItem = (conversation: ChatConversationRecord): LogConversationItem => ({
  ...conversation,
  key: `chat-${conversation.id}`,
  source: 'chat',
});

const getRuntimeBackendDisplay = (
  item: Pick<
    AgentApplicationRecord | ChatConversationRecord | LogConversationItem,
    'runtimeBackendType' | 'llmModelName' | 'llmModelDisplayName' | 'llmProviderName' | 'thirdPartyChatbotName' | 'thirdPartyChatbotProviderName'
  >,
) => {
  if (item.runtimeBackendType === 'third_party_chatbot') {
    const chatbotName = item.thirdPartyChatbotName || '未绑定第三方机器人';
    return item.thirdPartyChatbotProviderName ? `${item.thirdPartyChatbotProviderName} / ${chatbotName}` : chatbotName;
  }
  const modelName = item.llmModelDisplayName || item.llmModelName || '未配置大语言模型';
  return item.llmProviderName ? `${item.llmProviderName} / ${modelName}` : modelName;
};

const getLogConversationDetailId = (conversation: LogConversationItem) => (
  conversation.source === 'device' && conversation.id > 0 ? -conversation.id : conversation.id
);

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);



const fetchAllKnowledgeBases = async () => {
  const firstPage = await fetchKnowledgeBases({ page: 1 });
  const bases = [...firstPage.results];
  let page = 2;
  while (firstPage.next && bases.length < firstPage.count) {
    const nextPage = await fetchKnowledgeBases({ page });
    bases.push(...nextPage.results);
    if (!nextPage.next) break;
    page += 1;
  }
  return bases;
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
    gradient: 'from-emerald-500 to-brand-600',
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
    systemPrompt: 'You are an encouraging and friendly English Speaking Coach. Your goal is to help the User practice conversational English. Speak in clear, natural English, keep your sentences relatively short, and gently correct any major grammatical errors in the User\'s input with polite suggestions.',
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
      return <IconHeadphones size={24} />;
    case 'PenTool':
      return <IconPencil size={24} />;
    case 'BarChart2':
      return <IconChartBar size={24} />;
    case 'Languages':
      return <IconLanguage size={24} />;
    default:
      return <IconRobot size={24} />;
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
  const [publishSaving, setPublishSaving] = useState(false);
  const [llmOptions, setLlmOptions] = useState<CompanyLLMOptions | null>(null);
  const [thirdPartyChatbotOptions, setThirdPartyChatbotOptions] = useState<CompanyThirdPartyChatbotOptions | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseRecord[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);

  // Form states (direct React states instead of AntD forms)
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [runtimeBackendType, setRuntimeBackendType] = useState<RuntimeBackendType>('platform_llm');
  const [llmModelId, setLlmModelId] = useState<number | null>(null);
  const [thirdPartyChatbotId, setThirdPartyChatbotId] = useState<number | null>(null);
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
  const [ttsFilterPunctuation, setTtsFilterPunctuation] = useState(DEFAULT_TTS_FILTER_PUNCTUATION);
  const [ttsFilterEmoji, setTtsFilterEmoji] = useState(true);
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
  const [streamingBlocks, setStreamingBlocks] = useState<AgentReplyBlock[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // History & Log state (Logs Tab)
  const [logConversations, setLogConversations] = useState<LogConversationItem[]>([]);
  const [logConversationsLoading, setLogConversationsLoading] = useState(false);
  const [logConversationTotal, setLogConversationTotal] = useState(0);
  const [logConversationCategory, setLogConversationCategory] = useState<LogConversationCategory>('chat');
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
  const [annotationBlocks, setAnnotationBlocks] = useState<AgentReplyBlock[]>([textBlock('')]);
  const [annotationSaving, setAnnotationSaving] = useState(false);
  const [annotationsEnabled, setAnnotationsEnabled] = useState(true);
  const [resourcePickerOpen, setResourcePickerOpen] = useState(false);
  const [resourcePickerType, setResourcePickerType] = useState<ResourceType>('image');
  const [resourcePickerInsertIndex, setResourcePickerInsertIndex] = useState<number | null>(null);
  const [resourceOptions, setResourceOptions] = useState<ResourceRecord[]>([]);
  const [resourceOptionsLoading, setResourceOptionsLoading] = useState(false);

  // Monitor stats state (Monitor Tab)
  const [stats, setStats] = useState<AgentApplicationStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const selectedApplicationId = useMemo(() => {
    if (!applicationId) return null;
    const parsed = Number(applicationId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [applicationId]);

  const [showExitConfirm, setShowExitConfirm] = useState(false);

  useEffect(() => {
    if (!resourcePickerOpen) return;
    setResourceOptionsLoading(true);
    const loader = resourcePickerType === 'image' ? fetchImageResources : fetchVideoResources;
    loader({ pageSize: 100 })
      .then((response) => setResourceOptions(response.results))
      .catch(() => message.error('资源列表加载失败'))
      .finally(() => setResourceOptionsLoading(false));
  }, [resourcePickerOpen, resourcePickerType]);

  const applyApplicationState = useCallback((detail: AgentApplicationRecord) => {
    setSelectedApplication(detail);
    setName(detail.name);
    setDescription(detail.description || '');
    setRuntimeBackendType(detail.runtimeBackendType || 'platform_llm');
    setLlmModelId(detail.llmModelId);
    setThirdPartyChatbotId(detail.thirdPartyChatbotId);
    setSystemPrompt(detail.systemPrompt || '');
    setSelectedDocs(detail.knowledgeBaseIds || []);
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
    setTtsFilterPunctuation(detail.ttsFilterPunctuation || DEFAULT_TTS_FILTER_PUNCTUATION);
    setTtsFilterEmoji(detail.ttsFilterEmoji);
  }, []);

  const getApplicationSaveMismatch = (detail: AgentApplicationRecord, payload: AgentApplicationPayload) => {
    const stringValue = (value?: string) => value || '';
    const normalizedPunctuation = Array.from(new Set(stringValue(payload.ttsFilterPunctuation).trim())).join('');
    const hasTtsFilterPunctuation = Object.prototype.hasOwnProperty.call(detail, 'ttsFilterPunctuation');
    const hasTtsFilterEmoji = Object.prototype.hasOwnProperty.call(detail, 'ttsFilterEmoji');
    const payloadDocs = payload.knowledgeBaseIds || [];
    const detailDocs = detail.knowledgeBaseIds || [];
    const payloadQuestions = payload.suggestedQuestions || [];
    const detailQuestions = detail.suggestedQuestions || [];
    const hasSameDocs = payloadDocs.length === detailDocs.length && payloadDocs.every((id) => detailDocs.includes(id));
    const hasSameQuestions = (
      payloadQuestions.length === detailQuestions.length &&
      payloadQuestions.every((question, index) => question === detailQuestions[index])
    );

    if (detail.name !== payload.name) return '名称';
    if (stringValue(detail.description) !== stringValue(payload.description)) return '描述说明';
    if (payload.runtimeBackendType && detail.runtimeBackendType !== payload.runtimeBackendType) return '运行后端';
    if (payload.llmModelId != null && detail.llmModelId !== payload.llmModelId) return '选用模型';
    if (payload.thirdPartyChatbotId != null && detail.thirdPartyChatbotId !== payload.thirdPartyChatbotId) return '第三方机器人';
    if (stringValue(detail.systemPrompt) !== stringValue(payload.systemPrompt)) return '系统提示词';
    if (detail.temperature !== payload.temperature) return '随机性温度';
    if (detail.maxTokens !== payload.maxTokens) return '最大输出 Tokens';
    if (detail.maxTokensUnlimited !== payload.maxTokensUnlimited) return '不限制 Tokens';
    if (detail.isActive !== payload.isActive) return '启用状态';
    if (detail.openingMessageEnabled !== payload.openingMessageEnabled) return '开场白开关';
    if (stringValue(detail.openingMessage) !== stringValue(payload.openingMessage)) return '开场白';
    if (detail.voiceInputEnabled !== payload.voiceInputEnabled) return '语音输入';
    if (detail.replyPlaybackEnabled !== payload.replyPlaybackEnabled) return '回复播报';
    if (!hasTtsFilterPunctuation) return 'TTS 过滤规则字段';
    if (detail.ttsFilterPunctuation !== normalizedPunctuation) return 'TTS 过滤规则';
    if (!hasTtsFilterEmoji) return '过滤表情字段';
    if (detail.ttsFilterEmoji !== payload.ttsFilterEmoji) return '过滤表情';
    if (!hasSameQuestions) return '建议问题';
    if (!hasSameDocs) return '绑定知识库';
    return null;
  };

  const isDirty = useMemo(() => {
    if (!selectedApplication) return false;
    if (name.trim() !== selectedApplication.name) return true;
    if (description.trim() !== (selectedApplication.description || '')) return true;
    if (runtimeBackendType !== (selectedApplication.runtimeBackendType || 'platform_llm')) return true;
    if (llmModelId !== selectedApplication.llmModelId) return true;
    if (thirdPartyChatbotId !== selectedApplication.thirdPartyChatbotId) return true;
    if (systemPrompt !== (selectedApplication.systemPrompt || '')) return true;
    if (temperature !== selectedApplication.temperature) return true;
    if (maxTokens !== selectedApplication.maxTokens) return true;
    if (maxTokensUnlimited !== selectedApplication.maxTokensUnlimited) return true;
    if (isActive !== selectedApplication.isActive) return true;
    if (openingMessageEnabled !== selectedApplication.openingMessageEnabled) return true;
    if (openingMessage.trim() !== (selectedApplication.openingMessage || '')) return true;
    if (voiceInputEnabled !== selectedApplication.voiceInputEnabled) return true;
    if (replyPlaybackEnabled !== selectedApplication.replyPlaybackEnabled) return true;
    if (ttsFilterPunctuation !== selectedApplication.ttsFilterPunctuation) return true;
    if (ttsFilterEmoji !== selectedApplication.ttsFilterEmoji) return true;

    const previousQuestions = selectedApplication.suggestedQuestions || [];
    if (suggestedQuestions.length !== previousQuestions.length) return true;
    if (!previousQuestions.every((question, index) => question === suggestedQuestions[index])) return true;

    const prevDocs = selectedApplication.knowledgeBaseIds || [];
    if (selectedDocs.length !== prevDocs.length) return true;
    const currentDocsSet = new Set(selectedDocs);
    return !prevDocs.every((id) => currentDocsSet.has(id));
  }, [
    selectedApplication,
    name,
    description,
    runtimeBackendType,
    llmModelId,
    thirdPartyChatbotId,
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
    ttsFilterPunctuation,
    ttsFilterEmoji,
  ]);

  const getPublishStatus = (app: AgentApplicationRecord) => {
    if (!app.hasPublishedConfig) {
      return { color: 'default', text: '未发布' };
    }
    if (!app.isPublishedCurrent) {
      return { color: 'warning', text: '待发布' };
    }
    return { color: 'success', text: '已发布' };
  };

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
      const [llmResult, chatbotResult, documentsResult] = await Promise.allSettled([
        fetchCompanyLLMOptions(),
        fetchCompanyThirdPartyChatbotOptions(),
        fetchAllKnowledgeBases(),
      ]);
      if (llmResult.status === 'fulfilled') {
        setLlmOptions(llmResult.value);
      }
      if (chatbotResult.status === 'fulfilled') {
        setThirdPartyChatbotOptions(chatbotResult.value);
      }
      if (documentsResult.status === 'fulfilled') {
        setKnowledgeBases(documentsResult.value);
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
      applyApplicationState(detail);

      setConversation(null);
      setMessages([]);
      setStreamingContent('');
      setStreamingBlocks([]);
      setInputValue('');
    } catch {
      message.error('应用详情加载失败');
      navigate('..', { replace: true, relative: 'path' });
    } finally {
      setDetailLoading(false);
    }
  }, [applyApplicationState, navigate, selectedApplicationId]);

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
  const ttsPlaybackSessionConfig = ttsOptions?.ttsSessionConfig
    ? { ...ttsOptions.ttsSessionConfig, response_format: 'pcm' as const }
    : undefined;
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
  const thirdPartyChatbotSelectOptions = useMemo(
    () => [
      { label: '无第三方机器人', value: 'none' },
      ...((thirdPartyChatbotOptions?.chatbots || []).map((chatbot) => ({
        label: `${chatbot.providerName} / ${chatbot.name}`,
        value: String(chatbot.id),
      }))),
    ],
    [thirdPartyChatbotOptions],
  );
  const hasAvailableThirdPartyChatbots = thirdPartyChatbotSelectOptions.length > 1;
  const isOpeningPlaybackPending = agentAudio.pendingPlaybackKey === 'opening-message';
  const isOpeningPlaybackPlaying = agentAudio.playingKey === 'opening-message' && !agentAudio.paused;
  const isStreamingReplyPlaybackActive = (
    agentAudio.pendingPlaybackKey === 'streaming-reply' ||
    agentAudio.playingKey === 'streaming-reply'
  );

  // Reset states when switching applications
  useEffect(() => {
    setActiveTab('orchestrate');
    setSelectedLogConversation(null);
    setLogConversations([]);
    setLogConversationTotal(0);
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
      if (logConversationCategory === 'chat') {
        const chatData = await fetchConversations({
          application: selectedApplicationId,
          pageSize: LOG_CONVERSATION_PAGE_SIZE,
          excludeDeviceRuntime: true,
        });
        const items = chatData.results.map(toChatConversationItem);
        setLogConversations(items);
        setLogConversationTotal(chatData.count);
        if (items.length > 0 && !selectedLogConversation) {
          void loadSelectedLogConversation(items[0]);
        }
        return;
      }

      const deviceLogData = await fetchDeviceChatLogs({
        agentApplicationId: selectedApplicationId,
        pageSize: LOG_CONVERSATION_PAGE_SIZE,
      });
      const deviceLogItems = toDeviceChatLogItems(deviceLogData.results);
      const items = deviceLogItems.sort((a, b) => dayjs(b.updated_at).valueOf() - dayjs(a.updated_at).valueOf());
      setLogConversations(items);
      setLogConversationTotal(deviceLogItems.length);
      if (items.length > 0 && !selectedLogConversation) {
        void loadSelectedLogConversation(items[0]);
      }
    } catch {
      message.error('日志会话加载失败');
    } finally {
      setLogConversationsLoading(false);
    }
  }, [logConversationCategory, selectedApplicationId, selectedLogConversation]);

  const loadSelectedLogConversation = async (conversation: LogConversationItem) => {
    setSelectedLogConversationLoading(true);
    try {
      if (conversation.source === 'device' && conversation.detail) {
        setSelectedLogConversation(conversation.detail);
        return;
      }
      const detail = await fetchConversation(conversation.id);
      setSelectedLogConversation(detail);
    } catch {
      message.error('日志详情加载失败');
    } finally {
      setSelectedLogConversationLoading(false);
    }
  };

  const handleLogConversationCategoryChange = (value: LogConversationCategory) => {
    setLogConversationCategory(value);
    setLogConversations([]);
    setLogConversationTotal(0);
    setSelectedLogConversation(null);
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
    setAnnotationBlocks(normalizeAnnotationEditorBlocks(annotation?.answerBlocks, annotation?.answer || ''));
    setAnnotationDialogOpen(true);
  };

  const closeAnnotationDialog = () => {
    setAnnotationDialogOpen(false);
    setEditingAnnotation(null);
    setAnnotationQuestion('');
    setAnnotationBlocks([textBlock('')]);
  };

  const updateAnnotationText = (text: string) => {
    setAnnotationBlocks((current) => {
      const mediaBlocks = current.filter((block): block is AgentMediaReplyBlock => block.type !== 'text');
      return [textBlock(text), ...mediaBlocks];
    });
  };

  const removeAnnotationMediaBlock = (index: number) => {
    setAnnotationBlocks((current) => {
      const text = getEditorText(current);
      const mediaBlocks = current.filter((block): block is AgentMediaReplyBlock => block.type !== 'text');
      return [textBlock(text), ...mediaBlocks.filter((_, blockIndex) => blockIndex !== index)];
    });
  };

  const moveAnnotationMediaBlock = (index: number, direction: -1 | 1) => {
    setAnnotationBlocks((current) => {
      const text = getEditorText(current);
      const mediaBlocks = current.filter((block): block is AgentMediaReplyBlock => block.type !== 'text');
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= mediaBlocks.length) return current;
      const next = [...mediaBlocks];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return [textBlock(text), ...next];
    });
  };

  const openResourcePicker = (type: ResourceType, afterIndex: number | null = null) => {
    setResourcePickerType(type);
    setResourcePickerInsertIndex(afterIndex);
    setResourcePickerOpen(true);
  };

  const insertResourceBlock = (resource: ResourceRecord) => {
    const block: AgentReplyBlock = {
      type: resource.resourceType,
      resourceId: resource.id,
      resourceName: resource.name,
      url: resource.fileUrl || resource.cloudUrl,
    };
    setAnnotationBlocks((current) => {
      const text = getEditorText(current);
      const mediaBlocks = current.filter((item): item is AgentMediaReplyBlock => item.type !== 'text');
      const next = [...mediaBlocks];
      next.splice(resourcePickerInsertIndex == null ? next.length : resourcePickerInsertIndex + 1, 0, block);
      return [textBlock(text), ...next];
    });
    setResourcePickerOpen(false);
  };

  const saveAnnotation = async () => {
    if (!selectedApplicationId) return;
    const question = normalizeAnnotationQuestion(annotationQuestion);
    const answerBlocks = normalizeReplyBlocks(annotationBlocks);
    const answer = blocksToText(answerBlocks);
    if (!question || !answer) {
      message.warning('请填写问题和标准回复');
      return;
    }
    setAnnotationSaving(true);
    try {
      if (editingAnnotation) {
        await updateAgentAnnotation(selectedApplicationId, editingAnnotation.id, { question, answer, answerBlocks });
        message.success('标注已更新');
      } else {
        await createAgentAnnotation(selectedApplicationId, { question, answer, answerBlocks });
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
        question: normalizeAnnotationQuestion(previousUserMessage.content),
        answer: assistantMessage.content,
        answerBlocks: normalizeReplyBlocks(assistantMessage.contentBlocks, assistantMessage.content),
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
    if (runtimeBackendType === 'third_party_chatbot' && !thirdPartyChatbotId) {
      message.error('请选择第三方会话机器人');
      return;
    }
    setConfigSaving(true);
    try {
      const payload: AgentApplicationPayload = {
        name: name.trim(),
        description: description.trim(),
        runtimeBackendType,
        llmModelId: llmModelId,
        thirdPartyChatbotId,
        systemPrompt: systemPrompt,
        knowledgeBaseIds: selectedDocs,
        temperature: temperature,
        maxTokens: maxTokens,
        maxTokensUnlimited,
        isActive: isActive,
        openingMessageEnabled,
        openingMessage: openingMessage.trim(),
        suggestedQuestions: normalizedSuggestedQuestions,
        voiceInputEnabled,
        replyPlaybackEnabled,
        ttsFilterPunctuation,
        ttsFilterEmoji,
      };
      await updateAgentApplication(selectedApplication.id, payload);
      const updated = await fetchAgentApplication(selectedApplication.id);
      applyApplicationState(updated);
      const mismatch = getApplicationSaveMismatch(updated, payload);
      if (mismatch) {
        message.error(`${mismatch}保存未生效，请确认后端已更新并执行数据库迁移`);
        return;
      }
      if (conversation) {
        const nextConversation = await updateConversationConfig(conversation.id, {
          runtimeBackendType: updated.runtimeBackendType,
          llmModelId: updated.llmModelId,
          thirdPartyChatbotId: updated.thirdPartyChatbotId,
          systemPrompt: updated.systemPrompt,
          temperature: updated.temperature,
          maxTokens: updated.maxTokens,
          maxTokensUnlimited: updated.maxTokensUnlimited,
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
    runtimeBackendType,
    llmModelId,
    thirdPartyChatbotId,
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
    ttsFilterPunctuation,
    ttsFilterEmoji,
    conversation,
    loadApplications,
    applyApplicationState,
  ]);

  const handlePublish = useCallback(async () => {
    if (!selectedApplication || !canUpdate) return;
    if (isDirty) {
      message.warning('请先保存当前草稿，再发布到运行时');
      return;
    }
    setPublishSaving(true);
    try {
      const published = await publishAgentApplication(selectedApplication.id);
      applyApplicationState(published);
      message.success('智能体已发布，设备和 API 将使用最新发布版本');
      await loadApplications();
    } catch {
      message.error('发布失败');
    } finally {
      setPublishSaving(false);
    }
  }, [applyApplicationState, canUpdate, isDirty, loadApplications, selectedApplication]);

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

      // IconDeviceFloppy config: Ctrl + S (or Cmd + S)
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

  const startNewConversation = async () => {
    if (!selectedApplication || streaming || chatLoading) return null;
    abortRef.current?.abort();
    setConversation(null);
    setMessages([]);
    setStreamingContent('');
    setStreamingBlocks([]);
    setInputValue('');
    setChatLoading(true);
    try {
      const nextConversation = await createAgentApplicationConversation(selectedApplication.id);
      setConversation(nextConversation);
      setMessages(nextConversation.messages);
      message.success('已创建新对话');
      return nextConversation;
    } catch {
      message.error('新对话创建失败');
      return null;
    } finally {
      setChatLoading(false);
    }
  };

  const refreshConversation = async (conversationId: number) => {
    const nextConversation = await fetchConversation(conversationId);
    setConversation(nextConversation);
    setMessages(nextConversation.messages);
    setStreamingContent('');
    setStreamingBlocks([]);
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
      contentBlocks: [textBlock(content)],
      feedback: 'none',
      created_at: new Date().toISOString(),
    };
    setInputValue('');
    setMessages((current) => [...current, localUserMessage]);
    setStreaming(true);
    setStreamingContent('');
    setStreamingBlocks([]);
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
        agentAudio.finishStreamPlayback({
          punctuation: ttsFilterPunctuation,
          emoji: ttsFilterEmoji,
          sessionConfig: ttsPlaybackSessionConfig,
        });
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
          agentAudio.appendStreamPlaybackText(text, {
            punctuation: ttsFilterPunctuation,
            emoji: ttsFilterEmoji,
            sessionConfig: ttsPlaybackSessionConfig,
          });
        }
      },
      (blocks) => setStreamingBlocks(blocks),
      () => undefined,
      () => undefined,
      (error) => message.error(error),
      finish,
    );
    abortRef.current = controller;
  };

  const handleSend = async () => {
    const content = inputValue.trim();
    if (agentAudio.recording || agentAudio.transcribing) {
      agentAudio.stopRecording({ suppressDone: true, cancel: true });
    }
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
        contentBlocks: streamingBlocks.length ? streamingBlocks : [textBlock(streamingContent)],
        feedback: 'none' as const,
        created_at: new Date().toISOString(),
      },
    ];
  }, [conversation?.id, messages, streamingBlocks, streamingContent]);

  const applicationOverview = useMemo(() => {
    const activeCount = applications.filter((app) => app.isActive).length;
    const configuredModelCount = applications.filter((app) => app.llmModelId || app.thirdPartyChatbotId).length;
    const knowledgeReferenceCount = applications.reduce(
      (total, app) => total + (app.knowledgeBaseIds?.length || app.knowledgeBases?.length || 0),
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
            prefix={<IconSearch size={16} className="text-slate-400" />}
          />
          <Button type="primary" onClick={handleSearch} className="w-full sm:w-auto cursor-pointer flex items-center justify-center gap-1">
            <IconSearch size={14} />
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
              <IconPlus size={16} />
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
            <span className="text-xs text-slate-500 font-medium">后端绑定数</span>
            <span className="text-2xl font-bold font-mono leading-none text-brand-600">{applicationOverview.configuredModelCount}</span>
            <span className="text-xs text-slate-400 mt-1">已绑定标准模型或第三方机器人</span>
          </div>
        </Card>
        <Card variant="borderless" className="bg-white border border-slate-200/60 shadow-sm hover:shadow-md transition-all duration-300 rounded-2xl">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-medium">知识库引用数</span>
            <span className="text-2xl font-bold font-mono leading-none text-blue-600">{applicationOverview.knowledgeReferenceCount}</span>
            <span className="text-xs text-slate-400 mt-1">知识库关联引用次数</span>
          </div>
        </Card>
      </div>

      {/* Templates Section */}
      {!keyword && (
        <div className="bg-slate-50/50 border border-slate-200/40 rounded-2xl p-5 mt-1">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <IconSparkles size={20} className="text-brand-600" />
            <div className="text-base font-bold text-slate-800">选用推荐模板一键初始化</div>
            <Tag color="cyan">开箱即用</Tag>
          </div>
          <span className="text-xs text-slate-500 block mb-4">
            为您预置了企业常见业务场景的角色人设，包含完整的系统提示词和常用开场白设定。
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {/* Blank Custom Card */}
            <Card variant="borderless" className="flex flex-col justify-between border-2 border-dashed border-slate-200 hover:border-brand-400 hover:bg-brand-50/10 cursor-pointer transition-all duration-300 rounded-2xl group min-h-[220px]" onClick={() => {
                setSelectedTemplate(null);
                setCreateName('');
                setCreateDescription('');
                setCreateOpen(true);
              }}
            >
              <div className="flex flex-col justify-center items-center gap-3 py-6" style={{ height: '100%' }}>
                <div className="p-4 bg-slate-100 rounded-full text-slate-500 group-hover:bg-brand-50/80 group-hover:text-brand-600 transition-colors duration-300">
                  <IconPlus size={28} />
                </div>
                <div className="text-center">
                  <span className="text-base font-bold text-slate-700 group-hover:text-brand-700 transition-colors duration-300 block mb-1">
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
              <Card variant="borderless" key={tmpl.key} className="flex flex-col justify-between bg-white border border-slate-200/60 hover:border-brand-300 hover:shadow-md cursor-pointer transition-all duration-300 rounded-2xl relative overflow-hidden group min-h-[220px]" onClick={() => {
                  setSelectedTemplate(tmpl);
                  setCreateName(tmpl.name);
                  setCreateDescription(tmpl.description);
                  setCreateOpen(true);
                }}
              >
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-brand-400 to-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
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
                    <span className="text-base font-bold text-slate-800 group-hover:text-brand-700 transition-colors duration-300 block mb-1">
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
                      使用模板 <IconArrowRight size={10} />
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
          <IconRobot size={20} className="text-brand-600" />
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
                const isThirdPartyBackend = app.runtimeBackendType === 'third_party_chatbot';
                const backendName = isThirdPartyBackend
                  ? app.thirdPartyChatbotName
                  : (app.llmModelDisplayName || app.llmModelName);
                const knowledgeCount = app.knowledgeBaseIds?.length || app.knowledgeBases?.length || 0;
                const publishStatus = getPublishStatus(app);

                return (
                  <Card variant="borderless" key={app.id} className="flex flex-col justify-between bg-white border border-slate-200/60 hover:border-brand-200 hover:shadow-md transition-all duration-300 rounded-2xl relative overflow-hidden group min-h-[220px]">
                    <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-brand-500 to-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    
                    <div className="flex flex-col gap-3 p-1">
                      <div className="flex justify-between items-center">
                        <div className="p-2.5 bg-brand-50/80 rounded-xl text-brand-700">
                          <IconRobot size={20} />
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
                        <Tag color={isThirdPartyBackend ? 'purple' : 'cyan'} className="m-0">
                          {isThirdPartyBackend ? '第三方机器人' : '标准 LLM'}
                        </Tag>
                        {backendName ? (
                          <Tag color="cyan" className="max-w-full truncate m-0">
                            {backendName}
                          </Tag>
                        ) : (
                          <Tag color="warning" className="m-0">未绑定后端</Tag>
                        )}
                        <Tag color={knowledgeCount > 0 ? 'blue' : 'default'} className="m-0 flex items-center gap-1">
                          <IconBook size={10} className="shrink-0" />
                          {knowledgeCount} 库
                        </Tag>
                        <Tag color={publishStatus.color} className="m-0">
                          {publishStatus.text}
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
                              <IconTrash size={13} />
                            </Button>
                          </Popconfirm>
                        )}
                        <Button type="primary" size="small" onClick={() => navigate(`${app.id}`)} className="rounded-lg cursor-pointer flex items-center gap-0.5">
                          配置 <IconArrowRight size={12} />
                        </Button>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col justify-center items-center gap-3 bg-white rounded-2xl border border-slate-200/50 shadow-sm text-slate-400 py-12">
              <IconRobot size={40} className="text-slate-300" />
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

  const renderReplyBlocks = (blocks: AgentReplyBlock[] | undefined, fallback: string, className = 'chat-markdown') => {
    const normalized = normalizeReplyBlocks(blocks, fallback);
    return (
      <div className="flex flex-col gap-3">
        {normalized.map((block, index) => {
          if (block.type === 'text') {
            return <ChatMarkdown key={`text-${index}`} content={block.text} className={className} />;
          }
          if (block.missing || !block.url) {
            return <div key={`media-${index}`} className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-400">资源已缺失</div>;
          }
          const mediaUrl = normalizeMediaAssetUrl(block.url);
          if (block.type === 'image') {
            return <img key={`image-${block.resourceId}-${index}`} src={mediaUrl} alt={block.resourceName || '标注图片'} className="max-h-80 rounded-xl border border-slate-100 object-contain" />;
          }
          return (
            <video key={`video-${block.resourceId}-${index}`} src={mediaUrl} controls preload="metadata" className="max-h-80 rounded-xl border border-slate-100 bg-black" />
          );
        })}
      </div>
    );
  };

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
            icon={isUser ? <IconUser size={16} /> : <IconRobot size={16} />}
            className={isUser ? 'bg-indigo-600 shrink-0' : 'bg-brand-600 shrink-0'}
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
                renderReplyBlocks(msg.contentBlocks, msg.content)
              )}
              {msg.id === -1 && (
                <span className="ml-1 inline-block h-4 w-0.5 bg-brand-500 animate-pulse align-middle" />
              )}
            </div>
            {!isUser && msg.id !== -1 && (
              <div className="flex items-center gap-2 flex-wrap px-1">
                <Button 
                  type="text" 
                  size="small"
                  disabled={!ttsReady || isPlaybackPending} 
                  onClick={() => void agentAudio.playText(playbackKey, msg.content, {
                    punctuation: ttsFilterPunctuation,
                    emoji: ttsFilterEmoji,
                    sessionConfig: ttsPlaybackSessionConfig,
                  })}
                  className="flex items-center gap-1 text-slate-500 hover:text-brand-600 px-1.5"
                >
                  {isPlaybackPending ? <IconLoader2 size={12} className="animate-spin" /> : isPlaybackPlaying ? <IconPlayerPause size={12} /> : <IconPlayerPlay size={12} />}
                  <span className="text-xs">{isPlaybackPending ? '生成中' : isPlaybackPlaying ? '暂停' : '播放'}</span>
                </Button>
                {agentAudio.playingKey === playbackKey && (
                  <Button 
                    type="text" 
                    danger 
                    size="small"
                    onClick={agentAudio.stopPlayback}
                    className="flex items-center gap-1 px-1.5"
                  >
                    <IconSquare size={12} />
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
                  className="flex items-center gap-1 text-slate-500 hover:text-brand-600 px-1.5"
                >
                  <IconCopy size={12} />
                  <span className="text-xs">复制</span>
                </Button>
                <Button 
                  type="text" 
                  size="small"
                  disabled={!canUpdate} 
                  onClick={() => void createAnnotationFromAssistantMessage(msg)}
                  className="flex items-center gap-1 text-slate-500 hover:text-brand-600 px-1.5"
                >
                  <IconBookmarkPlus size={12} />
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

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-slate-700">运行后端</span>
                <Tooltip title="切换当前智能体实际使用标准 LLM 还是公司授权的第三方会话机器人。两个绑定都会保留，便于随时切换。">
                  <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
                </Tooltip>
              </div>
              <Segmented
                block
                disabled={!canUpdate}
                value={runtimeBackendType}
                onChange={(value) => setRuntimeBackendType(value as RuntimeBackendType)}
                options={[
                  { label: '标准 LLM', value: 'platform_llm' },
                  { label: '第三方机器人', value: 'third_party_chatbot' },
                ]}
              />
            </div>

            {runtimeBackendType === 'platform_llm' ? (
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold text-slate-700">标准 LLM 模型</span>
                  <Tooltip title="当前智能体会使用这里选择的标准 OpenAI 兼容模型。">
                    <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
                  </Tooltip>
                </div>
                <Select
                  disabled={!canUpdate || !hasAvailableLlmModels}
                  loading={optionsLoading}
                  options={llmModelOptions}
                  optionFilterProp="label"
                  placeholder="请选择标准模型"
                  showSearch
                  value={llmModelId ? String(llmModelId) : 'none'}
                  onChange={(val) => setLlmModelId(val === 'none' ? null : Number(val))}
                />
                {thirdPartyChatbotId ? (
                  <span className="text-xs text-slate-400">
                    已保留第三方机器人绑定，切换到第三方机器人后继续使用。
                  </span>
                ) : null}
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold text-slate-700">第三方会话机器人</span>
                  <Tooltip title="当前智能体会使用这里选择的第三方机器人；这里只显示超管授权给当前公司的机器人。">
                    <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
                  </Tooltip>
                </div>
                <Select
                  disabled={!canUpdate || !hasAvailableThirdPartyChatbots}
                  loading={optionsLoading}
                  options={thirdPartyChatbotSelectOptions}
                  optionFilterProp="label"
                  placeholder="请选择第三方机器人"
                  showSearch
                  value={thirdPartyChatbotId ? String(thirdPartyChatbotId) : 'none'}
                  onChange={(val) => setThirdPartyChatbotId(val === 'none' ? null : Number(val))}
                />
                {llmModelId ? (
                  <span className="text-xs text-slate-400">
                    已保留标准 LLM 模型绑定，切换回标准 LLM 后继续使用。
                  </span>
                ) : null}
              </div>
            )}

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-slate-700">系统提示词 (System Prompt)</span>
                <Tooltip title="设定智能体的角色人设、回复风格 and 行为约束，引导大模型产生符合预期的输出。">
                  <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
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
              <span className="text-sm font-bold text-slate-700">绑定知识库</span>
              <Popover
                placement="bottomLeft"
                trigger="click"
                styles={{ root: { width: 340 } }}
                content={
                  <div className="flex flex-col gap-2 max-h-[260px] overflow-y-auto pr-1 custom-scrollbar">
                    {knowledgeBases.length > 0 ? (
                      knowledgeBases.map((base) => {
                        const isChecked = selectedDocs.includes(base.id);
                        return (
                          <div className="text-sm flex items-start gap-2 hover:bg-slate-50 p-2 rounded-lg cursor-pointer" key={base.id}
                            onClick={() => {
                              if (isChecked) {
                                setSelectedDocs(selectedDocs.filter((id) => id !== base.id));
                              } else {
                                setSelectedDocs([...selectedDocs, base.id]);
                              }
                            }}
                          >
                            <Checkbox
                              checked={isChecked}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedDocs([...selectedDocs, base.id]);
                                } else {
                                  setSelectedDocs(selectedDocs.filter((id) => id !== base.id));
                                }
                              }}
                            />
                            <div className="flex flex-col">
                              <span className="text-sm font-semibold text-slate-800">{base.name}</span>
                              <span className="text-xs text-slate-400">{base.documentCount} 个文档</span>
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
                  <span className="text-sm text-slate-500">选择关联知识库 ({selectedDocs.length} 个已选)</span>
                  <IconChevronDown size={14} className="text-slate-400" />
                </Button>
              </Popover>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold text-slate-700">随机性温度 (Temperature)</span>
                  <Tooltip title="值越高回复越具创意 and 随机性；值越低回复越确定 and 保守。建议客服场景设为 0.2-0.5，创作场景设为 0.7-1.0。">
                    <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
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
                    <IconHelpCircle size={14} className="text-slate-400 cursor-help" />
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
              <IconSparkles size={16} className="text-brand-600" />
              <div className="text-lg font-bold">调试预览</div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="text"
                size="small"
                disabled={!selectedApplication || streaming || chatLoading}
                loading={chatLoading}
                onClick={() => void startNewConversation()}
                className="flex items-center gap-1 text-slate-500 hover:text-brand-600"
              >
                <IconRotate size={14} />
                <span className="text-xs">新对话</span>
              </Button>
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
                <IconMessage size={36} className="text-slate-300" />
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
                        className="rounded-full flex items-center gap-1 text-xs text-slate-600 hover:text-brand-600 hover:border-brand-500"
                      >
                        <IconHelpCircle size={12} /> {question}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="flex items-end gap-2 mt-3 pt-2 shrink-0">
            {voiceInputEnabled && (
              <Button 
                type="default" 
                disabled={!asrReady || agentAudio.transcribing} 
                onClick={() => {
                  if (agentAudio.recording) {
                    agentAudio.stopRecording();
                    return;
                  }
                  if (streaming) {
                    handleStopStreaming();
                  } else {
                    agentAudio.stopPlayback();
                  }
                  void agentAudio.startRecording(
                    (text) => setInputValue(normalizeAsrTranscript(text)),
                    {
                      onDone: (text) => {
                        const normalizedText = normalizeAsrTranscript(text);
                        setInputValue(normalizedText);
                        void sendChatContent(normalizedText);
                      },
                    },
                  );
                }}
                className={`flex items-center justify-center ${agentAudio.recording ? 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100' : ''}`}
              >
                {agentAudio.recording ? <IconMicrophoneOff size={16} /> : <IconMicrophone size={16} />}
              </Button>
            )}
            <Input.TextArea
              value={inputValue}
              placeholder="发送调试消息..."
              disabled={!canChat || streaming || !selectedApplication}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              autoSize={{ minRows: 1, maxRows: 8 }}
              style={{ flex: 1 }}
            />
            {isStreamingReplyPlaybackActive && (
              <Button danger onClick={agentAudio.interruptStreamPlayback} className="flex items-center gap-1">
                <IconSquare size={14} /> 打断播报
              </Button>
            )}
            {streaming ? (
              <Button type="primary" danger onClick={handleStopStreaming} className="flex items-center gap-1">
                <IconSquare size={14} /> 停止
              </Button>
            ) : (
              <Button type="primary" disabled={!inputValue.trim() || !canChat || !selectedApplication} onClick={() => void handleSend()} className="flex items-center justify-center">
                <IconSend size={16} />
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
                        <IconGripVertical size={14} className="text-slate-400 shrink-0 cursor-grab" />
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
                          <IconChevronUp size={12} />
                        </Button>
                        <Button 
                          type="default" 
                          size="small"
                          disabled={index === suggestedQuestions.length - 1 || !canUpdate} 
                          onClick={() => moveSuggestedQuestion(index, 1)}
                          style={{ padding: '4px 8px' }}
                        >
                          <IconChevronDown size={12} />
                        </Button>
                        <Button 
                          type="primary" 
                          danger 
                          size="small"
                          disabled={!canUpdate} 
                          onClick={() => removeSuggestedQuestion(index)}
                          style={{ padding: '4px 8px' }}
                        >
                          <IconTrash size={12} />
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
                    <IconPlus size={14} /> 添加
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
                <div className="grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-[minmax(0,1fr)_140px]">
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-bold text-slate-700">过滤规则</span>
                    <Input
                      value={ttsFilterPunctuation}
                      disabled={!canUpdate}
                      maxLength={64}
                      onChange={(event) => setTtsFilterPunctuation(event.target.value)}
                      placeholder={DEFAULT_TTS_FILTER_PUNCTUATION}
                      className="font-mono"
                    />
                    <span className="text-xs text-slate-400">播报前过滤这些字符，默认包含中文/英文句末标点与顿号</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2 md:self-end">
                    <span className="text-sm font-medium text-slate-700">过滤表情</span>
                    <Switch checked={ttsFilterEmoji} disabled={!canUpdate} onChange={setTtsFilterEmoji} />
                  </div>
                </div>
              </div>
            </Card>
          </div>

          <Button type="primary" size="large" disabled={!canUpdate || streaming} loading={configSaving} onClick={() => void handleSaveConfig()} className="shrink-0 w-full flex items-center justify-center gap-1.5">
            <IconDeviceFloppy size={16} /> 保存对话设置
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
              icon={<IconRobot size={32} />} 
              className="bg-brand-50 text-brand-700 shadow-sm"
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
                    onClick={() => void agentAudio.playText('opening-message', openingMessage, {
                      punctuation: ttsFilterPunctuation,
                      emoji: ttsFilterEmoji,
                      sessionConfig: ttsPlaybackSessionConfig,
                    })}
                    className="flex items-center gap-1 rounded-full px-3"
                  >
                    {isOpeningPlaybackPending ? <IconLoader2 size={12} className="animate-spin" /> : isOpeningPlaybackPlaying ? <IconPlayerPause size={12} /> : <IconVolume2 size={12} />}
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
                      <IconSquare size={12} />
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
                    className="rounded-full flex items-center gap-1 text-xs text-slate-600 hover:text-brand-600 hover:border-brand-500"
                  >
                    <IconHelpCircle size={12} /> {question}
                  </Button>
                ))}
              </div>
            ) : (
              <span className="text-xs text-slate-400">暂无推荐的建议问题</span>
            )}
          </div>

          <div className="flex items-end gap-2 mt-3 pt-2 shrink-0">
            {voiceInputEnabled && (
              <Button 
                type="default" 
                disabled={!asrReady || agentAudio.transcribing} 
                onClick={() => {
                  if (agentAudio.recording) {
                    agentAudio.stopRecording();
                    return;
                  }
                  if (streaming) {
                    handleStopStreaming();
                  } else {
                    agentAudio.stopPlayback();
                  }
                  void agentAudio.startRecording(
                    (text) => setInputValue(normalizeAsrTranscript(text)),
                    {
                      onDone: (text) => {
                        const normalizedText = normalizeAsrTranscript(text);
                        setInputValue(normalizedText);
                        void sendChatContent(normalizedText);
                      },
                    },
                  );
                }}
                className={`flex items-center justify-center ${agentAudio.recording ? 'bg-red-50 text-red-500 border-red-200 hover:bg-red-100' : ''}`}
              >
                {agentAudio.recording ? <IconMicrophoneOff size={16} /> : <IconMicrophone size={16} />}
              </Button>
            )}
            <Input.TextArea
              value={inputValue}
              placeholder="预览文本发送消息..."
              disabled={!canChat || streaming || !selectedApplication}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              autoSize={{ minRows: 1, maxRows: 8 }}
              style={{ flex: 1 }}
            />
            {isStreamingReplyPlaybackActive && (
              <Button danger onClick={agentAudio.interruptStreamPlayback} className="flex items-center gap-1">
                <IconSquare size={14} /> 打断播报
              </Button>
            )}
            <Button type="primary" disabled={!inputValue.trim() || !canChat || streaming} onClick={() => void handleSend()} className="flex items-center justify-center">
              <IconSend size={16} />
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
                <IconBook size={22} />
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

        {/* IconSearch & Create Actions */}
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
            prefix={<IconSearch size={16} className="text-slate-400" />}
          />
          
          <Button type="default" onClick={() => setAnnotationKeyword(annotationSearchValue.trim())} className="flex items-center gap-1 justify-center">
            <IconSearch size={14} /> 搜索
          </Button>
          <Button type="primary" disabled={!canUpdate} onClick={() => openAnnotationDialog()} className="flex items-center gap-1 justify-center shadow-sm">
            <IconPlus size={16} /> 新增标注
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
                      <Button type="text" size="small" disabled={!canUpdate} onClick={() => openAnnotationDialog(annotation)} className="text-slate-500 hover:text-brand-600">
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
                      {renderReplyBlocks(annotation.answerBlocks, annotation.answer, 'chat-markdown text-sm leading-relaxed text-slate-700')}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                    <span className="flex items-center gap-1 text-slate-500">
                      <IconBolt size={13} className="text-amber-500" /> 累计命中 <span className="font-semibold text-slate-700">{annotation.hitCount}</span> 次
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
    <Spin spinning={logConversationsLoading} className="h-full min-h-0" wrapperClassName="h-full-spin min-h-0">
      <div className="grid grid-cols-1 grid-rows-[minmax(0,_1fr)_minmax(0,_1fr)] xl:grid-cols-[380px_minmax(0,_1fr)] xl:grid-rows-1 gap-4 h-full min-h-0 overflow-hidden">
        {/* Conversation List */}
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm h-full min-h-0 overflow-hidden" styles={{ body: { padding: '16px', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}>
          <div className="flex flex-col gap-3 border-b border-slate-100 pb-3 mb-3 shrink-0">
            <div className="flex justify-between items-center">
              <div className="text-base font-bold text-slate-800">历史会话记录</div>
              <Tag color="default">{logConversationTotal || logConversations.length} 会话</Tag>
            </div>
            <Segmented<LogConversationCategory>
              block
              size="small"
              value={logConversationCategory}
              options={[
                { label: '网页调试', value: 'chat' },
                { label: '设备运行时', value: 'device' },
              ]}
              onChange={handleLogConversationCategoryChange}
            />
          </div>

          <div className="flex-1 overflow-y-auto overscroll-contain pr-1 flex flex-col gap-1.5 custom-scrollbar min-h-0">
            {logConversations.length > 0 ? (
              logConversations.map((conv) => (
                <div
                  key={conv.key}
                  onClick={() => void loadSelectedLogConversation(conv)}
                  className={`py-3 px-3 cursor-pointer rounded-xl transition-all duration-200 border ${
                    selectedLogConversation?.id === getLogConversationDetailId(conv)
                      ? 'bg-brand-50/50 border-brand-200 shadow-sm'
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
                    <Tag
                      color={conv.runtimeBackendType === 'third_party_chatbot' ? 'purple' : 'cyan'}
                      className="m-0 scale-90 origin-left"
                    >
                      {getRuntimeBackendDisplay(conv)}
                    </Tag>
                    {conv.source === 'device' && (
                      <Tag color="gold" className="m-0 scale-90 origin-left">设备运行时</Tag>
                    )}
                    <span className="flex items-center gap-1 text-slate-400">
                      <IconMessage size={11} /> {conv.messageCount} 消息
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
        <Card variant="borderless" className="flex flex-col bg-white border border-slate-200/50 shadow-sm overflow-hidden h-full min-h-0" styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, padding: '20px' } }}>
          {selectedLogConversation ? (
            <Spin spinning={selectedLogConversationLoading} className="flex-1 flex flex-col h-full min-h-0" wrapperClassName="h-full-spin flex-1 min-h-0">
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
                              icon={isUser ? <IconUser size={14} /> : <IconRobot size={14} />}
                              className={isUser ? 'bg-indigo-600 shrink-0' : 'bg-brand-600 shrink-0'}
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
                                ) : renderReplyBlocks(msg.contentBlocks, msg.content)}
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
                                    className="flex items-center gap-1 text-slate-400 hover:text-brand-600 p-0 h-auto"
                                    style={{ fontSize: 10 }}
                                  >
                                    <IconCopy size={10} />
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
              <IconMessage size={40} className="text-slate-300" />
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
            <span className={`mr-2.5 flex items-center transition-transform duration-200 ${isActive ? 'scale-110 text-white' : 'text-slate-400 group-hover:text-brand-700'}`}>
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
            <IconArrowLeft size={16} />
          </Button>
          <div className="flex flex-col" style={{ minWidth: 0 }}>
            <div className="text-lg font-bold text-slate-800 truncate leading-tight">{selectedApplication?.name || '智能体'}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
              <span className="text-xs text-slate-500 truncate">
                {selectedApplication ? getRuntimeBackendDisplay(selectedApplication) : '未配置运行后端'}
              </span>
              {selectedApplication && (
                <Tag color={getPublishStatus(selectedApplication).color} className="m-0">
                  {getPublishStatus(selectedApplication).text}
                </Tag>
              )}
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
              type="default"
              loading={publishSaving}
              disabled={!canUpdate || streaming || isDirty || !selectedApplication}
              onClick={() => void handlePublish()}
              style={{ minWidth: 96 }}
              className="flex items-center gap-1"
            >
              <IconBolt size={14} /> 发布
            </Button>
            <Button 
              type="primary"
              loading={configSaving} 
              disabled={!canUpdate || streaming} 
              onClick={() => void handleSaveConfig()}
              style={{ minWidth: 100 }}
              className="flex items-center gap-1 shadow-sm"
            >
              <IconDeviceFloppy size={14} /> 保存配置
            </Button>
          </div>
        )}
      </div>

      {/* Tab Navigation Layout */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        {/* Left Side Tab Navigation Menu */}
        <Card variant="borderless" className="w-full lg:w-56 shrink-0 bg-white border border-slate-200/50 shadow-sm flex flex-col" styles={{ body: { padding: '16px 12px', height: '100%', display: 'flex', flexDirection: 'column' } }}>
          <div className="flex flex-row lg:flex-col gap-1.5 flex-1 w-full">
            {renderTabButton('orchestrate', <IconSparkles size={16} />, '编排')}
            {renderTabButton('conversation', <IconMessage size={16} />, '对话设置')}
            {renderTabButton('annotations', <IconBook size={16} />, '标注', annotations.length)}
            {renderTabButton('logs', <IconFileUnknown size={16} />, '日志')}
            {renderTabButton('monitor', <IconChartBar size={16} />, '监测')}
          </div>
        </Card>

        {/* Right Side Content Pane */}
        <div className="flex-1 min-w-0 min-h-0 h-full flex flex-col">
          {activeTab === 'orchestrate' && renderOrchestrateTab()}
          {activeTab === 'conversation' && renderConversationSettingsTab()}
          {activeTab === 'annotations' && renderAnnotationsTab()}
          {activeTab === 'logs' && renderLogsTab()}
          {activeTab === 'monitor' && renderMonitorTab()}
        </div>
      </div>
    </div>
  );

  const renderAnnotationBlockEditor = () => {
    const text = getEditorText(annotationBlocks);
    const mediaBlocks = annotationBlocks.filter((block): block is AgentMediaReplyBlock => block.type !== 'text');
    return (
      <div className="flex flex-col gap-3">
        <Input.TextArea
          rows={5}
          value={text}
          onChange={(event) => updateAnnotationText(event.target.value)}
          placeholder="输入命中后要直接返回的标准答案"
        />
        {mediaBlocks.map((block, index) => (
          <div key={`${block.type}-${block.resourceId}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <Tag color={block.type === 'image' ? 'green' : 'purple'} className="m-0">
                {block.type === 'image' ? '图片' : '视频'}
              </Tag>
              <div className="flex items-center gap-1">
                <Button size="small" type="text" disabled={index === 0} onClick={() => moveAnnotationMediaBlock(index, -1)}>上移</Button>
                <Button size="small" type="text" disabled={index === mediaBlocks.length - 1} onClick={() => moveAnnotationMediaBlock(index, 1)}>下移</Button>
                <Button size="small" type="text" danger onClick={() => removeAnnotationMediaBlock(index)}>删除</Button>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <div className="text-sm font-medium text-slate-700">{block.resourceName || `资源 #${block.resourceId}`}</div>
              {block.type === 'image' && block.url && <img src={normalizeMediaAssetUrl(block.url)} alt={block.resourceName || '标注图片'} className="max-h-40 rounded-lg border border-slate-200 object-contain" />}
              {block.type === 'video' && block.url && <video src={normalizeMediaAssetUrl(block.url)} controls preload="metadata" className="max-h-40 rounded-lg border border-slate-200 bg-black" />}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-200/70 pt-3">
              <Button size="small" onClick={() => openResourcePicker('image', index)}>在后面插入图片</Button>
              <Button size="small" onClick={() => openResourcePicker('video', index)}>在后面插入视频</Button>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => openResourcePicker('image')}>插入图片</Button>
          <Button onClick={() => openResourcePicker('video')}>插入视频</Button>
        </div>
      </div>
    );
  };

  return (
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
          width={760}
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
              {renderAnnotationBlockEditor()}
            </div>
          </div>
        </Modal>

        <Modal
          open={resourcePickerOpen}
          title={resourcePickerType === 'image' ? '选择图片' : '选择视频'}
          onCancel={() => setResourcePickerOpen(false)}
          footer={null}
          width={720}
        >
          <Spin spinning={resourceOptionsLoading}>
            <div className="grid max-h-[520px] grid-cols-1 gap-3 overflow-y-auto py-2 sm:grid-cols-2">
              {resourceOptions.map((resource) => (
                <button
                  key={resource.id}
                  type="button"
                  onClick={() => insertResourceBlock(resource)}
                  className="flex cursor-pointer flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:border-brand-300 hover:bg-brand-50/40"
                >
                  <div className="text-sm font-semibold text-slate-800">{resource.name}</div>
                  {resource.resourceType === 'image' ? (
                    <img src={normalizeMediaAssetUrl(resource.fileUrl || resource.cloudUrl)} alt={resource.name} className="h-32 w-full rounded-lg bg-slate-100 object-contain" />
                  ) : (
                    <video src={normalizeMediaAssetUrl(resource.fileUrl || resource.cloudUrl)} preload="metadata" className="h-32 w-full rounded-lg bg-black object-contain" />
                  )}
                  <div className="truncate text-xs text-slate-400">{resource.fileName || resource.cloudUrl || resource.objectKey}</div>
                </button>
              ))}
              {!resourceOptionsLoading && resourceOptions.length === 0 && (
                <div className="col-span-full py-10">
                  <Empty description={resourcePickerType === 'image' ? '暂无可选图片' : '暂无可选视频'} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </div>
              )}
            </div>
          </Spin>
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
  );
};
