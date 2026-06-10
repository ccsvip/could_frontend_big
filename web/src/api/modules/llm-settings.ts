import { httpClient } from '../client';
import type { TestConnectionResult } from './llm-providers';

export type LLMModelOption = {
  id: number;
  name: string;
  displayName: string;
  isDefault: boolean;
};

export type LLMProviderOption = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  avatarUrl: string | null;
  models: LLMModelOption[];
};

export type LLMTestSettings = {
  testPrompt: string;
  testCooldownSeconds: number;
  testTimeoutSeconds: number;
  testMaxTokens: number;
};

export type CompanyLLMOptions = {
  defaultModelId: number | null;
  testSettings: LLMTestSettings;
  providers: LLMProviderOption[];
};

export type PlatformLLMProviderRecord = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  apiBaseUrl: string;
  apiKeyMasked: string;
  apiKeyConfigured: boolean;
  avatarUrl: string | null;
  clearAvatar: boolean;
  isActive: boolean;
  sortOrder: number;
  created_at: string;
  updated_at: string;
};

export type PlatformLLMProviderListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PlatformLLMProviderRecord[];
};

export type PlatformLLMProviderPayload = {
  name: string;
  providerType?: string;
  apiBaseUrl: string;
  apiKey?: string;
  avatar?: File;
  clearAvatar?: boolean;
  isActive?: boolean;
  sortOrder?: number;
};

export type PlatformLLMModelRecord = {
  id: number;
  providerId: number;
  providerName: string;
  name: string;
  displayName: string;
  isActive: boolean;
  sortOrder: number;
  created_at: string;
  updated_at: string;
};

export type PlatformLLMModelListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PlatformLLMModelRecord[];
};

export type PlatformLLMModelPayload = {
  providerId?: number;
  name: string;
  displayName?: string;
  isActive?: boolean;
  sortOrder?: number;
};

export type TenantLLMAuthorizationModel = {
  id: number;
  providerId: number;
  name: string;
  displayName: string;
  isActive: boolean;
  sortOrder: number;
  grantIsActive: boolean;
};

export type TenantLLMAuthorizationProvider = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  isActive: boolean;
  sortOrder: number;
  models: TenantLLMAuthorizationModel[];
};

export type TenantLLMAuthorization = {
  tenant: {
    id: number;
    name: string;
    isActive: boolean;
  };
  providers: TenantLLMAuthorizationProvider[];
  defaultModelId: number | null;
};

export type TenantLLMAuthorizationPayload = {
  modelGrants: Array<{
    modelId: number;
    isActive: boolean;
  }>;
  defaultModelId: number | null;
};

const buildProviderFormData = (payload: Partial<PlatformLLMProviderPayload>) => {
  const formData = new FormData();
  if (payload.name !== undefined) formData.append('name', payload.name);
  if (payload.providerType !== undefined) formData.append('providerType', payload.providerType);
  if (payload.apiBaseUrl !== undefined) formData.append('apiBaseUrl', payload.apiBaseUrl);
  if (payload.apiKey !== undefined) formData.append('apiKey', payload.apiKey);
  if (payload.avatar) formData.append('avatar', payload.avatar);
  if (payload.clearAvatar) formData.append('clearAvatar', 'true');
  if (payload.isActive !== undefined) formData.append('isActive', String(payload.isActive));
  if (payload.sortOrder !== undefined) formData.append('sortOrder', String(payload.sortOrder));
  return formData;
};

export const fetchCompanyLLMOptions = async () => {
  const response = await httpClient.get<CompanyLLMOptions>('/ai-models/llm/options/');
  return response.data;
};

export const updateCompanyDefaultLLMModel = async (modelId: number) => {
  const response = await httpClient.patch<CompanyLLMOptions>('/ai-models/llm/default-model/', { modelId });
  return response.data;
};

export const testCompanyLLMModel = async (modelId: number) => {
  const response = await httpClient.post<TestConnectionResult>(`/ai-models/llm/models/${modelId}/test/`);
  return response.data;
};

export const fetchPlatformLLMProviders = async () => {
  const response = await httpClient.get<PlatformLLMProviderListResponse>('/settings/llm/providers/');
  return response.data;
};

export const createPlatformLLMProvider = async (payload: PlatformLLMProviderPayload) => {
  const response = await httpClient.post<PlatformLLMProviderRecord>(
    '/settings/llm/providers/',
    buildProviderFormData(payload),
  );
  return response.data;
};

export const updatePlatformLLMProvider = async (id: number, payload: Partial<PlatformLLMProviderPayload>) => {
  const response = await httpClient.patch<PlatformLLMProviderRecord>(
    `/settings/llm/providers/${id}/`,
    buildProviderFormData(payload),
  );
  return response.data;
};

export const deletePlatformLLMProvider = async (id: number) => {
  await httpClient.delete(`/settings/llm/providers/${id}/`);
};

export const fetchPlatformLLMModels = async () => {
  const response = await httpClient.get<PlatformLLMModelListResponse>('/settings/llm/models/');
  return response.data;
};

export const createPlatformLLMModel = async (payload: PlatformLLMModelPayload) => {
  const response = await httpClient.post<PlatformLLMModelRecord>('/settings/llm/models/', payload);
  return response.data;
};

export const updatePlatformLLMModel = async (id: number, payload: Partial<PlatformLLMModelPayload>) => {
  const response = await httpClient.patch<PlatformLLMModelRecord>(`/settings/llm/models/${id}/`, payload);
  return response.data;
};

export const deletePlatformLLMModel = async (id: number) => {
  await httpClient.delete(`/settings/llm/models/${id}/`);
};

export const fetchPlatformLLMTestSettings = async () => {
  const response = await httpClient.get<LLMTestSettings>('/settings/llm/test-settings/');
  return response.data;
};

export const updatePlatformLLMTestSettings = async (payload: LLMTestSettings) => {
  const response = await httpClient.patch<LLMTestSettings>('/settings/llm/test-settings/', payload);
  return response.data;
};

export const fetchTenantLLMAuthorization = async (tenantId: number) => {
  const response = await httpClient.get<TenantLLMAuthorization>(`/settings/llm/tenants/${tenantId}/authorization/`);
  return response.data;
};

export const updateTenantLLMAuthorization = async (
  tenantId: number,
  payload: TenantLLMAuthorizationPayload,
) => {
  const response = await httpClient.put<TenantLLMAuthorization>(
    `/settings/llm/tenants/${tenantId}/authorization/`,
    payload,
  );
  return response.data;
};

export const testPlatformLLMModel = async (modelId: number) => {
  const response = await httpClient.post<TestConnectionResult>(`/settings/llm/models/${modelId}/test/`);
  return response.data;
};
