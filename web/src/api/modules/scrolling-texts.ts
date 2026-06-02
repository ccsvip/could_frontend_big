import { httpClient } from '../client';

export type ScrollingTextI18nScheme = 'zh_en';
export type ScrollingTextStatusFilter = 'all' | 'active' | 'inactive';

export type ScrollingTextItem = {
  id?: number;
  order: number;
  zh: string;
  en: string;
};

export type LocalizedScrollingTextItem = {
  id: number;
  order: number;
  text: string;
};

export type ScrollingTextRecord = {
  id: number;
  title: string;
  i18nScheme: ScrollingTextI18nScheme;
  i18nSchemeLabel: string;
  isActive: boolean;
  items: ScrollingTextItem[];
  localizedItems: LocalizedScrollingTextItem[];
  created_at: string;
  updated_at: string;
};

export type ScrollingTextListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScrollingTextRecord[];
};

export type ScrollingTextListQuery = {
  page?: number;
  pageSize?: number;
  title?: string;
  keyword?: string;
  status?: ScrollingTextStatusFilter;
  lang?: 'zh' | 'en';
};

export type ScrollingTextPayload = {
  title: string;
  i18nScheme: ScrollingTextI18nScheme;
  isActive: boolean;
  items: ScrollingTextItem[];
};

const buildListParams = (query?: ScrollingTextListQuery) => ({
  page: query?.page,
  page_size: query?.pageSize,
  title: query?.title || undefined,
  keyword: query?.keyword || undefined,
  lang: query?.lang || undefined,
  is_active:
    query?.status === 'active'
      ? 'true'
      : query?.status === 'inactive'
        ? 'false'
        : undefined,
});

export const fetchScrollingTexts = async (query?: ScrollingTextListQuery) => {
  const response = await httpClient.get<ScrollingTextListResponse>('/resources/scrolling-texts/', {
    params: buildListParams(query),
  });
  return response.data;
};

export const createScrollingText = async (payload: ScrollingTextPayload) => {
  const response = await httpClient.post<ScrollingTextRecord>('/resources/scrolling-texts/', payload);
  return response.data;
};

export const updateScrollingText = async (id: number, payload: ScrollingTextPayload) => {
  const response = await httpClient.patch<ScrollingTextRecord>(`/resources/scrolling-texts/${id}/`, payload);
  return response.data;
};

export const deleteScrollingText = async (id: number) => {
  await httpClient.delete(`/resources/scrolling-texts/${id}/`);
};
