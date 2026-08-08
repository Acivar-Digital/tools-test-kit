# BaziRAG FAQ — Classical Chinese Bazi Text Retrieval

## Overview

**What is BaziRAG?**
BaziRAG is a domain-specific RAG (Retrieval Augmented Generation) system for searching classical Chinese Bazi (Eight Characters / 八字) metaphysics texts. It combines a query-translation LLM agent, a dense vector store (TurboVec or Qdrant), and optional Redis caching.

**What source texts are covered?**
BaziRAG indexes traditional Bazi canons including *Yuan Hai Zi Ping*, *Zi Ping Zhen Quan*, *Qiong Tong Bao Jian*, *San Ming Tong Hui*, *Shen Feng Tong Kao*, *Qian Li Ming Gao*, *Di Tian Sui*, and *Ming Li Tan Yuan*. See `.env.example` → `RAG_DATA_DIR` for the full list.

**Is my data private?**
Yes. BaziRAG runs entirely locally — no API calls to external services unless you configure an embedding or LLM relay.

---

## Technical Architecture

**How does the embedding pipeline work?**
1. Source `.txt` files are cleaned and chunked (`run_rag_pipeline.py`).
2. Chunks are embedded via the BGE-M3 model (`BGEM3_URL`).
3. Embeddings are stored in TurboVec (`bazi_index.tv`) or Qdrant (`qdrant_db/`).
4. SQLite (`bazi_metadata.db`) stores chunk metadata and source text.

**What vector store is used?**
BaziRAG supports two backends:
- **TurboVec** (`bazirag.py`) — lightweight disk-based index
- **Qdrant** (`mcp_bazirag.py`) — embedded Qdrant with local path storage

**What embedding model is used?**
BGE-M3 (BAAI/bge-m3) served via the Text Embeddings Inference (TEI) router. Set `BGEM3_URL` and `BGEM3_TOKEN` in `.env`.

**How does query translation work?**
An LLM agent (`RAG_MODEL`) translates natural-language queries into exactly 3 Simplified Chinese search terms targeting (1) the Day Master/Stem-Branch, (2) the metaphysical structure (e.g. 食神, 官杀), and (3) the domain focus (e.g. 财运, 寿夭).

---

## Usage

**How do I run a query?**
```bash
# CLI
uv run python bazirag.py "Geng Metal day master with weak health and strong wood"
# or
uv run python query_cli.py "Geng Metal health"
```

**How to run as an MCP server?**
```bash
uv run python mcp_bazirag.py
# Then use with OpenCode or any MCP-compatible host
```

**What environment variables are required?**
Required at runtime: `BGEM3_URL` (embedding server), `RAG_MODEL` (translation LLM).
Everything else (`QDRANT_PATH`, `TURBOVEC_INDEX_PATH`, `BAZI_SQLITE_PATH`, Redis config) has sensible defaults.

**How to add my own texts?**
Drop `.txt` files into the directory pointed to by `RAG_DATA_DIR` (default `./data`). Re-run `run_rag_pipeline.py` to rebuild the index. Add the source to the `SOURCES` dict in `run_rag_pipeline.py` with its cleaning strategy.

---

## Comparison: bazirag vs mcp_bazirag

| Feature | `bazirag.py` | `mcp_bazirag.py` |
|---|---|---|
| Vector store | TurboVec | Qdrant |
| Entry point | CLI script | MCP server (stdio) |
| Query translation | Always via LLM | Falls back to heuristics if `RAG_MODEL` unset |
| Best for | Direct CLI usage | Integration with LLM agents / OpenCode |

---

## Performance & Caching

**Does BaziRAG cache results?**
Yes — `redis_cache.py` provides sync + async Redis caching for embeddings and query results. If Redis is unavailable, caching is silently disabled and queries proceed without cache.

**How do I enable Redis caching?**
```bash
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=1
```
Set `REDIS_HOST=disabled` or leave Redis down to skip caching.

---

## Troubleshooting

**"TurboVec index not found" / "SQLite metadata not found"**
Run the ingestion pipeline first: `uv run python run_rag_pipeline.py`

**"No baziRAG_model configured"**
Set `RAG_MODEL` in your `.env` file (e.g. `google/gemini-2.0-flash`).

**"Qdrant collection not found"**
Ensure `RAG_DATA_DIR/qdrant_db/bazi_classical` exists. Run `run_rag_pipeline.py` to populate it.

**"Embedding failed" / HTTP 401**
Check `BGEM3_URL` and `BGEM3_TOKEN` in `.env`.

---

## Deployment

**Can I containerize BaziRAG?**
Yes — add a `Dockerfile` that copies `kit-tools/rag/`, installs dependencies (`turbovec`, `qdrant-client`, `redis`, `mcp`, `pydantic-ai`, `httpx`, `requests`), copies `.env`, and runs `python mcp_bazirag.py` or `python bazirag.py`.

**What Python version is required?**
Python 3.11+ (uses `list[str] | None` union syntax and Pydantic AI).

**How much disk space do the indexes need?**
- TurboVec index: ~1–5 MB (varies by text volume)
- Qdrant DB: ~10–100 MB (includes payload + vectors)
- Source `.txt` files: ~1–5 MB combined

---

## Development

**How to run tests?**
```bash
cd kit-tools/rag
uv run python query_cli.py "test query"
```

**How to verify portability?**
Run the gate checks:
```bash
grep -rn "from admin\.\|from TEST\.\|from infra\.codebase" kit-tools/rag/
uv run ruff check kit-tools/rag/
```
All should return clean when run from any directory.

## See also

- [README.md](README.md) — installation, setup, and architecture overview
- [GUIDE.md](../GUIDE.md) — unified quick-start with codebase search tools
- [codebase/](../codebase/) — portable codebase search/analyze tools
