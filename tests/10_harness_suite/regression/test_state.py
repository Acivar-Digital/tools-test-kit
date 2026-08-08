"""Crash-resume state tests (README Crash-Resume + Build_06_Testing.md:136).

Drives state.py end-to-end with NO LLM: fresh_state -> record_phase/upsert_task
-> save_state -> load_state (resume) -> reset_stale_in_progress. Asserts the
three invariants: atomic write, newest-run resume, exactly-once re-execution.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra import models, state


def _task(tid: str, status: str = "pending", attempts: int = 0) -> models.TaskState:
    return models.TaskState(task_id=tid, status=status, attempts=attempts)


def _workplan():
    return models.ParallelisableWorkplan(
        groups=[
            models.WorkGroup(
                id="g1",
                tasks=[models.ApprovedTask(id="intern01", title="t", file_paths=["src2/x.py"], instruction="i", acceptance="a", tool_preference="AST-edit")],
            )
        ]
    )


def _draft():
    return models.DraftPlan(
        epic=models.Epic(title="t", deliverables=["d"], must_be_pydantic=True),
        user_stories=[models.UserStory(id="u1", story="s", acceptance_criteria=["a"], definition_of_done=["d"])],
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=models.RubricCube(cells=[]),
        summary="s",
        subtasks=[models.SubTaskBrief(id="s1", title="t", file_paths=["src2/x.py"], instruction="i", acceptance="a", tool_preference="AST-edit", evidence=[{"file_path": "src2/x.py", "content": "verified"}])],
        risks=[],
        strategy=models.Strategy(how_to_fix="f", tool_preference=[{"task_id": "s1", "preference": "AST-edit"}], parallelisable_workplan=_workplan()),
    )


def test_fresh_state_creates_run_dir(tmp_path):
    st = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    assert st.bd_id == "bd1"
    assert (Path(st.run_dir) / "state.json").exists() is False  # not written until save
    assert Path(st.run_dir).is_dir()


def test_save_state_atomic_and_resumable(tmp_path):
    st = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    state.record_phase(st, "intern")
    state.save_state(st)
    final = Path(st.run_dir) / "state.json"
    tmp = Path(st.run_dir) / "state.json.tmp"
    assert final.exists() and not tmp.exists()  # atomic: tmp replaced, never lingers

    # Resume: load_state returns the persisted + appended state.
    loaded = state.load_state("bd1", reports_dir=tmp_path)
    assert loaded is not None
    assert loaded.current_phase == "intern"
    assert loaded.phase_attempts == {"intern": 1}


def test_append_phase_attempts_increment(tmp_path):
    st = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    state.record_phase(st, "intern")
    state.save_state(st)
    # Simulate a re-execution of intern (e.g. engineer reopened it).
    state.record_phase(st, "intern")
    state.save_state(st)

    loaded = state.load_state("bd1", reports_dir=tmp_path)
    assert loaded.phase_attempts["intern"] == 2
    assert loaded.current_phase == "intern"


def test_append_tasks_and_handoffs(tmp_path):
    st = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    state.upsert_task(st, _task("t1", status="in_progress", attempts=1))
    state.upsert_task(st, _task("t2", status="pending"))
    # Hand-off models append across phases.
    st.draft = _draft()
    st.approved = models.ExecutablePlan(
        epic=st.draft.epic, user_stories=st.draft.user_stories, definition_of_done=["d"],
        acceptance_criteria=["a"], rubric_cube=models.RubricCube(cells=[]), summary="s",
        tasks=[models.ApprovedTask(id="intern01", title="t", file_paths=["src2/x.py"], instruction="i", acceptance="a", tool_preference="AST-edit")],
        alignment="a", workplan=_workplan(),
        strategy=st.draft.strategy,
    )
    state.save_state(st)

    loaded = state.load_state("bd1", reports_dir=tmp_path)
    assert set(loaded.tasks) == {"t1", "t2"}
    assert loaded.tasks["t1"].status == "in_progress"
    assert loaded.tasks["t1"].attempts == 1
    # Pydantic hand-off models round-trip intact (no dict loss).
    assert loaded.draft is not None and loaded.draft.subtasks[0].id == "s1"
    assert loaded.approved is not None and loaded.approved.alignment == "a"


def test_load_newest_run_when_multiple(tmp_path):
    older = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    state.record_phase(older, "PLAN")
    state.save_state(older)

    newer = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260202T000000")
    state.record_phase(newer, "senior")
    state.save_state(newer)

    loaded = state.load_state("bd1", reports_dir=tmp_path)
    assert loaded.current_phase == "senior"  # newest wins


def test_load_state_missing_returns_none(tmp_path):
    assert state.load_state("nope", reports_dir=tmp_path) is None


def test_reset_stale_in_progress_flips_to_pending(tmp_path):
    st = state.fresh_state("bd1", reports_dir=tmp_path, timestamp="20260101T000000")
    state.upsert_task(st, _task("t1", status="in_progress", attempts=2))
    state.upsert_task(st, _task("t2", status="done", attempts=1))
    state.upsert_task(st, _task("t3", status="blocked"))
    state.save_state(st)

    # Simulate a kill: reload, then reset stale units before re-spawn.
    loaded = state.load_state("bd1", reports_dir=tmp_path)
    assert loaded.tasks["t1"].status == "in_progress"
    state.reset_stale_in_progress(loaded)

    assert loaded.tasks["t1"].status == "pending"   # stale in_progress -> re-exec
    assert loaded.tasks["t2"].status == "done"      # untouched
    assert loaded.tasks["t3"].status == "blocked"   # untouched
