import axios from 'axios';
import { message } from 'antd';
import { useAuthStore } from '../store/auth';
import { useTenantScopeStore } from '../store/tenant-scope';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const normalizeMediaAssetUrl = (value: string) => {
  const raw = String(value || '').trim();
  if (!raw) return '';

  let apiOrigin = '';
  try {
    apiOrigin = new URL(API_BASE_URL).origin;
  } catch {
    apiOrigin = '';
  }

  if (raw.startsWith('/media/')) {
    return apiOrigin ? `${apiOrigin}${raw}` : raw;
  }

  try {
    const url = new URL(raw);
    if (
      apiOrigin
      && typeof window !== 'undefined'
      && url.origin === window.location.origin
      && url.pathname.startsWith('/media/')
    ) {
      return `${apiOrigin}${url.pathname}${url.search}${url.hash}`;
    }
  } catch {
    // Keep non-URL strings unchanged unless they are explicit /media paths.
  }

  return raw;
};

// 平台超管「按公司浏览」时，仅业务列表接口允许追加 ?tenant=<id>。
// 显式白名单避免给 /auth、/tenants、/audit、/menus 等管理类接口注入。
const TENANT_SCOPED_PREFIXES = [
  '/devices',
  '/device-groups',
  '/device-applications',
  '/resources',
  '/knowledge-base',
  '/knowledge-bases',
  '/commands',
  '/ai-models',
];

const isTenantScopedUrl = (url?: string): boolean => {
  if (!url) {
    return false;
  }
  // baseURL 为 /api/v1，业务调用传入的 url 形如 '/devices/'；统一取 pathname 后按前缀匹配。
  const path = url.startsWith('http')
    ? (() => {
        try {
          return new URL(url).pathname.replace(/^\/api\/v1/, '');
        } catch {
          return url;
        }
      })()
    : url;
  return TENANT_SCOPED_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
};

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

  // 用 getState() 实时读取作用域，避免订阅闭包陈旧。仅当存在公司作用域且命中业务接口白名单时注入。
  const tenantId = useTenantScopeStore.getState().tenantId;
  if (tenantId != null && isTenantScopedUrl(config.url)) {
    // 合并已有 params，不覆盖业务自身传入的 tenant（理论上不会有，仍保守保护）。
    const existing = (config.params as Record<string, unknown> | undefined) ?? {};
    if (existing.tenant == null) {
      config.params = { ...existing, tenant: tenantId };
    }
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
      return Promise.reject(error);
    }

    const errorData = error?.response?.data as ApiResponse | undefined;
    const errorMessage = errorData?.message || error?.response?.data?.detail || '请求失败，请稍后重试';

    message.error(errorMessage);
    return Promise.reject(error);
  },
);
