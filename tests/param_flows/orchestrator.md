---
name: param-test-orchestrator
description: Orchestrator prompt to run all TEST/param/ combinatorial pathway tests in parallel waves, with automated failure triage and fix-back guidance.
---

# TEST/param — Parallel Test Runner Orchestrator

## 🚨 Pre-Execution

Load BOTH skills before doing anything:
- **/skill param-test-runner** — `TEST/param/SKILL.md` (how to run, troubleshoot, write tests in this folder)
- **/skill bot-testing-observability** — combinatorial testing strategy + Sentry/Logfire isolation rules

Verify environment before launching waves:
```bash
cd kit-tests
# Confirm we can import the lightest test module without hanging
timeout 10 uv run python -c "from src2.interfaces.telegram.chronomancer.coordinator import _build_event_banner; print('OK')"
```

If that hangs, the Sentry sidecar is down. Fix: `export SENTRY_DSN=""` before running pytest.

### ⚠️ Orchestrator Role
**The orchestrator delegates. It does NOT fix.**
- Create tickets via `bd create` → Spawn agents → collect reports → summarize.
- If an agent reports `FIXED`, acknowledge and move on.
- If an agent reports `ESCALATE`, record and escalate.
- **Do not** personally edit `src2/` files, `test_*.py` files, or `conftest.py` in a loop. That is the agent's job.

---

## 🛠️ Subagent Deployment Criteria & Lifecycle

`TEST/param/` contains **12 test files**. Max 5 agents per wave → **3 waves**.

Before deploying subagents for a wave, the orchestrator MUST create tickets using `bd create` containing the details of the tasks they need to perform.

For each subagent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** `bd update <id> --claim`
2. **Load skills:** Load `param-test-runner` and `bot-testing-observability` (plus domain skills if fixing engine/coordinator code).
3. **Execute test:** Run `timeout 120 uv run pytest <TEST_FILE> -v --tb=short 2>&1`.
4. **Fix Phase (if failed/hung):**
   - Diagnose traceback using `TEST/param/SKILL.md#troubleshooting`.
   - Make minimal fixes to test file or `src2/`. **Never edit `src/`**.
   - Re-run `timeout 60 uv run pytest <TEST_FILE> -v --tb=short` until green or escalate.
5. **Capture decisions:** Record progress and fixes via `bd remember "Param test <TEST_FILE>: <summary of result/fixes>"`.
6. **Close the ticket:** `bd close <id>`.

---

## 📋 Wave Parallelism Plan & Ticket Details

### Wave 1 (5 agents) — Fast, top-level-import unit tests
- **Ticket 1:** `TEST/param/test_forecast_event_banner.py` — `_build_event_banner`, `_get_event_alert_line`, `_split_response` (no asyncio)
- **Ticket 2:** `TEST/param/test_trigger_keyword_extraction.py` — pure trigger→RAG mapping pipeline + Sentry-free AST guard
- **Ticket 3:** `TEST/param/test_daily_format_response.py` — `sifu_mode` on/off × events × split × `ChronomancerReply` dispatch
- **Ticket 4:** `TEST/param/test_callback_routing.py` — inline callback routing (lang, start, tailor, confirm, chart, forecast_cat, stakeholder)
- **Ticket 5:** `TEST/param/test_stakeholder_flow.py` — callback `add_rel_*` and `/add {relation}` name-mapping

### Wave 2 (5 agents) — Deferred-import bot pathway tests
- **Ticket 6:** `TEST/param/test_chronomancer_flow.py` — `/forecast`, `/30`, `/daily`, `/add`, `/forgetme`, `/lang`, `/reset`, `/week`
- **Ticket 7:** `TEST/param/test_start_boundary.py` — `PROCESSING` step: no queue re-trigger, generating wait message, forecast transitions
- **Ticket 8:** `TEST/param/test_start_pathways.py` — full `/start` → auto/manual → COLLECTING → CONFIRM → TAILORING → PROCESSING
- **Ticket 9:** `TEST/param/test_tailoring_flow.py` — 3 steps × 6 options = 18 combinatorial pathways
- **Ticket 10:** `TEST/param/test_negative_callback_errors.py` — DB raises, intake raises, unknown callback data

### Wave 3 (2 agents) — Negative / access-control and pipeline
- **Ticket 11:** `TEST/param/test_negative_command_errors.py` — invalid category passthrough, engine OOM propagation, RAG FileNotFoundError
- **Ticket 12:** `TEST/param/test_negative_access_control.py` — blacklisted user, non-chronomancer promo, queue capacity, monthly-code lock

---

## 🔁 Wave Orchestration

1. **Wave 1:** Create 5 beads tickets → launch 5 agents concurrently. Wait for completion.
2. **Wave 2:** Create 5 beads tickets → launch 5 agents concurrently. Wait for completion.
3. **Wave 3:** Create 2 beads tickets → launch 2 agents concurrently. Wait for completion.

---

## 🛠️ Skills Required

| Agent Scope | Skills to Load |
|---|---|
| All 12 subagents | `param-test-runner` + `bot-testing-observability` |
| Wave 1 fixing format/triggers | + `pydantic-ai-coding` (if coordinator/agent logic touched) |
| Wave 2/Wave 3 fixing pipeline | + `chronomancer-engine` (pipeline internals) |

---

## ✅ Final Gate (after all 3 waves report)

```bash
cd kit-tests
timeout 300 uv run pytest TEST/param/ -v --tb=short 2>&1
```

- **All green** → Report `ALL 12 FILES PASSED`.
- **Any failure** → Identify failing file, re-run with `-x`, and escalate with full traceback.
