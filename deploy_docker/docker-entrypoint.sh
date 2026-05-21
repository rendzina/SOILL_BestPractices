#!/bin/sh
set -e
cd /app

# Rebuild FAISS on disk from MongoDB when the index is missing or forced.
# Uses existing chunk embeddings when present (no re-embed); otherwise runs the
# full build_faiss_index.py pipeline (requires articles in webscrape + MISTRAL_API_KEY).
if [ ! -f data/faiss/index.faiss ] || [ "${REBUILD_FAISS_ON_START:-0}" = "1" ]; then
  echo "FAISS index missing or REBUILD_FAISS_ON_START=1 — rebuilding from MongoDB..."
  vector_count="$(python -c "
from soill_chatbot import store_faiss, store_mongo
store_mongo.ping_mongodb()
print(store_faiss.rebuild_faiss_from_mongo())
")"
  echo "FAISS vectors from chunks: ${vector_count}"
  if [ "${vector_count}" = "0" ]; then
    echo "No chunk embeddings in MongoDB — running full index build (build_faiss_index.py)..."
    python build_faiss_index.py
  fi
fi

PORT="${PORT:-8000}"
exec chainlit run app.py --headless --host 0.0.0.0 --port "${PORT}"
