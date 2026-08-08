# 📋 OpenCode Execution Plan: Complete Autonomous E2E Validation (Chronomancer, Auto Monthly, Input Monthly)

## 1. 🔍 Context, Tooling & AST Strategy
*Map out the codebase before writing a single line of code.*
- **Target Files:**
  - `[baziforecaster-only: TEST/GOLD/05_Chronomancer/agent_run/run_chronomancer_pipeline.py not in kit download]` (Chronomancer E2E Test)
  - `[baziforecaster-only: TEST/GOLD/02_auto/agent_run/run_auto_pipeline.py not in kit download]` (Auto Monthly E2E Test)
  - `[baziforecaster-only: TEST/GOLD/03_input/agent_run/run_pipeline.py not in kit download]` (Input Monthly E2E Test)
  - `src2/interfaces/telegram/intake/calendar_node.py` (Auto engine ingress seam)
  - `src2/interfaces/telegram/bridge.py` & `src2/core/schemas/unified.py` (C5/C4 schema boundary & tailoring threading)
  - `src2/interfaces/telegram/chronomancer/coordinator.py`, `state_writer.py`, `forecast_store.py` (Chronomancer runtime & BaziCache)
- **Exploration Tools:** 
  - `/investigate`: `_run_auto_engine`, `map_profile_to_k3`, `handle_ask`, `handle_daily`, `run_pydantic_engine`
  - `Codebase Indexing`: `ChartProfile`, `UserProfile`, `UserState`, `BaziCache`
  - `/search`: `tailoring_context`, `tailoring_concerns`, `statewriter_model`, `bazi_mini_library.jsonl`
- **AST Pre-Check:** 
  - We will perform AST analysis on any file where test failures occur (e.g., if schema mismatches occur between `UserProfile` and `ChartProfile` during tailoring injection, or if background async tasks in Chronomancer fail to drain). Specifically, we will verify that `tailoring_context` is properly preserved across C5 -> C4 boundaries and that `StateWriter` model attributes strictly conform to `ControlSheetSchema`.

## 2. 🎯 Scope & Key Decisions to Lock (`bd`)
*These are the foundational decisions. Once agreed upon, they will be locked into memory using `bd`.*
- **Objective:** Execute a unified, autonomous `test > fix > loop` validation suite sequentially across all three core E2E pipelines (`chronomancer`, `auto_monthly`, and `input_monthly`) until 100% test pass rates are achieved, confirming 0ms BaziCache latency, 100% Pydantic V2 Zero-Dicts compliance, and seamless memory threading.
- **Architecture Decisions (Locked from /grill-me Interview):** 
  - **Sequential Execution Order:** Run the test suites strictly in sequence (Chronomancer -> Auto Monthly -> Input Monthly) in a single worker to guarantee clean DB/Redis isolation and avoid OpenRouter API rate limits.
  - **Auto-Flush State Isolation:** Automatically flush Redis key `user_state:999998` and wipe transient Postgres session records for test user `999998` before executing Chronomancer to ensure 100% deterministic, reproducible assertions.
  - **Metaphysical Drift Accepted:** Explicitly accept **"Mild Strong"** Day Master strength as canonical algorithmic behavior for the `/auto` pipeline (compared to manual "Strong" in `/input`), leaving `lunar-python` classical math rules untouched.
  - **Zero-Dicts & Pydantic Only:** All payloads crossing the C5 ingress boundary into the C4 engine must strictly instantiate Pydantic V2 schemas (`ChartProfile`, `UserProfile`). No legacy `.dict()` or `.get()` calls are permitted.
  - **Live Services & No Mocks:** All tests must hit live Redis, Qdrant BaziRAG, and OpenRouter/Google LLM endpoints.
  - **Subagent Orchestration:** Long-running monthly report generators (`auto_monthly` and `input_monthly`) and complex multi-turn tests (`chronomancer`) will be delegated to subagents to prevent main thread context bloat and memory degradation.
- **Context Lock-in:** 
  - 🛑 *Action:* I will execute `bd` to log the scope, architecture decisions, and target schema so I do not lose this context during execution.

## 3. 🛡️ Pre-Mortem & Threat Model
*Identify failures before they happen.*
- **Input Edge Cases:** 
  - **Timeout Risks:** Monthly report generation calls LLMs for 12 successive months. Default 120s CLI timeouts will abort the test; subagent execution with extended timeouts (300s+) must be enforced.
  - **Async Race Conditions:** `asyncio.create_task` for background `StateWriter` in Chronomancer can be silently destroyed by Python's garbage collector if the main test script exits prematurely. Scripts must await background task draining before assertion completion.
- **UX Feedback Loop:** Fail fast and loudly with full tracebacks. No silent `except: pass` exception swallowing. If an LLM output is malformed or a cache hit fails, let the error propagate immediately.
- **Concurrency & State:** Redis keys (`user_state:999998`) and session state in Postgres must be cleanly isolated or pre-cleared before test runs so stale data does not pollute assertions.

