import { httpClient } from '../client';

export type LLMModelItem = {
  name: string;
  isDefault: boolean;
};

export type LLMProviderRecord = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  apiBaseUrl: string;
  apiKey: string;
  avatarUrl: string | null;
  modelsConfig: LLMModelItem[];
  isActive: boolean;
  created_at: string;
  updated_at: string;
};

export type LLMProviderListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: LLMProviderRecord[];
};

export type LLMProviderListQuery = {
  page?: number;
  keyword?: string;
  providerType?: string;
  isActive?: 'all' | 'active' | 'inactive';
};

export type LLMProviderPayload = {
  name: string;
  providerType: string;
  apiBaseUrl: string;
  apiKey?: string;
  avatar?: File;
  clearAvatar?: boolean;
  modelsConfig: LLMModelItem[];
  isActive: boolean;
};

export type TestConnectionResult = {
  success: boolean;
  message: string;
  latencyMs: number;
};

const buildListParams = (query?: LLMProviderListQuery) => ({
  page: query?.page,
  keyword: query?.keyword || undefined,
  provider_type: query?.providerType || undefined,
  is_active:
    query?.isActive === 'active'
      ? 'true'
      : query?.isActive === 'inactive'
        ? 'false'
        : undefined,
});

const buildFormData = (payload: LLMProviderPayload) => {
  const formData = new FormData();
  formData.append('name', payload.name);
  formData.append('providerType', payload.providerType);
  formData.append('apiBaseUrl', payload.apiBaseUrl);
  if (payload.apiKey) formData.append('apiKey', payload.apiKey);
  if (payload.avatar) formData.append('avatar', payload.avatar);
  if (payload.clearAvatar) formData.append('clearAvatar', 'true');
  formData.append('modelsConfig', JSON.stringify(payload.modelsConfig));
  formData.append('isActive', String(payload.isActive));
  return formData;
};

export const fetchLLMProviders = async (query?: LLMProviderListQuery) => {
  const response = await httpClient.get<LLMProviderListResponse>('/ai-models/llm-providers/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const createLLMProvider = async (payload: LLMProviderPayload) => {
  const response = await httpClient.post<LLMProviderRecord>('/ai-models/llm-providers/', buildFormData(payload));
  return response.data;
};

export const updateLLMProvider = async (id: number, payload: Partial<LLMProviderPayload>) => {
  const formData = new FormData();
  if (payload.name !== undefined) formData.append('name', payload.name);
  if (payload.providerType !== undefined) formData.append('providerType', payload.providerType);
  if (payload.apiBaseUrl !== undefined) formData.append('apiBaseUrl', payload.apiBaseUrl);
  if (payload.apiKey) formData.append('apiKey', payload.apiKey);
  if (payload.avatar) formData.append('avatar', payload.avatar);
  if (payload.clearAvatar) formData.append('clearAvatar', 'true');
  if (payload.modelsConfig !== undefined) formData.append('modelsConfig', JSON.stringify(payload.modelsConfig));
  if (payload.isActive !== undefined) formData.append('isActive', String(payload.isActive));
  const response = await httpClient.patch<LLMProviderRecord>(`/ai-models/llm-providers/${id}/`, formData);
  return response.data;
};

export const deleteLLMProvider = async (id: number) => {
  await httpClient.delete(`/ai-models/llm-providers/${id}/`);
};

export const testLLMConnection = async (id: number) => {
  const response = await httpClient.post<TestConnectionResult>(`/ai-models/llm-providers/${id}/test-connection/`);
  return response.data;
};
