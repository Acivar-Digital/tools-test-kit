# Orchestrator Test Suite — `admin/orchestrator/test/`

> ## 🚨 AGENTS: READ THIS FILE FIRST — THEN FOLLOW IT STRICTLY
> Before you **build, edit, run, or review anything** that touches the
> orchestrator test suite (this folder, `infra/`, `tools.py`, the harness), you
> MUST read this README in full and obey it — especially the **FROZEN SUITE
> POLICY** below. No exceptions, no "I'll just tweak the test to make it green."
> If a test blocks your change, you stop and surface it; you do not edit the
> test. This file is the contract.

> **This is a FEATURE-PRESERVATION GATE, not a nice-to-have.**
> Every behaviour the orchestrator ships with MUST have a test in this folder.
> Before go-live, `run_all.py` must be green. If a shipped feature has no test
> here, that gap is a detectable defect — not an accident we sweep under the rug.

---

## ⛔ FROZEN SUITE POLICY (read before touching anything)

**Tests may NOT be dropped, disabled (`@pytest.mark.skip`), or have their
assertions weakened unless Tester explicitly approves it in a chat message.**

Rationale: this suite is the only thing standing between a "passing" pipeline
and a feature that quietly stopped working. A test that starts failing because
the feature regressed is a *success* — that is the test doing its job. The
reflex to "fix the test because it's red" instead of "fix the feature" is the
exact failure mode this policy bans.

If you believe a test is wrong, you raise it with Tester. You do **not** edit
the test unilaterally. Approved removals/weakenings are recorded in
`CHANGELOG.md` with the ticket id.

**Consequence:** a green `run_all.py` is the go-live gate. A red run blocks
ship until the feature is restored **or** Tester approves the change.

---

## ▶️ How to run

```bash
# Everything, in parallel, with a consolidated report:
uv run python admin/orchestrator/test/run_all.py

# A subset, still in parallel:
uv run python admin/orchestrator/test/run_all.py test_state.py test_gates.py

# One file, plain pytest:
uv run python -m pytest admin/orchestrator/test/test_gates.py -q

# Just the timeout trip-wire:
uv run python -m pytest admin/orchestrator/test/test_timeout_fire.py -v
```

`run_all.py` fires each `test_*.py` (and the `bifr/` sub-suite) as its own
`pytest` subprocess via a `ThreadPoolExecutor`, then prints PASS/FAIL per file
plus totals. Flags: `--workers N` (default `min(16, cpus*2)`),
`--per-file-timeout S` (default 300 — bounds a wedged file). Returns non-zero
if any file fails, so it is CI-friendly.

---

## ➕ How to ADD a new test (do this for every new feature)

1. **One file per concern.** Name it `test_<feature>.py` and drop it in this
   folder (or `bifr/` for the BIFR gold sub-suite). `run_all.py` discovers it
   automatically — no registration needed.
2. **Imports:** most files start with
   `sys.path.insert(0, str(Path(__file__).resolve().parents[3]))` so the repo
   root is importable, then `from admin.orchestrator.infra import ...`.
3. **Be hermetic.** Use the `orch_runtime` / `freeze_dir` fixtures from
   `conftest.py` (they redirect `ORCH_ROOT` to a temp dir) so gold tests never
   touch the real repo. Stub LLM calls — do NOT require live API keys.
