# kit-tools

Community-facing utility scripts extracted into `ai-factory/tools/`.
Runs inside `ai-factory`: `uv run python tools/<tool>.py "args"`.

> **New:** Fully portable versions live in `codebase/` and `rag/`. See
> [GUIDE.md](GUIDE.md) for quick-start cross-references.

## Portability

`tools/` is fully portable via `KIT_*` environment variables (see `.env.example`).
Each tool declares its required env vars at the top. If a tool needs internal infra
that isn't available locally, it raises a clear `RuntimeError` rather than failing silently.

| category | tools | notes |
|---|---|---|
| **Codebase search & analysis** | `search.py`, `investigate.py`, `grep_codebase.py`, `read_file.py`, `list_files.py`, `get_file_symbols.py`, `get_repo_structure.py`, `query_knowledge_graph.py`, `graph_health.py` | Semantic search, file discovery, code hierarchy. Requires `KIT_TARGET_ROOT`. |
| **Code modification (AST)** | `add_function.py`, `add_class.py`, `add_constant.py`, `add_import.py`, `replace_function.py`, `replace_text.py`, `move_symbol.py`, `rename_file.py`, `delete_file.py`, `write_file.py`, `repair_imports.py` | Surgical edits via AST. Requires `KIT_TARGET_ROOT`. |
| **Index & collection management** | `index_repository.py`, `verify_file_path.py`, `load_schema_gate.py` | One-shot indexing, path validation, schema gates. Requires `KIT_TARGET_ROOT`, `KIT_COLLECTION_NAME`. |
| **DevOps / system** | `web.sh`, `mcp_git_guardrail.py`, `guardrail_check.py`, `smoke_test.py` | Git guardrails, smoke tests, web launcher. |
| **Utility / self-tests** | `_codebase_common.py`, `_fix_preprocess2.py`, `_gen_utils.py`, `_test_tools.py`, `control.py` | Shared helpers, env control, cleanup scripts. |
| **RAG demonstration** | `rag/bazirag.py`, `rag/mcp_bazirag.py`, `rag/query_cli.py`, `rag/redis_cache.py`, `rag/run_rag_pipeline.py` | Domain-specific RAG demo (see `rag/README.md`). |

## Quick start (anywhere)

```bash
cd /path/to/kit-tools
cp .env.example .env
# edit .env: set KIT_TARGET_ROOT to your target repository
uv venv
uv pip install python-dotenv pydantic-ai httpx qdrant-client numpy trafilatura pyyaml fastmcp
python control.py                          # verify config
uv run python search.py "query"            # semantic search
uv run python investigate.py --filename src/main.py --query "issues?"
```

## test/

`run_all.py` + self-tests for kit-tools. `cd kit-tools && uv run pytest test/ -q`.

## rag/

Domain-specific RAG demonstration (BaziRAG). See `rag/README.md`.

## See also

- [GUIDE.md](GUIDE.md) — unified quick-start spanning `codebase/` + `rag/`
- [codebase/README.md](codebase/README.md) — portable codebase search/analyze tools
- [codebase/FAQ.md](codebase/FAQ.md) — FAQ for codebase tools
- [rag/README.md](rag/README.md) — portable BaziRAG demo
- [rag/FAQ.md](rag/FAQ.md) — FAQ for RAG tools
