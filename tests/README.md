# Community Test-Kit

Curated, **runnable slices** of the `baziforecaster` test suite — extracted so
an engineer can drop a real, production-grade test in front of a candidate or a
community member and say: *"here — clone, run, go."*

> Everything in this kit runs with a bare `uv run pytest`. No monorepo checkout,
> no Docker, no API keys. If a slice needs a dependency, it is pinned in
> `pyproject.toml` and declared in the layer it lives in.

## The problem (90-second story)

`baziforecaster` has a huge, deeply coupled test suite. That is a strength in CI
and a liability in an interview: the candidate stares at `src2/` and an
`ImportError` instead of practicing **test design**. The suite, though, contains
exactly the thing you want students to see — frozen-clock tests, golden
snapshots, mutation targets, property/fuzz scans, silent-`except` AST gates — so
this kit *slices those patterns out, makes each one self-contained, and ships the
minimum runnable artifact* for each.

## What's inside

| Layer | Path | Contains |
|---|---|---|
| 01 | `01_gold_snapshots/` | canned agent-run outputs (`final_report.json`, `snapshot*.json`, `*.UI.md`) |
| 02 | `02_unit_bedrock/` | unit + root feature tests across `engine`, `bot`, math chapter tests |
| 03 | `03_regression_locks/` | pinned regression suites (benchmarks / calibration) |
| 04 | `04_bug_repros/` | concrete repros (`test_daily_cache_hit_bug` + 8 `test_replicate_*.py`) |
| 05 | `05_integration_e2e/` | day1–8 pipelines, RAG, billing, compliance |
| 06 | `06_property_fuzz/` | 12 `test_*_fuzz.py` suites + prompt sets |
| 07 | `07_mutation_testing/` | a mutation target + mutmut scripts + `[tool.mutmut]` |
| 08 | `08_static_gates/` | guardrail/sanitizer/AST scanners + `swallow/` silent-handler linter |
| 09 | `09_tech_debt_audit/` | tech-debt swarm + dead-code audit tooling + `codes/` |

| Support | Path | Contains |
|---|---|---|
| `math_chapters/` | chapter-level engine math tests (`ch01`–`ch12`) + conftest/prompts |
| `param_flows/` | parameterized flow tests (callbacks, monthly report, access control) |
| `infra/` | `conftest.py`, `pytest.ini`, `test_run.py`, `run_k3_pipeline.py`, `bazirag/` |
| `tools/` | dev/audit tooling (`find_bad_style`, `evaluate_*`) |
| `reports/` | sample reports + `logs/` |
| `plans/` | planning docs |
| `examples/` | **5 self-contained, interview-ready stubs** (no upstream deps) |

## Quick Start (downloadable kit)

### What you can run with a download

A bare checkout of `tests/` with **no API keys and no `.env`** runs only the
cloner-safe stubs in `examples/` (7 files — the 6 pattern stubs `01_*`–`06_*` plus this live-smoke attestation):

```bash
cd kit-tests
KIT_LIVE=false uv run pytest examples -q        # runs the 7 cloner-safe online stubs — no .env needed
```

> `uv run pytest -q` runs the **same** thing: `pyproject.toml` pins `testpaths = ["examples"]`,
> so an unqualified `uv run pytest -q` collects `examples/` only (the 10 baziforecaster-only
> dirs are excluded — see the callout below).

### What is NOT cloner-runnable (baziforecaster-only, ignored by default)

The `01_gold_snapshots` through `10_harness_suite` dirs are **NOT in the download's
run surface**. They hardcode `TEST`/`GOLD` or import `src2.*`, and are excluded by:

- `tests/conftest.py` — `collect_ignore` lists every `0N_*` dir (not collected).
- `pyproject.toml` — `[tool.pytest.ini_options]` sets `testpaths = ["examples"]` (only `examples/`).
- `tests/conftest.py` — `collect_ignore` lists every `0N_*` dir (defense-in-depth).

