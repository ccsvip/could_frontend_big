import { httpClient } from '../client';

export type VoiceToneRecord = {
  id: number;
  name: string;
  voiceCode: string;
  asrText: string;
  iconUrl: string;
  iconName: string;
  iconSize: number | null;
  hasIcon: boolean;
  audioUrl: string;
  audioName: string;
  audioSize: number | null;
  hasAudio: boolean;
  isActive: boolean;
  isVisible: boolean;
  created_at: string;
  updated_at: string;
};

export type VoiceToneListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: VoiceToneRecord[];
};

export type VoiceToneStatusFilter = 'all' | 'active' | 'inactive';

export type VoiceToneListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  status?: VoiceToneStatusFilter;
};

export type VoiceTonePayload = {
  name: string;
  voiceCode: string;
  asrText?: string;
  icon?: File;
  audio?: File;
  isActive: boolean;
  isVisible: boolean;
  clearIcon?: boolean;
  clearAudio?: boolean;
};

const buildFormData = (payload: VoiceTonePayload) => {
  const formData = new FormData();
  formData.append('name', payload.name);
  formData.append('voiceCode', payload.voiceCode);
  formData.append('asrText', payload.asrText || '');
  formData.append('isActive', String(payload.isActive));
  formData.append('isVisible', String(payload.isVisible));
  if (payload.icon) {
    formData.append('icon', payload.icon);
  }
  if (payload.audio) {
    formData.append('audio', payload.audio);
  }
  if (payload.clearIcon) {
    formData.append('clearIcon', 'true');
  }
  if (payload.clearAudio) {
    formData.append('clearAudio', 'true');
  }
  return formData;
};

const buildListParams = (query?: VoiceToneListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  keyword: query?.keyword || undefined,
  is_active:
    query?.status === 'active' ? 'true' : query?.status === 'inactive' ? 'false' : undefined,
});

export const fetchVoiceTones = async (query?: VoiceToneListQuery) => {
  const response = await httpClient.get<VoiceToneListResponse>('/resources/voice-tones/', { params: buildListParams(query) });
  return response.data;
};

export const createVoiceTone = async (payload: VoiceTonePayload) => {
  const response = await httpClient.post<VoiceToneRecord>('/resources/voice-tones/', buildFormData(payload));
  return response.data;
};

export const updateVoiceTone = async (id: number, payload: VoiceTonePayload) => {
  const response = await httpClient.patch<VoiceToneRecord>(`/resources/voice-tones/${id}/`, buildFormData(payload));
  return response.data;
};

export const deleteVoiceTone = async (id: number) => {
  await httpClient.delete(`/resources/voice-tones/${id}/`);
};
