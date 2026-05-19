"""Mistral embedding calls (L2-normalised for FAISS inner product)."""

from __future__ import annotations

from typing import Sequence

import numpy as np

import config as cfg
from soill_chatbot.mistral_client import Mistral


def get_client() -> Mistral:
    if not cfg.MISTRAL_API_KEY:
        raise RuntimeError('MISTRAL_API_KEY is not set. Add it to your .env file.')
    return Mistral(api_key=cfg.MISTRAL_API_KEY)


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (vectors / norms).astype('float32')


def _one_batch(client: Mistral, batch: list[str], normalise: bool) -> np.ndarray:
    response = client.embeddings.create(
        model=cfg.MISTRAL_EMBED_MODEL,
        inputs=batch,
    )
    if not response or not response.data:
        raise RuntimeError('Mistral embeddings response had no data.')

    def _order(item) -> int:
        index = getattr(item, 'index', None)
        return int(index) if index is not None else 0

    items = sorted(response.data, key=_order)
    rows: list[Sequence[float]] = []
    for item in items:
        embedding = item.embedding
        if embedding is None:
            raise RuntimeError('Mistral embedding entry had no vector.')
        rows.append(embedding)

    matrix = np.array(rows, dtype='float32')
    if normalise:
        matrix = _normalise(matrix)
    return matrix


def embed_texts(
    client: Mistral,
    texts: Sequence[str],
    normalise: bool = True,
) -> np.ndarray:
    """Return (n, d) float32 embeddings for the given strings."""
    if not texts:
        return np.zeros((0, 0), dtype='float32')

    batches: list[np.ndarray] = []
    batch: list[str] = []
    for text in texts:
        batch.append(text)
        if len(batch) >= cfg.EMBED_BATCH_SIZE:
            batches.append(_one_batch(client, batch, normalise))
            batch = []
    if batch:
        batches.append(_one_batch(client, batch, normalise))
    return np.vstack(batches)


def embed_query(client: Mistral, text: str) -> np.ndarray:
    """Single query vector, shape (1, d), L2-normalised."""
    return embed_texts(client, [text], normalise=True)
