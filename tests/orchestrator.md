# kit-tests portability refactor — orchestrator brief
**IF YOU ARE THE ORCHESTRATOR (the LLM that read this file):**
- **DO NOT EDIT FILES YOURSELF. DO NOT "INVESTIGATE" OR "THINK" IN LOOPS.**
- **You ONLY spawn 3 subagents in a single turn** (parallel). Each subagent gets the EXACT pinned prompt in Section 3. No decisions are permitted. No extra reading is permitted. Each subagent reports exactly ONE line; you pass it through unchanged.
- Canonical env names (SET ONCE — never write `LLM_API_KEY`/`CHRONO_MODEL`/`MEM0_MODEL` inline in conftest or tests):
  `KIT_LIVE`, `KIT_PATH`, `KIT_BASE_URL`, `KIT_API_KEY`, `KIT_MODEL`, `KIT_MEM0_MODEL`.
- Live-source invariant: edit ONLY under `kit-tests/`. Touch nothing else.
- Fail-loud: missing required env at import → `RuntimeError` naming the var.
- Kit-local lint gate is **stdlib `python -m compileall`/`py_compile`** (NOT `uv run ruff`):
  kit-tests' `pyproject.toml` ships only `pytest`+`hypothesis`; ruff lives in the
  ai-factory repo, not in kit-tests.
- Outcome you are delivering: a user **downloads the kit → copies `.env.example` to `.env` →
  edits `KIT_PATH`, `KIT_API_KEY`, `KIT_BASE_URL`, `KIT_MODEL` → runs `cd kit-tests &&
  uv run pytest examples -q` and it passes.**

---

## Role and Mission
You are a Staff-Level QA Architect and Orchestrator for the `community-test-kit` (`kit-tests/`). Your mission is to make the kit **downloadable + configurable from a single `.env`** and **purge stale throwaway clutter** so a fresh cloner can set `KIT_PATH`/creds and hit run with zero friction. You harden the config surface: one `.env.example` contract, one fail-loud `config.py` shim, one `conftest.py` bridge — and remove every stale artifact that bloats a download (`.venv/`, `.hypothesis/`, `.pytest_cache/`, `*.egg-info/`, all `__pycache__/` + `*.pyc`, stale `*.log`) via a root `.gitignore`.

## Environment Context
- **Kit root:** `/home/yapilwsl/arthityap/ai-factory/kit-tests` (baziforeporter-only: local-laptop path, not standalone kit download)
- **Canonical config (NEW):** `kit-tests/.env.example`
- **Config shim (NEW):** `kit-tests/config.py`
- **Bridge (REWRITE):** `kit-tests/infra/conftest.py` (replace inline `os.environ.setdefault("LLM_*"...")` block with a `from config import load_config` pull-through)
- **Ignore list (NEW):** `kit-tests/.gitignore`
- **Runnable Final Gate:** `cd kit-tests && KIT_LIVE=false uv run pytest examples -q` (only deps: `pytest` + `hypothesis`; `examples/` never imports `src2.*` or `infra/conftest.py`).
- **Source of truth note:** `baziforecaster/` is never modified; kit-tests is a one-way extraction (STRUCTURE.md §2.6).

## Subagent Deployment Criteria (lifecycle per agent)
1. **Claim** — acknowledge your S-label assignment.
2. **Understand target** — read the pinned current-on-disk source cited in your prompt (no other reading).
3. **Perform** — apply the EXACT edit, then run the EXACT verification commands.
4. **Capture decisions** — `bd remember "<S-label>: <one-line invariant verified>"`.
5. **Close** — report EXACTLY one line (format pinned per subagent).

---

## 1. Canonical contract (`kit-tests/.env.example`)
**CREATE from scratch — the single download contract.** A cloning user fills only the `KIT_*` rows; the rest are laptop-safe mocks.

