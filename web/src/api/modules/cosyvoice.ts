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
  avatar?: File;
};

export type CosyVoiceDesignPayload = {
  displayName: string;
  description: string;
  language: 'zh' | 'en';
  avatarPath?: string;
};

export type CosyVoiceVoiceUpdatePayload = Partial<
  Pick<CosyVoiceVoiceRecord, 'displayName' | 'isActive' | 'isVisible' | 'avatarPath' | 'isDefault'>
> & {
  avatar?: File;
};

const cosyVoiceSettingsPath = '/settings/tts/cosyvoice/';
const cosyVoiceBlobRequestConfig = {
  responseType: 'blob' as const,
  timeout: 60000,
};

const buildVoiceUpdateBody = (payload: CosyVoiceVoiceUpdatePayload): CosyVoiceVoiceUpdatePayload | FormData => {
  if (!payload.avatar) {
    const { avatar: _avatar, ...jsonPayload } = payload;
    return jsonPayload;
  }

  const formData = new FormData();
  if (payload.displayName !== undefined) formData.append('displayName', payload.displayName);
  if (payload.avatarPath !== undefined) formData.append('avatarPath', payload.avatarPath);
  if (payload.isActive !== undefined) formData.append('isActive', String(payload.isActive));
  if (payload.isVisible !== undefined) formData.append('isVisible', String(payload.isVisible));
  if (payload.isDefault !== undefined) formData.append('isDefault', String(payload.isDefault));
  formData.append('avatar', payload.avatar);
  return formData;
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
  const body = (() => {
    if (!payload.avatar) {
      const { avatar: _avatar, ...jsonPayload } = payload;
      return jsonPayload;
    }
    const formData = new FormData();
    formData.append('displayName', payload.displayName);
    formData.append('sourceAudioUrl', payload.sourceAudioUrl);
    if (payload.avatarPath !== undefined) formData.append('avatarPath', payload.avatarPath);
    formData.append('avatar', payload.avatar);
    return formData;
  })();
  const response = await httpClient.post<CosyVoiceVoiceRecord>(`${cosyVoiceSettingsPath}voices/enroll/`, body);
  return response.data;
};

export const designCosyVoice = async (payload: CosyVoiceDesignPayload): Promise<CosyVoiceVoiceRecord> => {
  const response = await httpClient.post<CosyVoiceVoiceRecord>(`${cosyVoiceSettingsPath}voices/design/`, payload);
  return response.data;
};

export const updateCosyVoiceVoice = async (
  voiceId: number,
  payload: CosyVoiceVoiceUpdatePayload,
): Promise<CosyVoiceVoiceRecord> => {
  const response = await httpClient.patch<CosyVoiceVoiceRecord>(
    `${cosyVoiceSettingsPath}voices/${voiceId}/`,
    buildVoiceUpdateBody(payload),
  );
  return response.data;
};


export const deleteCosyVoiceVoice = async (voiceId: number): Promise<void> => {
  await httpClient.delete(`${cosyVoiceSettingsPath}voices/${voiceId}/`);
};
