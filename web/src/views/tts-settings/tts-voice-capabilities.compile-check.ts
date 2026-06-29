import {
  getTtsModelCapability,
  isTtsVoiceSupportedByModel,
  supportsTtsInstructionControl,
} from './tts-voice-capabilities';

const instructCapability = getTtsModelCapability('qwen3-tts-instruct-flash-realtime');
const publicInstructCapability = getTtsModelCapability('instructional');
const flashCapability = getTtsModelCapability('qwen3-tts-flash-realtime');
const publicFlashCapability = getTtsModelCapability('standard');
const datedFlashCapability = getTtsModelCapability('qwen3-tts-flash-realtime-2025-11-27');
const unknownCapability = getTtsModelCapability('custom-qwen-tts-model');

if (!instructCapability.supportsInstructionControl) {
  throw new Error('instruct realtime model should support instruction control');
}
if (!publicInstructCapability.supportsInstructionControl) {
  throw new Error('public instructional model alias should support instruction control');
}
if (flashCapability.supportsInstructionControl) {
  throw new Error('plain flash realtime model should not support instruction control');
}
if (publicFlashCapability.supportsInstructionControl) {
  throw new Error('public standard model alias should not support instruction control');
}
if (!supportsTtsInstructionControl('qwen3-tts-instruct-flash-realtime', 'Cherry')) {
  throw new Error('Cherry should allow instructions on instruct realtime');
}
if (supportsTtsInstructionControl('qwen3-tts-flash-realtime', 'Cherry')) {
  throw new Error('plain flash realtime should disable instructions even for shared voices');
}
if (supportsTtsInstructionControl('standard', 'Cherry')) {
  throw new Error('standard public model alias should disable instructions');
}
if (isTtsVoiceSupportedByModel('qwen3-tts-instruct-flash-realtime', 'Dylan')) {
  throw new Error('Dylan should not be available for instruct realtime');
}
if (isTtsVoiceSupportedByModel('qwen3-tts-instruct-flash-realtime', 'Jennifer')) {
  throw new Error('Jennifer should not be available for instruct realtime');
}
if (!isTtsVoiceSupportedByModel('qwen3-tts-flash-realtime', 'Dylan')) {
  throw new Error('Dylan should be available for plain flash realtime');
}
if (!isTtsVoiceSupportedByModel('qwen3-tts-flash-realtime', 'Jennifer')) {
  throw new Error('Jennifer should be available for plain flash realtime');
}
if (!isTtsVoiceSupportedByModel('qwen3-tts-flash-realtime-2025-11-27', 'Dylan')) {
  throw new Error('dated qwen3 flash model names should map to the flash capability table');
}
if (datedFlashCapability.family !== 'qwen3-flash') {
  throw new Error('dated qwen3 flash aliases should resolve to the flash family');
}
if (unknownCapability.family !== 'custom') {
  throw new Error('unknown editable model names should remain valid custom models');
}