```env
# --- kit-tests portable config (set KIT_PATH + creds, then run) ---
KIT_LIVE=false                 # set true for live LLM slices (fail-fast if any creds missing)
KIT_PATH=/home/user/kit-tests  # REQUIRED: absolute path where the kit is downloaded
KIT_BASE_URL=http://localhost:8000   # LLM endpoint the slices talk to
KIT_MODEL=mock-chrono-model          # model name exposed to CHRONO_MODEL slices
KIT_MEM0_MODEL=mock-mem0-model       # model name exposed to MEM0_MODEL slices (independent of KIT_MODEL)
KIT_API_KEY=mock-test-key            # credential exposed to the slices
# --- src2 import-time isolation (laptop-safe; do not remove) ---
SENTRY_DSN=
DISABLE_SENTRY=1
LOGFIRE_NO_PLACEHOLDER=true
LOGFIRE_IGNORE_MISSING_DATA_KEYS=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/baziforecaster
```
The 5 `KIT_*` rows (plus `KIT_LIVE`) are the only place a user configures endpoint/api-key/model/path. `KIT_MODEL` and `KIT_MEM0_MODEL` are deliberately **separate** (granular: a user may set `KIT_MODEL=gemma-4-31b-it` and `KIT_MEM0_MODEL=KIT_MODEL`).

---

## 2. Source files (what each subagent touches — pinned, no ambiguity)

**`.env.example`** (NEW) — full content pinned verbatim in S1's prompt below.

**`config.py`** (NEW) — full content pinned verbatim in S2's prompt below. Fail-loud shim over `KIT_*`; stdlib `os` only; mirrors `kit-hygiene/control.py` shape (`SystemSettings`, `_Model`, `Config.get`, `load_config`). Defaults are laptop mocks so `import config` and `pytest examples` pass with no `.env`. When `KIT_LIVE=true`, missing any of `{KIT_PATH, KIT_BASE_URL, KIT_MODEL, KIT_API_KEY}` → `RuntimeError`.

**`infra/conftest.py`** — current on-disk env block (L14–L25, verbatim):
```python
# Ensure required test env vars are set before any src2 import
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("DISABLE_SENTRY", "1")
os.environ.setdefault("LOGFIRE_NO_PLACEHOLDER", "true")
os.environ.setdefault("LOGFIRE_IGNORE_MISSING_DATA_KEYS", "true")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:8000")
os.environ.setdefault("LLM_API_KEY", "mock-test-key")
os.environ.setdefault("MEM0_MODEL", "mock-mem0-model")
os.environ.setdefault("CHRONO_MODEL", "mock-chrono-model")
os.environ.setdefault("CHRONO_URL", "http://localhost:8000/v1")
os.environ.setdefault("TELEGRAM_API_BASE", "https://api.telegram.org")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/baziforecaster")
```
→ S3 rewrites L14–L25 to a `from config import load_config` pull-through (see S3 body); the `sys.path.insert` (L12), the src2-isolation mocks (`SENTRY_*`, `LOGFIRE_*`, `TELEGRAM_API_BASE`, `DATABASE_URL`), the SQLAlchemy mock-engine block (L27–L58), and the migration patch (L60–L65) stay **VERBATIM**.

---

## 3. Three pinned subagent prompts (copy verbatim; deploy all 3 at once)

### S1 — create `kit-tests/.env.example` (from-scratch contract)
```
You are S1. Create kit-tests/.env.example with the EXACT rows in brief §1 (6 KIT_* rows incl KIT_LIVE + 5 src2 isolation rows); no other content, no prose. Then run from kit-tests/:
  grep -cE "KIT_" .env.example
expect exactly 6.
  grep -nE "KIT_LIVE|KIT_PATH|KIT_BASE_URL|KIT_MODEL|KIT_MEM0_MODEL|KIT_API_KEY" .env.example | wc -l
expect exactly 6.
  test -f .env && echo "WARN: real .env exists — keep its creds out of this file" || echo ".env absent (OK)"
report EXACTLY one line: "S1 OK: KIT=6 .env-absent". Never mention other files. Capture: bd remember "S1: .env.example contract written (KIT_LIVE,PATH,BASE_URL,MODEL,MEM0_MODEL,API_KEY)".
```

