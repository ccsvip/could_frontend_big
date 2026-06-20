import type { AgentApplicationRecord } from '../../api/modules/applications';
import type { DeviceApplicationRecord, DeviceGroupRecord } from '../../api/modules/devices';
import type { TenantRecord } from '../../api/modules/tenants';
import type { BindForm } from './types';

export const buildBindPayload = (values: BindForm) => ({
  tenantId: values.tenantId,
  applicationId: values.applicationId ?? null,
  agentApplicationId: values.agentApplicationId ?? null,
  groupId: values.groupId ?? null,
  authorizationType: values.authorizationType,
  expiresAt: values.authorizationType === 'trial' ? values.expiresAt?.toISOString() : null,
  isEnabled: values.isEnabled,
});

export const buildTenantOptions = (tenants: TenantRecord[]) => tenants.map((item) => ({ label: item.name, value: item.id }));

export const buildApplicationOptions = (applications: DeviceApplicationRecord[]) => [
  { label: '暂不绑定资源应用', value: null as number | null },
  ...applications.map((item) => ({ label: item.name, value: item.id })),
];

export const buildAgentApplicationOptions = (agentApplications: AgentApplicationRecord[]) => [
  { label: '请选择智能体', value: null as number | null },
  ...agentApplications.map((item) => ({ label: item.name, value: item.id })),
];

export const buildGroupOptions = (groups: DeviceGroupRecord[]) => [
  { label: '暂不分组', value: null as number | null },
  ...groups.map((item) => ({ label: item.name, value: item.id })),
];

export const getInfoText = (info: Record<string, unknown>, key: string) => {
  const value = info[key];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
};
