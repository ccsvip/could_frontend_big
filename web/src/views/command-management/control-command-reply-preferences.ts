import type { ControlCommandReplyStrategy } from '../../api/modules/commands';

type ControlCommandReplyPreferencesInput = {
  executionReply?: string | null;
  replyStrategy?: string | null;
};

export type ControlCommandReplyPreferences = {
  executionReply: string;
  replyStrategy: ControlCommandReplyStrategy;
};

export const normalizeControlCommandReplyPreferences = (
  input: ControlCommandReplyPreferencesInput,
): ControlCommandReplyPreferences => ({
  executionReply: input.executionReply?.trim() || '',
  replyStrategy: input.replyStrategy === 'generated' ? 'generated' : 'fixed',
});
