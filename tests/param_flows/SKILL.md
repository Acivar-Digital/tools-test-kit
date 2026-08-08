---
name: param-test-runner
description: Teaches the LLM how to run, debug, and troubleshoot the combinatorial parametrized pathway tests in TEST/param/ for the Telegram bot.
---

# TEST/param — Parametric Bot Pathway Test Runner Skill

---

## 🎯 Core Directive

**Your objective is to run, debug, and maintain the combinatorial pytest suites in `TEST/param/`**
that validate the Telegram bot user pathways in `src2/interfaces/telegram/app.py`.

---

## 🚨 Pre-Execution Verification Checklist

Before running a single test:

1. **Working Directory**: You **MUST** be in the repo root:
   ```bash
   cd kit-tests
   ```
2. **Environment**: Always use `uv run` — never raw `pytest` or `python`:
   ```bash
   uv run pytest TEST/param/ -v
   ```
3. **Sentry Boundary**: Verify that `sentry_sdk` / `logfire` are **NEVER** imported in any `test_*.py` under this directory. If you see `import sentry_sdk` at the top of a test file, **remove it** — the observability skill forbids it.
4. **Test Selection**: Know what you are running. This folder contains **two categories** of tests:
   - **Fast, isolated unit tests** (`test_forecast_event_banner.py`, `test_trigger_keyword_extraction.py`) — top-level imports from `src2.*`, no live systems.
   - **Bot pathway tests** (`test_callback_routing.py`, `test_chronomancer_flow.py`, `test_start_pathways.py`, etc.) — **deferred imports inside `patch()` context** to skip heavy module-level Sentry initialization.
5. **No Live Systems**: No live Telegram bot, no Sentry DSN, no Logfire endpoint, no live LLM. All handlers are `AsyncMock`/`MagicMock`.

---

## 🏗️ Design Mindsets

### 1. Combinatorial Parametrization (The Multiplier Effect)

**Why**: Telegram bots have nested callback menus (e.g., 3 tailoring steps × 6 options × 2 modes = 36 pathways). Individual tests per button are unmaintainable.

**Action**: Always use stacked `@pytest.mark.parametrize` decorators. Each decorator multiplies the test count as a Cartesian product.

```python
@pytest.mark.parametrize("step", ["career", "relationships", "wealth"])
@pytest.mark.parametrize("option", ["1", "2", "3", "4", "5", "6"])
async def test_tailoring_step_navigation(mock_db, mock_session, step, option):
    callback_data = f"tailor_choice_{option}"
    # ...
```

> **Boundary Rule**: If stacked parametrize exceeds ~1,000 combinations, fall back to boundary-value testing instead.

### 2. Patch Target Discipline (The Consuming-Module Rule)

**Why**: Patching the *definition* site (e.g. `src2.interfaces.telegram.db.db`) silently fails because the consumer already bound the symbol at import time. You **must** patch where the symbol is **used**.

**Action**: Always patch at the consuming module:

```python
# ✅ Correct — patches where app.py imports and uses `db`
with patch("src2.interfaces.telegram.app.db", mock_db):

# ❌ Wrong — patches the source, but app.py already imported its own reference
with patch("src2.interfaces.telegram.db.db", mock_db):
```

Pattern: `patch("<consuming_module>.<symbol>", mock)`.

### 3. Fixture Pattern

**Why**: Every test file in this folder reuses an identical fixture structure for consistency.

**Action**: Two fixtures appear in every file:

| Fixture | Purpose | Standard Stubs |
|---|---|---|
| `mock_db` | MagicMock simulating `src2.interfaces.telegram.db.Database` | `get_user_prefs → {"language":"English","sifu_mode":0}`, `set_user_prefs → None`, `log_chat → None`, `is_admin → False`, `get_stakeholders → []` |
| `mock_session` | MagicMock simulating a user session | `.step = "START"`, `.profile = None`, `.metadata.tailoring = None`, `.metadata.intake_mode = None`, `.metadata.location = "SG"` |

