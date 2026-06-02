import { httpClient } from '../client';

export type ModelAssetType = 'male' | 'female';
export type ModelAssetOrientation = 'horizontal' | 'vertical';
export type ModelAssetVisibilityFilter = 'all' | 'visible' | 'hidden';

export type ModelAssetRecord = {
  id: number;
  name: string;
  modelType: ModelAssetType;
  modelTypeLabel: string;
  orientation: ModelAssetOrientation;
  orientationLabel: string;
  thumbnailUrl: string;
  thumbnailName: string;
  hasThumbnail: boolean;
  modelFileName: string;
  modelSize: number | null;
  hasModelFile: boolean;
  localUrl: string;
  cloudUrl: string;
  effectiveUrl: string;
  isVisible: boolean;
  created_at: string;
  updated_at: string;
};

export type ModelAssetListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ModelAssetRecord[];
};

export type ModelAssetListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  modelType?: ModelAssetType;
  orientation?: ModelAssetOrientation;
  visibility?: ModelAssetVisibilityFilter;
};

export type ModelAssetPayload = {
  name: string;
  modelType: ModelAssetType;
  orientation: ModelAssetOrientation;
  thumbnail?: File;
  modelFile?: File;
  cloudUrl?: string;
  isVisible: boolean;
  clearThumbnail?: boolean;
  clearModelFile?: boolean;
};

const buildFormData = (payload: ModelAssetPayload) => {
  const formData = new FormData();
  formData.append('name', payload.name);
  formData.append('modelType', payload.modelType);
  formData.append('orientation', payload.orientation);
  formData.append('cloudUrl', payload.cloudUrl || '');
  formData.append('isVisible', String(payload.isVisible));
  if (payload.thumbnail) {
    formData.append('thumbnail', payload.thumbnail);
  }
  if (payload.modelFile) {
    formData.append('model_file', payload.modelFile);
  }
  if (payload.clearThumbnail) {
    formData.append('clearThumbnail', 'true');
  }
  if (payload.clearModelFile) {
    formData.append('clearModelFile', 'true');
  }
  return formData;
};

const buildListParams = (query?: ModelAssetListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  keyword: query?.keyword || undefined,
  model_type: query?.modelType || undefined,
  orientation: query?.orientation || undefined,
  is_visible:
    query?.visibility === 'visible'
      ? 'true'
      : query?.visibility === 'hidden'
        ? 'false'
        : undefined,
});

export const fetchModelAssets = async (query?: ModelAssetListQuery) => {
  const response = await httpClient.get<ModelAssetListResponse>('/resources/models/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const createModelAsset = async (payload: ModelAssetPayload) => {
  const response = await httpClient.post<ModelAssetRecord>('/resources/models/', buildFormData(payload));
  return response.data;
};

export const updateModelAsset = async (id: number, payload: ModelAssetPayload) => {
  const response = await httpClient.patch<ModelAssetRecord>(`/resources/models/${id}/`, buildFormData(payload));
  return response.data;
};

export const deleteModelAsset = async (id: number) => {
  await httpClient.delete(`/resources/models/${id}/`);
};
