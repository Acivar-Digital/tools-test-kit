# Structure & Curation Rules

## Layout

```
tests/
├── 01_gold_snapshots/      # canned agent-run outputs (final_report.json, snapshot*.json, *.UI.md)
├── 02_unit_bedrock/        # unit tests + root feature tests (engine/bot/math_chapters chapter tests)
├── 03_regression_locks/    # pinned regression suites
├── 04_bug_repros/          # bug repros (daily_cache_hit + replicate_* crash tests)
├── 05_integration_e2e/     # integration + e2e (day1-8 pipelines, RAG, billing)
├── 06_property_fuzz/       # property/fuzz suites + prompts
├── 07_mutation_testing/    # mutation target + mutmut scripts + [tool.mutmut] (root pyproject.toml)
├── 08_static_gates/        # guardrail/sanitizer/scanners + swallow/ (silent-handler linter)
├── 09_tech_debt_audit/     # tech-debt swarm + dead-code audit + codes/ tooling
├── math_chapters/          # engine math chapter tests ch01-ch12 + conftest/prompts
├── param_flows/            # parameterized flow tests
├── infra/                  # conftest, pytest.ini, test_run, run_k3_pipeline, bazirag
├── tools/                  # find_bad_style, evaluate_* helpers
├── reports/                # sample reports + logs/
├── plans/                  # planning docs
├── examples/               # 5 self-contained, runnable stubs (the interview-critical gate)
├── 10_harness_suite/       # ai-factory self-tests, 8 domain bins (reference + parse-clean)
├── pyproject.toml          # deps (pytest, hypothesis) + [tool.mutmut]
├── orchestrator.md         # reproducible build recipe
└── README.md / QUICKSTART.md / STRUCTURE.md
```

## Curation rules (applied during build)
1. **Read-only source of truth**: all content derives from `_source/` (a staging
   mirror of `baziforecaster/TEST/`). `baziforecaster/` is **never modified**.
2. **Drop silently** from every layer: `__pycache__/`, `.pytest_cache/`, `*.pyc`,
   `*.db`, and the heavy audit blob `codes/20260626_SRC2/` (already excluded from
   `_source/`).
3. **Keep always**: every `SKILL.md`, `prompts/`, `conftest.py`, `pytest.ini`,
   and the `*.MD` narrative notes — they *are* the philosophy content.
4. **Dev throwaway dropped (documented)**: `scratch_compat.py`,
   `scratch_compat2.py`, `scratch_narrative_generation.py`.
5. **Gate** (build-time): `python -m compileall <layer>` (syntax fail-fast) — all
   layers passed.
6. **Final gate** (runnable proof): `uv run pytest examples -q` must pass on a
   bare laptop with only `pytest`+`hypothesis`.
7. **`10_harness_suite/` sourcing (Phase 2):** copied read-only from `ai-factory/tests/`
   via `cp -a` into `_harness_source/`; the live `tests/` is **never modified**
   (Final Gate #3 asserts the `tests/` working tree equals its Phase-1 baseline).
   Gate = critical-only (`E9,F63,F7,F82`) + per-bin `F401,I` **informational** (v1 faithful
   copy; normalization + F401 cleanup deferred to v2, roadmap in `NOTES_normalization.md`).
