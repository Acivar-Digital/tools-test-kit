# 📋 OpenCode Execution Plan: Chronomancer E2E Test Plan (V34hb Pipeline)

## 1. 🔍 Context, Tooling & AST Strategy
*Map out the codebase before writing a single line of code.*
- **Target Files:** `[baziforecaster-only: TEST/GOLD/05_Chronomancer/agent_run/run_chronomancer_pipeline.py not in kit download]`, `src2/engine/agents.py`, `src2/interfaces/telegram/chronomancer/coordinator.py`
- **Exploration Tools:** 
  - `/investigate`: `handle_ask`, `handle_daily`, `DailyDeps`
  - `Codebase Indexing`: `infrastructure/mem0`, `UserState` Redis caching
- **AST Pre-Check:** N/A for this test script implementation phase, as we rely on the existing 30-day rejection rule (`has_future_dates`).

## 2. 🎯 Scope & Key Decisions to Lock (`bd`)
*These are the foundational decisions. Once agreed upon, they will be locked into memory using `bd`.*
- **Objective:** Execute a sequential, 6-step conversational E2E test to validate the new Chronomancer `/ask` pipeline, memory threading, and background `StateWriter`.
- **Architecture Decisions:** 
  - **Live Services:** Prioritize quality by hitting real Redis, Qdrant, and LLM endpoints. No hermetic mocks.
  - **Test Subject:** Use existing test user `999998` in the database.
  - **Background Timing:** Use `asyncio.sleep()` between test turns to organically allow the background `StateWriter` to populate Redis `UserState`.
- **Context Lock-in:** 
  - 🛑 *Action:* I will execute `bd` to log the scope, architecture decisions, and target schema so I do not lose this context during execution.

## 3. 🛡️ Pre-Mortem & Threat Model
*Identify failures before they happen.*
- **Input Edge Cases:** The test script must explicitly wait for the background tasks to complete; otherwise, subsequent steps will read an empty/stale `UserState`.
- **UX Feedback Loop:** Step 3 must fail loud and instantly via the 30-day boundary check.
- **Concurrency & State:** The `StateWriter` task must not crash on missing keys when Redis is empty on Turn 1.

## 4. 🛠️ Step-by-Step Implementation
*Atomic steps. Must include validation.*

- [ ] **Phase 1: Implement 6-Step Conversational Script**
  - **Action:** Update `run_chronomancer_pipeline.py` to execute the following specific sequence for user `999998` with `asyncio.sleep` between steps:
    1. `/daily` (Validates history threading).
    2. *"what should I do now?"* (Validates basic Sifu response and context injection).
    3. *"what is best time to get married next year?"* (Validates 30-day rejection boundary).
    4. *"ok. in that case when is the best time go propose within these 30 days?"* (Validates specific target date extraction and structural map).
    5. *"tell me more about my bazi profile? luck cycle, everything"* (Validates profile summary injection).
    6. *"so what should i do now?"* (Validates that the `StateWriter` successfully captured the context from Step 4).
  - **Validation:** Test output must confirm responses for all 6 steps, explicitly asserting the rejection message in Step 3.
  - 🛑 **Context Lock:** Execute `bd` to log Phase 1 completion.

## 5. 🔄 The OpenCode Test & Resolution Protocol
*Strict instructions for how I will handle test failures during execution.*
- **Initial Test Phase:** Run the E2E script via `# baziforecaster-only: TEST/GOLD/05_Chronomancer/agent_run/run_chronomancer_pipeline.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.`.
- **Failure Protocol:** If a test fails, I WILL NOT blindly fall into a `test > fix > repeat` loop.
- **AST & Subagent Escalation:** 
  1. I will halt direct modification.
  2. I will spin up a subagent or utilize AST analysis tools to structurally diagnose the broken tree/logic path.
  3. Only after the AST confirms the root cause will I apply the fix and re-test.

## 6. 🚀 Deployment & Rollback Strategy
*How this goes live without breaking production.*
- **Pre-Flight Checks:** Ensure test user `999998` exists in DB. Clear Redis `user_state:999998` before test execution to ensure a clean slate.
- **Cutover Strategy:** N/A (Test script update).
- **Rollback Steps:** Revert `run_chronomancer_pipeline.py` to previous state via Git.
- 🛑 **Final Context Lock:** Execute `bd` to log the deployment state and completion of the objective.