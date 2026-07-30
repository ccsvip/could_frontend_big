import { httpClient } from '../client';
import { buildRealtimeWebSocketUrl } from '../realtime';

export type TtsVoiceRecord = {
  id: number;
  displayName: string;
  voiceCode: string;
  gender: string;
  avatarPath: string;
  isActive?: boolean;
  isVisible?: boolean;
  sortOrder?: number;
  isDefault: boolean;
  /** Card identity — present on company options, used to pick the config schema. */
  providerId?: number;
  providerCode?: string;
  providerName?: string;
  configSchemaKey?: string;
  supportedChannels?: TtsChannel[];
  capabilities?: TtsVoiceCapabilities;
};

export type TtsChannel = 'httpTest' | 'httpRuntime' | 'realtime';

export type TtsVoiceCapabilities = {
  speechRate?: boolean;
  pitchRate?: boolean;
  volume?: boolean;
};

export type TtsConfigFieldType = 'slider' | 'select' | 'switch' | 'textarea';

export type TtsConfigField = {
  name: string;
  label: string;
  type: TtsConfigFieldType;
  min?: number;
  max?: number;
  step?: number;
  options?: Array<{ value: string | number; label: string }>;
};

export type TtsPublicConfigSchema = {
  schemaKey: string;
  fields: TtsConfigField[];
};

export type TtsModelOption = {
  code: string;
  label: string;
  supportsInstructionControl: boolean;
};

/** One TTS card the company is authorized to use. */
export type TtsCardSummary = {
  id: number;
  code: string;
  name: string;
  isActive: boolean;
  defaultModelCode: string;
  modelOptions: TtsModelOption[];
  supportedChannels: TtsChannel[];
  publicConfigSchema: TtsPublicConfigSchema;
  capabilities?: Record<string, boolean>;
  publicConfig?: Partial<TtsSessionConfig> & Record<string, unknown>;
  voices: TtsVoiceRecord[];
};

export type TtsProviderSummary = {
  id: number;
  code: string;
  name: string;
  defaultVoiceId: number | null;
  defaultVoiceName: string;
  sampleRate: number;
  isActive: boolean;
  configured: boolean;
  voiceCount: number;
  updated_at: string | null;
};

export type TtsSessionConfig = {
  model_code?: string;
  mode: 'server_commit' | 'commit';
  language_type: 'Auto' | 'Chinese' | 'English' | 'German' | 'Italian' | 'Portuguese' | 'Spanish' | 'Japanese' | 'Korean' | 'French' | 'Russian';
  response_format: 'pcm' | 'wav' | 'mp3' | 'opus';
  sample_rate: 8000 | 16000 | 24000 | 48000;
  speech_rate: number;
  volume: number;
  pitch_rate: number;
  bit_rate: number;
  instructions: string;
  optimize_instructions: boolean;
};

export type TtsSettings = {
  id: number;
  code: string;
  name: string;
  apiKeyMasked: string;
  apiKeyConfigured: boolean;
  baseUrl: string;
  model: string;
  sampleRate: number;
  ttsSessionConfig: TtsSessionConfig;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
  configured: boolean;
  voices: TtsVoiceRecord[];
  updated_at: string | null;
};

export type TtsSettingsPayload = Partial<{
  apiKey: string;
  baseUrl: string;
  model: string;
  sampleRate: number;
  ttsSessionConfig: TtsSessionConfig;
  defaultVoiceId: number | null;
  defaultTestText: string;
  isActive: boolean;
  voices: Array<Partial<TtsVoiceRecord> & { id: number }>;
}>;

export type CompanyTtsOptions = {
  /**
   * Legacy single-card summary, kept for the migration window. Reflects the
   * default voice's card. Prefer `providers` for new code.
   */
  provider: {
    id?: number | null;
    code: string;
    name: string;
    defaultModelCode: string;
    modelOptions: TtsModelOption[];
    isActive: boolean;
  };
  /** All authorized cards, each with its own voices and config schema. */
  providers?: TtsCardSummary[];
  defaultVoiceId: number | null;
  sampleRate: number;
  ttsSessionConfig: TtsSessionConfig;
  defaultTestText: string;
  /** Flat union of every authorized card's voices. */
  voices: TtsVoiceRecord[];
};

