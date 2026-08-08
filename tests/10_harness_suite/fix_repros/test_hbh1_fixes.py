from factory.infra.validation import check_plan_invariants
from factory.infra.tools import ROLE_TOOL_BUDGET
from factory.infra.models import (
    ApprovedTask,
    Epic,
    ExecutablePlan,
    ParallelisableWorkplan,
    RubricCube,
    Strategy,
    WorkGroup,
)

def test_intern_budget():
    assert ROLE_TOOL_BUDGET.get("intern") == 75

def test_check_plan_invariants_valid():
    epic = Epic(title="Epic", deliverables=["d1"], must_be_pydantic=True)
    task1 = ApprovedTask(
        id="intern01",
        title="Task 1",
        file_paths=["file1.py"],
        instruction="Do something",
        acceptance="Acceptance",
        tool_preference="AST-edit",
        evidence=[]
    )
    task2 = ApprovedTask(
        id="intern02",
        title="Task 2",
        file_paths=["file3.py"],
        instruction="Do something else",
        acceptance="Acceptance",
        tool_preference="CLI-wrapper",
        evidence=[]
    )
    group1 = WorkGroup(
        id="group_1",
        tasks=[task1],
        depends_on=[]
    )
    group2 = WorkGroup(
        id="group_2",
        tasks=[task2],
        depends_on=["group_1"]
    )
    plan = ExecutablePlan(
        epic=epic,
        user_stories=[],
        definition_of_done=[],
        acceptance_criteria=[],
        rubric_cube=RubricCube(cells=[]),
        summary="Summary",
        tasks=[task1, task2],
        alignment="Alignment",
        workplan=ParallelisableWorkplan(groups=[group1, group2]),
        rejected_subtasks=[],
        strategy=Strategy(how_to_fix="How to fix", tool_preference=[], parallelisable_workplan=ParallelisableWorkplan(groups=[group1, group2])),
        approved=True
    )
    violations = check_plan_invariants(plan)
    assert not violations

def test_check_plan_invariants_over_five_files():
    epic = Epic(title="Epic", deliverables=["d1"], must_be_pydantic=True)
    task1 = ApprovedTask.model_construct(
        id="intern01",
        title="Task 1",
        file_paths=["f1.py", "f2.py", "f3.py", "f4.py", "f5.py", "f6.py"],
        instruction="Too many files",
        acceptance="Acceptance",
        tool_preference="AST-edit",
        evidence=[]
    )
    group1 = WorkGroup.model_construct(
        id="group_1",
        tasks=[task1],
        depends_on=[]
    )
    plan = ExecutablePlan.model_construct(
        epic=epic,
        user_stories=[],
        definition_of_done=[],
        acceptance_criteria=[],
        rubric_cube=RubricCube(cells=[]),
        summary="Summary",
        tasks=[task1],
        alignment="Alignment",
        workplan=ParallelisableWorkplan.model_construct(groups=[group1]),
        rejected_subtasks=[],
        strategy=Strategy(how_to_fix="How to fix", tool_preference=[], parallelisable_workplan=ParallelisableWorkplan.model_construct(groups=[group1])),
        approved=True
    )
    violations = check_plan_invariants(plan)
    assert len(violations) == 1
    assert "lists 6 files (exactly 1 required)" in violations[0]

def test_check_plan_invariants_collisions():
    epic = Epic(title="Epic", deliverables=["d1"], must_be_pydantic=True)
    task1 = ApprovedTask(
        id="intern01",
        title="Task 1",
        file_paths=["file1.py"],
        instruction="Do something",
        acceptance="Acceptance",
        tool_preference="AST-edit",
        evidence=[]
    )
    task2 = ApprovedTask(
        id="intern02",
        title="Task 2",
        file_paths=["file1.py"],
        instruction="Do something else",
        acceptance="Acceptance",
        tool_preference="CLI-wrapper",
        evidence=[]
    )
    group1 = WorkGroup(
        id="group_1",
        tasks=[task1],
        depends_on=[]
    )
    group2 = WorkGroup(
        id="group_2",
        tasks=[task2],
        depends_on=["group_1"]
    )
    plan = ExecutablePlan(
        epic=epic,
        user_stories=[],
        definition_of_done=[],
        acceptance_criteria=[],
        rubric_cube=RubricCube(cells=[]),
        summary="Summary",
        tasks=[task1, task2],
        alignment="Alignment",
        workplan=ParallelisableWorkplan(groups=[group1, group2]),
        rejected_subtasks=[],
        strategy=Strategy(how_to_fix="How to fix", tool_preference=[], parallelisable_workplan=ParallelisableWorkplan(groups=[group1, group2])),
        approved=True
    )
    violations = check_plan_invariants(plan)
    assert len(violations) == 1
    assert "file collision: file1.py" in violations[0]
