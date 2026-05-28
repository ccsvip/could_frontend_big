import { httpClient } from '../client';

export type PointRecord = {
  id: number;
  name: string;
  command: string;
  isActive: boolean;
  isShow: boolean;
  createdAt: string;
  updatedAt: string;
};

export type PointListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PointRecord[];
};

export type PointListQuery = {
  page?: number;
  pageSize?: number;
  keyword?: string;
  isActive?: 'all' | 'active' | 'inactive';
  includeHidden?: boolean;
  all?: boolean;
};

export type PointPayload = {
  name: string;
  command: string;
  isActive: boolean;
  isShow?: boolean;
};

const buildActiveParam = (value?: 'all' | 'active' | 'inactive') => {
  if (value === 'active') return 'true';
  if (value === 'inactive') return 'false';
  return undefined;
};

const buildPointParams = (query?: PointListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  keyword: query?.keyword || undefined,
  is_active: buildActiveParam(query?.isActive),
  include_hidden: query?.includeHidden ? 'true' : undefined,
  all: query?.all ? 'true' : undefined,
});

export const fetchPoints = async (query?: PointListQuery) => {
  const response = await httpClient.get<PointListResponse>('/commands/points/', {
    params: buildPointParams(query),
  });
  return response.data;
};

export const createPoint = async (payload: PointPayload) => {
  const response = await httpClient.post<PointRecord>('/commands/points/', payload);
  return response.data;
};

export const updatePoint = async (id: number, payload: Partial<PointPayload>) => {
  const response = await httpClient.patch<PointRecord>(`/commands/points/${id}/`, payload);
  return response.data;
};

export const deletePoint = async (id: number) => {
  await httpClient.delete(`/commands/points/${id}/`);
};
