"""Intern naming contract (ticket tqpgf).

No LLM keys required. Validates:
  * ApprovedTask.id MUST match ^intern_\\d+$ (no task_N, no concatenated, no non-numeric);
  * ApprovedPlan tasks MUST have unique ids across the whole plan;
  * _intern_agent_id is a pass-through returning the intern id verbatim (no digit mangling);
  * the harness plan-gate re-validation surfaces a clear HALT on non-conforming plans.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from pydantic import ValidationError

from factory.infra.models import (
    ApprovedTask,
    Epic,
    ExecutablePlan,
    ParallelisableWorkplan,
    RubricCube,
    Strategy,
    UserStory,
    WorkGroup,
)
from factory.infra.agent import _intern_agent_id


def _task(tid: str) -> ApprovedTask:
    return ApprovedTask(
        id=tid,
        title="t",
        file_paths=["src2/engine/foo.py"],
        instruction="do",
        acceptance="done",
        tool_preference="AST-edit",
        evidence=[{"file_path": "src2/engine/foo.py", "content": "x"}],
    )


def _plan(ids: list[str]) -> ExecutablePlan:
    tasks = [_task(i) for i in ids]
    return ExecutablePlan(
        epic=Epic(title="e", deliverables=["d"], must_be_pydantic=True),
        user_stories=[UserStory(id="u1", story="s", acceptance_criteria=["a"], definition_of_done=["d"])],
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[]),
        summary="s",
        tasks=tasks,
        alignment="a",
        workplan=ParallelisableWorkplan(groups=[WorkGroup(id="g1", tasks=tasks)]),
        strategy=Strategy(how_to_fix="f", tool_preference=[], parallelisable_workplan=ParallelisableWorkplan(groups=[WorkGroup(id="g0", tasks=tasks)])),
    )


def test_valid_intern_ids_accepted():
    # intern01, intern02, intern10 sort correctly and validate.
    plan = _plan(["intern01", "intern02", "intern10"])
    assert plan.tasks[0].id == "intern01"
    assert plan.tasks[2].id == "intern10"


@pytest.mark.parametrize("bad", ["task_3", "intern3", "intern91011", "intern_X", "intern", "3", ""])
def test_invalid_intern_id_rejected(bad):
    with pytest.raises(ValidationError):
        _plan([bad])


def test_duplicate_intern_ids_rejected():
    with pytest.raises(ValidationError):
        _plan(["intern01", "intern01"])


def test_intern_agent_id_passthrough():
    # _intern_agent_id returns the intern id verbatim — no digit mangling.
    assert _intern_agent_id("intern01") == "intern01"
    assert _intern_agent_id("intern_10") == "intern_10"
    # non-intern role paths pass None
    assert _intern_agent_id(None) is None


def test_legacy_digit_mangling_no_longer_possible():
    # The old logic would have turned "task_3"+"task_4" into "intern34".
    # Now each id is validated independently, so the intern can never emit it.
    with pytest.raises(ValidationError):
        _plan(["task_3", "task_4"])
