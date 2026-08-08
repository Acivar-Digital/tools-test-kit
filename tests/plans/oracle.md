# 📋 OpenCode Execution Plan: Oracle Mode E2E Test Plan (V34hb Oracle Pipeline)

## 1. 🔍 Context, Tooling & AST Strategy
*Map out the codebase before writing a single line of code.*
- **Target Files:** `src2/interfaces/telegram/chronomancer/oracle_coordinator.py`, `src2/interfaces/telegram/chronomancer/oracle_rewriter.py`, `src2/interfaces/telegram/chronomancer/oracle_gatherer.py`, `src2/interfaces/telegram/chronomancer/oracle_narrator.py`, `src2/core/schemas/unified.py`, `src2/interfaces/telegram/db.py`
- **Exploration Tools:** 
  - `/investigate`: `handle_oracle`, `session_to_chart_profile`, `gather_oracle_deps`, `Stakeholder` DB model
  - `Codebase Indexing`: CONTROL_SHEET slots (`oracle_rewriter`, `oracle_narrator`, `oracle_rag`), DB preference tracking (`active_mode`, `oracle_query_count`)
- **AST Pre-Check:** Verify that `granularity` is properly declared in `OracleQueryIntent` Pydantic schema and that `gather_oracle_deps` queries the `Stakeholder` DB table by name.

## 2. 🎯 Scope & Key Decisions to Lock (`bd`)
*These are the foundational decisions agreed upon during design alignment.*
- **Objective:** Execute a sequential, 6-turn E2E verification of `handle_oracle()` for test user `999998` (`sifu_mode=1`), testing 3-tier date granularity resolution, stakeholder DB integration, state persistence, query quota tracking, and surrogate/UTF-8 emoji payload safety.
- **Locked Architecture Decisions:**
  - **Runner Architecture:** Direct Python invocation of `handle_oracle()` (bypassing `app.py` webhook parsing).
  - **Sifu Baseline:** `sifu_mode = 1` (raw technical Sifu output).
  - **DB Environment:** Uses standard `DATABASE_URL` (PostgreSQL in production/staging; SQLite fallback locally).
  - **Date Granularity Hierarchy:**
    - **Range > 1 Year (e.g. 2027–2029):** Output annual resolution summary (highlighting key years) and instruct the user to narrow down.
    - **Range < 1 Year (e.g. within 2027):** Output monthly resolution (breakdown by transit months).
    - **Range < 1 Month:** Directed to pre-calculated 30-day daily forecast engine.
  - **Stakeholder DB Seeding:** Pre-seed DB `Stakeholder` table for user `999998` with partner `"Alex"` (Category: Business Partner). Turn 3 pulls `"Alex"` from DB and executes `module12_compatibility` math.
  - **State & Quota Verification:** Assert DB `active_mode` (`"ORACLE"` vs `"ASK"`), `oracle_query_count` increments (+1 per turn), and footer badge presence in response text.
  - **Payload Encoding Safety:** Assert defensive `sanitize_surrogates()` utility and literal UTF-8 emoji strings produce 0 `UnicodeEncodeError` exceptions during HTTP transmission.
- **Context Lock-in:** 
  - 🛑 *Action:* Log scope, architecture decisions, and target schema into `bd`.

## 3. 🛡️ Pre-Mortem & Threat Model
*Identify failures before they happen.*
- **Date Granularity Mismatch:** If rewriter fails to output `granularity` (`YEARLY`, `MONTHLY`, `DAILY`), narrator may default to unstructured date outputs.
- **Stakeholder DB Lookup Miss:** If query uses a variation of name (e.g., "my partner Alex"), gatherer must extract alias `"Alex"` and query `Stakeholder` DB table cleanly without `AttributeError`.
- **Background Task Errors:** Background tasks (`add_memory`, `update_user_state_background`) must not crash if Redis user state is empty on Turn 1.
- **Surrogate Escape & UTF-8 Encoding Failure:** Status messages or LLM advisories containing UTF-16 surrogate escapes must be sanitized by `sanitize_surrogates()` before HTTP transmission to guarantee 0 `UnicodeEncodeError` crashes.

## 4. 🛠️ Step-by-Step Implementation
*Atomic steps. Must include validation.*