**Variations**: 
- `test_start_boundary.py`, `test_start_pathways.py` add `db.clear_user_jobs` and `db.generate_and_link_semantic_id`.
- `test_monthly_report_pipeline.py` adds `db.get_user_tier`, `db.has_monthly_code`, `db.get_active_jobs`, `db.get_user_job_count_today`, etc.
- `test_negative_access_control.py` overrides `db.is_admin.return_value = False` and `db.has_monthly_code.return_value = False`.
- `test_daily_format_response.py` uses a `profile` with `.alias`, `.day_pillar.stem`, etc. instead of `None`.

### 4. Deferred Import Inside Patch Context

**Why**: `src2/interfaces/telegram/app.py` has a top-level `import sentry_sdk` at line 9. Importing `app` at module top-level in a test triggers Sentry initialization, which can hang or raise if the Sentry sidecar is unreachable. The `test_trigger_keyword_extraction.py` compliance guard explicitly AST-checks the file for forbidden imports.

**Action**: For tests that touch `app.py` functions, **always import inside the `with patch(...)` block**:

```python
with patch("src2.interfaces.telegram.app.db", mock_db), \
     patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock):
    from src2.interfaces.telegram.app import _handle_lang_callback  # ✅ deferred
    await _handle_lang_callback(callback_query_id, chat_id, callback_data, mock_session, platform)
```

> **Exception**: `test_forecast_event_banner.py` and `test_daily_format_response.py` import from lower-level modules (`coordinator`, `utils`) that do **not** import `sentry_sdk` at module level. Top-level imports are safe there.

---

## 🏃 Running Tests

### Run All Tests

```bash
cd kit-tests
uv run pytest TEST/param/ -v
```

### Run a Single Test File

```bash
uv run pytest TEST/param/test_callback_routing.py -v
```

### Run a Single Parametrized Case

```bash
uv run pytest "TEST/param/test_callback_routing.py::test_lang_selection[English]" -v
```

### Run Without Coverage / Plugins (fastest)

```bash
uv run pytest TEST/param/test_start_boundary.py -v -p no:cacheprovider --no-header
```

### Run with a Timeout (prevents hangs)

```bash
uv run pytest TEST/param/ -v --timeout=30
# If --timeout is not installed: use the shell `timeout` command:
timeout 60 uv run pytest TEST/param/test_monthly_report_pipeline.py -v
```

### asyncio Mode

`TEST/pytest.ini` sets `asyncio_mode = auto`. This means `@pytest.mark.asyncio` is **not required** on async test functions (auto-marking is in effect), but it is harmless to include it. Sync `def` functions with parametrize also work normally.

---

## 🔧 Troubleshooting & Fix Guide

### Problem 1: Tests hang at `collecting ...` (collection never completes)

**Cause**: Importing a `src2.*` module at the top level of a test file triggers heavy initialization (Sentry sidecar socket check, Logfire setup, or a blocking network call at import time). The `TEST/pytest.ini` `asyncio_mode = auto` can also cause collection to hang if the import itself deadlocks on an async loop.

**Solutions** (try in order):

1. **Run a single test with a shell timeout** to confirm the hang is import-related, not a runtime deadlock:
   ```bash
   timeout 15 uv run pytest "TEST/param/test_callback_routing.py::test_lang_selection[English]" -v -s 2>&1 | tail -30
   ```

