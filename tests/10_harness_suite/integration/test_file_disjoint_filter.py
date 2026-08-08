"""Regression tests for vw4dd.

The cross-group / intra-group file-disjointness HALT (added by closed
zu9u) must NOT trip on the Intern's untrusted file_paths
claims. The Intern is reasoning-only and routinely emits derived/staging/
hallucinated paths (e.g. ``factory/temp/src2/.../unified_patch.py``)
into file_paths. Those are not real source files and cannot cause a
concurrent-edit race, so they must be filtered out before the assertion.

Genuine overlap of TWO REAL existing src2/ source files across concurrent
groups MUST still HALT (true positive).

No LLM keys required: intern_fn is stubbed and the plan is built in-process.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import asyncio

from factory.infra.control import REPO_ROOT
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
from factory.infra.context import _real_source_paths
from factory.infra.execution import run_execute_phase


def _make_real_src2(rel: str) -> Path:
    """Create a real file under the repo's src2/ tree; return its Path."""
    fp = REPO_ROOT / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("# real source\n", encoding="utf-8")
    return fp


def _rm(p: Path) -> None:
    try:
        p.unlink()
    except OSError:
        pass


def _plan_with(groups: list[WorkGroup]) -> ExecutablePlan:
    epic = Epic(title="e", deliverables=["d"], must_be_pydantic=True)
    cube = RubricCube(cells=[RubricCell(dimension="x", criterion="c",
                                         severity="blocker", passed=True)])
    strat = Strategy(
        how_to_fix="x",
        tool_preference={t.id: "CLI-wrapper" for g in groups for t in g.tasks},
        parallelisable_workplan=ParallelisableWorkplan(groups=groups),
    )
    return ExecutablePlan(
        epic=epic,
        user_stories=[UserStory(id="s1", story="s", acceptance_criteria=["a"],
                                definition_of_done=["d"])],
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=cube,
        summary="s",
        tasks=[t for g in groups for t in g.tasks],
        alignment="align",
        workplan=ParallelisableWorkplan(groups=groups),
        strategy=strat,
        approved=True
    )


async def _stub_intern_fn(brief: str, task_id: str | None = None):
    tid = task_id or "x"
    return json.dumps({
        "status": "done", "rc": 0, "stdout": "ok", "stderr": "",
        "task_id": tid, "files_changed": [], "diff_summary": "", "notes": "ok",
    })


def test_real_source_paths_filters_derived_and_missing():
    """Derived/staging/hallucinated/missing paths are dropped; real src2 kept."""
    with tempfile.TemporaryDirectory() as d:
        real = _make_real_src2("src2/_vw4dd_real.py")
        try:
            got = _real_source_paths([
                "src2/_vw4dd_real.py",  # real existing src2 file -> kept
                str(Path(d) / "factory/temp/src2/core/schemas/unified_patch.py"),  # staging
                "src2/does_not_exist_yet.py",  # missing
                "factory/temp/foo.py",  # not under src2/
                "README.md",  # real but not under src2/
            ])
            assert got == ["src2/_vw4dd_real.py"]
        finally:
            _rm(real)


def test_false_positive_plan_does_not_crash(monkeypatch):
    """A plan whose file_paths are all derived/staging paths must NOT raise."""
    monkeypatch.setattr(
        "factory.infra.execution._write_harness_patches",
        lambda task_id, files, bd="": ([], 1),
    )

    g1 = WorkGroup(
        id="g1",
        tasks=[ApprovedTask(id="intern01", title="t1",
                            file_paths=["factory/temp/src2/core/schemas/unified_patch.py"],
                            instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
    )
    g2 = WorkGroup(
        id="g2",
        depends_on=["g1"],
        tasks=[ApprovedTask(id="intern02", title="t2",
                            file_paths=["src2/does_not_exist.py"],
                            instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
    )
    plan = _plan_with([g1, g2])
    # Must NOT raise RuntimeError([DAG] ...).
    with tempfile.TemporaryDirectory() as d:
        results = asyncio.run(run_execute_phase(
            plan, Path(d) / "run", asyncio.Semaphore(20), _stub_intern_fn))
    assert set(results) == {"intern01", "intern02"}


def test_true_positive_real_overlap_still_halts():
    """Two concurrent groups (no depends_on) sharing a REAL src2/ file MUST HALT."""
    shared = _make_real_src2("src2/_vw4dd_shared.py")
    try:
        g1 = WorkGroup(
            id="g1",
            tasks=[ApprovedTask(id="intern01", title="t1", file_paths=["src2/_vw4dd_shared.py"],
                                instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
        )
        g2 = WorkGroup(
            id="g2",
            # No depends_on — genuinely concurrent with g1, so file overlap is unsafe
            tasks=[ApprovedTask(id="intern02", title="t2", file_paths=["src2/_vw4dd_shared.py"],
                                instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
        )
        plan = _plan_with([g1, g2])
        with tempfile.TemporaryDirectory() as d:
            try:
                asyncio.run(run_execute_phase(
                    plan, Path(d) / "run", asyncio.Semaphore(20), _stub_intern_fn))
                raise AssertionError("expected [DAG] cross-group file overlap RuntimeError")
            except RuntimeError as e:
                assert "cross-group file overlap" in str(e)
    finally:
        _rm(shared)


def test_depends_on_chain_allows_file_overlap(monkeypatch):
    """Sequential groups in a depends_on chain MAY share a file."""
    monkeypatch.setattr(
        "factory.infra.execution._write_harness_patches",
        lambda task_id, files, bd="": ([], 1),
    )
    shared = _make_real_src2("src2/_vw4dd_chain_overlap.py")
    try:
        g1 = WorkGroup(
            id="g1",
            tasks=[ApprovedTask(id="intern01", title="t1", file_paths=["src2/_vw4dd_chain_overlap.py"],
                                instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
        )
        g2 = WorkGroup(
            id="g2",
            depends_on=["g1"],
            tasks=[ApprovedTask(id="intern02", title="t2", file_paths=["src2/_vw4dd_chain_overlap.py"],
                                instruction="i", acceptance="a", tool_preference="CLI-wrapper")],
        )
        plan = _plan_with([g1, g2])
        with tempfile.TemporaryDirectory() as d:
            # Must NOT raise — g2 runs after g1, no race condition
            results = asyncio.run(run_execute_phase(
                plan, Path(d) / "run", asyncio.Semaphore(20), _stub_intern_fn))
        assert set(results) == {"intern01", "intern02"}
    finally:
        _rm(shared)
