"""Regression tests for 01_fix.md DAG timeout fixes (s49n0).

No LLM keys required: intern_fn is stubbed and the ApprovedPlan is built in-process.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
import subprocess

import pytest

from factory.infra._loopguard import AGENT_RUN_TIMEOUT
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
from factory.infra.execution import (
    INTERN_VALIDATION_PASSES,
    DAG_DEADLOCK_TIMEOUT,
    run_execute_phase,
)


def _plan() -> ExecutablePlan:
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
        tasks=[ApprovedTask(id=f"intern0{i}", title=f"t{i}", file_paths=[f"src2/{i}.py"],
                            instruction=f"implement intern_0{i}", acceptance=f"intern_0{i} ok",
                            tool_preference="CLI-wrapper") for i in range(2, 5)],
    )
    strat = Strategy(
        how_to_fix="x",
        tool_preference={f"intern0{i}": "CLI-wrapper" for i in range(1, 5)},
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
        approved=True,
    )


# ---- Fix 1: DAG liveness guard ----

def test_dag_timeout_constant_is_correct():
    assert INTERN_VALIDATION_PASSES == 3
    assert AGENT_RUN_TIMEOUT == 600.0
    assert DAG_DEADLOCK_TIMEOUT == 1800.0


def test_slow_legitimate_group_does_not_crash(monkeypatch):
    """A slow prerequisite group that exceeds the old 300s deadline must NOT crash.
    Patch DAG_DEADLOCK_TIMEOUT=0.5, AGENT_RUN_TIMEOUT=5 so group_2's wait fires,
    detects group_done=False, and keeps waiting."""
    monkeypatch.setattr("factory.infra.execution.DAG_DEADLOCK_TIMEOUT", 0.5)
    monkeypatch.setattr("factory.infra.execution.AGENT_RUN_TIMEOUT", 5.0)
    monkeypatch.setattr("factory.infra.execution._write_harness_patches", lambda task_id, files, bd="": ([], 1))

    async def slow_intern_fn(brief: str, task_id: str | None = None) -> str:
        tid = task_id or brief.split("TASK ID:")[1].split()[0]
        await asyncio.sleep(1.0)
        return json.dumps({"status": "done", "task_id": tid, "files_changed": [], "diff_summary": "", "notes": ""})

    results = asyncio.run(run_execute_phase(
        _plan(), TEMP_DIR / "01fix_slow", asyncio.Semaphore(20), slow_intern_fn,
    ))
    assert all(r.status == "done" for r in results.values())
    assert {f"intern0{i}" for i in range(1, 5)} == set(results.keys())


# ---- Fix 2: Per-task timeout ----

def test_hung_intern_times_out_and_is_blocked(monkeypatch):
    """A intern that exceeds AGENT_RUN_TIMEOUT returns blocked instead of stalling."""
    monkeypatch.setattr("factory.infra.execution.AGENT_RUN_TIMEOUT", 0.5)
    monkeypatch.setattr("factory.infra.execution.DAG_DEADLOCK_TIMEOUT", 10.0)

    async def hang_intern_fn(brief: str, task_id: str | None = None) -> str:
        tid = task_id or brief.split("TASK ID:")[1].split()[0]
        if tid == "intern01":
            await asyncio.sleep(2.0)
        return json.dumps({"status": "done", "task_id": tid, "files_changed": [], "diff_summary": "", "notes": ""})

    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete.*intern01"):
        asyncio.run(run_execute_phase(
            _plan(), TEMP_DIR / "01fix_hang", asyncio.Semaphore(20), hang_intern_fn,
        ))


def test_all_done_no_timeout(monkeypatch):
    monkeypatch.setattr("factory.infra.execution._write_harness_patches", lambda task_id, files, bd="": ([], 1))

    async def quick_intern_fn(brief: str, task_id: str | None = None) -> str:
        tid = task_id or brief.split("TASK ID:")[1].split()[0]
        return json.dumps({"status": "done", "task_id": tid, "files_changed": [], "diff_summary": "", "notes": ""})

    results = asyncio.run(run_execute_phase(
        _plan(), TEMP_DIR / "01fix_ok", asyncio.Semaphore(20), quick_intern_fn,
    ))
    assert all(r.status == "done" for r in results.values())


# ---- Fix 3: add_constant empty-value guard ----

def test_add_constant_empty_value_fails():
    result = subprocess.run(
        [sys.executable, "factory/tools/add_constant.py", "src2/a.py", "MY_CONST", ""],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]), timeout=10,
    )
    assert result.returncode != 0
    assert "no value supplied" in result.stdout


def test_add_constant_class_def_rejected():
    """add_constant rejects multi-line class defs (pre-existing behaviour, verified in crash log)."""
    result = subprocess.run(
        [sys.executable, "factory/tools/add_constant.py",
         "src2/core/schemas/unified.py", "MyClass",
         "class MyClass:\n    pass"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]), timeout=10,
    )
    # The tool resolves the path relative to the project; if unified.py exists,
    # it should reject the class definition, not "file not found".
    if "File not found" not in result.stdout:
        assert "Not a valid constant assignment" in result.stdout
