import { httpClient } from '../client';

export type MinioSettingsRecord = {
  storageBackend: 'local' | 'r2';
  endpoint: string;
  accessKey: string;
  bucketName: string;
  secure: boolean;
  region: string;
  publicBaseUrl: string;
  r2AccountId: string;
  r2AccessKeyId: string;
  r2BucketName: string;
  r2PublicBaseUrl: string;
  videoMaxSizeMB: number;
  allowVideoCloudUrl: boolean;
  isActive: boolean;
  updated_at: string;
};

export type MinioSettingsPayload = Partial<Omit<MinioSettingsRecord, 'updated_at'>> & {
  secretKey?: string;
  r2SecretAccessKey?: string;
};

export type TenantVideoQuotaRecord = {
  tenantId: number;
  tenantName: string;
  tenantCode: string;
  quotaLimited: boolean;
  quotaMB: number | null;
  usedBytes: number;
  usedMB: number;
  remainingBytes: number | null;
  remainingMB: number | null;
  updated_at: string;
};

export type TenantVideoQuotaListResponse = {
  results: TenantVideoQuotaRecord[];
};

export type TenantVideoQuotaPayload = {
  items: Array<{
    tenantId: number;
    quotaLimited: boolean;
    quotaMB: number | null;
  }>;
};

export const fetchMinioSettings = async () => {
  const response = await httpClient.get<MinioSettingsRecord>('/settings/minio/');
  return response.data;
};

export const updateMinioSettings = async (payload: MinioSettingsPayload) => {
  const response = await httpClient.patch<MinioSettingsRecord>('/settings/minio/', payload);
  return response.data;
};

export const fetchTenantVideoQuotas = async () => {
  const response = await httpClient.get<TenantVideoQuotaListResponse>('/settings/minio/quotas/');
  return response.data;
};

export const updateTenantVideoQuotas = async (payload: TenantVideoQuotaPayload) => {
  const response = await httpClient.patch<TenantVideoQuotaListResponse>('/settings/minio/quotas/', payload);
  return response.data;
};
