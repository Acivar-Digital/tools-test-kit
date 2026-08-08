# FAQ — kit-hygiene: Production-Grade Technical Debt Scanner

> Answers to the questions developers actually Google when evaluating a **Python code quality scanner** — *does it work offline?* *how accurate is it?* *what real bugs does it catch?*

---

## Q1: What is kit-hygiene and why should I use it instead of pylint or ruff?

**A:** kit-hygiene is a **hybrid static-analysis + LLM-audit pipeline** that finds real bugs — not style nits. While `ruff`/`pylint` generate thousands of warnings (99% noise), kit-hygiene uses a two-tier approach:

1. **Tier 1 (offline)**: Fast Python AST analysis casts a wide net, flagging every suspicious pattern in milliseconds.
2. **Tier 2 (selective LLM)**: A Pydantic-AI agent reviews only the candidates — examining actual code context (snippet only, not your whole repo) — and classifies each as a **real bug** or **false positive**.

**Result**: You get **3–5 API calls per scan** (not thousands) and **zero false positives** worth your time. No vendor lock-in — bring your own LLM or run offline.

---

## Q2: Does kit-hygiene require an API key / internet connection?

**A:** **Tier 1 (static pass) runs 100% offline** — no API key, no internet. Tier 2 (LLM verification) is opt-in via `KIT_ENABLE_REGISTRY_CLASHES=true` in `.env`. You bring your own endpoint (`KIT_BASE_URL`, `KIT_API_KEY`, `KIT_MODEL`). The suite **fails closed**: if you enable LLM mode without credentials, it exits immediately rather than silently skipping.

---

## Q3: What real bugs does kit-hygiene detect? (swallowed exceptions, secrets, async, schema hazards)

**A:** kit-hygiene targets **production-breaking** issues across 11 scanners:

| Bug Class | Scanner | Severity Example |
|---|---|---|
| Swallowed exceptions | `find_silent_killers.py` | `except: pass` silently drops user data |
| Hardcoded secrets | `find_secrets.py` | Committed API keys, tokens, passwords |
| Async deadlocks | `find_async_hazards.py` | `requests.get()` inside `async def` blocks the event loop |
| Schema hazards | `find_engine_schemas.py` / `find_registry_clashes.py` | `dict`/`list` passed to Pydantic models (runtime `ValidationError`) |
| Env drift | `find_env_drift.py` | `os.getenv()` keys missing from `.env.example` |
| Circular imports | `find_circular_deps.py` | Import cycles causing `ImportError` at startup |
| Dict-access on Pydantic models | `find_dict_access_on_models.py` | `.get()`, `.keys()`, `in` on models post-migration |
| Dead code | `find_dead_code.py` | Unreachable classes/functions |
| Code duplication | `find_duplication.py` | Copy-pasted blocks (>N lines) |
| Type errors | `find_type_safety.py` | `mypy`/`pyright` errors filtered for false positives |
| Translation drift | `find_message_drift.py` | Missing Telegram translation keys vs `messages.yaml` |

Each verdict is categorized: `SILENT_KILLER`, `ASYNC_HAZARD`, `SCHEMA_HAZARD`, `HARDCODED_SECRET`, `ENV_DRIFT`, `CIRCULAR_DEP`, `DUPLICATE`, `TYPE_ERROR`, `DEAD_CODE`, etc.

---

## Q4: How do I run kit-hygiene on my own Python repo?

**A:** 30-second quick start — **works on any Python repo**, no integration needed:

```bash
# 1. Copy kit-hygiene/ into your repo root
cp -r kit-hygiene/ /path/to/your/repo/

# 2. Configure (copy the example, then edit the paths)
cd kit-hygiene/
cp .env.example .env
# Edit .env: set AIB_FACTORY_ROOT and SCAN_ROOTS to your repo paths

# 3. Run offline static scan (no API key needed)
uv run kit-hygiene/scanners/run_all.py --scripts

# 4. Review reports in kit-hygiene/reports/
```

For LLM-powered verification (optional): set `KIT_ENABLE_REGISTRY_CLASHES=true` and fill in `KIT_BASE_URL`/`KIT_API_KEY`/`KIT_MODEL`.

Full step-by-step: see **[GUIDE.md](./GUIDE.md)**.

---

## Q5: How expensive is kit-hygiene? Will I get a huge API bill?

**A:** Very cheap by design. The **two-tier pipeline** ensures the LLM only sees candidates — typically **3–5 API calls per full scan**, not thousands. Tier 1 (AST pre-filter) is free (local CPU). You also pay per-repo, not per-line: set `KIT_ENABLE_REGISTRY_CLASHES=false` for CI-free static runs.

---

## Q6: Can I use kit-hygiene in CI/CD? (GitHub Actions, fail thresholds)

**A:** Yes. Use `--scripts` for zero-cost static CI runs, or full mode for periodic audits. Configure `HARD_FAIL_THRESHOLD` in `.env`:

| Value | Behavior |
|---|---|
| `0` | Ignore findings — exit 0 |
| `1` | Warn — log findings, exit 0 |
| `2+` | **Fail-fast** — exit 1 if any findings |

