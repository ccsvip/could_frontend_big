from __future__ import annotations

import unicodedata


def normalize_annotation_question(value: str | None) -> str:
    text = str(value or '').strip()
    return ''.join(
        character
        for character in text
        if not unicodedata.category(character).startswith('P')
    ).strip()


def find_matching_annotation(queryset, question_text: str):
    normalized_question = normalize_annotation_question(question_text)
    if not normalized_question:
        return None

    ordered_queryset = queryset.filter(is_active=True).order_by('-updated_at', '-id')
    exact_match = ordered_queryset.filter(question__iexact=normalized_question).first()
    if exact_match is not None:
        return exact_match

    normalized_casefold = normalized_question.casefold()
    for annotation in ordered_queryset.only('id', 'question', 'answer', 'hit_count', 'last_hit_at', 'updated_at'):
        if normalize_annotation_question(annotation.question).casefold() == normalized_casefold:
            return annotation
    return None


def find_matching_published_annotation(annotation_snapshots, question_text: str):
    normalized_question = normalize_annotation_question(question_text)
    if not normalized_question:
        return None

    normalized_casefold = normalized_question.casefold()
    for annotation in annotation_snapshots or []:
        if not isinstance(annotation, dict) or not annotation.get('isActive', True):
            continue
        if normalize_annotation_question(annotation.get('question')).casefold() == normalized_casefold:
            return annotation
    return None
