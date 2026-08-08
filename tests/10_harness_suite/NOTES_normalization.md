# 10_harness_suite — Normalization Map (Iteration 2)

**Status:** `v1` (current) ships **original filenames inside semantic domain bins** to
preserve cross-test import paths (`from tests._probe import HarnessProbe` in
`boundary/`; `from tests.test_gates import _plan` in `guardrails/`). The critical-only
gate (`E9,F63,F7,F82`) is green on `v1`. This file is the **iteration-2 todo**: the set of
safe-to-rename files + their proposed normalized names. Apply with `ruff --select I,F401 --fix`
after rename so import sorting stays clean.

## Rename candidates (45)

### lifecycle → prefix `test_lifecycle_`
| original | normalized |
|---|---|
| test_spawn_all_halt.py | test_lifecycle_spawn_halt.py |
| test_spawn_all_halt_recovery.py | test_lifecycle_spawn_recovery.py |
| test_stop_continue.py | test_lifecycle_stop_continue.py |
| test_timeout_fire.py | test_lifecycle_timeout.py |
| test_loopguard.py | test_lifecycle_loopguard.py |
| test_loopguard_recovery.py | test_lifecycle_loopguard_recovery.py |
| test_planning_gate.py | test_lifecycle_planning_gate.py |
| test_staging_gate.py | test_lifecycle_staging_gate.py |
| test_status_board.py | test_lifecycle_status_board.py |
| test_prestage.py | test_lifecycle_prestage.py |
| test_intern_fn_adapter.py | test_lifecycle_intern_fn_adapter.py |
| test_intern_naming.py | test_lifecycle_intern_naming.py |

### guardrails → prefix `test_guard_`
| original | normalized |
|---|---|
| test_guard_silent_continue.py | test_guard_silent_continue.py |
| test_guardrail_changed_line_scoping.py | test_guard_line_scoping.py |
| test_guard_read_idempotency.py | test_guard_idempotency.py |
| test_sanitizer_malformed_call.py | test_guard_sanitizer.py |
| test_harness_gates.py | test_guard_harness_gates.py |
| test_audit_surface.py | test_guard_audit_surface.py |

### regression → prefix `test_reg_`
| original | normalized |
|---|---|
| test_state.py | test_reg_state.py |
| test_compaction_state.py | test_reg_compaction_state.py |
| test_validation_hardening.py | test_reg_validation.py |

### fix_repros → prefix `test_fix_`
| original | normalized |
|---|---|
| test_01_fix_harness.py | test_fix_harness.py |
| test_01_fix_liveness.py | test_fix_liveness.py |
| test_01_fix_strategy_double_encode.py | test_fix_double_encode.py |
| test_02_fix_status_contract.py | test_fix_status_contract.py |
| test_fix_b_loud_blocked_paths.py | test_fix_loud_blocked_paths.py |
| test_fix_diff_orig.py | test_fix_diff_orig.py |
| test_fix_kg_injection.py | test_fix_kg_injection.py |
| test_hbh1_fixes.py | test_fix_hbh1.py |

### integration → prefix `test_ctx_`
| original | normalized |
|---|---|
| test_batch_read_ergonomics.py | test_ctx_batch_read.py |
| test_cli_contract.py | test_ctx_cli_contract.py |
| test_context_injection.py | test_ctx_context_injection.py |
| test_file_disjoint_filter.py | test_ctx_file_disjoint_filter.py |
| test_http_client.py | test_ctx_http_client.py |
| test_jsonl_healer.py | test_ctx_jsonl_healer.py |
| test_md_bridge.py | test_ctx_md_bridge.py |
| test_new_modules.py | test_ctx_new_modules.py |
| test_payload_diet.py | test_ctx_payload_diet.py |
| test_read_memory_bridge.py | test_ctx_read_memory_bridge.py |
| test_scope_auto_context.py | test_ctx_scope_auto_context.py |
| test_string_output.py | test_ctx_string_output.py |

### boundary → prefix `test_bifr_`
| original | normalized |
|---|---|
| test_boundary.py | test_bifr_boundary.py |
| test_freeze.py | test_bifr_freeze.py |
| test_intercept.py | test_bifr_intercept.py |
| test_replay.py | test_bifr_replay.py |

## Exceptions — do NOT rename (siblings import these by original module path)
| file | imported by |
|---|---|
| `_shared/_probe.py` | `boundary/test_*.py` (`from tests._probe import HarnessProbe`) |
| `_shared/test_gates.py` | `guardrails/test_guard_silent_continue.py`, `guardrails/test_harness_gates.py` (`from tests.test_gates import _plan`) |

## No-rename infra (keep originals)
- `_shared/conftest.py`, `run_all.py`, `status.md`, `README.md`, `agent_guardrail.py`, `agent_guardrail.json`, `find_hallucinations.py` — shared tooling mirroring `08_static_gates/` provenance; keep in lockstep (see `NOTES_de_dup.md`).
- `_tooling/test_ast_verifier.py`, `test_tool_read_file.py`, `test_tool_replace_text.py`, `test_tool_replace_function.py`, `test_tool_investigate.py`, `test_tool_exceptions.py` — already descriptive; no rename needed.

## Counts
- Rename candidates: **45** (lifecycle 12 + guardrails 6 + regression 3 + fix_repros 8 + integration 12 + boundary 4)
- Kept as-is: **15** (2 import-exceptions + 8 infra + 6 tooling + 0 audit)
- Total: **60**
