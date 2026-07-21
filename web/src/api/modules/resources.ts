import axios from 'axios';
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
  storageBackend?: string;
  objectKey?: string;
  objectSize?: number | null;
  contentHash?: string;
  isDigitalHumanBackground: boolean;
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
  isDigitalHumanBackground?: boolean;
};

export type DuplicateImageLocation = {
  id: number;
  category: ResourceCategory;
  isDigitalHumanBackground: boolean;
};

export type ResourcePayload = {
  name: string;
  category: ResourceCategory;
  description?: string;
  cloudUrl?: string;
  storageBackend?: string;
  objectKey?: string;
  objectSize?: number | null;
  contentHash?: string;
  isDigitalHumanBackground?: boolean;
  file?: File;
  clearFile?: boolean;
};

export type BatchImageResourcePayload = {
  files: File[];
  category: ResourceCategory;
  description?: string;
  isDigitalHumanBackground?: boolean;
};

export type BatchImageResourceDuplicate = {
  fileName: string;
  reason: string;
};

export type BatchImageResourceResponse = {
  created: ResourceRecord[];
  duplicates: BatchImageResourceDuplicate[];
};

export type BulkImageResourceDeleteFailure = {
  id: number;
  name: string;
  reason: string;
};

export type BulkImageResourceDeleteResponse = {
  deletedIds: number[];
  failures: BulkImageResourceDeleteFailure[];
};

const buildFormData = (payload: ResourcePayload) => {
  const formData = new FormData();
  formData.append('name', payload.name);
  formData.append('category', payload.category);
  formData.append('description', payload.description || '');
  formData.append('cloudUrl', payload.cloudUrl || '');
  if (payload.storageBackend) {
    formData.append('storageBackend', payload.storageBackend);
  }
  if (payload.objectKey) {
    formData.append('objectKey', payload.objectKey);
  }
  if (payload.objectSize != null) {
    formData.append('objectSize', String(payload.objectSize));
  }
  if (payload.contentHash) {
    formData.append('contentHash', payload.contentHash);
  }
  if (payload.isDigitalHumanBackground != null) {
    formData.append('isDigitalHumanBackground', String(payload.isDigitalHumanBackground));
  }
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
  isDigitalHumanBackground: query?.isDigitalHumanBackground,
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

export const batchCreateImageResources = async (payload: BatchImageResourcePayload) => {
  const formData = new FormData();
  formData.append('category', payload.category);
  formData.append('description', payload.description || '');
  formData.append('isDigitalHumanBackground', String(Boolean(payload.isDigitalHumanBackground)));
  payload.files.forEach((file) => {
    formData.append('files', file);
  });
  const response = await httpClient.post<BatchImageResourceResponse>('/resources/images/bulk/', formData);
  return response.data;
};

export const updateImageResource = async (id: number, payload: ResourcePayload) => {
  const response = await httpClient.patch<ResourceRecord>(`/resources/images/${id}/`, buildFormData(payload));
  return response.data;
};

export const deleteImageResource = async (id: number) => {
  await httpClient.delete(`/resources/images/${id}/`);
};

export const bulkDeleteImageResources = async (ids: number[]) => {
  const response = await httpClient.delete<BulkImageResourceDeleteResponse>('/resources/images/bulk/', {
    data: { ids },
  });
  return response.data;
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

export type VideoUploadConfig = {
  enabled: boolean;
  storageBackend: 'local' | 'r2';
  maxSizeBytes: number;
  maxSizeMB: number;
  bucketName: string;
  expiresIn: number;
  allowCloudUrl: boolean;
  quotaLimited: boolean;
  quotaMB: number | null;
  quotaBytes: number | null;
  usedBytes: number;
  remainingBytes: number | null;
  usedMB: number;
  remainingMB: number | null;
};

export type VideoPresignResponse = {
  uploadUrl: string;
  objectKey: string;
  storageBackend?: string;
  publicUrl: string;
  bucket: string;
  expiresIn: number;
  maxSizeBytes: number;
  objectSize: number;
  quotaLimited: boolean;
  quotaMB: number | null;
  quotaBytes: number | null;
  usedBytes: number;
  remainingBytes: number | null;
  usedMB: number;
  remainingMB: number | null;
  headers: Record<string, string>;
};

export const fetchVideoUploadConfig = async () => {
  const response = await httpClient.get<VideoUploadConfig>('/resources/videos/upload-config/');
  return response.data;
};

export const fetchResourceUploadConfig = async () => {
  const response = await httpClient.get<VideoUploadConfig & { imageDirectUploadEnabled: boolean }>('/resources/upload-config/');
  return response.data;
};

export const presignResourceUpload = async (params: { resourceType: ResourceType; filename: string; contentType: string; fileSize: number; contentHash?: string }) => {
  const response = await httpClient.post<VideoPresignResponse>('/resources/presign/', {
    resourceType: params.resourceType,
    filename: params.filename,
    contentType: params.contentType,
    fileSize: params.fileSize,
    contentHash: params.contentHash,
  });
  return response.data;
};

export const isDuplicateImageError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409;

export const getDuplicateImageLocation = (error: unknown): DuplicateImageLocation | null => {
  if (!isDuplicateImageError(error) || !axios.isAxiosError(error)) {
    return null;
  }
  const existingResource = error.response?.data?.data?.existingResource;
  if (
    typeof existingResource?.id !== 'number'
    || !['horizontal', 'vertical', 'uncategorized'].includes(existingResource.category)
    || typeof existingResource.isDigitalHumanBackground !== 'boolean'
  ) {
    return null;
  }
  return existingResource as DuplicateImageLocation;
};

export const presignVideoUpload = async (params: { filename: string; contentType: string; fileSize: number }) => {
  const response = await httpClient.post<VideoPresignResponse>('/resources/videos/presign/', {
    filename: params.filename,
    contentType: params.contentType,
    fileSize: params.fileSize,
  });
  return response.data;
};

export const uploadFileToPresignedUrl = async (
  uploadUrl: string,
  file: File,
  options: {
    headers?: Record<string, string>;
    onProgress?: (percent: number, loaded: number, total: number) => void;
    signal?: AbortSignal;
  } = {},
) => {
  await axios.put(uploadUrl, file, {
    headers: options.headers,
    timeout: 0,
    signal: options.signal,
    onUploadProgress: (event) => {
      if (!options.onProgress) {
        return;
      }
      const total = event.total ?? file.size;
      const loaded = event.loaded;
      const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
      options.onProgress(percent, loaded, total);
    },
    transformRequest: [(data) => data],
  });
};
