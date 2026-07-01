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

export type ThirdPartyChatbotOption = {
  id: number;
  name: string;
  description: string;
  providerId: number;
  providerName: string;
  providerType: string;
};

export type CompanyThirdPartyChatbotOptions = {
  chatbots: ThirdPartyChatbotOption[];
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
  enableWebSearch: boolean;
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
  enableWebSearch?: boolean;
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

export type PlatformThirdPartyChatbotProviderRecord = {
  id: number;
  name: string;
  providerType: string;
  providerTypeLabel: string;
  apiBaseUrl: string;
  apiKeyMasked: string;
  apiKeyConfigured: boolean;
  isActive: boolean;
  sortOrder: number;
  created_at: string;
  updated_at: string;
};

export type PlatformThirdPartyChatbotProviderPayload = {
  name: string;
  providerType?: string;
  apiBaseUrl: string;
  apiKey?: string;
  isActive?: boolean;
  sortOrder?: number;
};

export type PlatformThirdPartyChatbotApplicationRecord = {
  id: number;
  providerId: number;
  providerName: string;
  providerType: string;
  name: string;
  description: string;
  externalApplicationId: string;
  isActive: boolean;
  sortOrder: number;
  created_at: string;
  updated_at: string;
};

export type PlatformThirdPartyChatbotApplicationPayload = {
  providerId: number;
  name: string;
  description?: string;
  externalApplicationId: string;
  isActive?: boolean;
  sortOrder?: number;
};

export type TenantThirdPartyChatbotAuthorizationRecord = {
  id: number;
  providerId: number;
  providerName: string;
  providerType: string;
  name: string;
  description: string;
  externalApplicationId: string;
  isActive: boolean;
  providerIsActive: boolean;
  sortOrder: number;
  grantIsActive: boolean;
};

export type TenantThirdPartyChatbotAuthorization = {
  tenant: {
    id: number;
    name: string;
    isActive: boolean;
  };
  chatbots: TenantThirdPartyChatbotAuthorizationRecord[];
};

export type TenantThirdPartyChatbotAuthorizationPayload = {
  chatbotGrants: Array<{
    chatbotId: number;
    isActive: boolean;
  }>;
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

export const fetchCompanyThirdPartyChatbotOptions = async () => {
  const response = await httpClient.get<CompanyThirdPartyChatbotOptions>('/ai-models/third-party-chatbots/options/');
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

export const fetchPlatformThirdPartyChatbotProviders = async () => {
  const response = await httpClient.get<{ results: PlatformThirdPartyChatbotProviderRecord[] }>(
    '/settings/third-party-chatbots/providers/',
  );
  return response.data;
};

export const createPlatformThirdPartyChatbotProvider = async (payload: PlatformThirdPartyChatbotProviderPayload) => {
  const response = await httpClient.post<PlatformThirdPartyChatbotProviderRecord>(
    '/settings/third-party-chatbots/providers/',
    payload,
  );
  return response.data;
};

export const updatePlatformThirdPartyChatbotProvider = async (
  id: number,
  payload: Partial<PlatformThirdPartyChatbotProviderPayload>,
) => {
  const response = await httpClient.patch<PlatformThirdPartyChatbotProviderRecord>(
    `/settings/third-party-chatbots/providers/${id}/`,
    payload,
  );
  return response.data;
};

export const deletePlatformThirdPartyChatbotProvider = async (id: number) => {
  await httpClient.delete(`/settings/third-party-chatbots/providers/${id}/`);
};

export const fetchPlatformThirdPartyChatbotApplications = async () => {
  const response = await httpClient.get<{ results: PlatformThirdPartyChatbotApplicationRecord[] }>(
    '/settings/third-party-chatbots/applications/',
  );
  return response.data;
};

export const createPlatformThirdPartyChatbotApplication = async (
  payload: PlatformThirdPartyChatbotApplicationPayload,
) => {
  const response = await httpClient.post<PlatformThirdPartyChatbotApplicationRecord>(
    '/settings/third-party-chatbots/applications/',
    payload,
  );
  return response.data;
};

export const updatePlatformThirdPartyChatbotApplication = async (
  id: number,
  payload: Partial<PlatformThirdPartyChatbotApplicationPayload>,
) => {
  const response = await httpClient.patch<PlatformThirdPartyChatbotApplicationRecord>(
    `/settings/third-party-chatbots/applications/${id}/`,
    payload,
  );
  return response.data;
};

export const deletePlatformThirdPartyChatbotApplication = async (id: number) => {
  await httpClient.delete(`/settings/third-party-chatbots/applications/${id}/`);
};

export const fetchTenantThirdPartyChatbotAuthorization = async (tenantId: number) => {
  const response = await httpClient.get<TenantThirdPartyChatbotAuthorization>(
    `/settings/third-party-chatbots/tenants/${tenantId}/authorization/`,
  );
  return response.data;
};

export const updateTenantThirdPartyChatbotAuthorization = async (
  tenantId: number,
  payload: TenantThirdPartyChatbotAuthorizationPayload,
) => {
  const response = await httpClient.put<TenantThirdPartyChatbotAuthorization>(
    `/settings/third-party-chatbots/tenants/${tenantId}/authorization/`,
    payload,
  );
  return response.data;
};
