import type { AxiosProgressEvent } from 'axios';
import { httpClient } from '../client';

export type AppReleaseRecord = {
  releaseId: string;
  packageName: string;
  versionName: string;
  versionCode: number;
  versionInfo: string;
  fileName: string;
  downloadUrl: string;
  fileSize: number;
  sha256: string;
  forceUpgradeVersionCode: number;
  releaseNotes: string;
  isActive: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
};

export type AppReleaseListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: AppReleaseRecord[];
};

export type CreateAppReleasePayload = {
  versionName: string;
  versionCode: number;
  versionInfo: string;
  apkFile: File;
  forceUpgradeVersionCode: number;
  releaseNotes: string;
  isActive: boolean;
};

export const fetchAppReleases = async () => {
  const response = await httpClient.get<AppReleaseListResponse>('/app-update-releases/', {
    params: { page_size: 100 },
  });
  return response.data;
};

export const createAppRelease = async (
  payload: CreateAppReleasePayload,
  onUploadProgress?: (percent: number) => void,
) => {
  const formData = new FormData();
  formData.append('versionName', payload.versionName);
  formData.append('versionCode', String(payload.versionCode));
  formData.append('versionInfo', payload.versionInfo);
  formData.append('apkFile', payload.apkFile);
  formData.append('forceUpgradeVersionCode', String(payload.forceUpgradeVersionCode));
  formData.append('releaseNotes', payload.releaseNotes);
  formData.append('isActive', String(payload.isActive));

  const response = await httpClient.post<AppReleaseRecord>('/app-update-releases/', formData, {
    timeout: 0,
    onUploadProgress: (event: AxiosProgressEvent) => {
      const total = event.total ?? payload.apkFile.size;
      const percent = total > 0 ? Math.round((event.loaded / total) * 100) : 0;
      onUploadProgress?.(Math.max(0, Math.min(100, percent)));
    },
  });
  return response.data;
};

export const updateAppReleaseActive = async (releaseId: string, isActive: boolean) => {
  const response = await httpClient.patch<AppReleaseRecord>(`/app-update-releases/${releaseId}/`, { isActive });
  return response.data;
};