### S2 — create `kit-tests/config.py` (NEW, fail-loud shim)
```
You are S2. Create kit-tests/config.py with this EXACT body (no edits, no additions):
import os

_ENABLE = os.getenv("KIT_LIVE", "false").lower() == "true"


class SystemSettings:
    base_url = os.getenv("KIT_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("KIT_API_KEY", "mock-test-key")
    model = os.getenv("KIT_MODEL", "mock-chrono-model")
    mem0_model = os.getenv("KIT_MEM0_MODEL", "mock-mem0-model")
    path = os.getenv("KIT_PATH", "")


def _Model(name):
    return type("M", (), {"model_name": name})


class Config:
    base_url = SystemSettings.base_url
    api_key = SystemSettings.api_key
    model = SystemSettings.model
    mem0_model = SystemSettings.mem0_model
    path = SystemSettings.path
    scanner_model = _Model(SystemSettings.model)

    @classmethod
    def get(cls, key, default=None):
        return {
            "base_url": SystemSettings.base_url,
            "api_key": SystemSettings.api_key,
            "model": SystemSettings.model,
            "mem0_model": SystemSettings.mem0_model,
            "path": SystemSettings.path,
        }.get(key, default)


def load_config():
    """Return (path, base_url, api_key, model, mem0_model) from environment. Stdlib os only."""
    path = os.getenv("KIT_PATH", "")
    base_url = os.getenv("KIT_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("KIT_API_KEY", "mock-test-key")
    model = os.getenv("KIT_MODEL", "mock-chrono-model")
    mem0_model = os.getenv("KIT_MEM0_MODEL", "mock-mem0-model")
    return path, base_url, api_key, model, mem0_model


if _ENABLE:
    _missing = [v for v in ("KIT_PATH", "KIT_BASE_URL", "KIT_MODEL", "KIT_API_KEY") if not os.getenv(v)]
    if _missing:
        raise RuntimeError("KIT_LIVE=true but missing required env: " + ", ".join(_missing) + " — set them in kit-tests/.env.")
Then run from kit-tests/:
  KIT_LIVE=false python3 -c "import config; print('S2 ok-off', config.Config.model, config.Config.mem0_model)"
  expect: S2 ok-off mock-chrono-model mock-mem0-model
  KIT_LIVE=true python3 -c "import config" 2>&1 | grep -o "missing required env"
  expect: missing required env
  KIT_LIVE=true KIT_API_KEY="" python3 -c "import config" 2>&1 | grep -o "KIT_API_KEY"
  expect: KIT_API_KEY
  python3 -m py_compile config.py
  expect: no output, exit 0
report EXACTLY one line: "S2 OK: off-green enabled-failKIT_API_KEY compile-green". Capture: bd remember "S2: config.py fail-loud shim (KIT_LIVE gate, 4 required; MEM0_MODEL independent); laptop mocks preserved".
```

### S3 — rewrite `kit-tests/infra/conftest.py` env block + purge stale artifacts + add `.gitignore`
```
You are S3. Three jobs ONLY, in this order.

(A) kit-tests/infra/conftest.py — replace the env block (the 10 os.environ.setdefault lines under "# Ensure required test env vars are set before any src2 import", i.e. the LLM_*/MEM0_*/CHRONO_* lines) with this pull-through (keep sys.path.insert, SENTRY/LOGFIRE/TELEGRAM/DATABASE_URL isolation, the sqlalchemy mock engine block, and the migration patch VERBATIM):
    # Kit config: fail-loud at import when KIT_LIVE=true. Source the kit-facing
    # vars HERE so a downloading user only fills kit-tests/.env (never hardcode creds).
    from config import load_config  # noqa: E402
    _path, _base_url, _api_key, _model, _mem0_model = load_config()
    os.environ.setdefault("KIT_PATH", _path or str(Path(__file__).parent.parent))
    os.environ.setdefault("LLM_BASE_URL", _base_url)
    os.environ.setdefault("LLM_API_KEY", _api_key)
    os.environ.setdefault("MEM0_MODEL", _mem0_model)
    os.environ.setdefault("CHRONO_MODEL", _model)
    os.environ.setdefault("CHRONO_URL", _base_url)
Do NOT touch the sqlalchemy mock block (L27–L58) or the migration patch (L60–L65).

(B) Purge stale throwaway artifacts (recreate nothing) from kit-tests/:
    rm -rf .venv .hypothesis .pytest_cache community_test_kit.egg-info
    find . -path ./.venv -prune -o -name "__pycache__" -type d -print -exec rm -rf {} + 2>/dev/null || true
    find . -path ./.venv -prune -o -name "*.pyc" -print -delete 2>/dev/null || true
    rm -f 06_property_fuzz/.fuzz_result.log 06_property_fuzz/.run.log

(C) Add root kit-tests/.gitignore (CREATE, overwrite-safe) with exactly:
    .venv/
    .hypothesis/
    .pytest_cache/
    *.pyc
    __pycache__/
    *.egg-info/
    *.egg
    .env

Then run from kit-tests/:
  grep -n "from config import load_config" infra/conftest.py          # expect 1 row
  grep -rn "LLM_API_KEY\|CHRONO_MODEL\|MEM0_MODEL" infra/conftest.py  # expect 3 rows (1 setdefault each)
  python3 -m py_compile config.py infra/conftest.py                   # green: no output, exit 0
  git check-ignore .venv __pycache__ .env                             # expect 3 lines (all ignored)
  find . -name "*.pyc" | head -1 | grep -q . && echo "FAIL: stale .pyc" || echo "NO .pyc"
report EXACTLY one line: "S3 OK: conftest-wired purged compile-green gitignored". Capture: bd remember "S3: conftest sources KIT_* via config.load_config; purged .venv/.hypothesis/.pytest_cache/egg-info/__pycache__/.pyc/stale .log; added .gitignore".
```

