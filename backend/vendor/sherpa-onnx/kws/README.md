# sherpa-onnx KWS resources

This directory contains pre-provisioned sherpa-onnx keyword spotting resources.
Runtime deployment copies these files into the image; it must not download model
files or Python wheels at startup.

Provisioned runtime files:

- `tokens.txt`
- `encoder.onnx`
- `decoder.onnx`
- `joiner.onnx`
- `../bin/sherpa-onnx-keyword-spotter`
- `../lib/*.so`
- `../wheels/*.whl`

The backend wake-word management API generates the frontend/runtime keyword line
with the same Mandarin ppinyin split used by `sherpa-onnx-cli text2token
--tokens-type ppinyin`, then validates each token against this `tokens.txt`.
This avoids requiring downloads or the Python CLI during deployment.

## Source packages

The Chinese KWS model files come from the official k2-fsa sherpa-onnx release asset:

`https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2`

The native Linux x64 KWS binary comes from:

`https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.3/sherpa-onnx-v1.13.3-linux-x64-shared-no-tts.tar.bz2`

The Docker build installs `sherpa-onnx`, `sherpa-onnx-core`, and `pypinyin` from
pre-downloaded Linux CPython 3.13 wheels in `../wheels/`.
