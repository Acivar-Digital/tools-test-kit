# kit

**Portable, runnable slices of `baziforecaster`** — extracted so anyone can clone, configure, and run real ML-agent test & analysis patterns without a monorepo checkout, Docker, or API keys.

This kit exists to:

1. **Demonstrate engineering depth** — not just "vibe coding", but reproducible test design, AST-driven refactoring, static-analysis pipelines, and LLM-audit architecture.
2. **Give back to the community** — every tool is configurable via `KIT_*` environment variables. Copy a folder, set two env vars, and go.

---

## What's inside

| Folder | Purpose | Requires API key? | Quick run |
|--------|---------|-------------------|-----------|
| [`hygiene/`](./hygiene) | Technical-debt scanner — 11 static + LLM audit passes (silent exceptions, circular imports, hardcoded secrets, async hazards, schema drift, ...) | Offline by default; set `KIT_API_KEY` for LLM tiers | `cd hygiene && cp .env.example .env && uv run scanners/run_all.py --scripts` |
| [`tests/`](./tests) | Interview-ready test-pattern stubs — golden snapshots, property/fuzz, mutation testing, guardrail gates | Offline (`KIT_LIVE=false` is the default) | `cd tests && uv run pytest examples -q` |
| [`tools/`](./tools) | Codebase search, AST code-mod, RAG demo, dev/audit utilities. Fully portable via `KIT_TARGET_ROOT` | Offline; LLM tiers need `KIT_BASE_URL` / `KIT_API_KEY` | `cd tools && uv run python search.py "your query"` |

> Each subfolder has its own `pyproject.toml` / `requirements.txt` and `.env.example`. See the `GUIDE.md` in each folder for detailed setup.

---

## Quick start (any subfolder)

```bash
# 1. Pick a subfolder
cd kit/hygiene        # or tests/ or tools/

# 2. Copy the config template
cp .env.example .env
# Edit .env — set your target path or API key

# 3. Run
uv run ./scanners/run_all.py   # hygiene: offline static scan
uv run pytest examples -q      # tests: 7 cloner-safe stubs, no .env needed
uv run python search.py "?"    # tools: semantic search (set KIT_TARGET_ROOT)
```

Or run everything with one `uv` workspace:

```bash
uv sync --all-projects
```

---

## Architecture

```
kit/
├── hygiene/       # Codebase hygiene scanner (static AST + LLM audit)
│   ├── scanners/   # 11 individual scanners (run_all.py master runner)
│   ├── reports/    # Generated audit outputs
│   └── cleanup.py  # One-shot AST auto-fixer
├── tests/         # Runnable test-pattern stubs (interview-ready)
│   ├── examples/   # 5 self-contained, cloner-safe stubs ← START HERE
│   ├── 01_gold_snapshots/ ... 10_harness_suite/   # Curated slices
│   └── math_chapters/                            # Engine math tests
├── tools/         # Portable dev utilities
│   ├── codebase/   # Search / AST code-mod tools
│   ├── rag/        # BaziRAG domain-specific demo
│   └── test/       # Self-tests for kit-tools
├── bd             # Beads issue-tracking wrapper
├── .beads/        # Beads Dolt config (shared Dolt server: 127.0.0.1:15432)
├── AGENTS.md      # AI agent workflow pointer (run `bd prime` for full context)
└── pyproject.toml # uv workspace — manages all three subfolders
```

---

## Why this matters

`baziforecaster` has a huge, deeply coupled codebase. That's a strength in CI and a liability in an interview. This kit **slices the patterns out**, makes each one self-contained, and ships the minimum runnable artifact — so a candidate can clone one folder and immediately see:

- **Golden-snapshot testing** (`examples/01_git_snapshots.py`)
- **Property/fuzz testing** (`examples/06_property_fuzz.py`)
- **Silent-exception detection** (`hygiene/scanners/find_silent_killers.py`)
- **AST-driven refactoring** (`tools/replace_function.py`, `tools/add_import.py`)
- **RAG with vector search** (`tools/rag/bazirag.py`)

---

## License

MIT — see [`LICENSE`](./LICENSE). Built on top of `baziforecaster` (also MIT).

---

## Contributing

All content is **read-only** — this kit extracts from staging mirrors and never writes back upstream. To extend:

1. `./bd ready` — find unblocked work
2. `./bd create "Title" --type task --priority 2` — create an issue
3. Make changes → run `./bd doctor` → `./bd dolt push` → commit & push
