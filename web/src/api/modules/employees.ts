import { httpClient } from '../client';
import type { MenuCatalogResponse } from './tenants';

export type EmployeeRecord = {
  id: number;
  username: string;
  displayName: string;
  isActive: boolean;
  mustChangePassword: boolean;
  roleId: number | null;
  roleName: string | null;
  created_at: string;
};

export type EmployeeListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: EmployeeRecord[];
};

export type TenantRoleRecord = {
  id: number;
  name: string;
  code: string;
  description: string;
  isActive: boolean;
  menuIds: number[];
  permissionPointIds: number[];
  created_at: string;
  updated_at: string;
};

export type TenantRoleListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: TenantRoleRecord[];
};

export const fetchEmployees = async (params?: { page?: number; page_size?: number }) => {
  const response = await httpClient.get<EmployeeListResponse>('/employees/', { params });
  return response.data;
};

export const createEmployee = async (payload: {
  username: string;
  displayName: string;
  password: string;
  roleName: string;
}) => {
  const response = await httpClient.post<EmployeeRecord>('/employees/', payload);
  return response.data;
};

export const updateEmployee = async (
  id: number,
  payload: { username?: string; displayName?: string; roleName?: string; isActive?: boolean },
) => {
  const response = await httpClient.patch<EmployeeRecord>(`/employees/${id}/`, payload);
  return response.data;
};

export const deleteEmployee = async (id: number) => {
  const response = await httpClient.delete(`/employees/${id}/`);
  return response.data;
};

export const resetEmployeePassword = async (id: number, newPassword: string) => {
  const response = await httpClient.post(`/employees/${id}/reset-password/`, { newPassword });
  return response.data;
};

export const fetchTenantRoles = async () => {
  const response = await httpClient.get<TenantRoleListResponse>('/roles/');
  return response.data;
};

export const createTenantRole = async (payload: {
  name: string;
  code: string;
  description?: string;
  menuIds?: number[];
  permissionPointIds?: number[];
}) => {
  const response = await httpClient.post<TenantRoleRecord>('/roles/', payload);
  return response.data;
};

export const updateTenantRole = async (
  id: number,
  payload: { name?: string; description?: string; isActive?: boolean; menuIds?: number[]; permissionPointIds?: number[] },
) => {
  const response = await httpClient.patch<TenantRoleRecord>(`/roles/${id}/`, payload);
  return response.data;
};

export const deleteTenantRole = async (id: number) => {
  const response = await httpClient.delete(`/roles/${id}/`);
  return response.data;
};

export const fetchMyTenantCatalog = async () => {
  const response = await httpClient.get<MenuCatalogResponse>('/my-tenant/catalog/');
  return response.data;
};
