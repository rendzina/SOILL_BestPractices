"""Log chat questions and answers to MongoDB (with optional client metadata)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from pymongo import ASCENDING, DESCENDING

import config as cfg
from soill_chatbot.chat_history import ChatTurn
from soill_chatbot import store_mongo
from soill_chatbot.user_identity import ClientMetadata

logger = logging.getLogger(__name__)
_indexes_ensured = False


def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured:
        return
    collection = store_mongo.conversations_col()
    collection.create_index([('created_at', DESCENDING)])
    collection.create_index([('thread_id', ASCENDING), ('created_at', DESCENDING)])
    collection.create_index([('visitor_fingerprint', ASCENDING), ('created_at', DESCENDING)])
    _indexes_ensured = True


def fetch_recent_turns(thread_id: str, limit: Optional[int] = None) -> List[ChatTurn]:
    """Load the latest completed Q&A turns for a Chainlit thread (newest last)."""
    if not cfg.LOG_CONVERSATIONS or not thread_id:
        return []
    turn_limit = limit if limit is not None else cfg.CHAT_HISTORY_TURNS
    if turn_limit <= 0:
        return []

    try:
        _ensure_indexes()
        cursor = (
            store_mongo.conversations_col()
            .find(
                {
                    'thread_id': thread_id,
                    'answer': {'$ne': None},
                    '$or': [{'error': None}, {'error': {'$exists': False}}],
                },
                {'question': 1, 'answer': 1, 'created_at': 1},
            )
            .sort('created_at', DESCENDING)
            .limit(turn_limit)
        )
        documents = list(cursor)
        documents.reverse()
        return [
            ChatTurn(question=str(doc.get('question', '')), answer=str(doc.get('answer', '')))
            for doc in documents
            if doc.get('question') and doc.get('answer')
        ]
    except Exception as exc:
        logger.warning('Failed to load conversation history: %s', exc)
        return []


def log_interaction(
    *,
    question: str,
    answer: Optional[str] = None,
    error: Optional[str] = None,
    cited_sources_count: int = 0,
    rag_top_k: Optional[int] = None,
    client: Optional[ClientMetadata] = None,
) -> None:
    if not cfg.LOG_CONVERSATIONS or not question.strip():
        return

    meta = client or ClientMetadata.anonymous()
    document: dict[str, Any] = {
        'created_at': datetime.now(timezone.utc),
        'thread_id': meta.thread_id,
        'session_id': meta.session_id,
        'visitor_fingerprint': meta.visitor_fingerprint,
        'client_type': meta.client_type,
        'question': question,
        'answer': answer,
        'error': error,
        'cited_sources_count': cited_sources_count,
        'rag_top_k': rag_top_k if rag_top_k is not None else cfg.RAG_TOP_K,
        'chat_model': cfg.MISTRAL_CHAT_MODEL,
        'embed_model': cfg.MISTRAL_EMBED_MODEL,
    }
    if cfg.LOG_CLIENT_METADATA:
        document['client_ip'] = meta.client_ip
        document['user_agent'] = meta.user_agent

    try:
        _ensure_indexes()
        store_mongo.conversations_col().insert_one(document)
    except Exception as exc:
        logger.warning('Failed to log conversation to MongoDB: %s', exc)
