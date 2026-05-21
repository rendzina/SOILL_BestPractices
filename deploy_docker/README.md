# Docker deploy (Render.com and local smoke test)

Standalone container for the Chainlit UI (`app.py`). MongoDB and scraped content live **outside** the image (typically [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)); the container only needs network access and API keys.

## Prerequisites

1. Atlas (or other MongoDB) with articles in `webscrape` (from `SOILL_scrape.py`).
2. Chunk embeddings in MongoDB — run once on your machine:
   ```bash
   python build_faiss_index.py
   ```
   On first container start, if chunks exist but `data/faiss/` is empty, the entrypoint rebuilds FAISS from MongoDB without re-embedding. If there are no chunks, it runs `build_faiss_index.py` (needs `MISTRAL_API_KEY` and can take several minutes).

## Local smoke test

From the **repository root**:

```bash
docker compose -f deploy_docker/docker-compose.yml --env-file .env up --build
```

Open http://localhost:8000

## Render.com

1. Connect this GitHub repository.
2. **Root Directory**: leave empty (repository root).
3. **Environment**: Docker.
4. **Dockerfile path**: `deploy_docker/Dockerfile`
5. **Instance type**: at least 512 MB RAM (FAISS + Chainlit).
6. **Environment variables** (from `.env.example` — do not commit `.env`):

   | Variable | Notes |
   |----------|--------|
   | `MONGO_URI` | `mongodb+srv://…` Atlas URI |
   | `MONGO_DB` | e.g. `SOILL_catalogue` |
   | `MISTRAL_API_KEY` | Required for chat; required on first start if chunks must be built |
   | `MISTRAL_CHAT_MODEL` | e.g. `open-mistral-nemo` |
   | Other chat/RAG vars | As in `.env.example` |

   Render sets `PORT` automatically; the entrypoint binds Chainlit to `0.0.0.0` on that port.

7. Optional: `REBUILD_FAISS_ON_START=1` to refresh the on-disk index after every deploy (uses existing MongoDB embeddings when possible).

8. Deploy → use the generated `https://….onrender.com` URL for colleagues.

**Note:** Render’s filesystem is ephemeral. The FAISS files under `data/faiss/` are recreated on each new instance from MongoDB via the entrypoint; keep chunks in Atlas so restarts stay fast.

## Files

| File | Role |
|------|------|
| `Dockerfile` | Python 3.11 image, installs deps, copies app code |
| `docker-entrypoint.sh` | FAISS rebuild if needed, then `chainlit run app.py` |
| `docker-compose.yml` | Local test with `../.env` |
| `.dockerignore` | Keeps secrets and large local artefacts out of the build |