- [ ] **Phase 1: Implement Date Granularity Slicing in Rewriter & Narrator**
  - **Action:** Add `granularity` enum (`YEARLY`, `MONTHLY`, `DAILY`) to `OracleQueryIntent` schema. Update `oracle_rewriter.py` system prompt to classify date scope into:
    - `YEARLY` for queries spanning > 1 year.
    - `MONTHLY` for queries spanning < 1 year down to 1 month.
    - `DAILY` for queries under 1 month.
  - Update `oracle_narrator.py` prompt to strictly output annual summaries for `YEARLY` and monthly breakdowns for `MONTHLY`.
  - **Validation:** Run unit tests for `oracle_rewriter.py` and verify intent parsing.

- [ ] **Phase 2: Implement Multi-Turn Conversational Oracle Script (`run_oracle_pipeline.py`)**
  - **Action:** Create `[baziforecaster-only: TEST/GOLD/06_Oracle/agent_run/run_oracle_pipeline.py not in kit download]` to execute the following sequence for test user `999998` (`sifu_mode=1`):
    1. **Pre-flight Setup:** Flush Redis `user_state:999998`, set `active_mode = "ORACLE"` in DB, and seed partner `"Alex"` into `Stakeholder` DB table.
    2. **Turn 1 (Range > 1 Year):** *"When is the best time for me to launch a major business venture between 2027 and 2029?"*
       - *Assert:* Output presents annual resolution for 2027, 2028, and 2029 and asks user to narrow down.
       - *Assert:* DB `oracle_query_count == 1`.
    3. **Turn 2 (Range < 1 Year):** *"Which specific months in 2027 are best for launching?"*
       - *Assert:* Output presents monthly resolution across 2027 transit months.
       - *Assert:* DB `oracle_query_count == 2`.
    4. **Turn 3 (Stakeholder `/compat`):** *"How compatible am I with my business partner Alex for this venture?"*
       - *Assert:* Gatherer pulls Alex from `Stakeholder` DB table, executes `module12_compatibility`, and output contains grounded compatibility analysis.
       - *Assert:* DB `oracle_query_count == 3`.
    5. **Turn 4 (Lifetime Trajectory):** *"What are my overall lifetime luck cycles and wealth turning points?"*
       - *Assert:* Output contains full Da Yun lifetime analysis and Oracle footer badge.
       - *Assert:* DB `oracle_query_count == 4`.
    6. **Turn 5 (Switch to Ask Mode):** Call `db.set_user_prefs(999998, active_mode="ASK")`.
       - *Assert:* Direct DB check verifies `db.get_user_prefs(999998)["active_mode"] == "ASK"`.
    7. **Turn 6 (Surrogate & Emoji Payload Safety Test):** Run `uv run pytest tests/test_telegram_unicode.py`.
       - *Assert:* All tests pass asserting 0 `UnicodeEncodeError` exceptions for UTF-16 surrogate pairs and literal UTF-8 emojis (`🔮`, `⚠️`).
  - 🛑 **Context Lock:** Log Phase 2 completion in `bd`.

## 5. 🔄 The OpenCode Test & Resolution Protocol
*Strict instructions for how I will handle test failures during execution.*
- **Initial Test Phase:** Run the E2E script via `# baziforecaster-only: TEST/GOLD/06_Oracle/agent_run/run_oracle_pipeline.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.` and `uv run pytest tests/test_telegram_unicode.py`.
- **Failure Protocol:** If a test fails, I WILL NOT blindly fall into a `test > fix > repeat` loop.
- **AST & Subagent Escalation:** 
  1. Halt direct modification.
  2. Spin up a subagent or utilize AST analysis tools to structurally diagnose the broken tree/logic path.
  3. Only after the AST confirms the root cause will I apply the fix and re-test.

## 6. 🚀 Deployment & Rollback Strategy
*How this goes live without breaking production.*
- **Pre-Flight Checks:** Seed DB user `999998` and `Stakeholder` record. Flush Redis test key.
- **Cutover Strategy:** Verify `handle_oracle` execution and state persistence.
- **Rollback Steps:** Revert changes via Git if issues are detected.
- 🛑 **Final Context Lock:** Log completion of objective in `bd`.
