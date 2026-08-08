# TEST/param — Parameterized Pathway Tests

## What This Folder Does

Contains pytest test suites that validate **Telegram bot user pathways** in `src2/interfaces/telegram/app.py` using **combinatorial parametrization** (`@pytest.mark.parametrize`). Each test mocks the database, session, and Telegram API layer — no live bot, no Sentry, no Logfire.

The suite is organized into three waves (see `orchestrator.md`):

| Wave | Category | Strategy |
|---|---|---|
| 1 | Fast unit tests | Top-level imports from `src2.*`, no `app.py` deferred-import complexity |
| 2 | Bot pathway tests | Deferred imports inside `patch()` context to skip `app.py`'s top-level `sentry_sdk` |
| 3 | Negative / access-control / pipeline | Error propagation, guard-clause failures, multi-stage report pipeline |

## Test Files & Coverage

| File | Tests | Parametrized Cases | What It Covers |
|---|---|---|---|
| `test_callback_routing.py` | 6 | 7 | Inline callback query dispatch: `lang_*`, `start_auto`/`start_manual`, `tailor_yes`/`tailor_no`, `confirm_yes`/`confirm_no`, `chart_7day`, `/forecast_{cat}` commands, stakeholder add/delete callbacks |
| `test_chronomancer_flow.py` | 10 | 15 | Chronomancer command entry points: `/forecast`, `/30`, `/daily`, `/add`, `/forgetme`, `/lang`, `/reset`, `/week` — verifies each command calls the correct handler with right args |
| `test_stakeholder_flow.py` | 2 | 16 | Stakeholder management: selecting a relation category via callback (`add_rel_*`) and adding a stakeholder by name (`/add {relation}` → auto-mapped category) |
| `test_start_boundary.py` | 5 | 0 | Boundary conditions at the `PROCESSING` step: queue is NOT called (no report re-trigger), a "generating" wait message IS sent, forecast commands transition step to `CHRONOMANCER` |
| `test_start_pathways.py` | 14 | 2+ | Full `/start` journey: start command → auto/manual choice → collect → confirm yes/no → tailoring yes/no → career/wealth steps — asserts step transitions and keyboard presence |
| `test_tailoring_flow.py` | 1 | 18 | Combinatorial: 3 tailoring steps (`career`, `relationships`, `wealth`) × 6 options (`1`-`6`) = 18 pathways through `_handle_tailor_choice_callback` |
| `test_forecast_event_banner.py` | 7 | 30+ | Event-banner rendering: `_get_event_alert_line` (5 severities × 6 event types = 30 cases), dict vs object interface equivalence, `_split_response` separator edge cases, `_build_event_banner` empty / all-non-critical / with-critical / dict-event variants |
| `test_trigger_keyword_extraction.py` | 13 | ~28 | Trigger→RAG mapping pipeline: `_extract_trigger_labels`, `_get_trigger_rag_keywords` (5-trigger cap, unknown skip), `_build_trigger_context` (empty, unknown-label passthrough, RAG context), interface tests (dict vs `SimpleNamespace`), plus an AST-based **compliance guard** that asserts no `sentry_sdk`/`logfire` imports exist in the file |
| `test_daily_format_response.py` | 1 | 8 | `_handle_daily_format_response` combinatorial: sifu OFF (HTML + event-banner emojis + footer) vs sifu ON (plain Markdown + "Cached" footer) × has-events / no-events × narrative-split / no-split; asserts `ChronomancerReply` type, `send_telegram_message` dispatch, `save_session` record, and parse-mode correctness |
| `test_negative_access_control.py` | 5 | 4 | Guard-clause failures: blacklisted user denied on `telegram`/`web`, non-chronomancer user sees promo/unlock, tailoring proceed blocked without monthly code, queue rejects at capacity, unauthorized free-text shows promo |
| `test_negative_callback_errors.py` | 5 | 0 | Error propagation through callbacks: DB `set_user_prefs` raises (RuntimeError), intake raises (ValueError on `start_auto`), intake raises (ConnectionError on `confirm_yes`), stakeholder DB read raises (RuntimeError), unknown callback data triggers no handler and no message send |
| `test_negative_command_errors.py` | 7 | 6 | Error propagation through commands: invalid `/forecast_{cat}` passes category through to handler, `/30` engine OOM (RuntimeError), `/daily` missing profile (ValueError), `/6` with `None` prefs (AttributeError), `/add` unknown relation shows keyboard, `/week` chart file corrupted (FileNotFoundError), RAG `FileNotFoundError` from broken index path propagates through `handle_daily` |
| `test_monthly_report_pipeline.py` | 22 | ~30+ | Full 12-month report pipeline: profile-validation abort, queue enqueuing (tier cap / global cap / dedup / admin bypass), full-success with 12 months, mixed success + ErrorPayload, engine exception → dev notification, transient-failure retry, permanent-failure session reset, worker lifecycle (start/dequeue/process/complete), report menu rendering (valid / empty / missing-file), month-narrative retrieval (sifu-mode bypass / not-found), 12-month concurrent generation (success + failure propagation) |

