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

export const getInfoText = (info: Record<string, unknown>, key: string) => {
  const value = info[key];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
};
