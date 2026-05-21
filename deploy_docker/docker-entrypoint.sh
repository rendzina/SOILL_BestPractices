#!/bin/sh
set -e
cd /app

# Rebuild FAISS on disk from MongoDB when the index is missing or forced.
if [ ! -f data/faiss/index.faiss ] || [ "${REBUILD_FAISS_ON_START:-0}" = "1" ]; then
  echo "FAISS index missing or REBUILD_FAISS_ON_START=1 — rebuilding from MongoDB..."
  python deploy_docker/prewarm_faiss.py
fi

PORT="${PORT:-8000}"
echo "Starting Chainlit on 0.0.0.0:${PORT}..."
exec chainlit run app.py --headless --host 0.0.0.0 --port "${PORT}"
