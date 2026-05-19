#!/usr/bin/env python3
"""
SOILL Catalogue of Best Practices (T4.4) — build FAISS index from MongoDB articles
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Reads all articles from MONGO_COLLECTION, clears MONGODB_CHUNKS_COLLECTION,
re-embeds every chunk, and replaces data/faiss/index.faiss (full rebuild).

Usage:
    python build_faiss_index.py

Requires:
    - MongoDB running (see mongodb_docker/)
    - MISTRAL_API_KEY in .env
    - Articles already scraped (SOILL_scrape.py)
"""

from __future__ import annotations

import sys

from soill_chatbot.ingest import build_index_from_webscrape


def main() -> None:
    try:
        build_index_from_webscrape()
    except FileNotFoundError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
