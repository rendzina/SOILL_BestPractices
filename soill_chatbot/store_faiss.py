"""Persist a FAISS index (inner product on L2-normalised vectors) alongside MongoDB."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

import faiss
import numpy as np
from pymongo import UpdateOne

import config as cfg
from soill_chatbot import store_mongo


def _l2_row_normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (matrix / norms).astype('float32')


def rebuild_faiss_from_mongo() -> int:
    """
    Rebuild FAISS from all chunk documents with embeddings; assign faiss_id
    0..N-1 and write index.faiss + meta.json.
    """
    collection = store_mongo.chunks_col()
    store_mongo.init_indexes()
    collection.update_many(
        {'faiss_id': {'$exists': True}},
        {'$unset': {'faiss_id': ''}},
    )
    docs = list(
        collection.find(
            {'embedding': {'$exists': True}},
            {'chunk_id': 1, 'embedding': 1},
        ).sort('chunk_id', 1)
    )
    if not docs:
        cfg.FAISS_DIR.mkdir(parents=True, exist_ok=True)
        if cfg.FAISS_INDEX_PATH.exists():
            cfg.FAISS_INDEX_PATH.unlink()
        with open(cfg.FAISS_META_PATH, 'w', encoding='utf-8') as handle:
            json.dump(
                {'dim': 0, 'n_vectors': 0, 'chunk_id_order': []},
                handle,
                indent=2,
            )
        return 0

    dimension = len(docs[0]['embedding'])
    count = len(docs)
    matrix = np.zeros((count, dimension), dtype='float32')
    chunk_order: list[str] = []
    for index, doc in enumerate(docs):
        matrix[index] = np.array(doc['embedding'], dtype='float32')
        chunk_order.append(doc['chunk_id'])
    matrix = _l2_row_normalise(matrix)

    index = faiss.IndexIDMap(faiss.IndexFlatIP(dimension))
    faiss_ids = np.arange(count, dtype='int64')
    index.add_with_ids(matrix, faiss_ids)

    operations = [
        UpdateOne({'chunk_id': chunk_id}, {'$set': {'faiss_id': int(i)}})
        for i, chunk_id in enumerate(chunk_order)
    ]
    if operations:
        collection.bulk_write(operations, ordered=False)

    _save_index(index, dimension, chunk_order, count)
    return count


def _save_index(
    index: faiss.Index,
    dimension: int,
    chunk_id_order: list[str],
    vector_count: int,
) -> None:
    cfg.FAISS_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(cfg.FAISS_INDEX_PATH))
    with open(cfg.FAISS_META_PATH, 'w', encoding='utf-8') as handle:
        json.dump(
            {
                'dim': dimension,
                'n_vectors': vector_count,
                'chunk_id_order': chunk_id_order,
            },
            handle,
            indent=2,
        )


def try_load_index() -> Optional[faiss.Index]:
    if not cfg.FAISS_INDEX_PATH.is_file():
        return None
    return faiss.read_index(str(cfg.FAISS_INDEX_PATH))


def reconstruct_rows_for_search_ids(
    index: faiss.Index,
    row_ids: list[int],
) -> np.ndarray:
    if not row_ids:
        return np.zeros((0, 0), dtype='float32')
    if hasattr(index, 'index'):
        inner = faiss.downcast_index(index.index)
    else:
        inner = faiss.downcast_index(index)
    rows: list[np.ndarray] = []
    for row_id in row_ids:
        vector = inner.reconstruct(int(row_id))
        rows.append(np.asarray(vector, dtype=np.float32).reshape(1, -1))
    return np.vstack(rows)


def search(
    query_vector: np.ndarray,
    top_k: int,
    index: faiss.Index,
) -> Tuple[np.ndarray, np.ndarray]:
    query = query_vector.astype('float32')
    if query.ndim == 1:
        query = query.reshape(1, -1)
    query = _l2_row_normalise(query)
    return index.search(query, int(top_k))
