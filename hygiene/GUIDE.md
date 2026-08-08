# 🧭 kit-hygiene Guide — Install, Configure & Run

> **Step-by-step. 5 minutes to your first audit. 5 minutes to your first audit.**

> **Related docs:** `README.md` (overview & scanner capabilities) · `FAQ.md` (troubleshooting & cost questions)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.14 | See `.python-version` |
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| API key | — | Only needed for LLM Tier 2 scanners. Tier 1 (static) runs offline. |

---

## 2. Installation

```bash
# Clone or copy hygiene/ into your repo (or alongside it)
# From your repo root:
cp hygiene/.env.example hygiene/.env
```

**Do not skip step 3.** If you leave `.env.example` as-is, the scanners will fail-fast on missing config.

---

## 3. Configuration

Open `hygiene/.env` in your editor. Here's what each variable does:

### Paths

| Variable | Purpose | Example |
|---|---|---|
| `AIB_FACTORY_ROOT` | Root of the directory tree containing kit-hygiene | `/home/user/my-repo` |
| `SCAN_ROOTS` | Comma-separated list of directories to scan | `./src` or `./src,./tests` |
| `TARGET_ROOT` | The codebase being audited (usually same as `AIB_FACTORY_ROOT`) | `/home/user/my-repo` |
| `HYGIENE_FILES_TO_SCAN` | Override — scan only specific files (comma-separated) | `./src/legacy.py,./src/auth.py` |
| `PATH_LEAK_ROOTS` | Paths the scanner must flag if they appear in your code | `/home,/mnt,/Users` (platform defaults) |
| `PATH_LEAK_ALLOWLIST` | Exempt specific path roots from the leak check | `./tests/mocks` |

**Quick mode (scan your own repo):**
```env
AIB_FACTORY_ROOT=/path/to/your/repo
SCAN_ROOTS=./src
TARGET_ROOT=/path/to/your/repo
```

### Thresholds

| Variable | Default | Effect |
|---|---|---|
| `HARD_FAIL_THRESHOLD` | `2` | `0`=ignore, `1`=warn+continue, `2+`=exit 1 |
| `SECRET_MAX_LINE` | (empty) | Max lines per file scanned for secrets |
| `DUPE_THRESHOLD_PCT` | `100` | % identity for duplicate detection (100=exact only) |

### LLM / API Settings (Tier 2 scanners only)

| Variable | Purpose | Required? |
|---|---|---|
| `KIT_ENABLE_REGISTRY_CLASHES` | Enable LLM audit in `find_registry_clashes.py` | `false` (set `true` to enable) |
| `KIT_BASE_URL` | Your LM proxy endpoint | Only if `KIT_ENABLE_REGISTRY_CLASHES=true` |
| `KIT_API_KEY` | API key for your LM proxy | Only if `KIT_ENABLE_REGISTRY_CLASHES=true` |
| `KIT_MODEL` | Model name to pass (e.g. `gemma-3-27b-it`) | Only if `KIT_ENABLE_REGISTRY_CLASHES=true` |

**If `KIT_ENABLE_REGISTRY_CLASHES=true` and any of `KIT_BASE_URL`/`KIT_API_KEY`/`KIT_MODEL` is empty → the scanner exits immediately with `RuntimeError`.** This is intentional (fail-closed).

### Feature toggles

| Variable | Default | Purpose |
|---|---|---|
| `ENABLE_DAILY_CHECKS` | `false` | Enables `daily/*.py` cron-style checks |
| `PYTHON_DEPS` | (empty) | Extra pip deps to install (leave empty for vendored loader) |

---

## 4. Running the Scanners

### 4a. Offline static scan (no API key needed)

This runs **Tier 1 only** — pure local AST analysis. Zero API calls, zero config.

```bash
# From repo root:
uv run hygiene/scanners/run_all.py --scripts
```

Output: JSON reports in `hygiene/reports/` (one per scanner).

### 4b. Full scan (with LLM verification)

```bash
uv run hygiene/scanners/run_all.py
```

This runs Tier 1 + Tier 2. You need valid `KIT_*` creds in `.env`.

### 4c. Individual scanner

```bash
uv run hygiene/scanners/find_silent_killers.py --scripts   # static only
uv run hygiene/scanners/find_silent_killers.py             # full (with LLM)
```

### 4d. Registry clashes scanner (long-running)

This scanner can take a long time (it reads your whole codebase context + invokes LLM). Run it in tmux:

```bash
hygiene/run-registry-scan.sh              # full mode
hygiene/run-registry-scan.sh --scripts    # static only
```

Detached in a tmux session named `registry-scanner`. Re-run to reattach.

### 4e. Diff mode

Only scan files changed in the current git state:

```bash
uv run hygiene/scanners/run_all.py --diff
```

---

## 5. Understanding the Reports

Each scanner writes two files to `hygiene/reports/`:

| File | Format | Contents |
|---|---|---|
| `<scanner_name>.json` | JSON | Machine-readable audit results |
| `<scanner_name>.md` | Markdown | Human-readable summary |

### JSON structure

