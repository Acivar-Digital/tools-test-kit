# BaziRAG — Classical Chinese Bazi Text RAG

A decoupled, portable subset of the baziforecaster RAG stack. Searches classical
Bazi (eight-characters / 八字) metaphysics texts using:

- **Query translation** — Pydantic AI agent converts natural-language queries into
  3 precise Simplified-Chinese search terms (e.g. `戊土 财运 身弱`).
- **Dual vector backends** — `bazirag.py` uses a **TurboVec** index + SQLite
  metadata; `mcp_bazirag.py` uses an embedded **Qdrant** instance.
- **Optional caching** — Redis-backed embedding & query-result cache with graceful
  degradation (`redis_cache.py`).

## Quick Start

```bash
cd kit-tools/rag

# 1. Install dependencies
uv pip install turbovec qdrant-client redis mcp pydantic-ai httpx requests

# 2. Copy env template and edit
cp .env.example .env
# Set BGEM3_URL, RAG_MODEL, etc.

# 3. Provide your classical text data (if rebuilding)
# Place .txt files in ./data/

# 4. Run a query
uv run python bazirag.py "Geng Metal day master, weak health, wood strong"

# 5. Or use the CLI wrapper
uv run python query_cli.py "Geng Metal health"

# 6. Or run as an MCP server (stdio) for OpenCode
uv run python mcp_bazirag.py
```

## Files

| File | Purpose |
|---|---|
| `bazirag.py` | Core RAG: query translation, TurboVec+SQLite search, CLI entry |
| `mcp_bazirag.py` | MCP server variant using Qdrant for OpenCode integration |
| `query_cli.py` | Simple CLI wrapper around `bazirag.search_bazi` |
| `redis_cache.py` | Optional Redis caching layer (degrades gracefully) |
| `run_rag_pipeline.py` | Ingestion pipeline: chunk + embed + index classical texts |
| `bazirag.yaml` | Prompt template for the Pydantic AI translation agent |
| `.env.example` | All configurable runtime variables |

## Environment Variables

See `.env.example`. Key ones:

- `RAG_MODEL` — LLM for Chinese term translation (e.g. `openai/gpt-4o-mini`)
- `BGEM3_URL` — BGE-M3 embedding server (`/v1/embeddings`)
- `TURBOVEC_INDEX_PATH` / `BAZI_SQLITE_PATH` — vector index & metadata locations
- `QDRANT_PATH` / `COLLECTION_NAME` — Qdrant alternative backend
- `RAG_DATA_DIR` — directory for source `.txt` files and vector stores

## Decoupled

All internal repo coupling has been removed. Configuration flows entirely from
`.env` / environment variables. Set `RAG_DATA_DIR` to bundle your own
classical texts and data directory.

## See also

- [FAQ.md](FAQ.md) — SEO-friendly Q&A for common questions
- [GUIDE.md](../GUIDE.md) — unified quick-start with codebase tools
- [codebase/](../codebase/) — portable codebase search/analyze tools