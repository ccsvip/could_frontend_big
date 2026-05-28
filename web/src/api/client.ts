import axios from 'axios';
import { message } from 'antd';
import { useAuthStore } from '../store/auth';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export type ApiResponse<T = unknown> = {
  status: 'success' | 'error';
  message: string;
  data?: T;
  code?: number;
};

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

const normalizeDevMediaUrl = (value: string) => {
  if (!import.meta.env.DEV) {
    return value;
  }

  try {
    const url = new URL(value);
    if (
      url.pathname.startsWith('/media/') &&
      (url.hostname === 'backend' || (typeof window !== 'undefined' && url.origin === window.location.origin))
    ) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
  } catch {
    // Keep non-URL strings unchanged.
  }

  return value;
};

const normalizeDevMediaUrls = (value: unknown): unknown => {
  if (!import.meta.env.DEV) {
    return value;
  }

  if (typeof value === 'string') {
    return normalizeDevMediaUrl(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => normalizeDevMediaUrls(item));
  }

  if (value && typeof value === 'object') {
    let changed = false;
    const normalized: Record<string, unknown> = {};

    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      const nextItem = normalizeDevMediaUrls(item);
      normalized[key] = nextItem;
      if (nextItem !== item) {
        changed = true;
      }
    });

    return changed ? normalized : value;
  }

  return value;
};

const clearAuth = () => {
  useAuthStore.getState().clearAuth();
};

export const handleUnauthorizedResponse = () => {
  clearAuth();
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};

httpClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

httpClient.interceptors.response.use(
  (response) => {
    response.data = normalizeDevMediaUrls(response.data);
    const data = response.data as ApiResponse;
    if (data.status === 'success' && data.message) {
      // message.success(data.message);
    }
    return response;
  },
  (error) => {
    if (error?.response?.status === 401) {
      handleUnauthorizedResponse();
    }

    const errorData = error?.response?.data as ApiResponse | undefined;
    const errorMessage = errorData?.message || error?.response?.data?.detail || '请求失败，请稍后重试';

    message.error(errorMessage);
    return Promise.reject(error);
  },
);
