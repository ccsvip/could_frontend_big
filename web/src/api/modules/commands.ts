import { httpClient } from '../client';

export type CommandGroupType = 'control' | 'task';
export type CommandCallMethod = 'UDP' | 'TCP';
export type CommandValueType = 'string' | 'hex' | 'ascii';
export type ControlCommandReplyStrategy = 'fixed' | 'generated';
export type TaskStepType = 'command' | 'text' | 'image' | 'video' | 'navigation';

export type CommandGroupRecord = {
  id: number;
  name: string;
  groupType: CommandGroupType;
  groupTypeLabel: string;
  exportEnabled: boolean;
  isActive: boolean;
  created_at: string;
  updated_at: string;
};

export type CommandGroupPayload = {
  name: string;
  groupType: CommandGroupType;
  exportEnabled: boolean;
  isActive: boolean;
};

export type CommandGroupListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  groupType?: CommandGroupType | 'all';
  isActive?: 'all' | 'active' | 'inactive';
};

export type ControlCommandRecord = {
  id: number;
  groupId: number;
  groupName: string;
  name: string;
  command: string;
  commandValueType: CommandValueType;
  ip: string;
  port: number;
  callMethod: CommandCallMethod;
  backendSendEnabled: boolean;
  executionReply: string;
  replyStrategy: ControlCommandReplyStrategy;
  isActive: boolean;
  created_at: string;
  updated_at: string;
};

export type ControlCommandPayload = {
  groupId: number;
  name: string;
  command: string;
  commandValueType: CommandValueType;
  ip: string;
  port: number;
  callMethod: CommandCallMethod;
  backendSendEnabled: boolean;
  executionReply: string;
  replyStrategy: ControlCommandReplyStrategy;
  isActive: boolean;
};

export type ControlCommandListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  groupId?: number | 'all';
  isActive?: 'all' | 'active' | 'inactive';
};

export type ControlCommandRecognitionPolicy = {
  fixedExecutionReply: string;
  directExecutionThreshold: string;
  llmConfirmationThreshold: string;
};

export type ControlCommandRecognitionPolicyPayload = Partial<ControlCommandRecognitionPolicy>;

export type TaskCommandStepRecord = {
  id: number;
  order: number;
  type: TaskStepType;
  delaySeconds: number;
  waitForInnerTasks?: boolean;
  isShow?: boolean;
  controlCommandId?: number | null;
  pointId?: number | null;
  resourceId?: number | null;
  text?: string;
  imageText?: string;
  innerTasks?: TaskCommandStepRecord[];
  content: Record<string, unknown>;
};

export type TaskCommandStepPayload = {
  order: number;
  type: TaskStepType;
  delaySeconds?: number;
  waitForInnerTasks?: boolean;
  isShow?: boolean;
  controlCommandId?: number | null;
  pointId?: number | null;
  resourceId?: number | null;
  text?: string;
  imageText?: string;
  innerTasks?: TaskCommandStepPayload[];
};

export type TaskCommandRecord = {
  id: number;
  groupId: number;
  groupName: string;
  name: string;
  command: string;
  isActive: boolean;
  tasks: TaskCommandStepRecord[];
  created_at: string;
  updated_at: string;
};

export type TaskCommandPayload = {
  groupId: number;
  name: string;
  command: string;
  isActive: boolean;
  tasks: TaskCommandStepPayload[];
};

export type TaskCommandListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  groupId?: number | 'all';
  isActive?: 'all' | 'active' | 'inactive';
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

const buildActiveParam = (value?: 'all' | 'active' | 'inactive') => {
  if (value === 'active') return 'true';
  if (value === 'inactive') return 'false';
  return undefined;
};

const buildGroupParams = (query?: CommandGroupListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  keyword: query?.keyword || undefined,
  group_type: query?.groupType && query.groupType !== 'all' ? query.groupType : undefined,
  is_active: buildActiveParam(query?.isActive),
});

const buildCommandParams = (query?: ControlCommandListQuery | TaskCommandListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  keyword: query?.keyword || undefined,
  group_id: query?.groupId && query.groupId !== 'all' ? query.groupId : undefined,
  is_active: buildActiveParam(query?.isActive),
});

export const fetchCommandGroups = async (query?: CommandGroupListQuery) => {
  const response = await httpClient.get<PaginatedResponse<CommandGroupRecord>>('/commands/groups/', {
    params: buildGroupParams(query),
  });
  return response.data;
};

export const createCommandGroup = async (payload: CommandGroupPayload) => {
  const response = await httpClient.post<CommandGroupRecord>('/commands/groups/', payload);
  return response.data;
};

export const updateCommandGroup = async (id: number, payload: Partial<CommandGroupPayload>) => {
  const response = await httpClient.patch<CommandGroupRecord>(`/commands/groups/${id}/`, payload);
  return response.data;
};

export const deleteCommandGroup = async (id: number) => {
  await httpClient.delete(`/commands/groups/${id}/`);
};

export const fetchControlCommands = async (query?: ControlCommandListQuery) => {
  const response = await httpClient.get<PaginatedResponse<ControlCommandRecord>>('/commands/control/', {
    params: buildCommandParams(query),
  });
  return response.data;
};

export const createControlCommand = async (payload: ControlCommandPayload) => {
  const response = await httpClient.post<ControlCommandRecord>('/commands/control/', payload);
  return response.data;
};

export const updateControlCommand = async (id: number, payload: Partial<ControlCommandPayload>) => {
  const response = await httpClient.patch<ControlCommandRecord>(`/commands/control/${id}/`, payload);
  return response.data;
};

export const deleteControlCommand = async (id: number) => {
  await httpClient.delete(`/commands/control/${id}/`);
};

export const fetchControlCommandRecognitionPolicy = async () => {
  const response = await httpClient.get<ControlCommandRecognitionPolicy>('/commands/control-recognition-policy/');
  return response.data;
};

export const updateControlCommandRecognitionPolicy = async (payload: ControlCommandRecognitionPolicyPayload) => {
  const response = await httpClient.patch<ControlCommandRecognitionPolicy>('/commands/control-recognition-policy/', payload);
  return response.data;
};

export const restoreControlCommandRecognitionPolicyDefaults = async () => {
  await httpClient.delete('/commands/control-recognition-policy/');
};

export const fetchTaskCommands = async (query?: TaskCommandListQuery) => {
  const response = await httpClient.get<PaginatedResponse<TaskCommandRecord>>('/commands/tasks/', {
    params: buildCommandParams(query),
  });
  return response.data;
};

export const createTaskCommand = async (payload: TaskCommandPayload) => {
  const response = await httpClient.post<TaskCommandRecord>('/commands/tasks/', payload);
  return response.data;
};

export const updateTaskCommand = async (id: number, payload: Partial<TaskCommandPayload>) => {
  const response = await httpClient.patch<TaskCommandRecord>(`/commands/tasks/${id}/`, payload);
  return response.data;
};

export const deleteTaskCommand = async (id: number) => {
  await httpClient.delete(`/commands/tasks/${id}/`);
};

export const exportEnabledCommandGroups = async () => {
  const response = await httpClient.get<{ status: string; message: string; data: CommandGroupRecord[] }>('/commands/export/enabled-groups/');
  return response.data.data;
};

export const exportAllCommands = async () => {
  const response = await httpClient.get<{
    status: string;
    message: string;
    data: {
      controlCommands: ControlCommandRecord[];
      taskCommands: TaskCommandRecord[];
    };
  }>('/commands/export/commands/');
  return response.data.data;
};
