import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import re

import pytest
from pydantic import ValidationError
from pydantic_ai.usage import UsageLimits

from factory.infra import _loopguard as lg
from factory.infra import models, runner, tools


# ── SA1 Security (ACL) ───────────────────────────────────────────────────────
def test_acl_normpath_escape_blocked():
    assert tools._acl_allows("src2/../.env", ["src2/"]) is False


def test_acl_empty_value_rejected():
    assert tools._acl_allows("", ["src2/"]) is False


def test_acl_confined_prefix_allowed():
    assert tools._acl_allows("src2/x.py", ["src2/"]) is True


def test_acl_empty_allowed_path_denies_everything():
    # F3 fix: an empty/whitespace ACL must DENY everything (never silently grant
    # blanket confinement). It returns False, it does NOT raise (which would have
    # been a config-error that disabled the ACL entirely).
    assert tools._acl_allows("x", [""]) is False


def test_acl_wrap_with_acl_stub():
    def stub(relative_path):
        return relative_path

    wrapped = tools.wrap_with_acl(stub, ["src2/"])
    # audit R5: denials are returned as a graceful error string (never an
    # unhandled exception) and logged, not raised.
    denied = wrapped("src2/../.env")
    assert isinstance(denied, str) and denied.startswith("ACL DENIED")
    assert wrapped("src2/ok.py") == "src2/ok.py"


def test_is_secret_path():
    assert tools._is_secret_path(".env") is True
    assert tools._is_secret_path("admin/controls/controls.py") is True
    assert tools._is_secret_path("src2/foo.py") is False


# ── SA2 Stability ─────────────────────────────────────────────────────────────
def test_loopguard_constants_positive():
    assert lg.AGENT_RUN_TIMEOUT > 0
    assert lg.MAX_LOOPGUARD_TURNS > 0


# ── SA3 Correctness (empty plans + green re-derive + ops real push) ──────────
def _epic():
    return models.Epic(title="t", deliverables=["d"], must_be_pydantic=True)


def _user_story():
    return models.UserStory(id="u1", story="s", acceptance_criteria=["a"], definition_of_done=["d"])


def _rubric_cube():
    return models.RubricCube(cells=[])


def _subtask():
    return models.SubTaskBrief(
        id="s1", title="t", file_paths=["src2/x.py"],
        instruction="i", acceptance="a", tool_preference="AST-edit",
        evidence=[{"file_path": "src2/x.py", "content": "verified"}],
    )


def _approved_task():
    return models.ApprovedTask(
        id="intern01", title="t", file_paths=["src2/x.py"],
        instruction="i", acceptance="a", tool_preference="AST-edit",
    )


def _workgroup():
    return models.WorkGroup(id="g1", tasks=[_approved_task()])


def _workplan():
    return models.ParallelisableWorkplan(groups=[_workgroup()])


def _strategy():
    return models.Strategy(how_to_fix="f", tool_preference=[{"task_id": "s1", "preference": "AST-edit"}], parallelisable_workplan=_workplan())


def _task_result():
    return models.TaskResult(task_id="t1", status="done", files_changed=[], diff_summary="", notes="")


def _valid_draft():
    return models.DraftPlan(
        epic=_epic(), user_stories=[_user_story()], definition_of_done=["d"],
        acceptance_criteria=["a"], rubric_cube=_rubric_cube(), summary="s",
        subtasks=[_subtask()], risks=[], strategy=_strategy(),
    )


def _empty_draft():
    return models.DraftPlan(
        epic=_epic(), user_stories=[_user_story()], definition_of_done=["d"],
        acceptance_criteria=["a"], rubric_cube=_rubric_cube(), summary="s",
        subtasks=[], risks=[], strategy=_strategy(),
    )


def _valid_approved():
    return models.ApprovedPlan(
        evaluations=[models.EvaluationItem(item_id="intern01", approved="Yes", comments="ok")]
    )