Reports are written as JSON + Markdown to `kit-hygiene/reports/`, easy to parse or upload as CI artifacts.

---

## Q7: What output does kit-hygiene produce? (JSON format, report structure)

**A:** Each scanner writes two files to `kit-hygiene/reports/`:

- `<scanner_name>.json` — Machine-readable audit results
- `<scanner_name>.md` — Human-readable summary

**JSON structure:**
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

---

## Q8: Is kit-hygiene safe? (Will it modify my source code?)

**A:** **Read-only by default.** The scanners only report findings — they never modify your source. For automated fixes:

- **`cleanup.py`** — One-shot AST auto-fixer for **simple** violations (e.g., `except: pass` → `except Exception:`).
- **`kill_tries.py`** — Batch LLM refactoring of high-complexity functions. Writes drafts to `kill_tries.json` (never touches your source). You review and apply via `kill_tries_apply.py`.

---

## Q9: How do I configure the LLM model? (OpenAI, Anthropic, local LM, LM Studio)

**A:** kit-hygiene is **model-agnostic**. Configure your endpoint in `.env`:

```env
KIT_BASE_URL=http://localhost:40142   # your local LM proxy / router
KIT_API_KEY=your-key-here            # fail-fast if empty when enabled
KIT_MODEL=gemma-4-31b-it            # model name passed to your endpoint
```

Supports any OpenAI-compatible endpoint — Ollama, LM Studio, local routers, Antigravity, etc. The LLM only sees **code snippets** (never your whole repo), keeping calls minimal and cost low.

---

## Q10: Can I scan only changed files? (Git diff mode)

**A:** Yes — **diff mode** scans only files changed in the current git state:

```bash
uv run kit-hygiene/scanners/run_all.py --diff
```

There's also `HYGIENE_FILES_TO_SCAN` in `.env` to override and scan specific files only.

---

## Q11: How do I know what counts as a "real bug"? (verdict taxonomy, severity levels)

**A:** Each scanner uses a **two-class verdict** (bug vs false-positive), with scanner-specific labels:

- `SILENT_KILLER` vs `FALSE_POSITIVE` (swallowed exceptions)
- `ASYNC_HAZARD` vs `SAFE` (blocking I/O in async)
- `SCHEMA_HAZARD` vs `FALSE_POSITIVE` (dict/list → Pydantic model)
- `HARDCODED_SECRET` vs `FALSE_POSITIVE` (committed secrets)
- `ENV_DRIFT` vs `OK` (missing env vars)
- `CIRCULAR_DEP` vs `FALSE_POSITIVE` (import cycles)
- `DUPLICATE` vs `FALSE_POSITIVE` (code duplication)
- `TYPE_ERROR` vs `FALSE_POSITIVE` (mypy/pyright)
- `DEAD_CODE` vs `VERIFIED_LIVE` (unreachable code)

Severity levels (`HIGH`, `MEDIUM`, `LOW`) are assigned per-finding, and `HARD_FAIL_THRESHOLD` controls whether the run exits non-zero.

---

## Q12: Is kit-hygiene extensible? Can I add my own scanner?

**A:** Yes. Each scanner in `kit-hygiene/scanners/find_*.py` is a self-contained script using shared helpers in `utils.py`. The pattern is simple — scan a file with Python's `ast` module, emit findings, done. New scanners are automatically picked up by `run_all.py` if they follow the naming convention and import contract.

---

## Q13: What Python version do I need?

**A:** Python 3.14 (see `.python-version`). Uses standard library `ast` for Tier 1 (no heavy deps). Tier 2 (LLM) requires `pydantic-ai` (in `requirements.txt`).

---

## Q14: How do I interpret "true positives" vs "false positives" in the summary?

**A:** The `summary` in each report shows:

| Field | Meaning |
|---|---|
| `total_candidates` | Total suspicious patterns found by Tier 1 (static pre-filter) |
| `true_positives` | Findings the LLM confirmed as real bugs (or all findings in `--scripts` mode) |
| `false_positives` | Findings the LLM classified as noise (only populated in full/LLM mode) |

In `--scripts` mode (offline), all candidates are reported as findings — you are the judge. In full mode (with LLM), the LLM filters them for you.

---

## Q15: What's the difference between `--scripts`, full mode, and individual scanners?

**A:**

| Command | Mode | API Calls | Use Case |
|---|---|---|---|
| `--scripts` | Tier 1 offline | 0 | CI, quick check, no API key |
| *(no flag)* | Tier 1 + Tier 2 | 3–5 per scan | Deep audit, periodic review |
| `find_silent_killers.py` | Single scanner | 0 or LLM | Targeted check |
| `run_all.py --diff` | Tier 1, changed files only | 0 | Git hook, PR check |
| `kill_tries.py` | Batch LLM refactor | per function | Reducing cyclomatic complexity |

---

## Related Documentation

- **[README.md](./README.md)** — Suite overview, architecture diagram, scanner capability table, and 30-second quick start.
- **[GUIDE.md](./GUIDE.md)** — Full installation, `.env` configuration, execution modes, report structure, troubleshooting, and `kill_tries.py` orchestration.
