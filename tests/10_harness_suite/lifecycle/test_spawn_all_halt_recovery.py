"""Regression tests: SPAWN-ALL HALT must NOT pre-empt the gate's
recovery loop, and harness-known-blocked tasks must be rerun regardless of the
LLM reviewer/auditor verdict.

No LLM keys required: intern_fn / reviewer_fn are stubbed and the ApprovedPlan
is built in-process.

Covers:

  * STRICT-FLAG — `run_execute_phase(strict=False)` RETURNS the incomplete
    results (no raise) so a gate can recover them; the default `strict=True`
    still hard-halts (guards the original uqj06 fix).
  * HARNESS-BLOCKED-RERUN (code_review) — a intern that returns `blocked`
    flows into `engineer_review`; even if the LLM reviewer passes it ("Yes"),
    the harness unions its own `blocked` status into the rerun set, so the task
    is re-executed (not silently force-passed). This restores the engineer's
    recovery authority the SPAWN-ALL HALT had usurped.
  * HARNESS-BLOCKED-RERUN (senior) — same contract through `run_senior_audit_gate`.

These fail loudly if a future change re-adds the pre-empting HALT or trusts
the LLM to rediscover a failure the harness already determined.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import asyncio
import json

import pytest

# Stub the beads CLI (`./bd`) so the regression test never spawns a real
# subprocess. The runner calls `subprocess.run(["./bd", ...])` for CQRS
# claim/update/close; we must NOT let it block (no TTY / no real beads run).
# (This is globally handled in tests/conftest.py)

from factory.infra import runner as _runner  # noqa: E402
from factory.infra.control import TEMP_DIR  # noqa: E402

# Stub the harness patch writer. The synthetic intern returns no `files_changed`,
# which would trip the real B3 "fake-done -> blocked" guard. For this regression
# test the intern is synthetic, so we treat a `done` result as having real changes
# and let it through. SPAWN-ALL / strict / rerun logic is untouched.
_runner._write_harness_patches = lambda task_id, files_changed, bd: (list(files_changed), 1)

from factory.infra.models import (  # noqa: E402
    ApprovedTask,
    Epic,
    ExecutablePlan,
    EvaluationItem,
    ParallelisableWorkplan,
    ReviewResult,
    RubricCell,
    RubricCube,
    Strategy,
    WorkGroup,
)
from factory.infra.execution import run_execute_phase  # noqa: E402


def _plan(single: bool = True) -> ExecutablePlan:
    """g1=[intern01]; when not single, g2=[intern02..intern06] depends_on g1
    (mirrors hbh1)."""
    epic = Epic(title="e", deliverables=["d"], must_be_pydantic=True)
    g1 = WorkGroup(
        id="g1",
        tasks=[ApprovedTask(id="intern01", title="t1", file_paths=["src2/a.py"],
                            instruction="implement intern01", acceptance="intern01 ok",
                            tool_preference="CLI-wrapper")],
    )
    groups = [g1]
    if not single:
        g2 = WorkGroup(
            id="g2",
            depends_on=["g1"],
            tasks=[ApprovedTask(id=f"intern{i:02d}", title=f"t{i}", file_paths=[f"src2/{i}.py"],
                                instruction=f"implement intern{i:02d}", acceptance=f"intern{i:02d} ok",
                                tool_preference="CLI-wrapper") for i in range(2, 7)],
        )
        groups.append(g2)
    strat = Strategy(
        how_to_fix="x",
        tool_preference={f"intern{i:02d}": "CLI-wrapper" for i in range(1, 7 if not single else 2)},
        parallelisable_workplan=ParallelisableWorkplan(groups=groups),
    )
    return ExecutablePlan(
        epic=epic,
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[RubricCell(dimension="x", criterion="c",
                                                      severity="blocker", passed=True)]),
        summary="s",
        tasks=list(g1.tasks) + (list(groups[1].tasks) if not single else []),
        alignment="align",
        workplan=ParallelisableWorkplan(groups=groups),
        strategy=strat,
        approved=True,
    )


def _intern_block_first(blocked_ids: set[str], calls: dict[str, int] | None = None):
    """Intern stub: returns `blocked` for ids in blocked_ids, else `done`.
    Counts every spawn into `calls` so the test can assert a blocked task was
    re-executed (spawned more than once)."""
    def _make(blocked: set[str]):
        async def intern_fn(brief: str, task_id: str | None = None) -> str:
            tid = task_id or brief.split("TASK ID:")[1].split()[0]
            if calls is not None:
                calls[tid] = calls.get(tid, 0) + 1
            status = "blocked" if tid in blocked else "done"
            return json.dumps({"status": status, "rc": 0, "stdout": "ok", "stderr": "",
                                "task_id": tid, "files_changed": [], "diff_summary": "",
                                "notes": "blocked on read budget" if status == "blocked" else ""})
        return intern_fn
    return _make(blocked_ids)


def _reviewer_always_pass(brief: str) -> str:
    """Simulates an LLM engineer_review that passes EVERYTHING (all 'Yes').
    If the harness trusted this verdict alone, a harness-`blocked` task would
    never be rerun — so this is the adversarial case the harness union must beat."""
    evals = [EvaluationItem(item_id="intern01", approved="Yes", comments="all ok")]
    return ReviewResult(evaluations=evals).model_dump_json()


async def _reviewer_always_pass_async(brief: str) -> str:
    return _reviewer_always_pass(brief)


def _audit_always_pass(brief: str) -> str:
    evals = [EvaluationItem(item_id="intern01", approved="Yes", comments="all ok")]
    from factory.infra.models import AuditResult
    return AuditResult(evaluations=evals).model_dump_json()


async def _audit_always_pass_async(brief: str) -> str:
    return _audit_always_pass(brief)


# ── STRICT-FLAG ────────────────────────────────────────────────────────────────

def test_strict_false_returns_incomplete_instead_of_raising():
    """run_execute_phase(strict=False) returns the blocked TaskResult
    rather than raising [HALT], so a gate can recover it."""
    plan = _plan()
    results = asyncio.run(run_execute_phase(
        plan, TEMP_DIR / "s00_strict_false", asyncio.Semaphore(20),
        _intern_block_first({"intern01"}),
        strict=False,
    ))
    assert "intern01" in results
    assert results["intern01"].status == "blocked"
    # All interns still spawned despite the block (SPAWN-ALL preserved).
    assert set(results) == {"intern01"}


def test_strict_true_default_still_halts():
    """The default strict=True MUST still hard-halt (guards uqj06).
    A future change must not weaken this for top-level callers."""
    plan = _plan()
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(run_execute_phase(
            plan, TEMP_DIR / "s00_strict_true", asyncio.Semaphore(20),
            _intern_block_first({"intern01"}),
        ))
    assert "[HALT] EXECUTE phase incomplete: intern01" in str(exc.value)