4. **Pin the contract, not the implementation trivia.** Assert the observable
   behaviour a downstream phase relies on (e.g. "senior-audit gates map
   user-story ids to intern ids", "a hung intern trips the timeout").
5. **No `@skip`, no weakened asserts** (see FROZEN policy).
6. **Update `CHANGELOG.md`** with the ticket id and what the test protects.
7. **Verify:** `uv run ruff check admin/orchestrator/test/<file>.py` must be
   clean, and the new test must pass.

The suite ships with `bifr/` (Boundary / Freeze / Intercept / Replay) which
exercises crash-resume against recorded real runs — treat those as the gold
standard for fidelity tests.

---

## 📋 Script registry (what each file guards)

| File | Guards / Asserts |
|------|------------------|
| `run_all.py` | The parallel runner + report itself. |
| `conftest.py` | Shared fixtures (`orch_runtime`, `freeze_dir`) redirecting `ORCH_ROOT` to temp. |
| `_probe.py` | Helper probe used by the `bifr/` gold sub-suite. |
| `test_01_fix_liveness.py` | DAG liveness guard + per-task timeout + `add_constant` empty-value guard (s49n0). |
| `test_audit_surface.py` | Harness security/observability invariants (timeouts, ACL, secrets) stay intact. |
| `test_batch_read_ergonomics.py` | Forgiving `batch_read` ergonomics (rj4ie): bounded head on missing line ranges, no blind budget burn. |
| `test_intern_naming.py` | Intern naming contract (tqpgf): ids match `^intern_\d+$`, unique, pass-through. |
| `test_context_injection.py` | Size-aware context injection (gx30p): Tier-A/B delivery, no token blow-up. |
| `test_file_disjoint_filter.py` | Senior file-disjointness filter (vw4dd): correctness + HALT on true overlap. |
| `test_gates.py` | DAG execution gates (code-review + senior-audit): forced-pass overrides, id mapping. |
| `test_guard_read_idempotency.py` | Intern read-budget hardening (0xvqo): redundant re-reads trip `_READ_FATAL`. |
| `test_harness_gates.py` | Staging diff gate + runtime load gate + budget/loopguard overrides. |
| `test_hbh1_fixes.py` | hbh1 fixes: plan-invariant validation + intern tool-budget values. |
| `test_jsonl_healer.py` | JSONL output healing / salvage path. |
| `test_loopguard.py` | Compaction gate + loop-guard control flow (request isolation, cleanup). |
| `test_md_bridge.py` | MD-twin per-turn re-injection bridge (mb1k5). |
| `test_new_modules.py` | New orchestrator modules (ledger / shadow_tools / gatekeeper). |
| `test_payload_diet.py` | Harness payload diet (nz4ai): lean system prompts, scoped repo map. |
| `test_prestage.py` | Conductor-led pre-staging. |
 | `test_read_memory_bridge.py` | Read-Memory Bridge feature. |
| `test_rerun_feedback.py` | Intern rerun feedback injection (R1) + frozen expected-behaviour appendix. |
| `test_sanitizer_malformed_call.py` | Framework-rejected tool-call salvage path (78j9m). |
| `test_scope_auto_context.py` | Scope-driven auto-context (86rmw / xfqkf / y1oqi). |
| `test_spawn_all_halt.py` | Spawn-all interns + halt-on-block (uqj06). |
| `test_state.py` | Crash-resume state (atomic save, stale-in-progress reset). |
| `test_status_board.py` | Orchestrator STATUS BOARD (l4wjg): live per-phase tracking. |
| `test_stop_continue.py` | Stop/Continue mechanism (udylx). |
| `test_string_output.py` | String-output resilience in the runner. |
| `test_timeout_fire.py` | **Trip-wire:** `AGENT_RUN_TIMEOUT=1` must actually halt (not hang) — direct + dependent-group. |
| `test_tool_exceptions.py` | IDE modification tools raise `ModelRetry` on error/failure. |
| `test_cli_contract.py` | CLI contracts: intern budget scaling/clamp, path normalization, fact-store roundtrip. |
| `test_validation_hardening.py` | Schema generation + validation hardening (structured-output recovery). |

### `bifr/` sub-suite (gold, real-run fidelity)

| File | Guards / Asserts |
|------|------------------|
| `bifr/test_boundary.py` | Boundary snapshot serialization (per-turn state). |
| `bifr/test_freeze.py` | Freeze snapshot (`freeze_NNN.json`) keys + loop counter. |
| `bifr/test_intercept.py` | Intercept layer against recorded real runs. |
| `bifr/test_replay.py` | Replay of recorded runs for regression. |
