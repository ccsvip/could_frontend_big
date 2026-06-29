export type TtsModelFamily = 'qwen3-instruct-flash' | 'qwen3-flash' | 'custom';

export type TtsModelOption = {
  label: string;
  publicLabel: string;
  value: string;
  code: 'instructional' | 'standard';
  family: Exclude<TtsModelFamily, 'custom'>;
  supportsInstructionControl: boolean;
};

export type TtsModelCapability = {
  family: TtsModelFamily;
  label: string;
  supportsInstructionControl: boolean;
  supportedVoiceCodes: Set<string> | null;
};

export const DEFAULT_TTS_MODEL_OPTIONS: TtsModelOption[] = [
  {
    label: 'Qwen3-TTS-Instruct-Flash-Realtime',
    publicLabel: '情感增强',
    value: 'qwen3-tts-instruct-flash-realtime',
    code: 'instructional',
    family: 'qwen3-instruct-flash',
    supportsInstructionControl: true,
  },
  {
    label: 'Qwen3-TTS-Flash-Realtime',
    publicLabel: '标准播报',
    value: 'qwen3-tts-flash-realtime',
    code: 'standard',
    family: 'qwen3-flash',
    supportsInstructionControl: false,
  },
];

const QWEN3_INSTRUCT_FLASH_VOICE_CODES = [
  'Cherry',
  'Serena',
  'Ethan',
  'Chelsie',
  'Momo',
  'Vivian',
  'Moon',
  'Maia',
  'Kai',
  'Nofish',
  'Bella',
  'Eldric Sage',
  'Mia',
  'Mochi',
  'Bellona',
  'Vincent',
  'Bunny',
  'Neil',
  'Arthur',
  'Nini',
  'Elias',
  'Seren',
  'Pip',
  'Stella',
] as const;

const QWEN3_FLASH_VOICE_CODES = [
  ...QWEN3_INSTRUCT_FLASH_VOICE_CODES,
  'Jennifer',
  'Ryan',
  'Katerina',
  'Aiden',
  'Jada',
  'Dylan',
  'Li',
  'Marcus',
  'Roy',
  'Peter',
  'Sunny',
  'Eric',
  'Rocky',
  'Kiki',
  'Bodega',
  'Sonrisa',
  'Alek',
  'Dolce',
  'Sohee',
  'Ono Anna',
  'Lenn',
  'Emilien',
  'Andre',
  'Radio Gol',
] as const;

const QWEN3_INSTRUCT_FLASH_VOICE_SET = new Set<string>(QWEN3_INSTRUCT_FLASH_VOICE_CODES);
const QWEN3_FLASH_VOICE_SET = new Set<string>(QWEN3_FLASH_VOICE_CODES);

export const normalizeTtsModelName = (model: string | null | undefined) => String(model || '').trim().toLowerCase();

export const getTtsModelCapability = (model: string | null | undefined): TtsModelCapability => {
  const normalized = normalizeTtsModelName(model);

  if (normalized === 'instructional' || normalized.startsWith('qwen3-tts-instruct-flash-realtime')) {
    return {
      family: 'qwen3-instruct-flash',
      label: 'Qwen3-TTS-Instruct-Flash-Realtime',
      supportsInstructionControl: true,
      supportedVoiceCodes: QWEN3_INSTRUCT_FLASH_VOICE_SET,
    };
  }

  if (normalized === 'standard' || normalized.startsWith('qwen3-tts-flash-realtime')) {
    return {
      family: 'qwen3-flash',
      label: 'Qwen3-TTS-Flash-Realtime',
      supportsInstructionControl: false,
      supportedVoiceCodes: QWEN3_FLASH_VOICE_SET,
    };
  }

  return {
    family: 'custom',
    label: model?.trim() || '自定义模型',
    supportsInstructionControl: false,
    supportedVoiceCodes: null,
  };
};

export const isTtsVoiceSupportedByModel = (model: string | null | undefined, voiceCode: string | null | undefined) => {
  const capability = getTtsModelCapability(model);
  if (!capability.supportedVoiceCodes) {
    return true;
  }
  return capability.supportedVoiceCodes.has(String(voiceCode || '').trim());
};

export const supportsTtsInstructionControl = (model: string | null | undefined, voiceCode?: string | null) => {
  const capability = getTtsModelCapability(model);
  if (!capability.supportsInstructionControl) {
    return false;
  }
  if (!voiceCode) {
    return true;
  }
  return isTtsVoiceSupportedByModel(model, voiceCode);
};

export const getTtsInstructionDisabledReason = (
  model: string | null | undefined,
  voiceCode?: string | null,
): string | null => {
  const capability = getTtsModelCapability(model);
  if (!capability.supportsInstructionControl) {
    if (capability.family === 'qwen3-flash') {
      return '当前模型不支持指令控制；请选择支持指令控制的模型后再填写。';
    }
    return '自定义模型暂无法确认指令控制能力；为避免上游报错，默认关闭指令控制。';
  }
  if (voiceCode && !isTtsVoiceSupportedByModel(model, voiceCode)) {
    return '当前音色不在该模型支持列表内，无法使用指令控制。';
  }
  return null;
};
