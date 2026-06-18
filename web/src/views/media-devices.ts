const MICROPHONE_UNSUPPORTED_MESSAGE = '当前访问地址不支持麦克风采集，请使用 HTTPS，或通过 localhost/127.0.0.1 访问后再测试';

export const requestMicrophoneStream = async (): Promise<MediaStream> => {
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
    throw new Error(MICROPHONE_UNSUPPORTED_MESSAGE);
  }
  return navigator.mediaDevices.getUserMedia({ audio: true });
};
