"""Regression tests for docs/01_fix.md Fix B — make the three SILENT blocked
paths loud.

Before this fix, three paths returned ``TaskResult(status="blocked")`` with no
``log_operator`` call, forcing a log dive to triage (hbh1 HALT). Fix B adds a
``log_operator(level="WARNING")`` at each path:

  1. initial intern timeout (``asyncio.wait_for`` around the first intern call)
  2. re-spawn (validation-loop) intern timeout
  3. validation-exhaustion: the harness-owned ``RuntimeError("[HALT] task <id>
     failed validation after N intern passes ...")`` is caught by the SPAWN-ALL
     gather and stored as a plain blocked result with a generic note — now it is
     surfaced loudly next to the HALT.

These tests monkeypatch ``log_operator`` and the relevant ``subprocess`` /
``asyncio.wait_for`` seams so they run without a real intern or pyright.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra import runner
from factory.infra.models import (
    ApprovedTask,
    Epic,
    ExecutablePlan,
    ParallelisableWorkplan,
    RubricCube,
    Strategy,
    ToolPreferenceItem,
    WorkGroup,
)


def _make_plan() -> ExecutablePlan:
    task = ApprovedTask(
        id="intern01",
        title="t",
        file_paths=["src2/x.py"],
        instruction="i",
        acceptance="a",
        tool_preference="AST-edit",
    )
    group = WorkGroup(id="g1", tasks=[task], depends_on=[])
    wp = ParallelisableWorkplan(groups=[group])
    return ExecutablePlan(
        epic=Epic(title="e", deliverables=["d"], must_be_pydantic=True),
        definition_of_done=["d"],
        acceptance_criteria=["a"],
        rubric_cube=RubricCube(cells=[]),
        summary="s",
        tasks=[task],
        alignment="a",
        workplan=wp,
        strategy=Strategy(
            how_to_fix="f",
            tool_preference=[ToolPreferenceItem(task_id="intern01", preference="AST-edit")],
            parallelisable_workplan=wp,
        ),
        approved=True,
    )


class _FakeCompleted:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _guardrail_fail_run(*args, **kwargs):
    """subprocess.run replacement: guardrail validate always FAILS (pyright);
    other subprocess calls (./bd CQRS) succeed silently."""
    argv = args[0] if args else []
    if len(argv) > 1 and "guardrail_check.py" in str(argv[1]):
        payload = {
            "success": False,
            "ruff_ok": True,
            "pyright_ok": False,
            "smoke_ok": True,
            "pyright_output": "x.py:1:1 - error: simulated pyright failure",
        }
        return _FakeCompleted(json.dumps(payload), returncode=1)
    return _FakeCompleted("", returncode=0)


def _intern_json(task_id: str = "intern01") -> str:
    return json.dumps(
        {
            "status": "done",
            "task_id": task_id,
            "files_changed": ["src2/x.py"],
            "diff_summary": "x",
            "notes": "y",
        }
    )


async def _intern_fn(brief, task_id=None):
    return _intern_json(task_id or "intern01")


async def test_fix_b_initial_timeout_is_loud(monkeypatch):
    logs: list[tuple[str, str]] = []

    def _log(msg, level="WARNING"):
        logs.append((level, msg))

    monkeypatch.setattr("factory.infra.execution.log_operator", _log)

    calls = {"n": 0}

    async def _fake_wait_for(coro, timeout=None):
        calls["n"] += 1
        try:
            res = await coro
        except Exception:
            res = None
        if calls["n"] == 1:
            raise TimeoutError()
        return res

    monkeypatch.setattr("asyncio.wait_for", _fake_wait_for)

    plan = _make_plan()
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        await runner.run_execute_phase(
            plan,
            Path(runner.RUNTIME_DIR),
            asyncio.Semaphore(1),
            _intern_fn,
            exchange=[],
            pass_counter={},
            bd="test",
            history=[],
        )
    assert any("intern01" in msg and "timed out" in msg for _, msg in logs)
    assert any(level == "WARNING" for level, _ in logs)


async def test_fix_b_respawn_timeout_is_loud(monkeypatch):
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr("factory.infra.execution.log_operator", lambda m, level="WARNING": logs.append((level, m)))
    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _guardrail_fail_run)

    calls = {"n": 0}

    async def _fake_wait_for(coro, timeout=None):
        calls["n"] += 1
        try:
            res = await coro
        except Exception:
            res = None
        if calls["n"] >= 2:
            raise TimeoutError()
        return res

    monkeypatch.setattr("asyncio.wait_for", _fake_wait_for)

    plan = _make_plan()
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        await runner.run_execute_phase(
            plan,
            Path(runner.RUNTIME_DIR),
            asyncio.Semaphore(1),
            _intern_fn,
            exchange=[],
            pass_counter={},
            bd="test",
            history=[],
        )
    assert any("intern01" in msg and "re-spawn timed out" in msg for _, msg in logs)


async def test_fix_b_validation_exhaustion_is_loud(monkeypatch):
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr("factory.infra.execution.log_operator", lambda m, level="WARNING": logs.append((level, m)))
    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _guardrail_fail_run)

    # Never time out — let validation exhaust and raise RuntimeError.
    monkeypatch.setattr("asyncio.wait_for", lambda coro, timeout=None: coro)

    plan = _make_plan()
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        await runner.run_execute_phase(
            plan,
            Path(runner.RUNTIME_DIR),
            asyncio.Semaphore(1),
            _intern_fn,
            exchange=[],
            pass_counter={},
            bd="test",
            history=[],
        )
    # The harness-owned validation RuntimeError message must be surfaced loudly.
    assert any(
        "failed validation after" in msg and "intern01" in msg for _, msg in logs
    )
