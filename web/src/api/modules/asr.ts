import { httpClient } from '../client';

export type AsrSettingsRecord = {
  workspaceId: string;
  apiKey: string;
  baseUrl: string;
  model: string;
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
  isActive: boolean;
}>;

export type AsrTestResult = {
  success: boolean;
  message: string;
  latencyMs: number;
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

export const testAsr = async () => {
  const response = await httpClient.post<AsrTestResult>('/ai-models/asr/test/');
  return response.data;
};
