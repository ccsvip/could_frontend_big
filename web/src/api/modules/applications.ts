import { httpClient } from '../client';
import type { ChatConversationDetail } from './chat';

export type AgentReplyBlock =
  | { type: 'text'; text: string }
  | { type: 'image' | 'video'; resourceId: number; resourceName: string; url: string; missing?: boolean };

export type AgentApplicationKnowledgeDocument = {
  id: number;
  title: string;
  fileName: string;
  updated_at: string;
};

export type AgentApplicationKnowledgeBase = {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  updated_at: string;
};

export type AgentApplicationRecord = {
  id: number;
  name: string;
  description: string;
  runtimeBackendType: 'platform_llm' | 'third_party_chatbot';
  llmModelId: number | null;
  llmModelName: string;
  llmModelDisplayName: string;
  llmProviderName: string | null;
  thirdPartyChatbotId: number | null;
  thirdPartyChatbotName: string;
  thirdPartyChatbotProviderName: string | null;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  maxTokensUnlimited: boolean;
  openingMessageEnabled: boolean;
  openingMessage: string;
  suggestedQuestions: string[];
  voiceInputEnabled: boolean;
  replyPlaybackEnabled: boolean;
  ttsFilterPunctuation: string;
  ttsFilterEmoji: boolean;
  ttsFilterExcludePatterns: string[];
  knowledgeDocumentIds: number[];
  knowledgeDocuments: AgentApplicationKnowledgeDocument[];
  knowledgeBaseIds: number[];
  knowledgeBases: AgentApplicationKnowledgeBase[];
  createdBy: string;
  isActive: boolean;
  publishedAt: string | null;
  publishedVersion: number;
  hasPublishedConfig: boolean;
  isPublishedCurrent: boolean;
  created_at: string;
  updated_at: string;
};

export type AgentApplicationListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: AgentApplicationRecord[];
};

export type AgentApplicationListQuery = {
  page?: number;
  keyword?: string;
  tenant?: number;
};

export type AgentApplicationPayload = {
  name: string;
  description?: string;
  runtimeBackendType?: 'platform_llm' | 'third_party_chatbot';
  llmModelId?: number | null;
  thirdPartyChatbotId?: number | null;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  maxTokensUnlimited?: boolean;
  openingMessageEnabled?: boolean;
  openingMessage?: string;
  suggestedQuestions?: string[];
  voiceInputEnabled?: boolean;
  replyPlaybackEnabled?: boolean;
  ttsFilterPunctuation?: string;
  ttsFilterEmoji?: boolean;
  ttsFilterExcludePatterns?: string[];
  knowledgeDocumentIds?: number[];
  knowledgeBaseIds?: number[];
  isActive?: boolean;
};

const buildListParams = (query?: AgentApplicationListQuery) => ({
  page: query?.page,
  keyword: query?.keyword || undefined,
  tenant: query?.tenant,
});

export const fetchAgentApplications = async (query?: AgentApplicationListQuery) => {
  const response = await httpClient.get<AgentApplicationListResponse>('/ai-models/applications/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const fetchAgentApplication = async (id: number) => {
  const response = await httpClient.get<AgentApplicationRecord>(`/ai-models/applications/${id}/`);
  return response.data;
};

export const createAgentApplication = async (payload: AgentApplicationPayload) => {
  const response = await httpClient.post<AgentApplicationRecord>('/ai-models/applications/', payload);
  return response.data;
};

export const updateAgentApplication = async (id: number, payload: Partial<AgentApplicationPayload>) => {
  const response = await httpClient.patch<AgentApplicationRecord>(`/ai-models/applications/${id}/`, payload);
  return response.data;
};

export const publishAgentApplication = async (id: number) => {
  const response = await httpClient.post<AgentApplicationRecord>(`/ai-models/applications/${id}/publish/`);
  return response.data;
};

export const deleteAgentApplication = async (id: number) => {
  await httpClient.delete(`/ai-models/applications/${id}/`);
};

export const createAgentApplicationConversation = async (id: number) => {
  const response = await httpClient.post<ChatConversationDetail>(`/ai-models/applications/${id}/conversations/`);
  return response.data;
};

export type AgentApplicationStats = {
  conversationCount: number;
  messageCount: number;
  userMessageCount: number;
  assistantMessageCount: number;
  upCount: number;
  downCount: number;
  dailyTrends: { date: string; count: number }[];
  updatedAt: string;
};

export const fetchAgentApplicationStats = async (id: number) => {
  const response = await httpClient.get<AgentApplicationStats>(`/ai-models/applications/${id}/stats/`);
  return response.data;
};

export type AgentAnnotationRecord = {
  id: number;
  applicationId: number;
  question: string;
  answer: string;
  answerBlocks: AgentReplyBlock[];
  sourceMessageId: number | null;
  isActive: boolean;
  hitCount: number;
  lastHitAt: string | null;
  createdBy: string;
  created_at: string;
  updated_at: string;
};

export type AgentAnnotationPayload = {
  question: string;
  answer: string;
  answerBlocks?: AgentReplyBlock[];
  isActive?: boolean;
};

export type AgentAnnotationFromMessagePayload = {
  messageId: number;
  question: string;
  answer: string;
  answerBlocks?: AgentReplyBlock[];
};

export const fetchAgentAnnotations = async (applicationId: number, keyword?: string) => {
  const response = await httpClient.get<AgentAnnotationRecord[]>(
    `/ai-models/applications/${applicationId}/annotations/`,
    { params: { keyword: keyword || undefined } },
  );
  return response.data;
};

export const createAgentAnnotation = async (
  applicationId: number,
  payload: AgentAnnotationPayload,
) => {
  const response = await httpClient.post<AgentAnnotationRecord>(
    `/ai-models/applications/${applicationId}/annotations/`,
    payload,
  );
  return response.data;
};

export const createAgentAnnotationFromMessage = async (
  applicationId: number,
  payload: AgentAnnotationFromMessagePayload,
) => {
  const response = await httpClient.post<AgentAnnotationRecord>(
    `/ai-models/applications/${applicationId}/annotations/from-message/`,
    payload,
  );
  return response.data;
};

export const updateAgentAnnotation = async (
  applicationId: number,
  annotationId: number,
  payload: Partial<AgentAnnotationPayload>,
) => {
  const response = await httpClient.patch<AgentAnnotationRecord>(
    `/ai-models/applications/${applicationId}/annotations/${annotationId}/`,
    payload,
  );
  return response.data;
};

export const deleteAgentAnnotation = async (applicationId: number, annotationId: number) => {
  await httpClient.delete(`/ai-models/applications/${applicationId}/annotations/${annotationId}/`);
};
