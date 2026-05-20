"""Multi-turn chat history (in-memory trim + optional MongoDB reload)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import config as cfg


@dataclass(frozen=True)
class ChatTurn:
    question: str
    answer: str


def trim_history(turns: List[ChatTurn]) -> List[ChatTurn]:
    """Keep only the most recent turns configured in .env."""
    if not cfg.CHAT_HISTORY_ENABLED:
        return []
    limit = max(0, cfg.CHAT_HISTORY_TURNS)
    if limit == 0:
        return []
    return turns[-limit:]


def truncate_answer(text: str) -> str:
    max_len = max(200, cfg.CHAT_HISTORY_MAX_ANSWER_CHARS)
    cleaned = (text or '').strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + '...'


def append_turn(
    history: List[ChatTurn],
    question: str,
    answer: str,
) -> List[ChatTurn]:
    updated = list(history)
    updated.append(
        ChatTurn(
            question=question.strip(),
            answer=truncate_answer(answer),
        )
    )
    return trim_history(updated)
