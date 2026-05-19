"""Log chat questions and answers to MongoDB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import DESCENDING

import config as cfg
from soill_chatbot import store_mongo

logger = logging.getLogger(__name__)
_indexes_ensured = False


def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured:
        return
    store_mongo.conversations_col().create_index([('created_at', DESCENDING)])
    _indexes_ensured = True


def log_interaction(
    *,
    question: str,
    answer: Optional[str] = None,
    error: Optional[str] = None,
    cited_sources_count: int = 0,
    rag_top_k: Optional[int] = None,
) -> None:
    if not cfg.LOG_CONVERSATIONS or not question.strip():
        return

    document: dict[str, Any] = {
        'created_at': datetime.now(timezone.utc),
        'question': question,
        'answer': answer,
        'error': error,
        'cited_sources_count': cited_sources_count,
        'rag_top_k': rag_top_k if rag_top_k is not None else cfg.RAG_TOP_K,
        'chat_model': cfg.MISTRAL_CHAT_MODEL,
        'embed_model': cfg.MISTRAL_EMBED_MODEL,
    }
    try:
        _ensure_indexes()
        store_mongo.conversations_col().insert_one(document)
    except Exception as exc:
        logger.warning('Failed to log conversation to MongoDB: %s', exc)
