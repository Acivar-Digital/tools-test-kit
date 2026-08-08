# 04_monthly — Monthly Forecast Generation

> [!NOTE]
> **Test Optimization**: Because `04_monthly` executes the full auto-intake sequence (Steps 1–7) as a prerequisite to saving the user profile in the database, running `04_monthly` already fully validates the [`02_auto`](file:///home/yapilwsl/arthityap/baziforecaster/[baziforecaster-only: TEST/GOLD/02_auto/README.md not in kit download]) flow. If you run `04_monthly`, there is no need to run `02_auto` separately.

## Scenario

User initiates automated intake via `/auto`, completes the standard details validation, declines customization (`No`), and triggers the background monthly report generation pipeline.

## Flow

1. User sends `/auto`. Bot prompts for promo code.
2. User enters `frenfren`. Bot accepts the code.
3. User sends `/auto` to begin intake. Bot asks for name/alias.
4. User enters details. Bot asks for DOB and location.
5. User enters birth data. Bot asks to verify understanding.
6. User replies `Yes`. Bot asks if customized report is wanted.
7. User replies `No`. Bot triggers `run_full_report_pipeline()` in background.
8. Bot sends "Generating standard report..." and finishes compiling.

## Verification Points

| # | Check | Expected |
|---|-------|----------|
| 1 | HTTP responses | 200 |
| 2 | Intake validation message | "Here is what I understood" |
| 3 | Report generation trigger | "Generating standard report" |
| 4 | Master JSON generated | `BaziForecast_2026_*_master.json` exists on disk |
| 5 | No Traceback | ✅ |

## Failure Categories & Mitigations

| Failure Category | Specific Causes | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **1. Classical RAG / Upstream DB** | Remote Qdrant server `10.32.34.109:6333` down, or BaziRAG MCP server timeout. | Report crashes during month retrieval. | **Fallback Cache**: Look up the query's MD5 hash in `rag_cache/`. If it misses, raise a RuntimeError. |
| **2. LLM API & Gateway** | Local port `18000` proxy timeout, or Google/OpenRouter API rate limits (HTTP 429/500). | Pipeline is interrupted or hangs. | **Retry & Backoff**: Configure HTTP clients with `tenacity` or retry loops with exponential backoff. Set reasonable timeouts (e.g. 90s) to fail fast instead of hanging. |
| **3. Content Constraint Violations** | LLM output is too short, or contains banned words (e.g. `luck`, `fortune`, `divorce`). | Pydantic validation fails, causing the month pipeline to error. | **System Prompt & Post-Processing**: Inject strict negative constraints into system prompts. Implement a lightweight rule-based post-processor to auto-strip/replace minor violations (e.g., swapping `luck` for `resonance`) if it passes semantic meaning checks. |
| **4. Database & State Store** | Local PostgreSQL port locks, or Valkey/Redis cache is offline. | User sessions are lost, or report metadata fails to persist. | **State Resilience**: Implement safe fallback to disk storage (`reports/` directory) and session recovery logic. |

## 🤖 Configured AI Model Matrix

The monthly report pipeline utilises the following specialized AI models configured via `.env`:

| Role / Component | Configured Model | Base Provider | Function |
| :--- | :--- | :--- | :--- |
| **Intake (UI)** | `gemma-4-31b-it` | local / proxy | Parses free-text Bazi inputs and constructs user profiles. |
| **Welcome Specialist** | `gemma-4-31b-it` | local / proxy | Handles onboarding interactions. |
| **Pipeline Core** | `gemma-4-31b-it` | local / proxy | Drives the orchestration of monthly forecasts. |
| **Simplifier Agent** | `gemma-4-31b-it` | local / proxy | Simplifies technical advisory text into readable domains. |
| **Narrative Synthesis** | `gemini-3.1-flash-lite` | local / proxy | Generates structured month-by-month narratives. |
| **RAG Assistant** | `gemini-3.1-flash-lite` | local / proxy | Formulates technical queries and evaluates context. |
| **Memory Stack (Mem0)** | `gemini-3.1-flash-lite` | local / proxy | Manages and queries user memory collections. |
| **Chronomancer Engine** | `openrouter/openrouter/owl-alpha` | OpenRouter / LiteRouter | Generates high-fidelity daily and categorization forecasts. |

## 🛡️ Implemented Preflight Check Plan

Before initiating the sequential monthly forecast compilation, a diagnostic verification is executed automatically at runtime inside [**`pipeline_check.py`**](file:///home/yapilwsl/arthityap/baziforecaster/src2/interfaces/telegram/pipeline_check.py). (baziforeporter-only: not in standalone kit download)

### Active Diagnostic Checklist:
* **Model Gateway Diagnostics**: Pings `gemma-4-31b-it` (or the configured `PIPELINE_MODEL`) on port `18000` to verify the proxy routing and keys are active.
* **RAG / Database Diagnostics**: Probes the BaziRAG endpoint (`BAZIRAG_MCP_URL`) to ensure grounding capabilities are resolved.
* **PostgreSQL Database Connectivity**: Verifies the SQLAlchemy connection pool is responsive.

---

## 📈 Sequential Processing & Context Optimizations

To fit the monthly generation within the **16K context limit** and respect rate limits:
1. **Sequential Breathers**: The engine processes the 12 months sequentially with a 1.5-second sleep interval.
2. **Overview Bypass**: Heavy overview and review steps (like `stitch_report` and `final_review` LLM calls) are bypassed.

---

## 📊 Training Data Telemetry (Logfire Capture)

All LLM inputs and outputs are captured automatically for training and analysis via a custom OpenTelemetry `SpanProcessor` registered in [**`app.py`**](file:///home/yapilwsl/arthityap/baziforecaster/src2/interfaces/telegram/app.py). (baziforeporter-only: not in standalone kit download)

* **Output Directory**: [**`logs/training_data/`**](file:///home/yapilwsl/arthityap/baziforecaster/logs/training_data/) (baziforeporter-only: not in standalone kit download)
* **Format**: Each LLM interaction is saved as a JSON file containing the timestamp, request payload (system prompt, user prompt, tools), and response payload.

---

## Testing Failure Paths

To verify that failures are handled loudly and pinpointed correctly, we can execute the following verification tests:

### Method A: Preflight Unit Test (Diagnostic Fault Injection)
We run the preflight test which validates that checks fail loudly when downstream components are offline:
```bash
# baziforecaster-only: TEST/GOLD/test_preflight.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.
```

### Method B: Mid-Run Crash Simulation (E2E Webhook Test)
We inject a mock error midway through report generation during an E2E run:
1. Start an E2E flow.
2. Sabotage the intermediate monthly generator query.
3. Poll the webhook response to verify that the user and developer channels get notified of the specific error trace.

---

## 🔍 RAG Query Validation Test Plan (`test_RAG.py`)

To resolve issue #3 (stupid/generic RAG queries), we have introduced `test_RAG.py` to run diagnostic tests on the RAG pipeline for Month 1.

### Setup and Requirements:
- **Profile Details**: Test Profile (User 999), Day Master `Yi Mao`, Day Master Strength `Strong`.
- **Target Month**: Month 1: `GengYin` (庚寅).
- **User Focus**:
  - Career: Job change, promotion, career transition
  - Wealth: Investments, wealth accumulation
  - Relationships: Romance, marriage, dating

### Test Execution:
Run the diagnostic script to observe the query returned by the Gemma specialist RAG agent and the resulting grounding passages:
```bash
# baziforecaster-only: TEST/GOLD/04_monthly/test_RAG.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.
```

### Expected Outcomes:
- **Specific Output**: The generated search query must be technical, written in Simplified Chinese, and directly represent the intersection of the Bazi context and the user's specific tailoring concerns (instead of just returning generic month-only search queries).
- **High-Quality Grounding**: The retrieved vector DB paragraphs must contain relevant classical guidance matching those specific concerns.
