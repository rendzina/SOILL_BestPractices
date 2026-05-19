"""Word-based chunking for scraped article text."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import config as cfg


@dataclass
class TextChunk:
    """One slice of an article, ready to embed and store."""

    chunk_index: int
    text: str
    chunk_id: str


def stable_chunk_id(article_key: str, content_hash: str, chunk_index: int) -> str:
    """Deterministic id so MongoDB and FAISS refer to the same record."""
    raw = f'{article_key}\0{content_hash}\0{chunk_index}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def content_hash(title: str, description: str, url: str) -> str:
    """Fingerprint article body for change detection."""
    raw = f'{title}\n{description}\n{url}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def chunk_article_text(
    text: str,
    article_key: str,
    fingerprint: str,
) -> list[TextChunk]:
    """
    Build overlapping word windows from article title + description.
    Default: ~500 words with 100-word overlap (stride 400).
    """
    words = text.split()
    if not words:
        return []

    size = cfg.CHUNK_SIZE_WORDS
    stride = cfg.CHUNK_STRIDE_WORDS
    if stride <= 0 or size <= 0:
        return []

    chunks: list[TextChunk] = []
    start = 0
    idx = 0
    total = len(words)

    while start < total:
        end = min(start + size, total)
        segment = ' '.join(words[start:end]).strip()
        if segment:
            chunks.append(
                TextChunk(
                    chunk_index=idx,
                    text=segment,
                    chunk_id=stable_chunk_id(article_key, fingerprint, idx),
                )
            )
            idx += 1
        if end >= total:
            break
        start += stride

    return chunks
