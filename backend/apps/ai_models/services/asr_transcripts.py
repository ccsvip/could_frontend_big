from __future__ import annotations

import unicodedata


def normalize_ignored_transcript(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', str(value or '')).casefold()
    normalized = ' '.join(normalized.split())
    start = 0
    end = len(normalized)
    while start < end and _is_surrounding_separator(normalized[start]):
        start += 1
    while end > start and _is_surrounding_separator(normalized[end - 1]):
        end -= 1
    return normalized[start:end].strip()


def contains_unicode_letter_or_number(value: str) -> bool:
    return any(character.isalnum() for character in value)


def _is_surrounding_separator(character: str) -> bool:
    return character.isspace() or unicodedata.category(character)[0] in {'P', 'S'}
