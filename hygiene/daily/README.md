# Daily Checks

Scripts that run as part of the daily CI hygiene gate.

| File | Purpose |
|---|---|
| `dailygit-check.py` | Git hook gatekeeper — runs selected scanners on changed files only, blocks push on high-severity violations (async hazards, circular deps, secrets, env drift). |
| `dotenv.py` | Environment guard — fail-fast `RuntimeError` if `KIT_ENABLE_REGISTRY_CLASHES=true` but `KIT_API_KEY`/`KIT_MODEL` is missing. |

## Usage

`dailygit-check.py` is invoked from the git `pre-push` hook (see repo root `.git/hooks/pre-push`). It auto-detects changed Python files in `src2/` and `kit-hygiene/`, runs 9 scanners on them, then parses JSON reports for blocking violations.

```bash
# Manual run (scans all of src2/ + kit-hygiene/):
uv run kit-hygiene/daily/dailygit-check.py
```

## How it works

1. Gets changed files via `git diff HEAD` (falls back to `HEAD~1..HEAD` if no upstream).
2. Filters for `.py` files in `src2/` or `kit-hygiene/` not in `exceptions.json`.
3. Sets `HYGIENE_FILES_TO_SCAN` env and runs 9 scanners via `uv run python`.
4. Parses `<scanner>_audit.json` reports — blocks on: `ASYNC_HAZARD` (HIGH), circular deps (any), secrets (any), `DRIFT_VIOLATION` (HIGH).
5. Exits `1` if any blocking violation found, `0` otherwise.

See **[GUIDE.md](../GUIDE.md)** for full execution modes and **[FAQ.md](../FAQ.md)** for troubleshooting.
