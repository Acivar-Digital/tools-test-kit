"""Regression tests for docs/01_fix.md — fast_json_repair corrupts double-encoded `strategy`.

The intern phase crashes with `strategy: Input should be an object` because a
free/low-tier model double-encodes the ENTIRE `final_result` payload as a JSON
string (and the nested `strategy` object is itself a JSON string). The old
pipeline ran `fast_json_repair` unconditionally, which truncated the inner
string at the first `{`. Fix A pre-parses with the stdlib `json.loads` (JSON-aware
about nested string values) BEFORE repair; Fix B hardens the model validators.
"""

import json

from pydantic import BaseModel as _BaseModel

from factory.infra import output_sanitizer as osan
from factory.infra.models import (
    ApprovedTask,
    DraftPlan,
    Epic,
    EvidenceItem,
    ExecutablePlan,
    ParallelisableWorkplan,
    RubricCell,
    RubricCube,
    Strategy,
    SubTaskBrief,
    ToolPreferenceItem,
    WorkGroup,
)


def _build_strategy() -> Strategy:
    return Strategy(
        how_to_fix="wire the patch generator",
        tool_preference=[ToolPreferenceItem(task_id="intern01", preference="AST-edit")],
        parallelisable_workplan=ParallelisableWorkplan(
            groups=[WorkGroup(id="g1", tasks=[ApprovedTask(id="intern01", title="t",
                file_paths=["src2/a.py"], instruction="i", acceptance="a",
                tool_preference="AST-edit")])]
        ),
    )


def _build_draft_plan(strategy: Strategy) -> DraftPlan:
    return DraftPlan(
        epic=Epic(title="ep", deliverables=["d"], must_be_pydantic=True),
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[RubricCell(dimension="pydantic", criterion="c",
            severity="blocker", passed=True)]),
        summary="sum",
        subtasks=[SubTaskBrief(id="intern01", title="t", file_paths=["src2/a.py"],
            instruction="i", acceptance="a", tool_preference="AST-edit",
            evidence=[EvidenceItem(file_path="src2/a.py", content="c")])],
        risks=[],
        strategy=strategy,
    )


def _build_executable_plan(strategy: Strategy) -> ExecutablePlan:
    return ExecutablePlan(
        epic=Epic(title="ep", deliverables=["d"], must_be_pydantic=True),
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[RubricCell(dimension="pydantic", criterion="c",
            severity="blocker", passed=True)]),
        summary="sum",
        tasks=[ApprovedTask(id="intern01", title="t", file_paths=["src2/a.py"],
            instruction="i", acceptance="a", tool_preference="AST-edit")],
        alignment="aligned",
        workplan=ParallelisableWorkplan(groups=[WorkGroup(id="g1",
            tasks=[ApprovedTask(id="intern01", title="t", file_paths=["src2/a.py"],
                instruction="i", acceptance="a", tool_preference="AST-edit")])]),
        strategy=strategy,
    )


def test_clean_role_output_recovers_double_encoded_strategy():
    """Fix A: whole-payload double-encoding with `strategy` also a string."""
    good = _build_draft_plan(_build_strategy())
    # Stringify the ENTIRE payload, AND stringify the nested strategy field.
    inner = good.model_dump(mode="json")
    inner["strategy"] = json.dumps(inner["strategy"], ensure_ascii=False)
    double_encoded = json.dumps(inner, ensure_ascii=False)

    result = osan.clean_role_output(double_encoded, DraftPlan)
    assert isinstance(result, DraftPlan)
    # strategy must be a parsed object, not a string
    assert isinstance(result.strategy, Strategy)
    assert result.strategy.how_to_fix == "wire the patch generator"


def test_clean_role_output_recovers_outer_string_only_strategy():
    """Fix A: only the outer payload is a string (strategy already an object)."""
    good = _build_draft_plan(_build_strategy())
    outer_string = json.dumps(good.model_dump(mode="json"), ensure_ascii=False)

    result = osan.clean_role_output(outer_string, DraftPlan)
    assert isinstance(result, DraftPlan)
    assert isinstance(result.strategy, Strategy)


def test_model_validator_unwraps_whole_payload_string():
    """Fix B: DraftPlan._coerce_strategy handles a whole-payload string."""
    good = _build_draft_plan(_build_strategy())
    inner = good.model_dump(mode="json")
    inner["strategy"] = json.dumps(inner["strategy"], ensure_ascii=False)
    double_encoded = json.dumps(inner, ensure_ascii=False)

    result = DraftPlan.model_validate_json(double_encoded)
    assert isinstance(result.strategy, Strategy)


def test_approved_plan_validator_unwraps_whole_payload_string():
    """Fix B: ExecutablePlan._coerce_strategy handles a whole-payload string."""
    good = _build_executable_plan(_build_strategy())
    inner = good.model_dump(mode="json")
    inner["strategy"] = json.dumps(inner["strategy"], ensure_ascii=False)
    double_encoded = json.dumps(inner, ensure_ascii=False)

    result = ExecutablePlan.model_validate_json(double_encoded)
    assert isinstance(result.strategy, Strategy)


def test_clean_role_output_still_runs_repair_on_broken_json():
    """Fix A must NOT break the genuinely-broken JSON path (repair still runs)."""

    class Minimal(_BaseModel):
        name: str

    # A valid-but-needs-repair case: trailing comma + nested string value.
    needs_repair = '{"name": "ok", "nested": "{"x": 1}"}'
    result = osan.clean_role_output(needs_repair, Minimal)
    assert isinstance(result, Minimal)
    assert result.name == "ok"
