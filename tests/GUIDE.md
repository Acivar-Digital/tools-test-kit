# Guide: How to Use and Configure This Test Kit

This guide walks you through **running the kit on your machine**, **configuring
it for your own environment**, and **knowing which files to ignore**.

---

## 1. Prerequisites

You need:

| Tool | Minimum | Why |
|---|---|---|
| Python | 3.11+ | f-strings `from __future__ import annotations`, modern syntax |
| `uv` | any | Fetches `pytest` + `hypothesis` from `pyproject.toml` automatically |

Install `uv` (one-liner, cross-platform):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or on macOS: brew install uv
# or on Windows: winget install astral.uv
```

That's it. No virtualenv, no conda, no Docker.

---

## 2. Clone and enter

```bash
git clone <this-repo-url> kit-tests
cd kit-tests
```

> **Note:** You only need the `tests/` subfolder. This kit is a standalone
> extraction — it does **not** need the parent `ai-factory` repo to run the
> examples.

---

## 3. Run the offline demos (no config needed)

```bash
uv run pytest examples -q
```

What happens:

- `uv` reads `pyproject.toml`, sees `pytest` and `hypothesis`, and fetches
  them into an ephemeral environment (no `venv` created in your folder).
- pytest collects the 8 files in `examples/`.
- All tests pass. No network, no API keys, no database.

**Expected output (tail):**

```
8 passed in 0.18s
```

You can also run a single file to see one pattern up close:

```bash
uv run pytest examples/05_hypothesis_fuzz.py -v
```

---

## 4. Folder visibility — what runs, what doesn't

### By default (bare `uv run pytest`), ONLY `examples/` is collected.

This is enforced in **two layers of defense**:

1. **`pyproject.toml`** has:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["examples"]
   ```
   So pytest only looks in `examples/` unless you explicitly point it elsewhere.

2. **`tests/conftest.py`** has a `collect_ignore` list that names every
   `01_gold_snapshots/` through `10_harness_suite/` directory. Even if pytest
   did look there, it would skip them.

### The `01_`–`09_` layers and `math_chapters/`, `param_flows/`

These are **full slices from the your-repo codebase**. They:

- Import `src2.*` (the original application source code)
- Hardcode references to `TEST/` and `GOLD/` directory paths
- Require a running PostgreSQL database (mocked in `infra/conftest.py`, but
  the underlying source tree is still needed)

**You cannot run these unless you already work on your-repo and have its
source tree checked out.** They're here as **reference material** — read the
test files to see how production patterns look in context, but don't expect
`uv run pytest` (with no arguments) to execute them.

### `10_harness_suite/`

A curated copy of ai-factory's own regression suite. It's **reference +
parse-clean** (syntax-checked) but **imports `factory.*`** — it's not meant to
run standalone either.

---

## 5. The live mode (optional, for real LLM interaction)

Three example files reference real infrastructure:

- `examples/02_snapshot_regression.py` — reads `KIT_PATH` for golden files
- `examples/06_kit_mem0_model.py` — calls `config.load_config()` which reads
  all `KIT_*` env vars
- `examples/test_kit_live_smoke.py` — validates the fail-fast behavior when
  `KIT_LIVE=true`

### Step 5a: Copy the env template

```bash
cp .env.example .env
```

Open `.env` in your editor. Here's what each variable means:

| Variable | Purpose | What to put |
|---|---|---|
| `KIT_LIVE` | Master switch. Set `false` for offline, `true` for live. | `true` or `false` (default) |
| `KIT_PATH` | Where the kit expects to find `src2/`, `TEST/`, `GOLD/` directories. | Absolute path to your your-repo checkout root |
| `KIT_BASE_URL` | The LLM API endpoint (e.g., Ollama, vLLM, OpenAI-compatible). | `http://localhost:8000` or your provider URL |
| `KIT_MODEL` | The chronomancer-layer model name (sent to the LLM API). | `gemma-2`, `phi-3`, etc. |
| `KIT_MEM0_MODEL` | The mem0-synthesis layer model name. **Independent** from `KIT_MODEL`. | `gemma-2-vision`, `nomic-embed-text`, etc. |
| `KIT_API_KEY` | Your LLM provider's API key. | `sk-...` (leave as-is if your endpoint doesn't need one) |
| `SENTRY_DSN` | Leave empty (kit is self-contained; no telemetry). | (empty) |
| `DISABLE_SENTRY` | Ensures no crash-reporting noise. | `1` (already set) |
| `DATABASE_URL` | Only needed for `05_integration_e2e/` and `param_flows/`. Not used by `examples/`. | `postgresql+asyncpg://...` or leave blank |

### Step 5b: Fail-fast behavior

`config.py` (at the kit root) reads `KIT_LIVE` at **import time**:

- If `KIT_LIVE=true` and **any** of `KIT_PATH`, `KIT_BASE_URL`, `KIT_MODEL`,
  `KIT_API_KEY` is missing or empty → it raises immediately:

  ```
  RuntimeError: KIT_LIVE=true but missing required env: KIT_PATH, KIT_API_KEY — set them in tests/.env.
  ```

  A test that's misconfigured **cannot silently proceed**. You always know what's
  wrong before any test code runs.

