import type { Dayjs } from 'dayjs';
import type { DeviceAuthorizationType } from '../../api/modules/devices';

export type BindForm = {
  tenantId: number;
  applicationId?: number | null;
  agentApplicationId?: number | null;
  groupId?: number | null;
  authorizationType: DeviceAuthorizationType;
  expiresAt?: Dayjs | null;
  isEnabled: boolean;
};

export type BindMode = 'bind' | 'authorize';
