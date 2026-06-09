import { httpClient } from '../client';

export type ChatMessage = {
  id: number;
  conversationId: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  feedback: 'none' | 'up' | 'down';
  created_at: string;
};

export type ChatConversationListItem = {
  id: number;
  title: string;
  applicationId: number | null;
  llmProviderId: number | null;
  llmProviderName: string | null;
  model_name: string;
  summary: string;
  messageCount: number;
  lastMessage: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatConversationDetail = {
  id: number;
  title: string;
  applicationId: number | null;
  llmProviderId: number | null;
  llmProviderName: string | null;
  modelName: string;
  summary: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type ChatConversationListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ChatConversationListItem[];
};

export type CreateConversationPayload = {
  title?: string;
  llmProviderId?: number | null;
  modelName?: string;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const parseSseDataLine = (line: string) => {
  if (!line.startsWith('data:')) return null;
  return line.slice(5).trimStart();
};

export const fetchConversations = async (page = 1, keyword = '') => {
  const response = await httpClient.get<ChatConversationListResponse>(
    '/ai-models/chat/conversations/',
    { params: { page, keyword: keyword || undefined } },
  );
  return response.data;
};

export const fetchConversation = async (id: number) => {
  const response = await httpClient.get<ChatConversationDetail>(
    `/ai-models/chat/conversations/${id}/`,
  );
  return response.data;
};

export const createConversation = async (payload: CreateConversationPayload) => {
  const response = await httpClient.post<ChatConversationListItem>(
    '/ai-models/chat/conversations/',
    payload,
  );
  return response.data;
};

export const deleteConversation = async (id: number) => {
  await httpClient.delete(`/ai-models/chat/conversations/${id}/`);
};

export const updateConversationTitle = async (id: number, title: string) => {
  const response = await httpClient.patch<ChatConversationListItem>(
    `/ai-models/chat/conversations/${id}/update-title/`,
    { title },
  );
  return response.data;
};

export const updateConversationConfig = async (
  id: number,
  payload: Pick<CreateConversationPayload, 'llmProviderId' | 'modelName' | 'systemPrompt' | 'temperature' | 'maxTokens'>,
) => {
  const response = await httpClient.patch<ChatConversationDetail>(
    `/ai-models/chat/conversations/${id}/update-config/`,
    payload,
  );
  return response.data;
};

/**
 * Send a message to a conversation and receive streaming response via SSE.
 * Uses native fetch because axios doesn't support streaming responses well.
 */
export const sendMessageStream = async (
  conversationId: number,
  content: string,
  stream: boolean,
  regenerateMessageId: number | null,
  onChunk: (text: string) => void,
  onTitle: (title: string) => void,
  onSummary: (summary: string) => void,
  onError: (error: string) => void,
  onDone: () => void,
): Promise<AbortController> => {
  const controller = new AbortController();
  const token = localStorage.getItem('token');

  try {
    const response = await fetch(
      `${API_BASE_URL}/ai-models/chat/conversations/${conversationId}/send/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          content,
          stream,
          regenerateMessageId: regenerateMessageId ?? undefined,
        }),
        signal: controller.signal,
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const errorMessage = errorData?.message || `请求失败 (${response.status})`;
      onError(errorMessage);
      onDone();
      return controller;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError('无法读取响应流');
      onDone();
      return controller;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    const processStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const data = parseSseDataLine(line);
            if (data === null) continue;
            if (data === '[DONE]') {
              onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.error) {
                onError(parsed.content || '未知错误');
              } else if (parsed.title) {
                onTitle(parsed.title);
              } else if (parsed.summary) {
                onSummary(parsed.summary);
              } else if (parsed.content) {
                onChunk(parsed.content);
              }
            } catch {
              // Ignore malformed JSON lines
            }
          }
        }
        onDone();
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          onDone();
          return;
        }
        onError(String(err));
        onDone();
      }
    };

    processStream();
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      onDone();
      return controller;
    }
    onError(String(err));
    onDone();
  }

  return controller;
};

export const updateMessageFeedback = async (
  conversationId: number,
  messageId: number,
  feedback: 'none' | 'up' | 'down',
) => {
  const response = await httpClient.patch<ChatMessage>(
    `/ai-models/chat/conversations/${conversationId}/messages/${messageId}/feedback/`,
    { feedback },
  );
  return response.data;
};
