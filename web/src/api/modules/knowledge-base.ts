import axios, { type AxiosProgressEvent } from 'axios';
import { message } from 'antd';
import { API_BASE_URL, handleUnauthorizedResponse, httpClient } from '../client';

export type KnowledgeDocumentRecord = {
  id: number;
  title: string;
  description: string;
  knowledgeBaseId: number | null;
  knowledgeBaseName: string;
  fileName: string;
  fileExtension: string;
  fileSize: number | null;
  uploadedBy: string;
  downloadCount: number;
  indexingStatus: 'pending' | 'indexing' | 'ready' | 'failed';
  indexingStatusLabel: string;
  indexingError: string;
  indexedAt: string | null;
  chunkCount: number;
  indexModel: string;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseRecord = {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  createdBy: string;
  isActive: boolean;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: KnowledgeBaseRecord[];
};

export type KnowledgeBaseListQuery = {
  page?: number;
  keyword?: string;
};

export type KnowledgeDocumentListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: KnowledgeDocumentRecord[];
};

export type KnowledgeDocumentListQuery = {
  page?: number;
  keyword?: string;
  knowledgeBaseId?: number;
};

export type KnowledgeDocumentUploadPayload = {
  file: File;
  knowledgeBaseId?: number;
  title?: string;
  description?: string;
};

export type KnowledgeDocumentUploadOptions = {
  onUploadProgress?: (percent: number) => void;
  timeoutMs?: number;
};

export type KnowledgeRecallChunk = {
  documentId: number | null;
  documentTitle: string;
  chunkIndex: number | null;
  content: string;
  score: number;
};

export type KnowledgeRecallResult = {
  mode: 'empty' | 'keyword' | 'vector';
  embeddingModelAlias: string;
  rerankModelAlias: string;
  chunks: KnowledgeRecallChunk[];
};

export type KnowledgeModelSettings = {
  embedding: {
    id: number;
    type: 'embedding';
    alias: string;
    model: string;
    baseUrl: string;
    apiKeyMasked: string;
    apiKeyConfigured: boolean;
    isActive: boolean;
    dimensions: number;
    updated_at: string;
  };
  rerank: {
    id: number;
    type: 'rerank';
    alias: string;
    model: string;
    baseUrl: string;
    apiKeyMasked: string;
    apiKeyConfigured: boolean;
    isActive: boolean;
    updated_at: string;
  };
};

export type TenantKnowledgeAuthorization = {
  tenant: { id: number; name: string; isActive: boolean };
  models: {
    embedding: { id: number; alias: string; isActive: boolean; grantIsActive: boolean };
    rerank: { id: number; alias: string; isActive: boolean; grantIsActive: boolean };
  };
  embeddingModelId: number | null;
  rerankModelId: number | null;
  isActive: boolean;
};

const DOWNLOAD_TIMEOUT_MS = 120000;
export const KNOWLEDGE_BASE_ACCEPT = '.doc,.docx,.ppt,.pptx,.md,.txt,.pdf,.xls,.xlsx';

const downloadClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: DOWNLOAD_TIMEOUT_MS,
  responseType: 'blob',
});

const buildListParams = (query?: KnowledgeDocumentListQuery) => ({
  page: query?.page,
  keyword: query?.keyword || undefined,
  knowledge_base: query?.knowledgeBaseId,
});

const buildUploadFormData = (payload: KnowledgeDocumentUploadPayload) => {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.title) {
    formData.append('title', payload.title);
  }
  if (payload.description) {
    formData.append('description', payload.description);
  }
  if (payload.knowledgeBaseId) {
    formData.append('knowledgeBaseId', String(payload.knowledgeBaseId));
  }
  return formData;
};

const readBlobErrorMessage = async (blob: unknown) => {
  if (!(blob instanceof Blob)) {
    return null;
  }

  try {
    const text = await blob.text();
    if (!text) {
      return null;
    }
    const parsed = JSON.parse(text) as { message?: string; detail?: string };
    return parsed.message || parsed.detail || null;
  } catch {
    return null;
  }
};

const extractFileName = (contentDisposition: string | undefined, fallbackName: string) => {
  if (!contentDisposition) {
    return fallbackName;
  }

  const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    try {
      return decodeURIComponent(filenameStarMatch[1]);
    } catch {
      return filenameStarMatch[1];
    }
  }

  const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  return filenameMatch?.[1] || fallbackName;
};

const saveBlob = (blob: Blob, fileName: string) => {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

const authorizedDownloadRequest = async (
  config: Parameters<typeof downloadClient.request>[0],
  fallbackName: string,
) => {
  try {
    const token = localStorage.getItem('token');
    const response = await downloadClient.request({
      ...config,
      headers: {
        Authorization: token ? `Bearer ${token}` : undefined,
        ...(config.headers || {}),
      },
    });
    const fileName = extractFileName(response.headers['content-disposition'], fallbackName);
    saveBlob(response.data, fileName);
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        handleUnauthorizedResponse();
      }

      const blobMessage = await readBlobErrorMessage(error.response?.data);
      message.error(blobMessage || '请求失败，请稍后重试');
    } else {
      message.error('请求失败，请稍后重试');
    }
    throw error;
  }
};

