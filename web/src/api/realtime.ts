import { API_BASE_URL } from './client';

export type RealtimeCommand = {
  type: string;
  id?: string;
  payload?: Record<string, unknown>;
};

export type RealtimeError = {
  code?: string;
  message?: string;
};

export type RealtimeEnvelope<TPayload = unknown> = {
  type?: string;
  id?: string;
  payload?: TPayload;
  error?: RealtimeError;
};

export const buildRealtimeWebSocketUrl = () => {
  const baseUrl = API_BASE_URL.startsWith('http')
    ? new URL(API_BASE_URL)
    : new URL(API_BASE_URL, window.location.origin);
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  baseUrl.pathname = '/ws/realtime/';
  baseUrl.search = '';
  return baseUrl.toString();
};

export const createRealtimeCommandId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const encodeRealtimeCommand = (command: RealtimeCommand) => JSON.stringify(command);

export const buildAsrSessionStartCommand = (
  id: string,
  payload: {
    token: string;
    tenantId?: number | null;
  },
): RealtimeCommand => ({
  type: 'asr.session.start',
  id,
  payload: {
    token: payload.token,
    tenantId: payload.tenantId ?? undefined,
  },
});

export const buildAsrSessionFinishCommand = (id: string): RealtimeCommand => ({
  type: 'asr.session.finish',
  id,
});

export const buildAsrSessionCancelCommand = (id: string): RealtimeCommand => ({
  type: 'asr.session.cancel',
  id,
});

export const buildDeviceEventsUnsubscribeCommand = (id: string): RealtimeCommand => ({
  type: 'devices.events.unsubscribe',
  id,
});

export const buildTtsSessionStartCommand = (
  id: string,
  payload: {
    token: string;
    tenantId?: number | null;
    text: string;
    voiceId?: number | null;
    providerCode?: string;
  },
): RealtimeCommand => ({
  type: 'tts.session.start',
  id,
  payload: {
    token: payload.token,
    tenantId: payload.tenantId ?? undefined,
    text: payload.text,
    voiceId: payload.voiceId ?? null,
    providerCode: payload.providerCode,
  },
});

export const buildTtsSessionCancelCommand = (id: string): RealtimeCommand => ({
  type: 'tts.session.cancel',
  id,
});

export const parseRealtimeMessage = <TPayload = unknown>(data: unknown): RealtimeEnvelope<TPayload> | null => {
  if (typeof data !== 'string') {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(data);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }
    return parsed as RealtimeEnvelope<TPayload>;
  } catch {
    return null;
  }
};
