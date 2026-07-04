from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django.conf import settings


class WakeWordEncodingError(ValueError):
    pass


@lru_cache(maxsize=4)
def _load_tokens(tokens_path_text: str) -> set[str]:
    tokens_path = Path(tokens_path_text)
    if not tokens_path.exists():
        raise WakeWordEncodingError(f'sherpa-onnx tokens.txt 未预置: {tokens_path}')

    tokens: set[str] = set()
    with tokens_path.open('r', encoding='utf-8') as file:
        for line in file:
            token = line.strip().split(maxsplit=1)[0] if line.strip() else ''
            if token:
                tokens.add(token)
    if not tokens:
        raise WakeWordEncodingError(f'sherpa-onnx tokens.txt 为空: {tokens_path}')
    return tokens


def encode_wake_word_text(text: str) -> str:
    """Encode Chinese wake words as sherpa-onnx ppinyin token text.

    This mirrors sherpa-onnx `text2token --tokens-type ppinyin` for Mandarin
    wake words, then validates every produced token against the vendored
    model `tokens.txt` so bad values fail at save time instead of runtime.
    """

    phrase = str(text or '').strip()
    if not phrase:
        raise WakeWordEncodingError('唤醒词不能为空')

    tokens_path = Path(getattr(settings, 'SHERPA_ONNX_TOKENS_PATH', ''))
    allowed_tokens = _load_tokens(str(tokens_path))

    try:
        from pypinyin import pinyin
        from pypinyin.contrib.tone_convert import to_finals_tone, to_initials
    except ImportError as exc:
        raise WakeWordEncodingError('pypinyin 未预置，无法生成 sherpa-onnx ppinyin 编码') from exc

    encoded_tokens: list[str] = []
    for item in (value[0] for value in pinyin(phrase)):
        initial = to_initials(item, strict=False)
        final = to_finals_tone(item, strict=False)
        parts = [item] if initial == '' and final == '' else [part for part in (initial, final) if part]
        for part in parts:
            if part not in allowed_tokens:
                raise WakeWordEncodingError(f'唤醒词编码 token 不在 tokens.txt 中: {part}')
            encoded_tokens.append(part)

    if not encoded_tokens:
        raise WakeWordEncodingError('唤醒词编码结果为空')
    return ' '.join(encoded_tokens)
