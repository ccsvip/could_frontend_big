import { httpClient } from '../client';

export type ChatMessage = {
  id: number;
  conversationId: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  feedback: 'none' | 'up' | 'down';
  created_at: string;
};

export type ChatConversationDetail = {
  id: number;
  title: string;
  applicationId: number | null;
  llmModelId: number | null;
  llmModelName: string;
  llmModelDisplayName: string;
  llmProviderName: string | null;
  summary: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type ChatConversationConfigPayload = {
  llmModelId?: number | null;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const parseSseDataLine = (line: string) => {
  if (!line.startsWith('data:')) return null;
  return line.slice(5).trimStart();
};

export const fetchConversation = async (id: number) => {
  const response = await httpClient.get<ChatConversationDetail>(
    `/ai-models/chat/conversations/${id}/`,
  );
  return response.data;
};

export const updateConversationConfig = async (
  id: number,
  payload: ChatConversationConfigPayload,
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

export type ChatConversationRecord = {
  id: number;
  title: string;
  applicationId: number | null;
  llmModelId: number | null;
  llmModelName: string;
  llmModelDisplayName: string;
  llmProviderName: string | null;
  summary: string;
  messageCount: number;
  lastMessage: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatConversationListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ChatConversationRecord[];
};

export const fetchConversations = async (params?: { application?: number; page?: number; keyword?: string }) => {
  const response = await httpClient.get<ChatConversationListResponse>('/ai-models/chat/conversations/', { params });
  return response.data;
};

