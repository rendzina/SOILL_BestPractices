# SOILL Catalogue of Best Practices (Task T4.4)

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

**Author:** Prof. S. Hallett, Cranfield University
**Date:** 19/5/2026
**Licence:** [CC BY 4.0](LICENSE)

Toolkit for the [SOILL](https://www.soill2030.eu/) project (Support Structure for Soil Health Living Labs and Lighthouses). It crawls partner project websites, stores extracted articles in MongoDB, builds a local FAISS retrieval index, and answers questions via a Chainlit chatbot.

## What it does

1. **Database setup** — Creates the MongoDB database and article collection (names from `.env`).
2. **Web scraping** — Crawls seed URLs in `urls_to_scrape.txt`, extracts HTML articles, and appends them to MongoDB.
3. **RAG index** — Chunks and embeds articles (Mistral), stores vectors in MongoDB and FAISS.
4. **Chatbot** — Retrieves relevant chunks and answers with cited sources (Chainlit UI or terminal CLI).

## How to use the system

```mermaid
flowchart TB
    subgraph setup [One-time setup]
        A[Clone repository] --> B["Configure .env<br/>(from .env.example)"]
        B --> C["Start MongoDB<br/>docker compose … up -d"]
        C --> D["Python venv + pip install<br/>requirements.txt"]
        D --> E["Create database<br/>Create_SOILL_Best_Practices_database.py"]
    end

    subgraph ingest [Ingest partner content]
        F["Edit urls_to_scrape.txt<br/>(seed URLs + project names)"] --> G["Crawl websites<br/>SOILL_scrape.py"]
        G --> H[("MongoDB<br/>scraped articles")]
    end

    subgraph rag [Build retrieval index]
        H --> I["Chunk + embed articles<br/>build_faiss_index.py"]
        I --> J[("MongoDB<br/>chunks + embeddings")]
        I --> K[("FAISS index<br/>data/faiss/")]
    end

    subgraph query [Query the catalogue]
        J --> L{Choose interface}
        K --> L
        L --> M["Web UI<br/>chainlit run app.py"]
        L --> N["Terminal<br/>python chat_cli.py"]
    end

    E --> F

    G -.->|"More projects:<br/>add URLs, run scrape again"| F
    G -.->|"Then refresh index"| I
```

**Full reset** (wipe articles and start over): run `Create_SOILL_Best_Practices_database.py --reset`, then scrape and `build_faiss_index.py` again. `--reset` does not delete the FAISS files until you rebuild the index.

## Project layout

| Path | Purpose |
|------|---------|
| `Create_SOILL_Best_Practices_database.py` | Create or reset the scraped-articles collection |
| `SOILL_scrape.py` | Crawl websites and save articles |
| `build_faiss_index.py` | Rebuild chunks + FAISS from all articles in MongoDB |
| `app.py` | Chainlit web UI (`chainlit run app.py`) |
| `chat_cli.py` | Terminal chat (no Chainlit; works on Python 3.14) |
| `config.py` | Loads settings from `.env` |
| `.env.example` | Template for `.env` (committed) |
| `urls_to_scrape.txt` | Seed URLs and project names (CSV) |
| `soill_chatbot/` | RAG package (chunking, embeddings, FAISS, Mistral) |
| `mongodb_docker/` | Docker Compose for local MongoDB |
| `public/` | Logos, favicon, Chainlit welcome CSS |
| `.chainlit/` | Chainlit UI configuration |
| `webscraping-important-considerations.md` | Ethics and crawling guidelines |

Generated locally (gitignored): `.env`, `.venv/`, `logs/`, `data/faiss/`.

## Prerequisites

- Python **3.10–3.13** for Chainlit (`app.py`); **3.14** is fine for scraping and `chat_cli.py`
- pip
- Docker (for local MongoDB)
- [Mistral API](https://console.mistral.ai/) key for embeddings and chat

## Quick start

### 1. Clone and configure

```bash
git clone <repository-url>
cd SOILL_BestPractices
cp .env.example .env
```

Edit `.env` — set `MONGO_DB`, `MISTRAL_API_KEY`, and other values. **Do not commit `.env`.**

| Variable | Description |
|----------|-------------|
| `MONGO_URI` | MongoDB connection string |
| `MONGO_DB` | Database name (e.g. `SOILL_catalogue`) |
| `MONGO_COLLECTION` | Scraped articles (e.g. `webscrape`) |
| `MONGODB_CHUNKS_COLLECTION` | RAG chunks with embeddings |
| `MIN_DELAY` | Minimum seconds between HTTP requests |
| `REQUEST_TIMEOUT` | HTTP timeout (seconds) |
| `MAX_PAGES_PER_SITE` | Page cap per seed (`0` = no cap) |
| `MISTRAL_API_KEY` | Mistral API key |
| `MISTRAL_CHAT_MODEL` | Chat model (see `.env.example` for fallbacks) |
| `RAG_TOP_K` | Chunks retrieved per question |

See [`.env.example`](.env.example) for the full list.

### 2. MongoDB (Docker)

From the repository root:

```bash
docker compose -f mongodb_docker/docker-compose.yml --env-file .env up -d
```

Details: [mongodb_docker/README.md](mongodb_docker/README.md).

### 3. Python environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create the database (first time only)

```bash
python Create_SOILL_Best_Practices_database.py
```

To **wipe all scraped articles** and recreate the collection:

```bash
python Create_SOILL_Best_Practices_database.py --reset
```

This does **not** remove the FAISS index or `chunks` collection; run `build_faiss_index.py` after re-scraping.

### 5. Scrape

Edit `urls_to_scrape.txt`, then:

```bash
python SOILL_scrape.py
```

Console progress and `logs/SOILL_scrape_*.log`.

### 6. Build the FAISS index

```bash
python build_faiss_index.py
```

Reads **all** articles in `MONGO_COLLECTION`, clears `MONGODB_CHUNKS_COLLECTION`, re-embeds, and replaces `data/faiss/index.faiss`. Re-run after any scrape that changes the catalogue.

### 7. Run the chatbot

**Web UI (Chainlit):**

```bash
chainlit run app.py
```

Open http://localhost:8000 (or the URL shown).

If you see `anyio.NoEventLoopError`, use Python 3.13 for the venv.

**Terminal:**

```bash
python chat_cli.py
```

Type `quit` to exit. Restart Chainlit after rebuilding the index.

## Adding projects without wiping the database

1. Add new lines to `urls_to_scrape.txt` (comment out seeds already scraped if you only want new sites).
2. Run `python SOILL_scrape.py` — new articles are **appended** (no `--reset`).
3. Run `python build_faiss_index.py` — re-indexes the **entire** catalogue in MongoDB.

**Note:** Re-scraping the same URL can create duplicate MongoDB documents (deduplication is per crawl run only). To refresh one project, delete its documents first:

```bash
mongosh "$MONGO_URI" --eval 'db.getSiblingDB("SOILL_catalogue").webscrape.deleteMany({ project_name: "GOV4ALL" })'
```

Adjust database and collection names to match `.env`.

## Seed URLs and crawl scope

`urls_to_scrape.txt` format: `URL,ProjectName`

```text
# Nested project page — crawl only under this path
https://www.example.org/projects/demo,DemoProject

# Domain root — crawl entire site on that host
https://partner-site.eu,PartnerSite
```

- Lines starting with `#` are comments.
- `ProjectName` is stored as `project_name` on each article.
- **Nested seeds** (e.g. `/projects/gov4all`): crawler stays on the same domain and **only under that path prefix**; it does not walk up to parent sections.
- **Domain-root seeds**: full same-domain crawl (subject to `MAX_PAGES_PER_SITE` and `robots.txt`).

## Article schema (`MONGO_COLLECTION`)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Article heading |
| `description` | string | Body text |
| `url` | string | Article or canonical URL |
| `scrape_date` | date (UTC) | When scraped |
| `content_type` | string | Always `article` |
| `source` | string | Page URL where the block was found |
| `seed_url` | string | Seed from `urls_to_scrape.txt` |
| `project_name` | string | Label from `urls_to_scrape.txt` |
| `source_domain` | string | Hostname |
| `heading_level` | string | Optional HTML heading tag |

## How scraping works

For each seed in `urls_to_scrape.txt`, in order:

1. Start at the seed URL (breadth-first, same domain, path prefix if nested).
2. Find **articles**: `<article>` or blocks whose CSS class matches markers in `CONTENT_CLASSES` (`SOILL_scrape.py`).
3. Insert into MongoDB with delays, `robots.txt` checks, and in-run duplicate detection.

See [webscraping-important-considerations.md](webscraping-important-considerations.md).

## Logs

```bash
ls logs/
tail -f logs/SOILL_scrape_*.log
```

## Dependencies

See `requirements.txt`. Main packages: `pymongo`, `requests`, `beautifulsoup4`, `chainlit`, `faiss-cpu`, `mistralai`, `numpy`.

## Licence

Source code and documentation in this repository are licensed under [Creative Commons Attribution 4.0 International](LICENSE) (CC BY 4.0).

Scraped third-party website content is **not** covered by this licence; respect each source site’s terms of use and copyright.

## References

- [SOILL project](https://www.soill2030.eu/)
- [MongoDB with Docker](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-community-with-docker/)
- [Mission Soil catalogue (Zenodo)](https://zenodo.org/records/17549268)
- [Creative Commons BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Contact

SOILL@cranfield.ac.uk
