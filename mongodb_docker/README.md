# Local MongoDB (Docker) for SOILL Best Practices

**Alternative:** you can use cloud MongoDB (e.g. Atlas) instead of Docker — set `MONGO_URI` in `.env` and skip this folder. See the [main README](../README.md) § MongoDB.

Docker Compose starts MongoDB using **only values from the project root [`.env`](../.env)**. `docker-compose.yml` contains no host names, ports, or container names (safe to commit to Git).

**Setup:** copy [`.env.example`](../.env.example) to `.env` in the repository root and edit your local values. **Do not commit `.env`.**

## Prerequisites

- [Docker Desktop](https://www.docker.com/) installed and running
- `.env` in the repository root (from `.env.example`)

## Environment variables

All variables live in the root `.env`. The sections below match [`.env.example`](../.env.example).

### Used by Docker Compose (`docker-compose.yml`)

| Variable | Description |
|----------|-------------|
| `MONGO_IMAGE` | Docker image tag (e.g. `mongo:7`) |
| `MONGO_HOST` | Host interface to bind (e.g. `127.0.0.1`) |
| `MONGO_PORT` | Port published on your machine (e.g. `27017`) |
| `MONGO_CONTAINER_NAME` | Docker container name (choose a unique local name) |
| `MONGO_VOLUME_NAME` | Named volume for persistent data |
| `MONGO_DB` | Initial database name created when the container first starts |

### Used by Python scripts (same `.env`)

| Variable | Description |
|----------|-------------|
| `MONGO_URI` | Connection string — **must use the same host and port** as `MONGO_HOST` and `MONGO_PORT` |
| `MONGO_DB` | Database name (same value as for Docker) |
| `MONGO_COLLECTION` | Scraped articles (e.g. `webscrape`) |
| `MONGODB_CHUNKS_COLLECTION` | RAG chunks (created by `build_faiss_index.py`) |
| `MONGODB_CONVERSATIONS_COLLECTION` | Optional chat logs from the UI |

Loaded by [`config.py`](../config.py) for all Python scripts.

Crawl and Mistral settings are documented in the [main README](../README.md); they are not used by Docker.

### Consistency check

If you change `MONGO_HOST` or `MONGO_PORT`, update `MONGO_URI` to match, for example:

```text
MONGO_HOST=127.0.0.1
MONGO_PORT=27017
MONGO_URI=mongodb://127.0.0.1:27017/
```

## Start MongoDB

Run from the **repository root** (not from `mongodb_docker/`):

```bash
docker compose -f mongodb_docker/docker-compose.yml --env-file .env up -d
```

Check status:

```bash
docker compose -f mongodb_docker/docker-compose.yml --env-file .env ps
```

## Initialise the application database

With MongoDB running, from the repository root (virtual environment active):

```bash
source .venv/bin/activate
python Create_SOILL_Best_Practices_database.py
```

This creates `MONGO_DB` and `MONGO_COLLECTION` with JSON schema validation. See the [main README](../README.md) for scraping, indexing, and the chatbot.

To drop and recreate **only** the articles collection (deletes scraped data):

```bash
python Create_SOILL_Best_Practices_database.py --reset
```

## Stop MongoDB

Stop the container but **keep** data in the volume:

```bash
docker compose -f mongodb_docker/docker-compose.yml --env-file .env down
```

Stop and **delete** the volume (wipes all MongoDB data, including chunks and chat logs):

```bash
docker compose -f mongodb_docker/docker-compose.yml --env-file .env down -v
```

## Troubleshooting

**Connection refused**

- Confirm Docker Desktop is running.
- Check `MONGO_HOST`, `MONGO_PORT`, and `MONGO_URI` in `.env` are consistent.
- Run `docker compose -f mongodb_docker/docker-compose.yml --env-file .env ps` — the service should be `running`.

**Port already in use**

- Change `MONGO_PORT` in `.env` (e.g. `27018`) and update `MONGO_URI` to match, then run `up -d` again.

**`.env` not found**

- Copy `.env.example` to `.env` in the **repository root**, not inside `mongodb_docker/`.

**Variable not substituted / empty container name**

- Always pass `--env-file .env` and run Compose from the repository root.

## Application collections

| Setting | Created by | Role |
|---------|------------|------|
| `MONGO_COLLECTION` | `Create_SOILL_Best_Practices_database.py` | Scraped articles (`SOILL_scrape.py`) |
| `MONGODB_CHUNKS_COLLECTION` | `build_faiss_index.py` | Embedded chunks for RAG |
| `MONGODB_CONVERSATIONS_COLLECTION` | Chatbot (if `LOG_CONVERSATIONS=true`) | Optional interaction log |

When using **cloud MongoDB** (Atlas) via `MONGO_URI` in `.env`, you do not need local Docker; chat logs are still written to `MONGODB_CONVERSATIONS_COLLECTION` in `MONGO_DB`.

FAISS files live under `data/faiss/` (gitignored), not in MongoDB.

## See also

- [Main project README](../README.md) — full workflow, crawl scope, licence
- [`.env.example`](../.env.example) — committed template (no secrets)
- [LICENSE](../LICENSE) — CC BY 4.0
