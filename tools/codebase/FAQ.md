# kit-tools/codebase — FAQ

## Getting Started

**How do I set the target repository?**
```bash
cd kit-tools/codebase
cp .env.example .env
# Edit .env: set KIT_TARGET_ROOT=/path/to/your/repo
```

**What Python packages do I need?**
Minimal (stdlib only): `grep_codebase`, `read_file`, `list_files`, `get_file_symbols`,
`get_repo_structure`, `add_class`, `add_constant`, `add_function`, `add_import`,
`move_symbol`, `replace_function`, `replace_text`, `rename_file`, `write_file`, `delete_file`.

LLM-assisted tools require extra deps:
```bash
uv pip install "pydantic-ai[httpx]" qdrant-client numpy
```

## Tool Usage

**How to search for code patterns?**
```bash
python grep_codebase.py "def authenticate" "" --extension-filter ".py"
python grep_codebase.py "TODO" "" --case-sensitive
```

**How to do semantic search?**
```bash
python search.py "how does session handling work?"
# Requires KIT_QDRANT_URL + KIT_COLLECTION_NAME (after indexing)
```

**How to add a function to a file?**
```bash
python add_function.py --file src/auth.py --name verify_token \
  --source "def verify_token(token: str): return token"
```

**How to replace a function?**
```bash
python replace_function.py --file src/main.py --name old_handler --new-source "def old_handler(): ..."
```

**How to investigate a file?**
```bash
python investigate.py --filename src/main.py --query "any security issues?"
# Requires KIT_CODEBASE_MODEL to be set
```

## Environment Variables

| variable | default | description |
|---|---|---|
| `KIT_TARGET_ROOT` | **required** | Path to your target repository |
| `KIT_CODEBASE_MODEL` | `""` | LLM model for query translation (search/investigate) |
| `KIT_QDRANT_URL` | `http://localhost:6333` | Qdrant for embedding search |
| `KIT_QDRANT_TOKEN` | `""` | Bearer token for Qdrant |
| `KIT_COLLECTION_NAME` | `codebase_index` | Qdrant collection name |
| `KIT_INFRA_ROOT` | `""` | Infra root for knowledge graph (optional) |

## Troubleshooting

**"KIT_TARGET_ROOT is required" error**
Set it in `.env` or as an environment variable: `export KIT_TARGET_ROOT=/path/to/repo`

**grep_codebase finds nothing**
Check `--extension-filter` (must include the dot, e.g. `.py`). Use `*` for all extensions.

**"ModuleNotFoundError: No module named 'pydantic_ai'"**
Install extras: `uv pip install "pydantic-ai[httpx]" qdrant-client`

**Path escape error**
This is a security feature. All paths are sandboxed to `KIT_TARGET_ROOT`. Verify your path
doesn't traverse outside the target repo.

## Portability

**Can I run this on any repo?**
Yes — set `KIT_TARGET_ROOT` to any directory. All path resolution goes through
`_codebase_common.resolve_secure_path` which enforces sandboxing.

**How to verify portability?**
```bash
grep -rn "from admin\.\|from TEST\.\|from infra\.codebase" kit-tools/codebase/
uv run ruff check kit-tools/codebase/ --select E9,F63,F7,F82
```

## See also

- [README.md](README.md) — file list and quick start
- [GUIDE.md](../GUIDE.md) — unified quick-start with RAG tools
- [rag/](../rag/) — portable BaziRAG demonstration