## Categorization by Test Type

### Fast Unit Tests (top-level imports)
These files import directly from `src2.interfaces.telegram.chronomancer.coordinator`, `src2.interfaces.telegram.chronomancer.forecast_store`, or `src2.interfaces.telegram.utils` — modules that do **not** perform top-level `sentry_sdk` initialization. Safe to import at module scope.

- `test_forecast_event_banner.py` — pure functions, sync
- `test_trigger_keyword_extraction.py` — pure functions + AST guard, sync

### Deferred-Import Bot Pathway Tests
These files test handlers in `src2.interfaces.telegram.app.py`, which does `import sentry_sdk` at line 9. All `from src2.interfaces.telegram.app import ...` statements are **deferred inside `with patch(...)` blocks** to avoid triggering Sentry initialization during collection.

- `test_callback_routing.py`
- `test_chronomancer_flow.py`
- `test_stakeholder_flow.py`
- `test_start_boundary.py`
- `test_start_pathways.py`
- `test_tailoring_flow.py`
- `test_daily_format_response.py` (imports from `coordinator` + `utils`, deferred to avoid side-effects)
- `test_negative_access_control.py`
- `test_negative_callback_errors.py`
- `test_negative_command_errors.py`

### Pipeline / Multi-stage Tests
- `test_monthly_report_pipeline.py` — covers `pipeline.py`, `queue_worker.py`, `report_utils.py`, `reliability.py`, `monthly_generator.py`; uses `tmp_path` for filesystem mock writes

## Key Patterns

- **Combinatorial stacking**: Multiple `@pytest.mark.parametrize` decorators multiply into a Cartesian product (e.g. `test_tailoring_step_navigation` = 3 × 6 = 18 cases; `test_trigger_extraction_pipeline` = 4 × 2 × 2 = 16 cases).
- **Shared fixtures**: Every file defines `mock_db` (returns `sifu_mode=0`, `language="English"`) and `mock_session` (MagicMock with `.metadata` attributes stubbed). Variations exist per file (e.g. `test_monthly_report_pipeline.py` adds `get_user_tier`, `has_monthly_code`, `get_active_jobs`).
- **Patch targets**: Patches target the *consuming module* path (e.g. `src2.interfaces.telegram.app.db`, not `src2.interfaces.telegram.db.db`), ensuring the mock is active where the import is used.
- **Sentry/Logfire isolation**: No `sentry_sdk`, `logfire`, or live LLM calls — all agents and handlers are mocked via `AsyncMock`. The `test_trigger_keyword_extraction.py` file includes an explicit AST guard (`test_sentry_free_fixture_and_constraint`) that programmatically verifies no forbidden imports exist.

## Running

```bash
cd kit-tests
uv run pytest TEST/param/ -v
```

### Wave-parallel execution (see `orchestrator.md`)

```bash
# Wave 1 — fast unit tests (least likely to hang)
uv run pytest TEST/param/test_forecast_event_banner.py TEST/param/test_trigger_keyword_extraction.py TEST/param/test_daily_format_response.py -v

# Wave 2 — deferred-import bot pathway tests
uv run pytest TEST/param/test_callback_routing.py TEST/param/test_stakeholder_flow.py TEST/param/test_chronomancer_flow.py TEST/param/test_start_boundary.py TEST/param/test_start_pathways.py TEST/param/test_tailoring_flow.py TEST/param/test_negative_callback_errors.py -v

# Wave 3 — negative / access-control / pipeline
uv run pytest TEST/param/test_negative_command_errors.py TEST/param/test_negative_access_control.py TEST/param/test_monthly_report_pipeline.py -v
```

## Supporting Files

| File | Purpose |
|---|---|
| `SKILL.md` | Skill prompt: how to run, troubleshoot, and write new tests in this folder |
| `orchestrator.md` | Parallel test-runner orchestration plan (3 waves, 12+ agents) |

## Skill Reference

See `bot-testing-observability` skill: combinatorial testing, observability isolation, trace-driven test creation.
