# E2E Test Plan: Auto Monthly Report Generation

## Objective
Validate the end-to-end flow from receiving raw telegram `/auto` inputs (DOB, Time, Location) to generating the 12-month live narrative output.
This plan validates that the `lunar-python` based auto-calculation correctly creates a strict `UserProfile` and properly threads the `tailoring_concerns` and `tailoring_context` all the way down to the final LLM prompt.

## Biography Data (Tester)
*   **Alias:** Tester
*   **Gender:** Male
*   **DOB:** 1977-04-28 11:51
*   **Location:** Singapore
*   **Expected Auto-Calculation Differences:** The algorithmic calculation will derive the Day Master strength as **"Mild Strong"** (whereas manual entry used "Strong"). This drift is mathematically expected and should be explicitly accepted by the test without attempting to "fix" the math engine.

## Tailoring Data
*   **Career:** "Is this a good year to seek a promotion or salary raise in my current role?"
*   **Relationships:** "What are my prospects for meeting a new romantic partner this year?"
*   **Wealth:** "Is 2026 favorable for aggressive investments and new wealth creation?"

## Scope & Constraints
*   **Entry Point:** `src2.interfaces.telegram.intake.calendar_node._run_auto_engine()` simulating an `/auto` followed by tailoring completion.
*   **Anti-Corruption Seam (C5):** Ensure the generated `UserProfile` successfully merges with `tailoring_context` in `map_profile_to_k3()` and converts to a valid `ChartProfile`.
*   **Engine Core (C4):** The internal engine must receive fully typed structures and serialize them properly for the LLM.
*   **Egress:** Ensure the `tailoring_context` is physically present in the final prompt constructed by `src2.engine.prompt_maker.py`.

## Test Execution Steps

### 1. Payload Construction & Intake (Including Tailoring)
*   **Action:** Construct a mock Telegram `Session` with Tester's DOB and metadata. Call `_run_auto_engine()` to compute the pillars and strength dynamically.
*   **Validation:**
    *   Assert `session.profile` is a valid `UserProfile`.
    *   Verify `build_tailoring_context()` converts the concerns correctly and is injected into the payload via `map_profile_to_k3()`.
    *   Assert `ChartProfile.model_validate(dict)` successfully captures `tailoring_context`.

### 2. Core Engine Initialization
*   **Action:** Pass the parsed `ChartProfile` to the engine initialization.
*   **Validation:**
    *   Verify `tailoring_context` remains attached to the `ChartProfile` object.

### 3. Monthly Report Generation (Prompt Engine)
*   **Action:** Invoke the pipeline that builds the monthly narrative/report via `run_pydantic_engine()`.
*   **Validation:**
    *   Intercept or verify the prompt built in `src2.engine.prompt_maker.make_month` contains the `tailoring_context` string.
    *   Confirm the pipeline outputs `.yaml` files showing the live LLM prompt execution.

## Autonomous Execution Strategy (Subagent Delegation)
The background subagent will execute `[baziforecaster-only: TEST/GOLD/02_auto/agent_run/run_auto_pipeline.py not in kit download]`. The script will output intermediate files demonstrating the engine's behavior. The agent will read these artifacts to confirm success.
