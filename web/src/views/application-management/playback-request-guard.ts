export type PlaybackRequest = {
  id: number;
  key: string;
  content: string;
};

export const createPlaybackRequestGuard = () => {
  let nextId = 0;
  let currentRequest: PlaybackRequest | null = null;

  const isCurrent = (request: PlaybackRequest) => currentRequest?.id === request.id;

  return {
    begin(key: string, content: string) {
      nextId += 1;
      currentRequest = { id: nextId, key, content };
      return currentRequest;
    },
    cancel() {
      currentRequest = null;
    },
    complete(request: PlaybackRequest) {
      if (isCurrent(request)) {
        currentRequest = null;
      }
    },
    isCurrent,
    isPending(key: string, content: string) {
      return currentRequest?.key === key && currentRequest.content === content;
    },
  };
};
