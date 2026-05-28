import { httpClient } from '../client';

export type ResourceType = 'image' | 'video';
export type ResourceCategory = 'horizontal' | 'vertical' | 'uncategorized';

export type ResourceRecord = {
  id: number;
  name: string;
  resourceType: ResourceType;
  resourceTypeLabel: string;
  category: ResourceCategory;
  categoryLabel: string;
  description: string;
  cloudUrl: string;
  fileUrl: string;
  fileName: string;
  fileSize: number | null;
  hasFile: boolean;
  thumbnailUrl?: string;
  created_at: string;
  updated_at: string;
};

export type ResourceListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ResourceRecord[];
};

export type ResourceListQuery = {
  page?: number;
  pageSize?: number;
  category?: ResourceCategory | 'all';
  keyword?: string;
};

export type ResourcePayload = {
  name: string;
  category: ResourceCategory;
  description?: string;
  cloudUrl?: string;
  file?: File;
  clearFile?: boolean;
};

const buildFormData = (payload: ResourcePayload) => {
  const formData = new FormData();
  formData.append('name', payload.name);
  formData.append('category', payload.category);
  formData.append('description', payload.description || '');
  formData.append('cloudUrl', payload.cloudUrl || '');
  if (payload.file) {
    formData.append('file', payload.file);
  }
  if (payload.clearFile) {
    formData.append('clearFile', 'true');
  }
  return formData;
};

const buildListParams = (query?: ResourceListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  category: query?.category && query.category !== 'all' ? query.category : undefined,
  keyword: query?.keyword || undefined,
});

export const fetchImageResources = async (query?: ResourceListQuery) => {
  const response = await httpClient.get<ResourceListResponse>('/resources/images/', { params: buildListParams(query) });
  return response.data;
};

export const fetchVideoResources = async (query?: ResourceListQuery) => {
  const response = await httpClient.get<ResourceListResponse>('/resources/videos/', { params: buildListParams(query) });
  return response.data;
};

export const createImageResource = async (payload: ResourcePayload) => {
  const response = await httpClient.post<ResourceRecord>('/resources/images/', buildFormData(payload));
  return response.data;
};

export const updateImageResource = async (id: number, payload: ResourcePayload) => {
  const response = await httpClient.patch<ResourceRecord>(`/resources/images/${id}/`, buildFormData(payload));
  return response.data;
};

export const deleteImageResource = async (id: number) => {
  await httpClient.delete(`/resources/images/${id}/`);
};

export const createVideoResource = async (payload: ResourcePayload) => {
  const response = await httpClient.post<ResourceRecord>('/resources/videos/', buildFormData(payload));
  return response.data;
};

export const updateVideoResource = async (id: number, payload: ResourcePayload) => {
  const response = await httpClient.patch<ResourceRecord>(`/resources/videos/${id}/`, buildFormData(payload));
  return response.data;
};

export const deleteVideoResource = async (id: number) => {
  await httpClient.delete(`/resources/videos/${id}/`);
};