def _empty_approved():
    return models.ApprovedPlan(
        evaluations=[]
    )


@pytest.mark.parametrize(
    "valid_fn,empty_fn",
    [
        (_valid_draft, _empty_draft),
        (_valid_approved, _empty_approved),
        (lambda: models.ParallelisableWorkplan(groups=[_workgroup()]), lambda: models.ParallelisableWorkplan(groups=[])),
        (lambda: models.WorkGroup(id="g1", tasks=[_approved_task()]), lambda: models.WorkGroup(id="g1", tasks=[])),
        (lambda: models.TaskBatch(results=[_task_result()]), lambda: models.TaskBatch(results=[])),
    ],
)
def test_models_require_non_empty_list(valid_fn, empty_fn):
    assert valid_fn() is not None
    with pytest.raises(ValidationError):
        empty_fn()


def test_security_checks_passed_truth_table():
    assert runner.security_checks_passed([], [{"severity": "blocker", "passed": False}]) is False
    assert runner.security_checks_passed([{"severity": "blocker", "task_id": "t1"}], []) is False
    assert runner.security_checks_passed([{"severity": "warn"}], [{"severity": "blocker", "passed": True}]) is True
    assert runner.security_checks_passed([], []) is False  # empty audit = no data = fail




# ── SA4 Observability ────────────────────────────────────────────────────────
class BoomDir:
    def __truediv__(self, other):
        return self

    def mkdir(self, *a, **k):
        pass

    def write_text(self, *a, **k):
        raise OSError("disk full")


def test_dump_failure_is_loud(capsys):
    lg._dump_failure(BoomDir(), "ph", "ro", [], UsageLimits(request_limit=40), ValueError("boom"))
    captured = capsys.readouterr().err
    assert "FAILED to persist failure dump" in captured


@pytest.fixture
def orch_runtime(tmp_path, monkeypatch):
    rt = tmp_path
    monkeypatch.setattr(tools, "ORCH_ROOT", rt)
    (rt / "logs" / "runtime").mkdir(parents=True, exist_ok=True)
    return rt


def test_dump_failure_golden_path(orch_runtime):
    runtime = orch_runtime / "logs" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    lg._dump_failure(runtime, "ph", "ro", [], UsageLimits(request_limit=40), ValueError("x"))
    assert (runtime / "fail_ph_ro.json").exists()


def test_transcript_logging(orch_runtime, monkeypatch):
    import factory.infra.tools_guard
    monkeypatch.setattr(factory.infra.tools_guard, "ORCH_ROOT", orch_runtime)
    tools.log_prompt_sent("ph", "ro", "myid", "MY_INSTRUCTIONS")
    tools.log_run_prompt("ph", "ro", "myid", "MY_PROMPT")
    runtime_dir = orch_runtime / "logs" / "runtime"
    sent_files = sorted(runtime_dir.glob("prompt_sent_myid_*.txt"))
    run_files = sorted(runtime_dir.glob("prompt_run_myid_*.txt"))
    assert sent_files, "log_prompt_sent did not write expected file"
    assert run_files, "log_run_prompt did not write expected file"
    assert "MY_INSTRUCTIONS" in sent_files[0].read_text()
    assert "MY_PROMPT" in run_files[0].read_text()
    # NOTE: log_response_raw requires a real Agent run result (res.all_messages())
    # and is therefore not exercised deterministically here without an LLM run;
    # its file-writing path mirrors log_prompt_sent/log_run_prompt which are covered.


# ── SA5 v2 Compliance (static, no LLM) ───────────────────────────────────────
def test_no_v1_pydantic_antipatterns():
    infra_dir = Path(__file__).resolve().parents[1] / "infra"
    banned = [r"\.dict\(", r"\.parse_obj\(", r"result_type=", r"class Config"]
    for py in sorted(infra_dir.glob("*.py")):
        text = py.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.search(pat, text), f"{py.name} matches banned pattern {pat!r}"
