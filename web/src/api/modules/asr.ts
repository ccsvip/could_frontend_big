import { httpClient } from '../client';
import { buildRealtimeWebSocketUrl } from '../realtime';

export type AsrSettingsRecord = {
  workspaceId: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  vadThreshold: number;
  vadSilenceDurationMs: number;
  isActive: boolean;
  configured: boolean;
  updated_at: string | null;
};

export type AsrStatusRecord = Omit<AsrSettingsRecord, 'apiKey'>;

export type AsrSettingsPayload = Partial<{
  workspaceId: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  vadThreshold: number;
  vadSilenceDurationMs: number;
  isActive: boolean;
}>;

export type AsrTestResult = {
  success: boolean;
  message: string;
  latencyMs: number;
};

export type AsrReplacementRuleRecord = {
  id: number;
  sourceText: string;
  replacementText: string;
  isActive: boolean;
  tenantId: number;
  created_at: string;
  updated_at: string;
};

export type AsrReplacementRuleListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: AsrReplacementRuleRecord[];
};

export type AsrReplacementRulePayload = {
  sourceText: string;
  replacementText: string;
  isActive: boolean;
};

export type AsrFillerWordSet = {
  fillerWords: string;
};

export const fetchAsrSettings = async () => {
  const response = await httpClient.get<AsrSettingsRecord>('/settings/asr/');
  return response.data;
};

export const updateAsrSettings = async (payload: AsrSettingsPayload) => {
  const response = await httpClient.patch<AsrSettingsRecord>('/settings/asr/', payload);
  return response.data;
};

export const testAsrSettings = async () => {
  const response = await httpClient.post<AsrTestResult>('/settings/asr/test/');
  return response.data;
};

export const fetchAsrStatus = async () => {
  const response = await httpClient.get<AsrStatusRecord>('/ai-models/asr/status/');
  return response.data;
};

export const updateAsrRuntimeConfig = async (
  payload: Pick<AsrSettingsPayload, 'vadThreshold' | 'vadSilenceDurationMs'>,
) => {
  const response = await httpClient.patch<AsrStatusRecord>('/ai-models/asr/config/', payload);
  return response.data;
};

export const testAsr = async () => {
  const response = await httpClient.post<AsrTestResult>('/ai-models/asr/test/');
  return response.data;
};

export const fetchAsrFillerWords = async () => {
  const response = await httpClient.get<AsrFillerWordSet>('/ai-models/asr/filler-words/');
  return response.data;
};

export const updateAsrFillerWords = async (payload: AsrFillerWordSet) => {
  const response = await httpClient.patch<AsrFillerWordSet>('/ai-models/asr/filler-words/', payload);
  return response.data;
};

export const fetchAsrReplacementRules = async (page?: number) => {
  const response = await httpClient.get<AsrReplacementRuleListResponse>('/ai-models/asr/replacement-rules/', {
    params: { page },
  });
  return response.data;
};

export const createAsrReplacementRule = async (payload: AsrReplacementRulePayload) => {
  const response = await httpClient.post<AsrReplacementRuleRecord>('/ai-models/asr/replacement-rules/', payload);
  return response.data;
};

export const updateAsrReplacementRule = async (id: number, payload: Partial<AsrReplacementRulePayload>) => {
  const response = await httpClient.patch<AsrReplacementRuleRecord>(`/ai-models/asr/replacement-rules/${id}/`, payload);
  return response.data;
};

export const deleteAsrReplacementRule = async (id: number) => {
  await httpClient.delete(`/ai-models/asr/replacement-rules/${id}/`);
};

export const buildAsrRealtimeWebSocketUrl = () => buildRealtimeWebSocketUrl();
