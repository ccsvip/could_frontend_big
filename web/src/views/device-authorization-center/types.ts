import type { Dayjs } from 'dayjs';
import type { DeviceAuthorizationType } from '../../api/modules/devices';

export type BindForm = {
  tenantId: number;
  authorizationType: DeviceAuthorizationType;
  expiresAt?: Dayjs | null;
  isSoftwareTrial: boolean;
  isEnabled: boolean;
};

export type BindMode = 'bind' | 'authorize';

export type SelectOption<T extends string | number | null = number> = {
  label: string;
  value: T;
};
