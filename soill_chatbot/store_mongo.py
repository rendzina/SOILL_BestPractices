"""
MongoDB access for scraped articles, RAG chunks, and conversation logs.

get_client() reconnects when MONGO_URI changes so editing .env does not require
restarting long-running processes (e.g. Chainlit) to pick up a new database host.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import certifi
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

import config as cfg

_client: Optional[MongoClient] = None
_client_uri: Optional[str] = None


def _client_kwargs(uri: str) -> dict:
    """TLS options for Atlas (mongodb+srv) — avoids macOS/Python SSL handshake errors."""
    kwargs: dict = {'serverSelectionTimeoutMS': 20000}
    if uri.startswith('mongodb+srv://') or 'tls=true' in uri.lower():
        ca_file = getattr(cfg, 'MONGO_TLS_CA_FILE', None) or certifi.where()
        kwargs['tlsCAFile'] = ca_file
    return kwargs


def get_client() -> MongoClient:
    """Return a MongoClient; reconnect if MONGO_URI changed (e.g. after editing .env)."""
    global _client, _client_uri
    uri = cfg.MONGO_URI
    if _client is None or _client_uri != uri:
        _client = MongoClient(uri, **_client_kwargs(uri))
        _client_uri = uri
    return _client


def get_db() -> Database:
    return get_client()[cfg.MONGO_DB]


def articles_col() -> Collection:
    return get_db()[cfg.MONGO_COLLECTION]


def chunks_col() -> Collection:
    return get_db()[cfg.MONGODB_CHUNKS_COLLECTION]


def conversations_col() -> Collection:
    return get_db()[cfg.MONGODB_CONVERSATIONS_COLLECTION]


def init_indexes() -> None:
    """Idempotent index creation for retrieval."""
    chunks = chunks_col()
    chunks.create_index('chunk_id', unique=True)
    chunks.create_index('article_id')
    chunks.create_index('project_name')
    chunks.create_index('faiss_id', sparse=True)
    conversations_col().create_index([('created_at', DESCENDING)])


def ping_mongodb() -> None:
    get_client().admin.command('ping')


def count_articles() -> int:
    return articles_col().count_documents({})


def count_chunks() -> int:
    return chunks_col().count_documents({})


def fetch_all_articles() -> List[Dict[str, Any]]:
    return list(articles_col().find({}).sort('scrape_date', DESCENDING))


def clear_chunks() -> int:
    return int(chunks_col().delete_many({}).deleted_count)


def insert_chunk_docs(docs: List[Dict[str, Any]]) -> None:
    if docs:
        chunks_col().insert_many(docs)


def fetch_chunks_by_ids(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []
    cursor = chunks_col().find({'chunk_id': {'$in': chunk_ids}})
    by_id = {doc['chunk_id']: doc for doc in cursor}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


def fetch_embeddings_matrix_ordered(chunk_ids: Sequence[str]) -> np.ndarray:
    if not chunk_ids:
        return np.zeros((0, 0), dtype='float32')
    cursor = chunks_col().find(
        {'chunk_id': {'$in': list(chunk_ids)}},
        {'chunk_id': 1, 'embedding': 1},
    )
    by_id: Dict[str, list] = {}
    for doc in cursor:
        chunk_id = doc.get('chunk_id')
        embedding = doc.get('embedding')
        if chunk_id and embedding is not None:
            by_id[str(chunk_id)] = embedding
    rows: list[np.ndarray] = []
    for chunk_id in chunk_ids:
        if chunk_id not in by_id:
            raise KeyError(f'Missing embedding for chunk_id={chunk_id!r}')
        rows.append(np.asarray(by_id[chunk_id], dtype='float32').reshape(1, -1))
    return np.vstack(rows)
