import { httpClient } from '../client';

export type DeviceStatus = 'online' | 'offline';
export type DeviceAuthorizationType = 'permanent' | 'trial';
export type DeviceEnabledStatus = 'enabled' | 'disabled';

export type DeviceRecord = {
  id: string;
  recordId: number;
  deviceCode: string;
  name: string;
  location: string;
  tenantId: number | null;
  tenantName: string;
  status: DeviceStatus;
  groupId: number | null;
  groupName: string;
  applicationId: number | null;
  applicationName: string;
  agentApplicationId: number | null;
  agentApplicationName: string;
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
  ignoredAt: string | null;
  created_at: string;
  updated_at: string;
};

export type DeviceListQuery = {
  page?: number;
  keyword?: string;
  status?: DeviceStatus | 'all';
  enabledStatus?: DeviceEnabledStatus | 'all';
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
  name?: string;
  location?: string;
  applicationId?: number | null;
  groupId?: number | null;
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
  agentApplicationId: number | null;
  agentApplicationName: string;
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
  agentApplicationId?: number | null;
  resourceIds?: number[];
  scrollingTextIds?: number[];
  voiceToneIds?: number[];
  modelAssetIds?: number[];
  commandGroupIds?: number[];
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type DeviceAuthorizationRequestRecord = DeviceRecord & {
  bindingStatus: 'pending' | 'bound' | 'ignored';
  runtimeStatus: 'waiting_application' | 'waiting_agent' | 'ready';
  latestActivationAt: string | null;
  latestActivationMessage: string;
  latestActivationIp: string | null;
  latestActivationDeviceInfo: Record<string, unknown>;
};

export type DeviceActivationLogRecord = {
  id: number;
  code: string;
  action: 'activate' | 'bind' | 'ignore' | 'authorize' | 'revoke';
  result: boolean;
  message: string;
  tenantId: number | null;
  tenantName: string;
  applicationId: number | null;
  applicationName: string;
  agentApplicationId: number | null;
  agentApplicationName: string;
  deviceName: string;
  ipAddress: string | null;
  deviceInfo: Record<string, unknown>;
  createdAt: string;
};

export type DeviceChatLogRecord = {
  id: number;
  code: string;
  source: 'http' | 'websocket';
  tenantId: number | null;
  tenantName: string;
  applicationId: number | null;
  applicationName: string;
  agentApplicationId: number | null;
  agentApplicationName: string;
  deviceName: string;
  questionText: string;
  answerText: string;
  requestId: string;
  traceId: string;
  modelName: string;
  createdAt: string;
};

export type DeviceAuthorizationRequestQuery = {
  page?: number;
  bindingStatus?: 'pending' | 'bound' | 'ignored' | 'all';
  keyword?: string;
  tenantId?: number;
};

export type DeviceBindPayload = {
  tenantId: number;
  authorizationType?: DeviceAuthorizationType;
  expiresAt?: string | null;
  isEnabled?: boolean;
};

const normalizeList = <T>(value: PaginatedResponse<T> | T[]): PaginatedResponse<T> => {
  if (Array.isArray(value)) {
    return { count: value.length, next: null, previous: null, results: value };
  }
  return value;
};

const buildDeviceParams = (query?: DeviceListQuery) => ({
  page: query?.page,
  keyword: query?.keyword || undefined,
  status: query?.status && query.status !== 'all' ? query.status : undefined,
  enabledStatus: query?.enabledStatus && query.enabledStatus !== 'all' ? query.enabledStatus : undefined,
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

export const deleteDevice = async (deviceCode: string) => {
  await httpClient.delete(`/devices/${encodeURIComponent(deviceCode)}/`);
};

export const fetchDeviceAuthorizationRequests = async (query?: DeviceAuthorizationRequestQuery) => {
  const response = await httpClient.get<PaginatedResponse<DeviceAuthorizationRequestRecord>>(
    '/device-authorization-requests/',
    {
      params: {
        page: query?.page,
        bindingStatus: query?.bindingStatus && query.bindingStatus !== 'all' ? query.bindingStatus : undefined,
        keyword: query?.keyword || undefined,
        tenantId: query?.tenantId,
      },
    },
  );
  return response.data;
};

export const fetchDeviceAuthorizations = async (query?: { page?: number; keyword?: string; tenantId?: number }) => {
  const response = await httpClient.get<PaginatedResponse<DeviceAuthorizationRequestRecord>>(
    '/device-authorization-requests/authorizations/',
    { params: query },
  );
  return response.data;
};

export const updateDeviceAuthorizationRequestName = async (deviceCode: string, name: string) => {
  const response = await httpClient.patch<DeviceAuthorizationRequestRecord>(
    `/device-authorization-requests/${encodeURIComponent(deviceCode)}/name/`,
    { name },
  );
  return response.data;
};

export const fetchDeviceActivationLogs = async (query?: { page?: number; keyword?: string; tenantId?: number }) => {
  const response = await httpClient.get<PaginatedResponse<DeviceActivationLogRecord>>(
    '/device-authorization-requests/logs/',
    { params: query },
  );
  return response.data;
};

export const fetchDeviceChatLogs = async (query?: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  tenantId?: number;
  agentApplicationId?: number;
}) => {
  const response = await httpClient.get<PaginatedResponse<DeviceChatLogRecord>>('/devices/chat-logs/', {
    params: {
      page: query?.page,
      page_size: query?.pageSize,
      keyword: query?.keyword || undefined,
      tenantId: query?.tenantId,
      agentApplicationId: query?.agentApplicationId,
    },
  });
  return response.data;
};

export const bindDeviceAuthorizationRequest = async (deviceCode: string, payload: DeviceBindPayload) => {
  const response = await httpClient.post<DeviceAuthorizationRequestRecord>(
    `/device-authorization-requests/${encodeURIComponent(deviceCode)}/bind/`,
    payload,
  );
  return response.data;
};

export const ignoreDeviceAuthorizationRequest = async (deviceCode: string) => {
  const response = await httpClient.post<DeviceAuthorizationRequestRecord>(
    `/device-authorization-requests/${encodeURIComponent(deviceCode)}/ignore/`,
  );
  return response.data;
};

export const authorizeDevice = async (deviceCode: string, payload: DeviceBindPayload) => {
  const response = await httpClient.post<DeviceAuthorizationRequestRecord>(
    `/device-authorization-requests/${encodeURIComponent(deviceCode)}/authorize/`,
    payload,
  );
  return response.data;
};

export const revokeDeviceAuthorization = async (deviceCode: string) => {
  const response = await httpClient.post<DeviceAuthorizationRequestRecord>(
    `/device-authorization-requests/${encodeURIComponent(deviceCode)}/revoke/`,
  );
  return response.data;
};

export const fetchDeviceGroups = async (params?: { tenant?: number }) => {
  const response = await httpClient.get<PaginatedResponse<DeviceGroupRecord> | DeviceGroupRecord[]>('/device-groups/', {
    params,
  });
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

export const deleteDeviceGroup = async (id: number) => {
  await httpClient.delete(`/device-groups/${id}/`);
};

export const fetchDeviceApplications = async (params?: { tenant?: number }) => {
  const response = await httpClient.get<PaginatedResponse<DeviceApplicationRecord> | DeviceApplicationRecord[]>(
    '/device-applications/',
    { params },
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
