# kit-tools/codebase — Portable Codebase Search & Analysis Tools

Self-contained CLI utilities for searching, analyzing, and modifying any codebase
via environment-variable configuration (no hardcoded paths).

## Files

| tool | purpose | dependencies |
|---|---|---|
| `search.py` | Semantic + keyword codebase search | pydantic-ai, qdrant-client, httpx, pydantic |
| `investigate.py` | Deep-dive file analysis | pydantic-ai |
| `grep_codebase.py` | Regex/grep search across files | stdlib |
| `read_file.py` | Read file content | stdlib |
| `list_files.py` | Glob/path listing | stdlib |
| `get_file_symbols.py` | Extract class/function symbols | stdlib |
| `get_repo_structure.py` | Directory tree view | stdlib |
| `add_class.py` | Add a class via AST | stdlib |
| `add_function.py` | Add a function via AST | stdlib |
| `add_constant.py` | Add a module constant | stdlib |
| `add_import.py` | Add an import statement | stdlib |
| `move_symbol.py` | Relocate a symbol | stdlib |
| `replace_function.py` | Replace a function via AST | stdlib |
| `replace_text.py` | Surgical text replacement | stdlib |
| `rename_file.py` | Rename a file safely | stdlib |
| `write_file.py` | Write/overwrite a file | stdlib |
| `delete_file.py` | Delete a file safely | stdlib |

## Quick Start

```bash
cd kit-tools/codebase
cp .env.example .env
# edit .env: set KIT_TARGET_ROOT to your target repository path

# stdlib-only tools (no pip install needed)
python grep_codebase.py "def main" "*.py"
python read_file.py "src/main.py"
python list_files.py "src/" "*.py"
python get_repo_structure.py "src/"

# LLM-assisted tools (requires pydantic-ai + optional Qdrant)
uv pip install "pydantic-ai[httpx]" qdrant-client
python search.py "how does session handling work?"
python investigate.py --filename src/main.py --query "any issues?"
```

## Environment Variables

| variable | required | description |
|---|---|---|
| `KIT_TARGET_ROOT` | yes | Path to your target repository |
| `KIT_CODEBASE_MODEL` | no | LLM model for query translation |
| `KIT_QDRANT_URL` | no | Qdrant URL for embedding search |
| `KIT_QDRANT_TOKEN` | no | Bearer token for Qdrant |
| `KIT_COLLECTION_NAME` | no | Qdrant collection name |
| `KIT_INFRA_ROOT` | no | Infre root for knowledge graph |

## Portability

All tools resolve paths via `KIT_TARGET_ROOT` — run from any directory.
The `_codebase_common.py` module enforces path escaping (paths cannot leave `KIT_TARGET_ROOT`).

## See also

- [FAQ.md](FAQ.md) — frequently asked questions
- [GUIDE.md](../GUIDE.md) — unified quick-start with RAG tools
- [rag/](../rag/) — portable BaziRAG demonstration