- If `KIT_LIVE=false` (default) → everything imports cleanly. No errors.

### Step 5c: Run with live mode

```bash
KIT_LIVE=true uv run pytest examples -q
```

The smoke test (`examples/test_kit_live_smoke.py`) proves this contract
programmatically.

---

## 6. Configuring for your own environment

### Scenario A: You're a student/newcomer (most common)

You don't have your-repo. You just want to learn the patterns.

```bash
cd kit-tests
uv run pytest examples -q
```

Done. Read the files in `examples/` in order (`01` through `06`, then
`test_kit_live_smoke.py`). Each has a docstring explaining the lesson and a
`if __name__ == "__main__"` block so you can run it directly:

```bash
uv run python examples/01_frozen_clock.py
```

### Scenario B: You work on your-repo and want the full suite

1. Clone your-repo to some directory, e.g. `/home/you/code/your-repo/`
2. Edit `tests/.env`:
   ```
   KIT_LIVE=true
   KIT_PATH=/home/you/code/your-repo
   KIT_BASE_URL=http://localhost:8000   # your LLM endpoint
   KIT_MODEL=gemma-2
   KIT_MEM0_MODEL=gemma-2-vision
   KIT_API_KEY=sk-your-real-key
   ```
3. Run specific layers (they're excluded from default collection):

   ```bash
   uv run pytest 01_gold_snapshots/ -q
   uv run pytest 04_bug_repros/ -q
   uv run pytest 06_property_fuzz/ -q
   ```

   Or run them all plus a layer that needs the source tree + DB:

   ```bash
   uv run pytest 01_gold_snapshots/ 02_unit_bedrock/ 04_bug_repros/ -q
   ```

   > `infra/conftest.py` patches `sqlalchemy.create_engine` to use SQLite
   > in-memory when it detects a `postgresql://` URL — so many integration tests
   > run without a real Postgres. But you still need `src2/` on the Python path,
   > which `KIT_PATH` sets up.

### Scenario C: You want to build your own test kit from a different codebase

1. Read [orchestrator.md](orchestrator.md) — it documents the exact extraction
   recipe: how the `0N_*` directories were curated from `your-repo/TEST/`,
   how PII was scrubbed, and how the `collect_ignore` / `testpaths` gates were
   wired.
2. Adapt the recipe: swap `your-repo/` for your repo, adjust the
   `0N_*` layer names to match your test categories, and update
   `pyproject.toml` with your dependencies.
3. Keep the `examples/` folder as your "cloner-runnable" gate — every commit
   must pass `uv run pytest examples -q` on a clean laptop.

---

## 7. Quick reference

```bash
# Offline demos (no setup)
uv run pytest examples -q

# Run one pattern file directly
uv run python examples/03_mutation_target.py

# Live mode (needs .env configured)
cp .env.example .env    # edit it
KIT_LIVE=true uv run pytest examples -q

# Run a your-repo layer (needs src2/ tree)
uv run pytest 04_bug_repros/ -v

# Check what pytest will collect (debug visibility)
uv run pytest --collect-only examples

# Run with async support (for param_flows/)
uv run pytest -c infra/pytest.ini param_flows/ -q

# Mutation testing (requires mutmut)
uv run mutmut run
uv run mutmut results
uv run mutmut apply 1
uv run mutmut html
```

---

## 8. Troubleshooting

### "ModuleNotFoundError: No module named 'src2'"

You're trying to run a `0N_*` layer or `param_flows/` without the your-repo
source tree. Either:

- **For learning:** stick to `examples/` (which works offline with no upstream).
- **For your-repo work:** set `KIT_PATH` to your your-repo checkout
  root in `.env`.

### "RuntimeError: KIT_LIVE=true but missing required env"

You set `KIT_LIVE=true` but didn't fill all four required variables. Open
`.env`, set `KIT_PATH`, `KIT_BASE_URL`, `KIT_MODEL`, `KIT_API_KEY`, and retry.

### Tests in `01_gold_snapshots/` etc. are not collected when I run `uv run pytest`

That's by design. Run them explicitly:

```bash
uv run pytest 01_gold_snapshots/ 04_bug_repros/ -q
```

### `uv run pytest` is slow / hanging

The `10_harness_suite/` and `math_chapters/` layers have import-time side
effects. Don't run them with a bare `uv run pytest`. Either target
`examples/` or specific layers.

---

## 9. What's a "pattern" worth studying?

Each file in `examples/` teaches one technique. Spend 5-10 minutes with each:

1. **Read the docstring** (first thing in the file — explains the lesson)
2. **Read the test** (usually 1 function, 3-8 assertions)
3. **Run it:** `uv run python examples/0X_name.py` (each has a `__main__` block)
4. **Tweak it:** change a value, break the test assertion, see the failure
   message
5. **Apply it:** copy the pattern into your own project

This is not "watch a video and take notes." This is **read it, run it, break
it, fix it**. That's how you internalize a testing technique.