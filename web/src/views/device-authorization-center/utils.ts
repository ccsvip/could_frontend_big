import type { TenantRecord } from '../../api/modules/tenants';
import type { BindForm } from './types';

export const buildBindPayload = (values: BindForm) => ({
  tenantId: values.tenantId,
  authorizationType: values.authorizationType,
  expiresAt: values.authorizationType === 'trial' ? values.expiresAt?.toISOString() : null,
  isEnabled: values.isEnabled,
});

export const buildTenantOptions = (tenants: TenantRecord[]) => tenants.map((item) => ({ label: item.name, value: item.id }));

export const getInfoText = (info: Record<string, unknown>, key: string) => {
  const value = info[key];
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
};
