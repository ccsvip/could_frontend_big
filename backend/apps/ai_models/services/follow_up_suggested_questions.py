"""回答后下一步建议问题（旁路二次 LLM，不污染主对话上下文）。"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from apps.ai_models import llm_services
from apps.ai_models.models import LLMModel

logger = logging.getLogger(__name__)

FOLLOW_UP_QUESTION_COUNT = 3
FOLLOW_UP_MAX_CHARS = 40
FOLLOW_UP_HISTORY_MESSAGE_LIMIT = 3
FOLLOW_UP_HISTORY_CHAR_LIMIT = 3000
FOLLOW_UP_TEMPERATURE = 0.2
FOLLOW_UP_MAX_TOKENS = 256
FOLLOW_UP_TIMEOUT_SECONDS = 25

_INSTRUCTION = (
    '请根据下面的对话历史与助手最新回复，预测用户接下来最可能继续问的三个问题。\n'
    f'要求：\n'
    f'1. 恰好输出 {FOLLOW_UP_QUESTION_COUNT} 个问题；\n'
    f'2. 每个问题尽量简短（建议不超过 {FOLLOW_UP_MAX_CHARS} 个汉字或字符）；\n'
    '3. 输出语言必须与助手最新回复一致；\n'
    '4. 只输出 JSON 数组，不要其它说明文字，格式如下：\n'
    '["问题1","问题2","问题3"]\n'
)

_ARRAY_RE = re.compile(r'\[[\s\S]*\]')


def generate_follow_up_suggested_questions(
    *,
    model: LLMModel | None,
    history_messages: Iterable[dict] | None,
    latest_answer: str,
    enabled: bool,
    timeout: int = FOLLOW_UP_TIMEOUT_SECONDS,
) -> list[str]:
    """Generate follow-up questions. Never raises; returns [] on any soft failure."""
    if not enabled:
        return []
    answer = str(latest_answer or '').strip()
    if model is None or not answer:
        return []

    try:
        histories = _format_history_text(history_messages, latest_answer=answer)
        messages = [
            {'role': 'system', 'content': _INSTRUCTION},
            {
                'role': 'user',
                'content': f'{histories}\n\n助手最新回复：\n{answer}\n\nquestions:\n',
            },
        ]
        raw = llm_services.run_llm_chat_completion(
            model=model,
            messages=messages,
            temperature=FOLLOW_UP_TEMPERATURE,
            max_tokens=FOLLOW_UP_MAX_TOKENS,
            timeout=timeout,
        )
        return _parse_question_list(raw)
    except Exception:
        logger.warning('follow_up_suggested_questions.generate_failed', exc_info=True)
        return []


def _format_history_text(history_messages: Iterable[dict] | None, *, latest_answer: str) -> str:
    turns: list[str] = []
    for item in history_messages or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role') or '').strip().lower()
        content = str(item.get('content') or '').strip()
        if not content:
            continue
        if role not in {'user', 'assistant', 'human', 'ai'}:
            continue
        label = '用户' if role in {'user', 'human'} else '助手'
        turns.append(f'{label}: {content}')

    if not turns:
        turns = [f'助手: {latest_answer}']

    # 仅保留最近若干条 user/assistant 轮次
    turns = turns[-FOLLOW_UP_HISTORY_MESSAGE_LIMIT:]
    text = '\n'.join(turns)
    if len(text) > FOLLOW_UP_HISTORY_CHAR_LIMIT:
        text = text[-FOLLOW_UP_HISTORY_CHAR_LIMIT:]
    return text


def _parse_question_list(raw: str) -> list[str]:
    text = str(raw or '').strip()
    if not text:
        return []

    match = _ARRAY_RE.search(text)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # 宽松：去掉可能的代码围栏后再试
        cleaned = candidate.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []

    questions: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        question = item.strip()
        if not question:
            continue
        if len(question) > FOLLOW_UP_MAX_CHARS:
            question = question[:FOLLOW_UP_MAX_CHARS].rstrip()
        questions.append(question)
        if len(questions) >= FOLLOW_UP_QUESTION_COUNT:
            break
    return questions
