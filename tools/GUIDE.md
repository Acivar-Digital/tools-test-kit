# kit-tools Guide — Unified Usage

Quick reference spanning both portable subdirectories.

## Two toolkits

| toolkit | purpose | docs |
|---|---|---|
| `codebase/` | Search, analyze, and modify any codebase via `KIT_TARGET_ROOT` | [README.md](codebase/README.md) |
| `rag/` | Domain-specific RAG on classical Bazi texts | [README.md](rag/README.md) |

## When to use what

- **Browse a repo, find code, fix bugs** → `codebase/` tools
  (`grep_codebase.py`, `search.py`, `investigate.py`, `add_function.py`, ...)
- **Query dense documents with LLM query-translation + embeddings** → `rag/` tools
  (`bazirag.py`, `query_cli.py`)

Both share the same env-var pattern: copy the local `.env.example`, set
`KIT_TARGET_ROOT`, then run from inside the toolkit folder.

```bash
# Codebase tools
cd tools/codebase
cp .env.example .env
python grep_codebase.py "def main" "" --extension-filter ".py"

# RAG demo
cd tools/rag
cp .env.example .env
uv run python query_cli.py "my Bazi question"
```

## FAQ

| question | answer |
|---|---|
| Where do I set the target repo? | `KIT_TARGET_ROOT` in either `.env` file |
| Do codebase and rag conflict? | No — they use separate `.env.example` files |
| Can I use search.py without Qdrant? | Yes — install deps but set `KIT_QDRANT_URL` to nothing and the LLM path degrades gracefully |
| Do I need Redis for RAG? | No — see [rag/FAQ.md](rag/FAQ.md#performance--caching) |
