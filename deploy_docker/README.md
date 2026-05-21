# Docker deploy (`deploy_docker/`)

Short guide for the **production Chainlit image**. Full project workflow (scrape, index, local dev): [main README](../README.md).

## What the image contains

- `app.py`, `config.py`, `build_faiss_index.py`, `soill_chatbot/`, `.chainlit/`
- Runtime deps from `requirements-docker.txt` (Chainlit, FAISS, Mistral, MongoDB client)
- **Not** included: scraped data, FAISS files, or `.env` — those come from Atlas + host env vars

## Before you deploy

On your machine, against the same MongoDB you will use in production:

```bash
python build_faiss_index.py
```

Atlas should have articles in `webscrape` and embeddings in `chunks`.

## Local smoke test

From the **repository root**:

```bash
docker compose -f deploy_docker/docker-compose.yml --env-file .env up --build
```

→ http://localhost:8000

## Render.com

| Setting | Value |
|---------|--------|
| Root directory | *(empty — repo root)* |
| Environment | Docker |
| Dockerfile path | `deploy_docker/Dockerfile` |
| RAM | ≥ 512 MB |

**Environment variables** (minimum): `MONGO_URI`, `MONGO_DB`, `MISTRAL_API_KEY`, plus chat/RAG settings from [`.env.example`](../.env.example). Do not commit `.env`.

Optional: `REBUILD_FAISS_ON_START=1` forces a FAISS rebuild on every container start.

Render sets `PORT`; the entrypoint runs `chainlit run app.py --headless --host 0.0.0.0`.

**Ephemeral disk:** `data/faiss/` is recreated on startup from MongoDB when missing. Keep chunk embeddings in Atlas so restarts stay quick.

### Deploy failed at “rebuilding from MongoDB”

The Docker **build** succeeded; the container exited during **startup** (MongoDB or FAISS). Check Render logs after redeploying with the latest `prewarm_faiss.py` for a clearer `ERROR:` line.

| Cause | Fix |
|-------|-----|
| `MONGO_URI` still `127.0.0.1` | Set Atlas `mongodb+srv://…` in Render env vars |
| Atlas blocks Render | Atlas → Network Access → allow `0.0.0.0/0` (test) or Render IPs |
| Wrong password / user | Regenerate URI; URL-encode special characters in the password |
| No chunks in Atlas | Run `python build_faiss_index.py` locally against the same `MONGO_URI` |
| `MISTRAL_API_KEY` empty | Set in Render if the container must run a full index build |

## Files in this folder

| File | Purpose |
|------|---------|
| `Dockerfile` | Build image (context = repo root) |
| `docker-entrypoint.sh` | FAISS rebuild if needed, then Chainlit |
| `docker-compose.yml` | Local test (`../.env`) |
| `requirements-docker.txt` | Slim runtime dependencies |
| `.dockerignore` | Exclude secrets and local `data/faiss/` from build |