`math_chapters/` and `param_flows/` are also optional in-kit slices that import
`src2.*` and need baziforecaster's source tree (plus `sqlalchemy`) installed — they
are outside the download run surface and never collected by default.

```bash
# or, full included suite (baziforecaster-only slices are auto-ignored):
KIT_LIVE=false uv run pytest -q
```

### The KIT_LIVE=true journey (proven by a cloner-safe smoke test)

For live LLM slices, copy `.env.example` -> `.env`, then set the env vars and point
at a real kit server:

```bash
cp .env.example .env
KIT_LIVE=true KIT_PATH=/your/kit KIT_BASE_URL=https://... KIT_MODEL=gemma-2 KIT_MEM0_MODEL=gemma-2-vision KIT_API_KEY=sk-... \
  uv run pytest examples/test_kit_live_smoke.py -q
```

This journey is **attested** by `examples/test_kit_live_smoke.py` (the 8th cloner-safe
stub — runs with `KIT_LIVE=false`): it imports the real `config.py` in a subprocess
and asserts the fail-fast behavior.

#### Fail-fast behavior

`config.py` reads `KIT_LIVE` at **import time**. If `KIT_LIVE=true` and any required
var is unset, it raises immediately:

```
RuntimeError: KIT_LIVE=true but missing required env: KIT_PATH, KIT_BASE_URL, KIT_MODEL, KIT_API_KEY — set them in tests/.env.
```

So a misconfigured live run **fails loudly and by name** before any test executes.

#### KIT_MODEL and KIT_MEM0_MODEL are independent (granular)

These two knobs control **separate** layers and are NOT collapsed into one value:

- `KIT_MODEL` (`-> CHRONO_MODEL`) — the chronomancer layer model.
- `KIT_MEM0_MODEL` (`-> MEM0_MODEL`) — the mem0-synthesis layer model.

They default to distinct mock names (`mock-chrono-model` / `mock-mem0-model`) so
granularity is observable. `examples/06_kit_mem0_model.py` exercises this contract.

## Want to extend it?

Read [`orchestrator.md`](orchestrator.md) (reproducible build recipe) and
[`STRUCTURE.md`](STRUCTURE.md) (full layout + per-layer curation rules).
Drop a new slice → `ruff` it → `pytest --collect-only` → add a layer.

## Note on source

This kit is a **one-way extraction**. It reads from staging mirrors and never
writes back upstream. The `baziforecaster` repository is not modified by building this kit.

### `10_harness_suite/` — ai-factory self-tests (Phase 2)

`10_harness_suite/` is a **curated copy of this repo's own regression suite**
(`ai-factory/tests/`) — 60 files organized into 8 semantic domain bins:

| bin | v1 files | role |
|---|---|---|
| `lifecycle/` | 12 | spawn/halt, loopguard, planning/stage/status, intern (naming + fn adapter) |
| `guardrails/` | 7 | silent-continue, line scoping, idempotency, sanitizer, audit surface, gates |
| `regression/` | 3 | state, compaction state, validation hardening |
| `fix_repros/` | 8 | all `*_fix_*` / `hbh1` reproduction tests |
| `integration/` | 12 | context, payload, md bridge, http, cli/string, new modules, batch read |
| `boundary/` | 4 | `bifr/` control suite (boundary/freeze/intercept/replay) |
| `_shared/` | 8 | conftest, run_all, status, _probe, agent_guardrail.*, find_hallucinations |
| `_tooling/` | 6 | `test_tool_*` + `test_ast_verifier.py` |

It is **reference + parse-clean** (gate: `E9,F63,F7,F82` → green), **not** laptop-runnable:
it imports `factory.*` and the live `tests/conftest.py`. The original `ai-factory/tests/`
is **never modified**. v1 ships original filenames in domain bins; the v2 rename roadmap
is in `10_harness_suite/NOTES_normalization.md` (deferred — see `orchestrator_01.md`). See [`orchestrator_01.md`](orchestrator_01.md)."]
