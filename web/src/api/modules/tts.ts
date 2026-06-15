import { httpClient } from '../client';

export type TtsVoiceRecord = {
  id: number;
  displayName: string;
  voiceCode: string;
  gender: string;
  avatarPath: string;
  isActive?: boolean;
  isVisible?: boolean;
  sortOrder?: number;
  isDefault: boolean;
};

export type TtsSettings = {
  id: number;
  code: string;
  name: string;
  apiKeyMasked: string;
  apiKeyConfigured: boolean;
  baseUrl: string;
  model: string;
  sampleRate: number;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
  configured: boolean;
  voices: TtsVoiceRecord[];
  updated_at: string | null;
};

export type TtsSettingsPayload = Partial<{
  apiKey: string;
  baseUrl: string;
  model: string;
  sampleRate: number;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
  voices: Array<Partial<TtsVoiceRecord> & { id: number }>;
}>;

export type CompanyTtsOptions = {
  provider: {
    code: string;
    name: string;
    isActive: boolean;
  };
  defaultVoiceId: number | null;
  sampleRate: number;
  defaultTestText: string;
  voices: TtsVoiceRecord[];
};

export type TtsTestPayload = {
  text?: string;
  voiceId?: number | null;
};

const blobRequestConfig = {
  responseType: 'blob' as const,
  timeout: 60000,
};

export const fetchTtsSettings = async () => {
  const response = await httpClient.get<TtsSettings>('/settings/tts/');
  return response.data;
};

export const updateTtsSettings = async (payload: TtsSettingsPayload) => {
  const response = await httpClient.patch<TtsSettings>('/settings/tts/', payload);
  return response.data;
};

export const testPlatformTts = async (payload: TtsTestPayload) => {
  const response = await httpClient.post<Blob>('/settings/tts/test/', payload, blobRequestConfig);
  return response.data;
};

export const fetchCompanyTtsOptions = async () => {
  const response = await httpClient.get<CompanyTtsOptions>('/ai-models/tts/options/');
  return response.data;
};

export const updateCompanyDefaultTtsVoice = async (voiceId: number) => {
  const response = await httpClient.patch<CompanyTtsOptions>('/ai-models/tts/default-voice/', { voiceId });
  return response.data;
};

export const testCompanyTts = async (payload: TtsTestPayload) => {
  const response = await httpClient.post<Blob>('/ai-models/tts/test/', payload, blobRequestConfig);
  return response.data;
};
