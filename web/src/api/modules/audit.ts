import { httpClient } from '../client';

export type OperationLogAction = 'create' | 'update' | 'delete';

// 字段命名与 backend/apps/audit/serializers.py 的 OperationLogSerializer 一一对应（camelCase 由后端序列化器输出）。
export type OperationLogRecord = {
  id: number;
  actor: number | null;
  actorUsername: string;
  actorDisplayName: string;
  actorRoleName: string;
  tenant: number | null;
  tenantName: string | null;
  action: OperationLogAction;
  method: string;
  path: string;
  description: string;
  statusCode: number;
  createdAt: string;
};

export type OperationLogListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: OperationLogRecord[];
};

export type FetchOperationLogsParams = {
  page?: number;
  tenant?: number;
};

export const fetchOperationLogs = async (params?: FetchOperationLogsParams) => {
  const response = await httpClient.get<OperationLogListResponse>('/audit/logs/', { params });
  return response.data;
};

export const clearOperationLogs = async () => {
  const response = await httpClient.delete<{ deleted: number }>('/audit/logs/clear/');
  return response.data;
};
