#!/usr/bin/env python3
"""
Startup helper for Docker/Render: verify MongoDB, rebuild FAISS if needed.
Prints clear errors to logs when configuration or Atlas access is wrong.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Script lives in deploy_docker/; app root is one level up (/app in Docker).
_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import config as cfg


def _mongo_hint() -> str:
    uri = (cfg.MONGO_URI or '').strip()
    if not uri:
        return 'MONGO_URI is empty — set it in Render Environment variables.'
    if uri.startswith('mongodb://127.0.0.1') or uri.startswith('mongodb://localhost'):
        return (
            'MONGO_URI points at localhost. On Render use your Atlas '
            'mongodb+srv://… connection string.'
        )
    return (
        'Check MONGO_URI credentials and Atlas Network Access '
        '(allow 0.0.0.0/0 for testing, or Render outbound IPs).'
    )


def main() -> int:
    print(f'Startup: database={cfg.MONGO_DB!r}, collection={cfg.MONGO_COLLECTION!r}')
    uri = (cfg.MONGO_URI or '').strip()
    if not uri:
        print(f'ERROR: {_mongo_hint()}', file=sys.stderr)
        return 1

    try:
        from soill_chatbot import store_faiss, store_mongo

        client = store_mongo.get_client()
        client.admin.command('ping')
        print('Startup: MongoDB ping OK')
        vector_count = store_faiss.rebuild_faiss_from_mongo()
        print(f'Startup: FAISS vectors from chunks: {vector_count}')
    except Exception as exc:
        print(f'ERROR: MongoDB or FAISS rebuild failed: {exc}', file=sys.stderr)
        print(f'Hint: {_mongo_hint()}', file=sys.stderr)
        traceback.print_exc()
        return 1

    if vector_count == 0:
        if not (cfg.MISTRAL_API_KEY or '').strip():
            print(
                'ERROR: No chunk embeddings in MongoDB and MISTRAL_API_KEY is unset. '
                'Run build_faiss_index.py locally against Atlas, or set MISTRAL_API_KEY.',
                file=sys.stderr,
            )
            return 1
        print('Startup: no chunks — running full build_faiss_index.py (may take several minutes)...')
        try:
            from build_faiss_index import main as build_main

            build_main()
        except Exception as exc:
            print(f'ERROR: build_faiss_index.py failed: {exc}', file=sys.stderr)
            traceback.print_exc()
            return 1

    if not cfg.FAISS_INDEX_PATH.is_file():
        print('ERROR: FAISS index file still missing after rebuild.', file=sys.stderr)
        return 1

    print('Startup: FAISS index ready')
    return 0


if __name__ == '__main__':
    sys.exit(main())
