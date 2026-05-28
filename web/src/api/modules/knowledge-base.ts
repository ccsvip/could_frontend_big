import axios, { type AxiosProgressEvent } from 'axios';
import { message } from 'antd';
import { API_BASE_URL, handleUnauthorizedResponse, httpClient } from '../client';

export type KnowledgeDocumentStatus = 'pending' | 'approved' | 'rejected';

export type KnowledgeDocumentRecord = {
  id: number;
  title: string;
  description: string;
  fileName: string;
  fileExtension: string;
  fileSize: number | null;
  processingStatus: KnowledgeDocumentStatus;
  processingStatusLabel: string;
  processingResult: string;
  uploadedBy: string;
  downloadCount: number;
  created_at: string;
  updated_at: string;
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
  processingStatus?: KnowledgeDocumentStatus | 'all';
};

export type KnowledgeDocumentUploadPayload = {
  file: File;
  title?: string;
  description?: string;
};

export type KnowledgeDocumentUploadOptions = {
  onUploadProgress?: (percent: number) => void;
  timeoutMs?: number;
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
  processing_status:
    query?.processingStatus && query.processingStatus !== 'all'
      ? query.processingStatus
      : undefined,
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

