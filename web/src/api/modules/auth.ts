import { httpClient, type ApiResponse } from '../client';
import type { AppMenu, AppRole } from '../../store/auth';

export type LoginPayload = {
  username: string;
  password: string;
};

export type CurrentUser = {
  id: number;
  username: string;
  display_name: string;
  role: AppRole;
  permissions: string[];
  menus: AppMenu[];
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: CurrentUser;
  message: string;
};

export type AccountApplicationPayload = {
  username: string;
  applicantName: string;
  enterpriseName: string;
  phone: string;
  password: string;
  confirmPassword: string;
  reason: string;
};

export type AccountApplicationRecord = {
  id: number;
  username: string;
  applicantName: string;
  enterpriseName: string;
  phone: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
};

export type AccountApplicationListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: AccountApplicationRecord[];
};

export type AccountApplicationStatusPayload = {
  status: 'approved' | 'rejected';
};

export type ChangePasswordPayload = {
  oldPassword: string;
  newPassword: string;
};

export const loginRequest = async (payload: LoginPayload) => {
  const response = await httpClient.post<LoginResponse>('/auth/login/', payload);
  return response.data;
};

export const fetchCurrentUser = async () => {
  const response = await httpClient.get<CurrentUser>('/auth/me/');
  return response.data;
};

export const applyAccountRequest = async (payload: AccountApplicationPayload) => {
  const response = await httpClient.post<ApiResponse<AccountApplicationRecord>>('/auth/account-applications/', payload);
  return response.data;
};

export const fetchAccountApplications = async () => {
  const response = await httpClient.get<AccountApplicationListResponse>('/auth/account-applications/manage/');
  return response.data;
};

export const updateAccountApplicationStatus = async (id: number, payload: AccountApplicationStatusPayload) => {
  const response = await httpClient.patch<ApiResponse<AccountApplicationRecord>>(`/auth/account-applications/manage/${id}/`, payload);
  return response.data;
};

export const changePasswordRequest = async (payload: ChangePasswordPayload) => {
  const response = await httpClient.post<ApiResponse>('/auth/change-password/', payload);
  return response.data;
};
