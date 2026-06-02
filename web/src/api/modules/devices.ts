import { httpClient } from '../client';

export type DeviceStatus = 'online' | 'offline';
export type DeviceAuthorizationType = 'permanent' | 'trial';

export type DeviceRecord = {
  id: string;
  deviceCode: string;
  name: string;
  location: string;
  status: DeviceStatus;
  groupId: number | null;
  groupName: string;
  applicationId: number | null;
  applicationName: string;
  authorizationType: DeviceAuthorizationType;
  authorizationTypeLabel: string;
  expiresAt: string | null;
  softwareVersion: string;
  systemVersion: string;
  mainboardInfo: string;
  isEnabled: boolean;
  registeredAt: string | null;
  lastAuthAt: string | null;
  lastHeartbeat: string | null;
  created_at: string;
  updated_at: string;
};

export type DeviceListQuery = {
  keyword?: string;
  status?: DeviceStatus | 'all';
  groupId?: number | 'all';
  applicationId?: number | 'all';
  authorizationType?: DeviceAuthorizationType | 'all';
};

export type DeviceListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: DeviceRecord[];
};

export type DeviceStatsResponse = {
  total: number;
  online: number;
  offline: number;
  trial: number;
  permanent: number;
};

export type DeviceUpdatePayload = {
  name: string;
  groupId?: number | null;
  isEnabled?: boolean;
  authorizationType?: DeviceAuthorizationType;
  expiresAt?: string | null;
};

export type DeviceGroupRecord = {
  id: number;
  name: string;
  remark: string;
  created_at: string;
  updated_at: string;
};

export type DeviceGroupPayload = {
  name: string;
  remark?: string;
};

export type DeviceApplicationRecord = {
  id: number;
  name: string;
  code: string;
  description: string;
  isActive: boolean;
  resourceIds: number[];
  scrollingTextIds: number[];
  voiceToneIds: number[];
  modelAssetIds: number[];
  commandGroupIds: number[];
  created_at: string;
  updated_at: string;
};

export type DeviceApplicationPayload = {
  name: string;
  code: string;
  description?: string;
  isActive: boolean;
  resourceIds?: number[];
  scrollingTextIds?: number[];
  voiceToneIds?: number[];
  modelAssetIds?: number[];
  commandGroupIds?: number[];
};

export type DeviceAuthorizationCodeStatus = 'unused' | 'used' | 'disabled';

export type DeviceAuthorizationCodeRecord = {
  id: number;
  code: string;
  status: DeviceAuthorizationCodeStatus;
  applicationId: number;
  applicationName: string;
  authorizationType: DeviceAuthorizationType;
  authorizationTypeLabel: string;
  expiresAt: string | null;
  usedAt: string | null;
  usedDeviceCode: string;
  remark: string;
  created_at: string;
  updated_at: string;
};

export type DeviceAuthorizationCodePayload = {
  code: string;
  applicationId: number;
  authorizationType: DeviceAuthorizationType;
  expiresAt?: string | null;
  remark?: string;
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

const normalizeList = <T>(value: PaginatedResponse<T> | T[]): PaginatedResponse<T> => {
  if (Array.isArray(value)) {
    return { count: value.length, next: null, previous: null, results: value };
  }
  return value;
};

const buildDeviceParams = (query?: DeviceListQuery) => ({
  keyword: query?.keyword || undefined,
  status: query?.status && query.status !== 'all' ? query.status : undefined,
  groupId: query?.groupId && query.groupId !== 'all' ? query.groupId : undefined,
  applicationId: query?.applicationId && query.applicationId !== 'all' ? query.applicationId : undefined,
  authorizationType:
    query?.authorizationType && query.authorizationType !== 'all' ? query.authorizationType : undefined,
});

export const fetchDevices = async (query?: DeviceListQuery) => {
  const response = await httpClient.get<DeviceListResponse>('/devices/', { params: buildDeviceParams(query) });
  return response.data;
};

export const fetchDeviceStats = async () => {
  const response = await httpClient.get<DeviceStatsResponse>('/devices/stats/');
  return response.data;
};

export const updateDevice = async (deviceCode: string, payload: DeviceUpdatePayload) => {
  const response = await httpClient.patch<DeviceRecord>(`/devices/${encodeURIComponent(deviceCode)}/`, payload);
  return response.data;
};

export const fetchDeviceGroups = async () => {
  const response = await httpClient.get<PaginatedResponse<DeviceGroupRecord> | DeviceGroupRecord[]>('/device-groups/');
  return normalizeList(response.data);
};

export const createDeviceGroup = async (payload: DeviceGroupPayload) => {
  const response = await httpClient.post<DeviceGroupRecord>('/device-groups/', payload);
  return response.data;
};

export const updateDeviceGroup = async (id: number, payload: DeviceGroupPayload) => {
  const response = await httpClient.patch<DeviceGroupRecord>(`/device-groups/${id}/`, payload);
  return response.data;
};

export const fetchDeviceApplications = async () => {
  const response = await httpClient.get<PaginatedResponse<DeviceApplicationRecord> | DeviceApplicationRecord[]>(
    '/device-applications/',
  );
  return normalizeList(response.data);
};

export const createDeviceApplication = async (payload: DeviceApplicationPayload) => {
  const response = await httpClient.post<DeviceApplicationRecord>('/device-applications/', payload);
  return response.data;
};

export const updateDeviceApplication = async (id: number, payload: DeviceApplicationPayload) => {
  const response = await httpClient.patch<DeviceApplicationRecord>(`/device-applications/${id}/`, payload);
  return response.data;
};

export const fetchDeviceAuthorizationCodes = async () => {
  const response = await httpClient.get<
    PaginatedResponse<DeviceAuthorizationCodeRecord> | DeviceAuthorizationCodeRecord[]
  >('/device-authorization-codes/');
  return normalizeList(response.data);
};

export const createDeviceAuthorizationCode = async (payload: DeviceAuthorizationCodePayload) => {
  const response = await httpClient.post<DeviceAuthorizationCodeRecord>('/device-authorization-codes/', payload);
  return response.data;
};
