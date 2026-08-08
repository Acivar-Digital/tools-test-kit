# E2E Test Plan: Monthly Report Generation

## Objective
Validate the end-to-end flow from receiving raw telegram inputs (bio + tailoring concerns) to generating the 12-month live narrative output.
This plan specifically validates that the strict Pydantic V2 data pipeline correctly threads the `tailoring_concerns` and `tailoring_context` all the way from the user input down to the actual LLM prompt payload, without data loss or dict-fallback crashes.

## Biography Data
*   **Alias:** Tester
*   **Gender:** Male
*   **Year:** Ding Si (丁巳)
*   **Month:** Jia Chen (甲辰)
*   **Day:** Yi Mao (乙卯)
*   **Hour:** Ren Wu (壬午)
*   **Da Yun:** Ji Hai (己亥)
*   **Strength:** Strong
*   **Favorable:** Fire, Earth
*   **Unfavorable:** Water, Wood
*   **Neutral:** Metal

## Tailoring Data
*   **Career:** "Thinking of quitting my corporate job to start a Bazi consultancy."
*   **Relationships:** "Not looking for anything right now, just want peace."
*   **Wealth:** "Want to know if 2026 is a good year to buy a house."

## Scope & Constraints
*   **Entry Point:** `src2.interfaces.telegram.bridge.map_profile_to_k3()` simulating an `/input` followed by tailoring completion.
*   **Anti-Corruption Seam (C5):** Ensure the raw payload + tailoring context correctly passes into `src2.core.schemas.unified.ChartProfile` via `model_validate()`. (Requires adding `tailoring_context` fields to `ChartProfile`).
*   **Engine Core (C4):** The internal engine must receive fully typed structures and serialize them properly for the LLM. 
*   **Egress:** Ensure the `tailoring_context` is physically present in the final prompt constructed by `src2.engine.prompt_maker.py`.

## Test Execution Steps

### 1. Payload Construction & Intake (Including Tailoring)
*   **Action:** Construct a dictionary payload mirroring Tester's bio data AND tailoring concerns.
*   **Validation:**
    *   Verify `build_tailoring_context()` correctly converts the concerns into the markdown prompt block.
    *   Assert that `ChartProfile.model_validate(dict)` successfully captures `tailoring_context`. (Will require updating `ChartProfile`).

### 2. Core Engine Initialization
*   **Action:** Pass the parsed `ChartProfile` to the orchestrator to initialize the `EngineContext`.
*   **Validation:**
    *   Assert `stems` and `branches` are properly wrapped into `PillarMap` objects.
    *   Verify `tailoring_context` remains attached to the `ChartProfile` object.

### 3. Ge Ju & Interactions Calculation
*   **Action:** Execute engine calculations.
*   **Validation:**
    *   Assert interaction rules resolve normally.

### 4. Monthly Report Generation (Prompt Engine)
*   **Action:** Invoke the pipeline that builds the monthly narrative/report.
*   **Validation:**
    *   Intercept or verify the prompt built in `src2.engine.prompt_maker.make_month` contains the `tailoring_context` string.
    *   Confirm there are no silent swallowing of exceptions (Fail Fast, Fail Loudly).
    *   The resulting JSON must contain the monthly outputs reflecting the pipeline run.

## Autonomous Execution Strategy (Subagent Delegation)
Because this is a true End-to-End test hitting live LLMs (OpenRouter/Google) for 12 successive monthly reports, execution will take a substantial amount of time and exceed standard command timeouts. 

To run this autonomously without requiring the user to wait at the terminal:
1. **Delegate to Subagent:** The main agent will spawn a background subagent (using the `Task` tool with `general` subagent_type) and hand off the execution of `run_pipeline.py`.
2. **Subagent Execution:** The subagent will run the long-running script and monitor its output. 
3. **Automatic Wake-Up:** Once the script finishes, the subagent will automatically ping the main agent with the final results, logs, and any tracebacks.
4. **Final Report:** The main agent "wakes up" upon receiving the subagent's message and reports the final synthesis directly back to the user asynchronously. 