---

## 4. Master Final Gate (orchestrator runs once S1/S2/S3 report)
Run from inside `kit-tests/` (stale-absence checks FIRST, before `uv run` may reprovision `.venv`):
```
grep -rIlE "(password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]" . --include=*.py | grep -v "sample" | grep -v "__pycache__" || echo "OK: no credential literals in production .py"
test -f .env.example && echo "OK: .env.example present"
test -f config.py && echo "OK: config.py present"
test -f .gitignore && echo "OK: .gitignore present"
test -f infra/conftest.py && echo "OK: conftest.py present"
python3 -m compileall -q config.py infra/conftest.py
find . -name "*.pyc" | head -1 | grep -q . && echo "FAIL: stale .pyc" || echo "OK: no .pyc"
find . -type d -name ".pytest_cache" | grep -q . && echo "FAIL: .pytest_cache" || echo "OK: no .pytest_cache"
find . -type d -name ".hypothesis" | grep -q . && echo "FAIL: .hypothesis" || echo "OK: no .hypothesis"
test -d community_test_kit.egg-info && echo "FAIL: egg-info present" || echo "OK: no egg-info"
KIT_LIVE=false python3 -c "import config; print('config import ok:', config.Config.model, config.Config.mem0_model)"
KIT_LIVE=false uv run pytest examples -q
```
SHIP when every check prints `OK`, `compileall` is silent+exit-0, `config import ok` prints, and `pytest examples` is green. Otherwise `ESCALATE` (report the failing gate verbatim, do not patch).

## Known out-of-scope (do NOT touch this pass)
- `infra/test_run.py` — stale baziforecaster runner referencing non-existent `TEST/` + `.venv/lib/...`; documented in STRUCTURE.md infra table, left intact (purge needs a STRUCTURE.md edit too).
- `09_tech_debt_audit/agents/{base_agent,cleanup_swarm,massive_discovery_swarm}.py` read `LLM_API_KEY`/`os.getenv("LLM_API_KEY", "localfreegemini")` directly (bypass conftest bridge); they self-fallback and are audit scripts, not the runnable gate. Normalization to `KIT_*` deferred.
- `01_gold_snapshots/04_monthly/archive/swap.sample.py` — **KEPT**: it is the live `model_a`/`model_b` control-sheet demo your granularity decision references (`.sample`-excluded from the credential gate).
- `02_unit_bedrock/bot/test_replicate_openai_credentials_crash.py` — possible curation duplicate of `04_bug_repros/test_replicate_openai_credentials_crash.py`; review separately.
- `10_harness_suite/` — v1 faithful copy of `ai-factory/tests/` (reference + parse-clean); F401 normalization deferred per STRUCTURE.md.
- `kit-tests` is a data/extraction kit, not an importable package (pyproject sets `py-modules=[]`); do not add `config` to the package table.
