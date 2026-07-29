import { httpClient } from '../client';

export type CosyVoiceVoiceRecord = {
  id: number;
  displayName: string;
  voiceCode: string;
  gender: string;
  language?: string;
  sourceType?: string;
  avatarPath: string;
  isActive: boolean;
  isVisible: boolean;
  sortOrder?: number;
  isDefault: boolean;
};

export type CosyVoiceSettings = {
  apiKeyMasked: string;
  apiKeyConfigured: boolean;
  websocketUrl: string;
  customizationUrl: string;
  model: 'cosyvoice-v3.5-plus';
  isActive: boolean;
  defaultVoiceId: number | null;
  defaultTestText: string;
  configured: boolean;
  voices: CosyVoiceVoiceRecord[];
};

export type CosyVoiceSettingsPayload = Partial<{
  apiKey: string;
  websocketUrl: string;
  customizationUrl: string;
  isActive: boolean;
  defaultVoiceId: number | null;
  defaultTestText: string;
}>;

export type CosyVoiceTestPayload = {
  text?: string;
  voiceId?: number | null;
};

export type CosyVoiceEnrollPayload = {
  displayName: string;
  sourceAudioUrl: string;
  avatarPath?: string;
};

export type CosyVoiceDesignPayload = {
  displayName: string;
  description: string;
  language: 'zh' | 'en';
  avatarPath?: string;
};

export type CosyVoiceVoiceUpdatePayload = Partial<Pick<CosyVoiceVoiceRecord, 'displayName' | 'isActive' | 'isVisible' | 'avatarPath' | 'isDefault'>>;

const cosyVoiceSettingsPath = '/settings/tts/cosyvoice/';
const cosyVoiceBlobRequestConfig = {
  responseType: 'blob' as const,
  timeout: 60000,
};

export const fetchCosyVoiceSettings = async (): Promise<CosyVoiceSettings> => {
  const response = await httpClient.get<CosyVoiceSettings>(cosyVoiceSettingsPath);
  return response.data;
};

export const updateCosyVoiceSettings = async (payload: CosyVoiceSettingsPayload): Promise<CosyVoiceSettings> => {
  const response = await httpClient.patch<CosyVoiceSettings>(cosyVoiceSettingsPath, payload);
  return response.data;
};

export const testCosyVoice = async (payload: CosyVoiceTestPayload): Promise<Blob> => {
  const response = await httpClient.post<Blob>(`${cosyVoiceSettingsPath}test/`, payload, cosyVoiceBlobRequestConfig);
  return response.data;
};

export const enrollCosyVoice = async (payload: CosyVoiceEnrollPayload): Promise<CosyVoiceVoiceRecord> => {
  const response = await httpClient.post<CosyVoiceVoiceRecord>(`${cosyVoiceSettingsPath}voices/enroll/`, payload);
  return response.data;
};

export const designCosyVoice = async (payload: CosyVoiceDesignPayload): Promise<CosyVoiceVoiceRecord> => {
  const response = await httpClient.post<CosyVoiceVoiceRecord>(`${cosyVoiceSettingsPath}voices/design/`, payload);
  return response.data;
};

export const updateCosyVoiceVoice = async (voiceId: number, payload: CosyVoiceVoiceUpdatePayload): Promise<CosyVoiceVoiceRecord> => {
  const response = await httpClient.patch<CosyVoiceVoiceRecord>(`${cosyVoiceSettingsPath}voices/${voiceId}/`, payload);
  return response.data;
};

export const deleteCosyVoiceVoice = async (voiceId: number): Promise<void> => {
  await httpClient.delete(`${cosyVoiceSettingsPath}voices/${voiceId}/`);
};
