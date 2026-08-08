"""Tests for Conductor-led Pre-staging.

Exercises stage_workspace_from_draft to ensure:
  1. Existing source files (src2/...) are copied to factory/temp/src2/...
  2. Proposed new deliverables (ending in .diff, .md or with temp/ in path) are touched as empty files.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


from factory.infra.models import (
    ApprovedTask,
    DraftPlan,
    Epic,
    EvidenceItem,
    ParallelisableWorkplan,
    RubricCell,
    RubricCube,
    Strategy,
    SubTaskBrief,
    UserStory,
    WorkGroup,
)
from factory.infra.context import stage_workspace_from_draft


def test_stage_workspace_from_draft(tmp_path, monkeypatch):
    # Setup mock REPO_ROOT and TEMP_DIR
    import factory.infra.context as context_mod
    import factory.infra.control as ctrl

    monkeypatch.setattr(ctrl, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_mod, "REPO_ROOT", tmp_path)

    mock_temp = tmp_path / "admin" / "orchestrator" / "temp"
    monkeypatch.setattr(ctrl, "TEMP_DIR", mock_temp)
    monkeypatch.setattr(context_mod, "TEMP_DIR", mock_temp)

    # Create dummy source files
    src2_dir = tmp_path / "src2" / "engine"
    src2_dir.mkdir(parents=True, exist_ok=True)
    live_file = src2_dir / "module_test.py"
    live_file.write_text("print('hello')", encoding="utf-8")

    # Define DraftPlan with subtasks referencing existing files and new deliverables
    subtask = SubTaskBrief(
        id="intern01",
        title="Edit test module",
        file_paths=["src2/engine/module_test.py", "factory/temp/patch_test.diff"],
        instruction="Do something",
        acceptance="done",
        tool_preference="AST-edit",
        evidence=[
            EvidenceItem(file_path="src2/engine/module_test.py", content="print('hello')"),
            EvidenceItem(file_path="factory/temp/patch_test.diff", content="")
        ]
    )

    draft = DraftPlan(
        epic=Epic(title="e", deliverables=["d"], must_be_pydantic=True),
        user_stories=[UserStory(id="s1", story="s", acceptance_criteria=["a"], definition_of_done=["d"])],
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[RubricCell(dimension="x", criterion="c", severity="blocker", passed=True)]),
        summary="s",
        subtasks=[subtask],
        risks=[],
        strategy=Strategy(
            how_to_fix="x",
            tool_preference=[{"task_id": "intern01", "preference": "AST-edit"}],
            parallelisable_workplan=ParallelisableWorkplan.model_construct(
                groups=[
                    WorkGroup.model_construct(
                        id="group_1",
                        depends_on=[],
                        tasks=[
                            ApprovedTask.model_construct(
                                id="intern01",
                                title="Edit test module",
                                file_paths=["src2/engine/module_test.py", "factory/temp/patch_test.diff"],
                                instruction="Do something",
                                acceptance="done",
                                tool_preference="AST-edit",
                                evidence=[
                                    EvidenceItem(file_path="src2/engine/module_test.py", content="print('hello')"),
                                    EvidenceItem(file_path="factory/temp/patch_test.diff", content="")
                                ],
                                approved=True,
                                notes=""
                            )
                        ],
                    )
                ]
            )
        )
    )

    # Execute pre-staging
    stage_workspace_from_draft(draft, bd="test_bd")

    # Assertions
    # 1. Existing source file is copied to temp/src2/...
    copied_src = mock_temp / "src2" / "engine" / "module_test.py"
    assert copied_src.exists()
    assert copied_src.read_text(encoding="utf-8") == "print('hello')"

    # 2. Proposed new deliverable is touched as a 0-byte file
    touched_diff = tmp_path / "factory/temp" / "patch_test.diff"
    assert touched_diff.exists()
    assert touched_diff.stat().st_size == 0
