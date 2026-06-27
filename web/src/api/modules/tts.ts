import { httpClient } from '../client';
import { buildRealtimeWebSocketUrl } from '../realtime';

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

export type TtsProviderSummary = {
  id: number;
  code: string;
  name: string;
  defaultVoiceId: number | null;
  defaultVoiceName: string;
  sampleRate: number;
  isActive: boolean;
  configured: boolean;
  voiceCount: number;
  updated_at: string | null;
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

export type TtsRealtimeMessage = {
  type?: string;
  sampleRate?: number;
  responseFormat?: 'pcm' | 'wav' | 'mp3' | 'opus';
  voice?: string;
  message?: string;
};

const blobRequestConfig = {
  responseType: 'blob' as const,
  timeout: 60000,
};

const ttsSettingsPath = (providerCode?: string) =>
  providerCode ? `/settings/tts/providers/${providerCode}/` : '/settings/tts/';

const ttsSettingsTestPath = (providerCode?: string) =>
  providerCode ? `/settings/tts/providers/${providerCode}/test/` : '/settings/tts/test/';

export const fetchTtsProviders = async () => {
  const response = await httpClient.get<TtsProviderSummary[]>('/settings/tts/providers/');
  return response.data;
};

export const fetchTtsSettings = async (providerCode?: string) => {
  const response = await httpClient.get<TtsSettings>(ttsSettingsPath(providerCode));
  return response.data;
};

export const updateTtsSettings = async (payload: TtsSettingsPayload, providerCode?: string) => {
  const response = await httpClient.patch<TtsSettings>(ttsSettingsPath(providerCode), payload);
  return response.data;
};

export const testPlatformTts = async (payload: TtsTestPayload, providerCode?: string) => {
  const response = await httpClient.post<Blob>(ttsSettingsTestPath(providerCode), payload, blobRequestConfig);
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

export const buildTtsRealtimeWebSocketUrl = () => buildRealtimeWebSocketUrl();