export const fetchKnowledgeDocuments = async (query?: KnowledgeDocumentListQuery) => {
  const response = await httpClient.get<KnowledgeDocumentListResponse>('/knowledge-base/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const fetchKnowledgeBases = async (query?: KnowledgeBaseListQuery) => {
  const response = await httpClient.get<KnowledgeBaseListResponse>('/knowledge-bases/', {
    params: {
      page: query?.page,
      keyword: query?.keyword || undefined,
    },
  });
  return response.data;
};

export const createKnowledgeBase = async (payload: { name: string; description?: string }) => {
  const response = await httpClient.post<KnowledgeBaseRecord>('/knowledge-bases/', payload);
  return response.data;
};

export const updateKnowledgeBase = async (id: number, payload: Partial<{ name: string; description: string; isActive: boolean }>) => {
  const response = await httpClient.patch<KnowledgeBaseRecord>(`/knowledge-bases/${id}/`, payload);
  return response.data;
};

export const deleteKnowledgeBase = async (id: number) => {
  await httpClient.delete(`/knowledge-bases/${id}/`);
};

export const fetchKnowledgeBaseDocuments = async (knowledgeBaseId: number, query?: KnowledgeDocumentListQuery) => {
  const response = await httpClient.get<KnowledgeDocumentRecord[]>(`/knowledge-bases/${knowledgeBaseId}/documents/`, {
    params: buildListParams(query),
  });
  return response.data;
};

export const uploadKnowledgeDocument = async (
  payload: KnowledgeDocumentUploadPayload,
  options?: KnowledgeDocumentUploadOptions,
) => {
  const response = await httpClient.post<KnowledgeDocumentRecord>(
    '/knowledge-base/',
    buildUploadFormData(payload),
    {
      timeout: options?.timeoutMs ?? DOWNLOAD_TIMEOUT_MS,
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (!options?.onUploadProgress) {
          return;
        }
        const total = progressEvent.total || payload.file.size;
        const percent = total > 0 ? Math.round((progressEvent.loaded / total) * 100) : 0;
        options.onUploadProgress(Math.max(0, Math.min(100, percent)));
      },
    },
  );
  return response.data;
};

export const uploadKnowledgeBaseDocument = async (
  knowledgeBaseId: number,
  payload: KnowledgeDocumentUploadPayload,
  options?: KnowledgeDocumentUploadOptions,
) => {
  const response = await httpClient.post<KnowledgeDocumentRecord>(
    `/knowledge-bases/${knowledgeBaseId}/documents/`,
    buildUploadFormData({ ...payload, knowledgeBaseId }),
    {
      timeout: options?.timeoutMs ?? DOWNLOAD_TIMEOUT_MS,
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (!options?.onUploadProgress) {
          return;
        }
        const total = progressEvent.total || payload.file.size;
        const percent = total > 0 ? Math.round((progressEvent.loaded / total) * 100) : 0;
        options.onUploadProgress(Math.max(0, Math.min(100, percent)));
      },
    },
  );
  return response.data;
};

export const recallTestKnowledgeBase = async (knowledgeBaseId: number, payload: { query: string; topN?: number }) => {
  const response = await httpClient.post<KnowledgeRecallResult>(`/knowledge-bases/${knowledgeBaseId}/recall-test/`, payload);
  return response.data;
};

export const indexKnowledgeBase = async (knowledgeBaseId: number) => {
  const response = await httpClient.post<{ queuedCount: number; documents: Array<{ documentId: number; queued: boolean }> }>(
    `/knowledge-bases/${knowledgeBaseId}/index/`,
  );
  return response.data;
};

export const indexKnowledgeDocument = async (documentId: number) => {
  const response = await httpClient.post<{ documentId: number; queued: boolean }>(`/knowledge-base/${documentId}/index/`);
  return response.data;
};

export const downloadKnowledgeDocument = async (document: KnowledgeDocumentRecord) => {
  await authorizedDownloadRequest(
    {
      method: 'get',
      url: `/knowledge-base/${document.id}/download/`,
    },
    document.fileName || `${document.title || 'knowledge-document'}.bin`,
  );
};

export const deleteKnowledgeDocument = async (id: number) => {
  await httpClient.delete(`/knowledge-base/${id}/`);
};

export const bulkDownloadKnowledgeDocuments = async (ids: number[]) => {
  await authorizedDownloadRequest(
    {
      method: 'post',
      url: '/knowledge-base/bulk-download/',
      data: { ids },
    },
    'knowledge-base.zip',
  );
};

export const fetchKnowledgeModelSettings = async () => {
  const response = await httpClient.get<KnowledgeModelSettings>('/settings/knowledge-base/models/');
  return response.data;
};

export const updateKnowledgeModelSettings = async (
  payload: Partial<{
    embedding: Partial<{ alias: string; model: string; baseUrl: string; apiKey: string; isActive: boolean; dimensions: number }>;
    rerank: Partial<{ alias: string; model: string; baseUrl: string; apiKey: string; isActive: boolean }>;
  }>,
) => {
  const response = await httpClient.patch<KnowledgeModelSettings>('/settings/knowledge-base/models/', payload);
  return response.data;
};

export const fetchTenantKnowledgeAuthorization = async (tenantId: number) => {
  const response = await httpClient.get<TenantKnowledgeAuthorization>(`/settings/knowledge-base/tenants/${tenantId}/authorization/`);
  return response.data;
};

export const updateTenantKnowledgeAuthorization = async (
  tenantId: number,
  payload: { embeddingModelId: number | null; rerankModelId: number | null; isActive: boolean },
) => {
  const response = await httpClient.put<TenantKnowledgeAuthorization>(
    `/settings/knowledge-base/tenants/${tenantId}/authorization/`,
    payload,
  );
  return response.data;
};