2. **Check if the import hangs standalone** — this isolates from pytest internals:
   ```bash
   timeout 10 uv run python -c "from src2.interfaces.telegram.app import _handle_lang_callback" 2>&1
   ```
   - If this hangs, the problem is in the `src2` module import chain, **not** in the test.
   - Two common culprits: (1) `src2/interfaces/telegram/app.py:9` does `import sentry_sdk` which may block on a socket check to `localhost:8969` if the Spotlight sidecar is unreachable. (2) `src2/core/memory/memory_manager.py:26` executes `_db = Database("bot.db")` at module load — `Database.__init__` calls `_run_pg_migrations()` which tries a live PostgreSQL connection to `localhost:5432` → hang.
   - **Fix**: Ensure `TEST/param/conftest.py` sets `SENTRY_DSN=""`, `LOGFIRE_NO_PLACEHOLDER="true"`, `LOGFIRE_IGNORE_MISSING_DATA_KEYS="true"` at the top (before any src2 import), and starts a module-level `patch("src2.interfaces.telegram.db.Database._run_pg_migrations", lambda self: None)`.
   ```

4. **Force deferred import** if the test file imports at top-level: Move the `from src2...` import inside the `with patch(...)` block. This is the pattern used by `test_callback_routing.py`, `test_start_pathways.py`, etc.

5. **Use `--import-mode=importlib`** to avoid stale `.pyc` cache issues:
   ```bash
   uv run pytest TEST/param/ -v --import-mode=importlib
   ```

### Problem 2: `ModuleNotFoundError: No module named 'src2'`

**Cause**: Not running from the repo root, or `pythonpath` not configured.

**Fix**:
```bash
cd kit-tests
uv run pytest TEST/param/ -v
```
The `pyproject.toml` sets `pythonpath = ["."]` and `testpaths = ["TEST"]` at the root level.

### Problem 3: `fixture 'mock_db' not found`

**Cause**: The `TEST/conftest.py` only adds the repo root to `sys.path`. The `mock_db` and `mock_session` fixtures are defined **per-file** in each test file, not in a shared conftest. Do **not** expect shared fixtures from `TEST/conftest.py`.

**Fix**: Each test file defines its own `mock_db` and `mock_session` fixtures. If you create a new test file, copy the fixtures from a sibling file.

### Problem 4: `async def` test function is not collected / skipped silently

**Cause**: Missing `@pytest.mark.asyncio` in strict asyncio mode, or a version mismatch in `pytest-asyncio`.

**Fix**: `TEST/pytest.ini` sets `asyncio_mode = auto`, so this should not happen. If you see it:
```bash
uv run pytest TEST/param/ --co -q 2>&1 | head -5
# Confirm asyncio mode
uv run python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"
```
Ensure `pytest-asyncio >= 0.24` (it is, per `pyproject.toml`).

### Problem 5: Tests pass locally but fail in CI / different environment

**Cause**: A test imports a `src2` module that has conditional Sentry/Logfire initialization based on environment variables.

**Fix**:
```bash
# Always set these for test isolation
export SENTRY_DSN=""
export LOGFIRE_NO_PLACEHOLDER="true"
export LOGFIRE_IGNORE_MISSING_DATA_KEYS="true"
uv run pytest TEST/param/ -v
```

### Problem 6: `.pyc` cache causes stale test behavior

**Cause**: Python's `__pycache__` directory contains compiled bytecode from a different source version.

**Fix**:
```bash
# Clear caches
find TEST/param/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
uv run pytest TEST/param/ --cache-clear -v
```

---

## 🧪 Writing a New Test File (Quick Reference)

Follow this skeleton:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "START"
    session.profile = None
    # ... stub metadata fields ...
    return session


@pytest.mark.asyncio  # optional under auto mode, but harmless and explicit
async def test_my_new_callback(mock_db, mock_session):
    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock):

        from src2.interfaces.telegram.app import _handle_my_callback  # deferred import
        await _handle_my_callback("query_id", 123456789, "my_callback", mock_session, "telegram")

        mock_send.assert_called_once()
```

---

## 🗺️ Triggering Situational Skills

When working on tests in this folder:

- **`bot-testing-observability`** — Combinatorial testing strategy, Sentry/Logfire isolation, trace-driven test creation. **ALWAYS load this** alongside this skill.
- **`script-hygiene`** — Pydantic-first design, no silent failures, fail-loudly conventions for any test utility code you write.