```json
{
  "scanner": "find_silent_killers",
  "audit_results": [
    {
      "file_path": "src/auth/handlers.py",
      "line": 42,
      "name": "swallowed_exception",
      "type": "swallowed_exception",
      "status": "SILENT_KILLER",
      "severity": "HIGH",
      "reason": "Bare except swallows all exceptions including KeyboardInterrupt..."
    }
  ],
  "summary": {
    "total_candidates": 5,
    "true_positives": 2,
    "false_positives": 3
  }
}
 ```

### Verdict taxonomy

Each scanner uses scanner-specific severity labels:

- `SILENT_KILLER` vs `FALSE_POSITIVE` (find_silent_killers)
- `ASYNC_HAZARD` vs `SAFE` (find_async_hazards)
- `SCHEMA_HAZARD` vs `FALSE_POSITIVE` (find_engine_schemas, find_registry_clashes)
- `HARDCODED_SECRET` vs `FALSE_POSITIVE` (find_secrets)
- `ENV_DRIFT` vs `OK` (find_env_drift)
- `CIRCULAR_DEP` vs `FALSE_POSITIVE` (find_circular_deps)
- `DUPLICATE` vs `FALSE_POSITIVE` (find_duplication)
- `TYPE_ERROR` vs `FALSE_POSITIVE` (find_type_safety)
- `DEAD_CODE` vs `VERIFIED_LIVE` (find_dead_code)

---

## 6. Cache Management

Bot-driven scanners cache results **per candidate** in the JSON report.

- **Automatic**: On re-run, already-verified candidates are skipped (only line numbers updated if code shifted).
- **Manual invalidate**: If you refactored the code and want to force re-audit of specific files, delete the matching entries from the `<scanner_name>.json` file's `audit_results` array.
- **Full reset**: `rm hygiene/reports/*.json` then re-run.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `RuntimeError: KIT_API_KEY required` | Either set `KIT_ENABLE_REGISTRY_CLASHES=false`, or fill in `KIT_API_KEY` in `.env` |
| `RuntimeError: missing required env` | When `KIT_ENABLE_REGISTRY_CLASHES=true`, all of `KIT_BASE_URL`, `KIT_API_KEY`, `KIT_MODEL` must be set |
| Scanner imports fail (`ModuleNotFoundError`) | Run `pip install -r hygiene/requirements.txt` from repo root |
| `--scripts` mode exits 0 but no reports | Check `reports/` — static pass output may be empty if code is clean |
| LLM rate-limited | The scanner has 3-tier backoff (90s → 120s → 240s). Just let it run. |
| Want to scan a specific file only | Set `HYGIENE_FILES_TO_SCAN=./path/to/file.py` in `.env` |
| Scanners point at wrong directory | Verify `AIB_FACTORY_ROOT` and `SCAN_ROOTS` in `.env` |
| "Path leak" warnings on Windows paths | Edit `PATH_LEAK_ROOTS` to match your platform, or add to `PATH_LEAK_ALLOWLIST` |

---

## 8. Advanced: kill_tries.py (batch LLM refactoring)

`kill_tries.py` is a separate orchestration tool that:
1. Takes a list of source files (`kill_tries_list.txt`)
2. For each function with high cyclomatic complexity, generates a refactored version via LLM
3. Writes results to `kill_tries.json`
4. You review and manually apply (it never writes to your source)

**Usage:**
```bash
# Edit the list
echo "./src/problem_file.py" > hygiene/scanners/kill_tries_list.txt

# Run the batch refactor
uv run hygiene/scanners/kill_tries.py

# Apply approved refactors
uv run hygiene/scanners/kill_tries_apply.py

# Verify
uv run hygiene/scanners/kill_tries_post_check.py
```

See the YAML prompt templates in `scanners/kill_tries_prompt*.yaml` for the agent instructions.

---

## 9. Environment variable reference (all)

```
AIB_FACTORY_ROOT       — repo root holding hygiene/
SCAN_ROOTS             — dirs to scan (comma-separated, relative or absolute)
TARGET_ROOT            — codebase being audited
HYGIENE_FILES_TO_SCAN  — specific file override (comma-separated)
PATH_LEAK_ROOTS        — path prefixes to flag as leaks
PATH_LEAK_ALLOWLIST    — path prefix exemptions
HARD_FAIL_THRESHOLD    — 0/1/2+ (ignore/warn/fail)
SECRET_MAX_LINE        — max lines per file for secret scanning
DUPE_THRESHOLD_PCT     — duplicate identity threshold (100=exact)
ENABLE_DAILY_CHECKS    — enable daily cron-style checks
KIT_ENABLE_REGISTRY_CLASHES — enable LLM audit in find_registry_clashes.py
KIT_BASE_URL           — LM proxy endpoint (required if KIT_ENABLE_REGISTRY_CLASHES=true)
KIT_API_KEY            — LM proxy API key (required if KIT_ENABLE_REGISTRY_CLASHES=true)
KIT_MODEL              — model name (required if KIT_ENABLE_REGISTRY_CLASHES=true)
PYTHON_DEPS            — extra pip deps to install
```

> **Related docs:** [README.md](./README.md) (overview & scanner table) · [FAQ.md](./FAQ.md) (cost, CI/CD, troubleshooting)
