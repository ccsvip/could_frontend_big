import { httpClient } from '../client';

export type ErrorCodeRecord = {
  code: string;
  defaultMessage: string;
  category: string;
  description: string;
  recommendedAction: string;
  transports: string[];
};

export type ErrorCodeListQuery = {
  keyword?: string;
  category?: string;
  page?: number;
};

export type ErrorCodePaginatedResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ErrorCodeRecord[];
  categories?: string[];
};

export type ErrorCodeListResponse = ErrorCodePaginatedResponse | ErrorCodeRecord[];

const buildListParams = (query?: ErrorCodeListQuery) => ({
  keyword: query?.keyword || undefined,
  category: query?.category || undefined,
  page: query?.page,
});

export const fetchErrorCodes = async (query?: ErrorCodeListQuery) => {
  const response = await httpClient.get<ErrorCodeListResponse>('/error-codes/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const fetchErrorCode = async (code: string) => {
  const response = await httpClient.get<ErrorCodeRecord>(`/error-codes/${encodeURIComponent(code)}/`);
  return response.data;
};
