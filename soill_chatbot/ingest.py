"""Build RAG chunks and embeddings from scraped articles in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import config as cfg
from soill_chatbot.mistral_client import Mistral
from soill_chatbot import chunking, embeddings, store_faiss, store_mongo


def _article_key(article: Dict[str, Any]) -> str:
    return str(article.get('_id', ''))


def _article_body(article: Dict[str, Any]) -> str:
    title = (article.get('title') or '').strip()
    description = (article.get('description') or '').strip()
    if title and description:
        return f'{title}\n\n{description}'
    return title or description


def ingest_articles_from_webscrape(client: Mistral) -> tuple[int, int]:
    """
    Read all documents from the webscrape collection, chunk, embed, and store
    in the chunks collection. Returns (articles_processed, chunks_created).
    """
    store_mongo.init_indexes()
    articles = store_mongo.fetch_all_articles()
    if not articles:
        return 0, 0

    deleted = store_mongo.clear_chunks()
    print(f'Cleared {deleted} existing chunk(s) from {cfg.MONGODB_CHUNKS_COLLECTION}.')

    chunk_docs: List[Dict[str, Any]] = []
    texts_to_embed: List[str] = []
    metadata_rows: List[Dict[str, Any]] = []

    for article in articles:
        body = _article_body(article)
        if not body.strip():
            continue

        article_id = _article_key(article)
        url = (article.get('url') or article.get('source') or '').strip()
        fingerprint = chunking.content_hash(
            article.get('title', ''),
            article.get('description', ''),
            url,
        )
        chunks = chunking.chunk_article_text(body, article_id, fingerprint)
        if not chunks:
            continue

        for chunk in chunks:
            texts_to_embed.append(chunk.text)
            metadata_rows.append({
                'chunk_id': chunk.chunk_id,
                'chunk_index': chunk.chunk_index,
                'article_id': article_id,
                'project_name': article.get('project_name', ''),
                'title': article.get('title', ''),
                'url': url,
                'source': article.get('source', ''),
                'seed_url': article.get('seed_url', ''),
                'source_domain': article.get('source_domain', ''),
            })

    if not texts_to_embed:
        return len(articles), 0

    print(f'Embedding {len(texts_to_embed)} chunk(s) via Mistral …')
    matrix = embeddings.embed_texts(client, texts_to_embed, normalise=True)
    now = datetime.now(timezone.utc)

    for index, meta in enumerate(metadata_rows):
        chunk_docs.append({
            **meta,
            'text': texts_to_embed[index],
            'embedding': matrix[index].tolist(),
            'indexed_at': now,
        })

    store_mongo.insert_chunk_docs(chunk_docs)
    return len(articles), len(chunk_docs)


def build_index_from_webscrape() -> int:
    """Full pipeline: webscrape → chunks → FAISS. Returns FAISS vector count."""
    store_mongo.ping_mongodb()
    article_count = store_mongo.count_articles()
    if article_count == 0:
        raise RuntimeError(
            f'No articles in {cfg.MONGO_DB}.{cfg.MONGO_COLLECTION}. '
            'Run SOILL_scrape.py first.'
        )

    client = embeddings.get_client()
    articles_processed, chunks_created = ingest_articles_from_webscrape(client)
    print(
        f'Processed {articles_processed} article(s); '
        f'created {chunks_created} chunk(s) in {cfg.MONGODB_CHUNKS_COLLECTION}.'
    )

    if chunks_created == 0:
        raise RuntimeError('No chunks were created — articles may have empty text.')

    vector_count = store_faiss.rebuild_faiss_from_mongo()
    print(f'FAISS index rebuilt with {vector_count} vector(s).')
    print(f'Index path: {cfg.FAISS_INDEX_PATH}')
    return vector_count
