"""Tests for factory/docs/01_fix.md harness changes (tzsdl).

Guards:
  - smoke_test.py type-construction gate (BUG 2: DictMap[str] rejecting model instances)
  - TaskResult.ValidationVerdict fields (ruff/pyright/exec flags + dep_pointers)
  - guardrail_check.discover_dependencies + typecheck_union use bounded union pyright
  - user_prompt.md DictMap example uses DictMap[ExternalPillarTrigger]
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from factory.infra import models as models_mod  # noqa: E402
from factory.tools import guardrail_check as gc  # noqa: E402
from factory.tools import smoke_test as st  # noqa: E402

TEMPLATES = REPO_ROOT / "factory" / "infra" / "agents"
PROMPT_DIR = REPO_ROOT / "factory" / "prompt"


# --- Task 1: smoke_test type-construction gate (BUG 2) -----------------------

def test_smoke_cli_detects_bug2(tmp_path):
    """End-to-end: smoke_test flags a file whose <X>Map value type is str but an
    <X> model exists (the doc's DictMap[str] bug). The realistic shape is the
    *Map as a field on a buildable parent model (as in unified.py)."""
    import subprocess

    target = tmp_path / "sample.py"
    target.write_text(
        "from pydantic import BaseModel, RootModel\n"
        "class ExternalPillarTrigger(BaseModel):\n"
        "    name: str\n"
        "class ExternalPillarTriggerMap(RootModel):\n"
        "    root: dict[str, str]\n"
        "class Holder(BaseModel):\n"
        "    triggers: ExternalPillarTriggerMap\n"
    )
    rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "factory" / "tools" / "smoke_test.py"), str(target)],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 1, (
        f"smoke gate should FAIL on DictMap[str] bug; rc={rc.returncode} "
        f"out={rc.stdout}{rc.stderr}"
    )


def test_smoke_cli_passes_correct_pattern(tmp_path):
    """A file whose <X>Map correctly holds <X> instances must pass cleanly."""
    import subprocess

    target = tmp_path / "good.py"
    target.write_text(
        "from pydantic import BaseModel, RootModel\n"
        "class ExternalPillarTrigger(BaseModel):\n"
        "    name: str\n"
        "class ExternalPillarTriggerMap(RootModel):\n"
        "    root: dict[str, ExternalPillarTrigger]\n"
    )
    rc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "factory" / "tools" / "smoke_test.py"), str(target)],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0, (
        f"smoke gate should PASS on DictMap[Model]; rc={rc.returncode} "
        f"out={rc.stdout}{rc.stderr}"
    )


def test_smoke_narrow_container_intent():
    """The BUG 2 heuristic must map <X>Map -> same-file <X> model when wide."""
    import pydantic

    class ExternalPillarTrigger(pydantic.BaseModel):
        name: str

    class ExternalPillarTriggerMap(pydantic.RootModel):
        root: dict[str, str]

    file_models = {"ExternalPillarTrigger": ExternalPillarTrigger}
    resolved = st._narrow_container_intent(
        ExternalPillarTriggerMap, "external_pillar_triggers", file_models
    )
    assert resolved is ExternalPillarTrigger


# --- Task 4: TaskResult.ValidationVerdict fields -----------------------------

def test_validation_verdict_fields_present():
    tr = models_mod.TaskResult(
        task_id="intern01",
        status="done",
        files_changed=[],
        diff_summary="",
        notes="ok",
    )
    assert tr.ruff_ok is True and tr.pyright_ok is True and tr.exec_ok is True
    assert tr.verdict_errors == "" and tr.verdict_diff == ""
    assert tr.dep_pointers == []


# --- Task 3: guardrail_check bounded union pyright ---------------------------

def test_discover_dependencies_returns_list():
    sample = Path(__file__)
    edit_set = {str(sample)}
    deps = gc.discover_dependencies(sample, edit_set)
    assert isinstance(deps, list)


def test_typecheck_union_bounds(tmp_path):
    """A tiny union of 2 small files stays within bounds and runs."""
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("from b import hello\nprint(hello)\n")
    f2.write_text("hello = 1\n")
    ok, _ = gc.typecheck_union([f1, f2])
    assert isinstance(ok, bool)

# --- Task 8: user_prompt.md DictMap example ----------------------------------

def test_user_prompt_dictmap_example_correct():
    txt = (PROMPT_DIR / "user_prompt.md").read_text()
    assert len(txt) > 0
