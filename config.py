"""
SOILL Catalogue of Best Practices (T4.4) — shared configuration from .env
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Loaded by all Python scripts in this repository (scraper, database setup,
build_faiss_index, app.py, chat_cli.py, soill_chatbot package).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _ROOT / '.env'
load_dotenv(_ENV_PATH)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


# MongoDB — Docker
MONGO_IMAGE = os.getenv('MONGO_IMAGE', 'mongo:7')
MONGO_HOST = os.getenv('MONGO_HOST', '127.0.0.1')
MONGO_PORT = _env_int('MONGO_PORT', 27017)
MONGO_CONTAINER_NAME = os.getenv('MONGO_CONTAINER_NAME', 'local-mongo-dev')
MONGO_VOLUME_NAME = os.getenv('MONGO_VOLUME_NAME', 'local_mongo_data')

# MongoDB — application
MONGO_URI = os.getenv('MONGO_URI', f'mongodb://{MONGO_HOST}:{MONGO_PORT}/')
MONGO_DB = os.getenv('MONGO_DB', 'SOILL_catalogue')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'webscrape')

# Crawling
MIN_DELAY = _env_int('MIN_DELAY', 2)
REQUEST_TIMEOUT = _env_int('REQUEST_TIMEOUT', 15)
MAX_PAGES_PER_SITE = _env_int('MAX_PAGES_PER_SITE', 0)

# Chatbot — data paths
DATA_DIR = _ROOT / os.getenv('DATA_DIR', 'data')
FAISS_DIR = DATA_DIR / 'faiss'
FAISS_INDEX_PATH = FAISS_DIR / 'index.faiss'
FAISS_META_PATH = FAISS_DIR / 'meta.json'

# Chatbot — MongoDB collections
MONGODB_CHUNKS_COLLECTION = os.getenv('MONGODB_CHUNKS_COLLECTION', 'chunks')
MONGODB_CONVERSATIONS_COLLECTION = os.getenv(
    'MONGODB_CONVERSATIONS_COLLECTION', 'soill_conversations'
)

# Chatbot — Mistral API
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
MISTRAL_EMBED_MODEL = os.getenv('MISTRAL_EMBED_MODEL', 'mistral-embed')
MISTRAL_CHAT_MODEL = os.getenv('MISTRAL_CHAT_MODEL', 'mistral-small-latest')
MISTRAL_CHAT_MODEL_FALLBACK = os.getenv('MISTRAL_CHAT_MODEL_FALLBACK', '')
MISTRAL_CHAT_RETRY_COUNT = _env_int('MISTRAL_CHAT_RETRY_COUNT', 2)
MISTRAL_CHAT_RETRY_DELAY = _env_float('MISTRAL_CHAT_RETRY_DELAY', 2.0)

# Chatbot — retrieval
RAG_TOP_K = _env_int('RAG_TOP_K', 8)
RAG_MMR_ENABLED = _env_bool('RAG_MMR_ENABLED', True)
RAG_MMR_LAMBDA = min(1.0, max(0.0, _env_float('RAG_MMR_LAMBDA', 0.58)))
RAG_MMR_FETCH_MULT = min(8, max(2, _env_int('RAG_MMR_FETCH_MULT', 3)))
RAG_MMR_FETCH_CAP = min(64, max(12, _env_int('RAG_MMR_FETCH_CAP', 40)))

LOG_CONVERSATIONS = _env_bool('LOG_CONVERSATIONS', True)
LOG_CLIENT_METADATA = _env_bool('LOG_CLIENT_METADATA', True)

# Multi-turn chat (Chainlit / CLI)
CHAT_HISTORY_ENABLED = _env_bool('CHAT_HISTORY_ENABLED', True)
CHAT_HISTORY_TURNS = max(0, _env_int('CHAT_HISTORY_TURNS', 3))
CHAT_HISTORY_MAX_ANSWER_CHARS = max(200, _env_int('CHAT_HISTORY_MAX_ANSWER_CHARS', 1500))
CHAT_HISTORY_EXPAND_RETRIEVAL = _env_bool('CHAT_HISTORY_EXPAND_RETRIEVAL', True)
CHAT_HISTORY_RETRIEVAL_MAX_CHARS = max(500, _env_int('CHAT_HISTORY_RETRIEVAL_MAX_CHARS', 2000))

# Chatbot — chunking (word-based, overlapping)
CHUNK_SIZE_WORDS = _env_int('CHUNK_SIZE_WORDS', 500)
CHUNK_OVERLAP_WORDS = _env_int('CHUNK_OVERLAP_WORDS', 100)
CHUNK_STRIDE_WORDS = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS
EMBED_BATCH_SIZE = _env_int('EMBED_BATCH_SIZE', 32)
