export const TARGET_SAMPLE_RATE = 16000;
export const AUDIO_CHUNK_SIZE = 4096;
export const AUDIO_WORKLET_PROCESSOR_NAME = 'agent-asr-pcm-capture-processor';

export const AUDIO_WORKLET_PROCESSOR_SOURCE = `
class AgentAsrPcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.chunkSize = ${AUDIO_CHUNK_SIZE};
    this.buffer = new Float32Array(this.chunkSize);
    this.offset = 0;
  }

  process(inputs, outputs) {
    const input = inputs[0] && inputs[0][0];
    const output = outputs[0] && outputs[0][0];

    if (output) {
      output.fill(0);
    }
    if (!input) {
      return true;
    }

    let inputOffset = 0;
    while (inputOffset < input.length) {
      const available = this.chunkSize - this.offset;
      const length = Math.min(available, input.length - inputOffset);
      this.buffer.set(input.subarray(inputOffset, inputOffset + length), this.offset);
      this.offset += length;
      inputOffset += length;

      if (this.offset === this.chunkSize) {
        const chunk = this.buffer;
        this.port.postMessage(chunk, [chunk.buffer]);
        this.buffer = new Float32Array(this.chunkSize);
        this.offset = 0;
      }
    }

    return true;
  }
}

registerProcessor('${AUDIO_WORKLET_PROCESSOR_NAME}', AgentAsrPcmCaptureProcessor);
`;

export const downsampleBuffer = (
  buffer: Float32Array,
  inputSampleRate: number,
  outputSampleRate = TARGET_SAMPLE_RATE,
) => {
  if (inputSampleRate === outputSampleRate) {
    return buffer;
  }
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
      accum += buffer[i];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }

  return result;
};

export const encodePCM16 = (samples: Float32Array) => {
  const output = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return output.buffer;
};
