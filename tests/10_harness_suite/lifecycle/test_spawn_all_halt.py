"""Regression tests for uqj06: spawn-all interns + halt-on-block.

No LLM keys required: intern_fn is stubbed and the ApprovedPlan is built in-process.

Validates end-to-end through `run_execute_phase`:

  * SPAWN-ALL — when a prerequisite group's only task returns `blocked`, the
    dependent group's unrelated tasks STILL spawn and execute (the old code
    short-circuited the whole dependent group with "produced 0 usable tasks").
  * HALT-ON-BLOCK — after ALL groups finish, if ANY task is `blocked`/`failed`
    (or produced no result), the run is hard-halted with
    `RuntimeError("[HALT] EXECUTE phase incomplete: <ids>")`, listing every
    incomplete task id. This guarantees incomplete work never reaches review.

These guard the fix from `uqj06`. If a future change re-adds the
skip-short-circuit, tasks 2-6 silently vanish again — this test fails loudly.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import factory.infra.execution as exec_mod

from factory.infra.control import TEMP_DIR
from factory.infra.models import (
    ApprovedTask,
    Epic,
    ExecutablePlan,
    ParallelisableWorkplan,
    RubricCell,
    RubricCube,
    Strategy,
    UserStory,
    WorkGroup,
)
from factory.infra.execution import run_execute_phase


@pytest.fixture(autouse=True)
def _patch_harness(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        exec_mod, "_write_harness_patches",
        lambda task_id, files, bd="": ([], 1),
    )


def _plan() -> ExecutablePlan:
    """g1=[intern_1]; g2=[intern_2..intern_6] depends_on g1 (mirrors hbh1)."""
    epic = Epic(title="e", deliverables=["d"], must_be_pydantic=True)
    g1 = WorkGroup(
        id="g1",
        tasks=[ApprovedTask(id="intern01", title="t1", file_paths=["src2/a.py"],
                            instruction="implement intern_1", acceptance="intern_1 ok",
                            tool_preference="CLI-wrapper")],
    )
    g2 = WorkGroup(
        id="g2",
        depends_on=["g1"],
        tasks=[ApprovedTask(id=f"intern{i:02d}", title=f"t{i}", file_paths=[f"src2/{i}.py"],
                            instruction=f"implement intern_{i}", acceptance=f"intern_{i} ok",
                            tool_preference="CLI-wrapper") for i in range(2, 7)],
    )
    strat = Strategy(
        how_to_fix="x",
        tool_preference={f"intern{i:02d}": "CLI-wrapper" for i in range(1, 7)},
        parallelisable_workplan=ParallelisableWorkplan(groups=[g1, g2]),
    )
    return ExecutablePlan(
        epic=epic,
        user_stories=[UserStory(id="s1", story="s", acceptance_criteria=["a"],
                                definition_of_done=["d"])],
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[RubricCell(dimension="x", criterion="c",
                                                  severity="blocker", passed=True)]),
        summary="s",
        tasks=list(g1.tasks) + list(g2.tasks),
        alignment="align",
        workplan=ParallelisableWorkplan(groups=[g1, g2]),
        strategy=strat,
        approved=True
    )


def _intern_block_first(blocked_ids: set[str], spawned: dict[str, str] | None = None):
    """Intern stub: returns `blocked` for ids in blocked_ids, else `done`.

    Records every spawned task into `spawned` so the test can assert all
    dependent-group interns still ran despite a prerequisite block.
    """
    def _make(blocked: set[str]):
        async def intern_fn(brief: str, task_id: str | None = None) -> str:
            tid = task_id or brief.split("TASK ID:")[1].split()[0]
            if spawned is not None:
                spawned[tid] = brief
            status = "blocked" if tid in blocked else "done"
            return json.dumps({"status": status, "rc": 0, "stdout": "ok", "stderr": "",
                                "task_id": tid, "files_changed": [], "diff_summary": "",
                                "notes": "blocked on read budget" if status == "blocked" else ""})
        return intern_fn
    return _make(blocked_ids)


def _intern_record_spawn(spawned: dict[str, str]):
    async def intern_fn(brief: str, task_id: str | None = None) -> str:
        tid = task_id or brief.split("TASK ID:")[1].split()[0]
        spawned[tid] = brief
        return json.dumps({"status": "done", "rc": 0, "stdout": "ok", "stderr": "",
                            "task_id": tid, "files_changed": [], "diff_summary": "",
                            "notes": ""})
    return intern_fn


def test_spawn_all_when_prerequisite_blocked():
    """SPAWN-ALL: task_1 blocks but tasks 2-6 MUST still spawn and execute."""
    plan = _plan()
    spawned: dict[str, str] = {}
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(run_execute_phase(
            plan, TEMP_DIR / "spawn_all", asyncio.Semaphore(20),
            _intern_block_first({"intern01"}, spawned),
        ))
    # All six interns spawned despite the prerequisite block.
    assert set(spawned) == {f"intern{i:02d}" for i in range(1, 7)}
    # The halt names only the incomplete task(s).
    assert "[HALT] EXECUTE phase incomplete: intern01" in str(exc.value)


def test_halt_lists_all_incomplete_tasks():
    """HALT-ON-BLOCK: multiple blocked tasks are all reported, not just one."""
    plan = _plan()
    spawned: dict[str, str] = {}
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(run_execute_phase(
            plan, TEMP_DIR / "spawn_all_multi", asyncio.Semaphore(20),
            _intern_block_first({"intern01", "intern04", "intern06"}, spawned),
        ))
    assert set(spawned) == {f"intern{i:02d}" for i in range(1, 7)}
    msg = str(exc.value)
    assert "[HALT] EXECUTE phase incomplete:" in msg
    for tid in ("intern01", "intern04", "intern06"):
        assert tid in msg


def test_no_halt_when_all_done():
    """No regression: a fully-successful run proceeds without raising."""
    plan = _plan()
    spawned: dict[str, str] = {}
    results = asyncio.run(run_execute_phase(
        plan, TEMP_DIR / "spawn_all_ok", asyncio.Semaphore(20),
        _intern_record_spawn(spawned),
    ))
    assert set(spawned) == {f"intern{i:02d}" for i in range(1, 7)}
    assert all(r.status == "done" for r in results.values())


def test_halt_on_exception_mapping():
    """Verify that if intern_fn raises an exception, the runner wraps it into a TaskResult(status="blocked") instead of crashing."""
    plan = _plan()
    
    async def throwing_intern_fn(brief: str, task_id: str | None = None) -> str:
        tid = task_id or brief.split("TASK ID:")[1].split()[0]
        if tid == "intern01":
            raise RuntimeError("Simulation of a tool/subprocess failure")
        return json.dumps({"status": "done", "rc": 0, "stdout": "ok", "stderr": "",
                            "task_id": tid, "files_changed": [], "diff_summary": "",
                            "notes": ""})

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(run_execute_phase(
            plan, TEMP_DIR / "spawn_all_exception", asyncio.Semaphore(20),
            throwing_intern_fn,
        ))
    msg = str(exc.value)
    assert "[HALT] EXECUTE phase incomplete: intern01" in msg
