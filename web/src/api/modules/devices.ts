import { httpClient } from '../client';

export type DeviceRecord = {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline' | 'maintaining';
  lastHeartbeat: string;
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
  maintaining: number;
};

export const fetchDevices = async () => {
  const response = await httpClient.get<DeviceListResponse>('/devices/');
  return response.data;
};

export const fetchDeviceStats = async () => {
  const response = await httpClient.get<DeviceStatsResponse>('/devices/stats/');
  return response.data;
};

export type CreateDevicePayload = {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline' | 'maintaining';
};

export const createDevice = async (payload: CreateDevicePayload) => {
  const response = await httpClient.post<DeviceRecord>('/devices/', payload);
  return response.data;
};
