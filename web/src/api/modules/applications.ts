import { httpClient } from '../client';
import type { ChatConversationDetail } from './chat';

export type AgentApplicationKnowledgeDocument = {
  id: number;
  title: string;
  fileName: string;
  processingStatus: string;
  updated_at: string;
};

export type AgentApplicationRecord = {
  id: number;
  name: string;
  description: string;
  llmModelId: number | null;
  llmModelName: string;
  llmModelDisplayName: string;
  llmProviderName: string | null;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  knowledgeDocumentIds: number[];
  knowledgeDocuments: AgentApplicationKnowledgeDocument[];
  createdBy: string;
  isActive: boolean;
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
};

export type AgentApplicationPayload = {
  name: string;
  description?: string;
  llmModelId?: number | null;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  knowledgeDocumentIds?: number[];
  isActive?: boolean;
};

const buildListParams = (query?: AgentApplicationListQuery) => ({
  page: query?.page,
  keyword: query?.keyword || undefined,
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