export type TtsTestPayload = {
  text?: string;
  voiceId?: number | null;
};

export type TtsRealtimeMessage = {
  type?: string;
  sampleRate?: number;
  responseFormat?: 'pcm' | 'wav' | 'mp3' | 'opus';
  voice?: string;
};

const blobRequestConfig = {
  responseType: 'blob' as const,
  timeout: 60000,
};

const ttsSettingsPath = (providerCode?: string) =>
  providerCode ? `/settings/tts/providers/${providerCode}/` : '/settings/tts/';

const ttsSettingsTestPath = (providerCode?: string) =>
  providerCode ? `/settings/tts/providers/${providerCode}/test/` : '/settings/tts/test/';

export const fetchTtsProviders = async () => {
  const response = await httpClient.get<TtsProviderSummary[]>('/settings/tts/providers/');
  return response.data;
};

export const fetchTtsSettings = async (providerCode?: string) => {
  const response = await httpClient.get<TtsSettings>(ttsSettingsPath(providerCode));
  return response.data;
};

export const updateTtsSettings = async (payload: TtsSettingsPayload, providerCode?: string) => {
  const response = await httpClient.patch<TtsSettings>(ttsSettingsPath(providerCode), payload);
  return response.data;
};

export const testPlatformTts = async (payload: TtsTestPayload, providerCode?: string) => {
  const response = await httpClient.post<Blob>(ttsSettingsTestPath(providerCode), payload, blobRequestConfig);
  return response.data;
};

export const fetchCompanyTtsOptions = async () => {
  const response = await httpClient.get<CompanyTtsOptions>('/ai-models/tts/options/');
  return response.data;
};

export const updateCompanyDefaultTtsVoice = async (voiceId: number, ttsSessionConfig?: TtsSessionConfig, modelCode?: string) => {
  const response = await httpClient.patch<CompanyTtsOptions>('/ai-models/tts/default-voice/', { voiceId, ttsSessionConfig, modelCode });
  return response.data;
};

export const testCompanyTts = async (payload: TtsTestPayload) => {
  const response = await httpClient.post<Blob>('/ai-models/tts/test/', payload, blobRequestConfig);
  return response.data;
};

export type TenantTtsCardGrantPayload = {
  providerId: number;
  isActive: boolean;
  publicConfig?: Record<string, unknown>;
};

export type TenantTtsCardUsage = {
  tenantDefault: boolean;
  deviceCount: number;
  deviceApplicationCount: number;
};

export type TenantTtsCardAuthorizationVoice = TtsVoiceRecord & {
  effectiveAuthorized: boolean;
  usage: TenantTtsCardUsage;
};

export type TenantTtsCardAuthorization = Omit<TtsCardSummary, 'voices'> & {
  sortOrder: number;
  grantIsActive: boolean;
  usage: TenantTtsCardUsage;
  canDisableGrant: boolean;
  voices: TenantTtsCardAuthorizationVoice[];
};

export type TenantTtsCardAuthorizationResponse = {
  tenant: { id: number; name: string; isActive: boolean };
  providers: TenantTtsCardAuthorization[];
  defaultVoiceId: number | null;
};

const tenantTtsCardAuthorizationPath = (tenantId: number) =>
  `/settings/tts/tenants/${tenantId}/card-authorizations/`;

export const fetchTenantTtsCardAuthorization = async (tenantId: number) => {
  const response = await httpClient.get<TenantTtsCardAuthorizationResponse>(
    tenantTtsCardAuthorizationPath(tenantId),
  );
  return response.data;
};

export const updateTenantTtsCardAuthorization = async (
  tenantId: number,
  payload: { cardGrants: TenantTtsCardGrantPayload[]; defaultVoiceId?: number | null },
) => {
  const response = await httpClient.put<TenantTtsCardAuthorizationResponse>(
    tenantTtsCardAuthorizationPath(tenantId),
    payload,
  );
  return response.data;
};

export const buildTtsRealtimeWebSocketUrl = () => buildRealtimeWebSocketUrl();