## 4. 🛠️ Step-by-Step Implementation
*Atomic steps. Must include validation. Executed sequentially as agreed.*

- [ ] **Phase 1: Chronomancer 6-Step Conversational Pipeline Validation (`chronomancer.md`)**
  - **Action:** Spawn a subagent to execute `[baziforecaster-only: TEST/GOLD/05_Chronomancer/agent_run/run_chronomancer_pipeline.py not in kit download]` with an extended timeout (300s+). Prior to running, auto-flush Redis key `user_state:999998` and DB test session records. Validate all 6 conversational turns (`/daily`, *"what should I do now?"*, *"best time to get married next year?"* rejection boundary, proposal date extraction, profile summary, and follow-up memory test).
  - **Validation:** Confirm 0ms BaziCache hits/misses function as expected, Redis `UserState` updates asynchronously without crashes, and all 6 assertions pass cleanly.
  - 🛑 **Context Lock:** Execute `bd` to log Phase 1 completion and lock the verified conversational state into memory.

- [ ] **Phase 2: Auto Monthly Report E2E Validation (`auto_monthly.md`)**
  - **Action:** Spawn a subagent to execute `[baziforecaster-only: TEST/GOLD/02_auto/agent_run/run_auto_pipeline.py not in kit download]`. Verify that `lunar-python` derives Tester's Day Master as "Mild Strong" (accepted drift), creates a valid `UserProfile`, injects `tailoring_concerns`, maps to `ChartProfile`, and includes `tailoring_context` in the prompt built by `prompt_maker.py`.
  - **Validation:** Confirm the script completes with exit code 0 and generated `.yaml` prompt artifacts confirm `tailoring_context` presence across all 12 monthly evaluations.
  - 🛑 **Context Lock:** Execute `bd` to log Phase 2 completion and note any schema or prompt adjustments made.
  
- [ ] **Phase 3: Input Monthly Report E2E Validation (`input_monthly.md`)**
  - **Action:** Spawn a subagent to execute `[baziforecaster-only: TEST/GOLD/03_input/agent_run/run_pipeline.py not in kit download]`. Validate that manual dictionary input ingress (Tester's Ding Si / Jia Chen / Yi Mao / Ren Wu chart) passes through `map_profile_to_k3()`, builds `PillarMap` objects without dict-access crashes, and serializes all 12 monthly outputs into JSON.
  - **Validation:** Assert no silent exception swallowing occurred and inspect output JSON to confirm 12 monthly evaluations with tailoring context.
  - 🛑 **Context Lock:** Execute `bd` to log Phase 3 completion and verify Zero-Dicts adherence across all 12 monthly turns.

## 5. 🔄 The OpenCode Test & Resolution Protocol
*Strict instructions for how I will handle test failures during execution.*
- **Initial Test Phase:** Execute each E2E suite sequentially via subagents running `# baziforecaster-only: TEST/GOLD/... not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.`.
- **Failure Protocol:** If a test fails, I WILL NOT blindly fall into a `test > fix > repeat` loop.
- **AST & Subagent Escalation (3x Auto-Loop Autonomy):** 
  1. I will halt direct modification in the main thread.
  2. I will spin up a subagent or utilize AST analysis tools (`/investigate`, `ast_clean_imports`, `get_file_symbols`) to structurally diagnose the broken tree or schema mismatch.
  3. **3x Auto-Loop:** The subagent is authorized to autonomously apply code fixes and re-run the failed test suite up to 3 retry iterations.
  4. If the test still fails after 3 autonomous iterations, the subagent will halt immediately and escalate the full AST traceback to the main thread for verification and manual guidance.

## 6. 🚀 Deployment, Testing & Rollback Strategy
*How this goes live and how tests are executed without polluting the main agent's context.*

- **Pre-Flight Checks:** Verify test user accounts (`999998`, etc.) exist or are cleanly initialized. Automatically flush Redis key `user_state:999998` and DB session state for user `999998` before test initiation.
- **Cutover Strategy:** Upon all 3 test suites passing cleanly in sequence, commit all bug fixes and schema adjustments to the repository.
- **Deployment Testing & Resolution Protocol (Anti-Bloat):**
  - If deployment tests fail and trigger a `test > fix > repeat` loop, I will NOT attempt to blind-patch in the main thread.
  - **Step 1 (AST Diagnosis):** I will first run AST (Abstract Syntax Tree) analysis to structurally map the root cause of the failure.
  - **Step 2 (3x Subagent Auto-Loop):** Once diagnosed, I will spawn subagents to implement and verify the fix up to 3 times autonomously. This strictly prevents context bloat and memory degradation in my main execution thread.
- **Rollback Steps:** 
  1. If an unrecoverable regression occurs, run `git checkout -- <files>` to restore the last stable state from commit `df16d0ec`.
  2. Flush Redis user state keys (`user_state:*`) and drop transient test session records from the database.
- 🛑 **Final Context Lock:** Execute `bd` to log the final deployment state, note any fixes handled by subagents, and lock the completed objective into memory.
