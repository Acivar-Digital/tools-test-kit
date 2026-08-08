# TEST ARCHITECTURE — BaziForecast

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    TEST SUITE RUNNER                    │
│                  ([baziforecaster-only: TEST/GOLD/run.py not in kit download])                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              IMPACT-DRIVEN TARGETED GATING              │
│   • Only tests components affected by recent commits    │
│   • Uses predefined Gold Folders for module mapping     │
└────────────────────────┬────────────────────────────────┘
                         │ 
                         ▼
┌─────────────────────────────────────────────────────────┐
│              E2E NARRATIVE & LOGIC COMPARISON           │
│   • Runs the Deterministic Engine                       │
│   • Injects static LLM seeds (Mocked API calls)         │
│   • Serializes the final output JSON                     │
└────────────────────────┬────────────────────────────────┘
                         │ Snapshot Match
                         ▼
┌─────────────────────────────────────────────────────────┐
│              GOLD BASELINE VALIDATION                   │
│   • Compares output JSON against GOLD standard snapshot │
│   • If match: PASS                                      │
│   • If mismatch: FAIL (Shows deterministic diff)        │
└─────────────────────────┴───────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Rationale |
|:------|:-----------|:----------|
| **Test Runner** | pytest | Standard Python testing framework |
| **Snapshots** | syrupy / JSON diff | Verifiable, deterministic output checking |
| **Mocking** | unittest.mock | Freezes time, API calls, and LLM entropy |
| **E2E Tool** | Custom Gold Scripts | Runs full pipeline end-to-end (Modules 0-12) |
| **Guardrails** | TEST/agent_guardrail.py | Validates file integrity pre/post edits |

---

## Key Design Decisions

1. **Opt-In Testing Philosophy** — General unit tests are strictly opt-in. The system values rapid iteration over theoretical test coverage. Tests are only run when explicitly requested or when modifying core logic.
2. **Impact-Driven Gold Testing** — The system uses End-to-End (E2E) "Gold Tests." When core files are modified, a targeted gold test must be run against the specific domain (e.g., `01_start`, `02_auto`, `04_daily`, `12_stakeholder`).
3. **No Simulated Test Results** — Agents are strictly banned from simulating test outputs. All test claims must be verifiable via actual command execution.
4. **Agent Guardrails & Sanitization** — Because agents often introduce escape artifacts (`\n`, `\u`) or syntax errors during automated file editing, the `agent_guardrail.py` pipeline validates files structurally (`checkpoint` -> `edit` -> `validate`) before committing them.
5. **No Test Isolation (Real Data Injection)** — Gold testing does not mock the database. It runs against local test databases to ensure the raw DB schema interactions match the actual queries being sent.
6. **Time-Frozen Inference** — Because Bazi calculations depend heavily on the current Solar time, `unittest.mock` is used to freeze time inside the test suite, guaranteeing identical outputs on every run regardless of the real-world calendar.
7. **Strict Failure Strategy** — No fallback values are inserted into tests. If a configuration is missing or the logic breaks, the test must crash loudly to prevent silent corruption.

---

## Gold Target Matrix

When modifying files in the repository, you MUST run the corresponding target Gold E2E tests instead of the entire suite to save compute and time:

| If you modified: | Run ONLY this target command: | Gold Folder impacted: |
|---|---|---|
| `src/bot/intake.py` or `conductor.py` | `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --test 01_start --test 02_auto` | `01_start`, `02_auto` |
| `src/bot/tailoring.py` | `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --test 02_auto` | `02_auto` |
| `src/bot/chronomancer_handler.py` | `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --test 04_daily --test 05_forecast --test 06_forecast_category --test 09_chrono_ask` | `04_daily`, `05_forecast`, `06_forecast_category`, `09_chrono_ask` |
| `src/bot/stakeholder_intake.py` | `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --test 12_stakeholder` | `12_stakeholder` |

> [!WARNING]
> **Gold Snapshots:** If you intentionally change Bazi mathematical formulas (like the Flat Tier 1 DM strengths), the Gold Snapshots will fail. You must explicitly update the Gold snapshots (e.g., `--update-snapshots`) after receiving user approval.
