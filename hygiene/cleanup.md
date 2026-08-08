# 🧹 Codebase Hygiene Cleanup Plan

This plan details the step-by-step strategy to eliminate the **252 codebase hygiene violations** across the active `TARGET_REPO/` directory without manual overhead or token exhaustion.

---

## 🛑 Problem

The codebase currently contains **252 active hygiene violations** (Dead Code, Environment Drift, Async Hazards, and Schema Hazards) across **60 files**. Attempting to fix all issues at once causes:

1. **Context/Token Bloat:** Large edits exceed the local agent's context limits.
2. **LLM Output Limitations:** The Studio model's max output is 65,535 tokens, meaning large file batches get cut off.
3. **API Rate Limits / Cost:** Running full audits repeatedly is expensive and rate-limiting.

---

## 💡 Solution

A two-phased **AST-First + Studio-Tranches** pipeline:

1. **Phase 1 (AST-First):** Use pure local Python scripts (using `ast`, regex, and local I/O) to automatically fix structural issues like Environment Drift and simple Dead Code. No LLM calls.
2. **Phase 2 (Studio-Tranches):** Group remaining files into 9 logical tranches (max 1,500 lines of code per batch) and refactor them surgically using the high-reasoning Outsource Model.

---

## 🎯 Target Outcome

- **Zero Active Violations:** All 252 violations successfully resolved or marked as verified exceptions in `exceptions.json`.
- **Type Safety & Speed:** Codebase runs cleanly with no event-loop starvation (Async Hazards) and strictly validated data contracts (Schema Hazards).
- **Token Efficiency:** Minimised external LLM cost by exhausting local AST automation first.

---

## 🛠️ Method

### Phase 1: AST-First Automation (0 Tokens)

We run local scripts under `scratch/` to execute:

1. **Env Drift Auto-Sync:** Extract all `getenv`/`environ` usage in `TARGET_REPO/` and automatically append missing keys to `.env.example`.
2. **Dead Code Stripper:** Use `ast`/`libcst` to prune functions/classes explicitly verified as `CONFIRMED_DEAD` in the JSON reports.

### Phase 2: Studio Tranches (Surgical Refactoring)

For Async and Schema hazards, we stage files in `<target-repo>/studio/upload/`, write a targeted prompt in `prompt.md`, get the fix in `check.md`, and apply it to `TARGET_REPO/`.

- **Tranche 1 (Core Memory):** `mem0_store.py`, `memory_manager.py`, `storage.py`, `rotator.py`
- **Tranche 2 (Core Platforms):** `valkey.py`, `telegram.py`, `identity/service.py`
- **Tranche 3 (Env & Celery):** `.env.example`, `celery_app.py`, `logging_utils.py`
- **Tranche 4 (Engine Prompts):** `prompt_engine.py`, `narrative_simplifier.py`, `openrouter.py`
- **Tranche 5 (Pydantic Engine):** `pydantic_prompt_engine.py`, `prompt_maker.py`
- **Tranche 6 (Deterministic Bazi):** `module0_geju.py`, `module6_ten_gods.py`, `module12_compatibility.py`
- **Tranche 7 (Contradictions & RAG):** `contradiction_resolver.py` (Staged Alone), `monthly_generator.py`
- **Tranche 8 (Telegram DB):** `db.py` (Staged Alone), `schemas.py`, `preflight.py`
- **Tranche 9 (Telegram Agents):** `coordinator.py`, `agents.py`, `app.py` (Staged Alone)

---

## 🚨 Context Re-alignment Prompt

_If the agent loses context or the session resets, paste the following message to restore execution:_

> Hey my trustworthy assistant, this is what we are doing: We are executing the codebase hygiene cleanup plan documented in [cleanup.md](./cleanup.md). Do NOT run any scanner tools (e.g. `run_all.py`). We are currently executing:
>
> **Current Stage:** [Specify: e.g., Phase 1 - Env Drift Auto-Sync / Phase 2 - Tranche 1]
>
> Please read the current state of files in `kit-hygiene/reports/` and check what needs to be done next.
