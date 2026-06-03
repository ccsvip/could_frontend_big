import { httpClient } from '../client';

export type TenantRecord = {
  id: number;
  name: string;
  code: string;
  isActive: boolean;
  isLegacy: boolean;
  menuCount: number;
  memberCount: number;
  created_at: string;
  updated_at: string;
};

export type TenantListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: TenantRecord[];
};

export type MenuCatalogItem = {
  id: number;
  name: string;
  key: string;
  path: string;
  icon: string;
  parent: number | null;
  sort_order: number;
};

export type PermissionPointCatalogItem = {
  id: number;
  name: string;
  code: string;
  module: string;
};

export type MenuCatalogResponse = {
  menus: MenuCatalogItem[];
  permissionPoints: PermissionPointCatalogItem[];
};

export type TenantMenuSelection = {
  menuIds: number[];
  permissionPointIds: number[];
};

export const fetchTenants = async (params?: { page?: number; page_size?: number; include_hidden?: boolean }) => {
  const response = await httpClient.get<TenantListResponse>('/tenants/', { params });
  return response.data;
};

export const createTenant = async (payload: { name: string }) => {
  const response = await httpClient.post<TenantRecord>('/tenants/', payload);
  return response.data;
};

export const updateTenant = async (id: number, payload: { name?: string; isActive?: boolean }) => {
  const response = await httpClient.patch<TenantRecord>(`/tenants/${id}/`, payload);
  return response.data;
};

export const fetchMenuCatalog = async () => {
  const response = await httpClient.get<MenuCatalogResponse>('/menus/catalog/');
  return response.data;
};

export const fetchTenantMenuSelection = async (id: number) => {
  const response = await httpClient.get<TenantMenuSelection>(`/tenants/${id}/menus/`);
  return response.data;
};

export const assignTenantMenus = async (id: number, payload: TenantMenuSelection) => {
  const response = await httpClient.put<TenantRecord>(`/tenants/${id}/menus/`, payload);
  return response.data;
};
