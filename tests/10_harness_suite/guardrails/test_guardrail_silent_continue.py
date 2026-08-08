"""Tests: guardrail crash/parse-fail is NOT silently treated as pass.

Guards against regression of the `continue`-swallow pattern in
execution.py's guardrail validation loop — when guardrail_check.py
crashes or produces unparseable output, the task must be blocked
(fail-loudly discipline), not silently passed.
"""
import sys
import json
import asyncio
import subprocess as real_subprocess
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra.execution import run_execute_phase
from tests.test_gates import _plan


def _setup_staging(tmp_path):
    """Create dummy live + staged files as test_harness_gates does."""
    live = tmp_path / "src2" / "a.py"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text("x = 1")

    staged = tmp_path / "admin" / "orchestrator" / "temp" / "src2" / "a.py"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("x = 2")
    return live, staged


async def _intern_done(brief: str, task_id: str | None = None) -> str:
    from factory.infra.context import stage_path
    try:
        sp = Path(stage_path("src2/a.py"))
        if sp.exists():
            sp.write_text("x = 3")
    except Exception:
        pass

    return json.dumps({
        "status": "done",
        "task_id": "intern01",
        "files_changed": ["src2/a.py"],
        "diff_summary": "changed",
        "notes": "Done",
    })


def test_guardrail_crash_blocks_task(tmp_path, monkeypatch):
    """guardrail_check.py crash sets ruff_failed and blocks the task."""
    _setup_staging(tmp_path)
    monkeypatch.setattr("factory.infra.control.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.context.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.execution.REPO_ROOT", tmp_path)

    orig_run = real_subprocess.run

    def _mock_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        kwargs.get("args") or (list(args[0]) if args else [])
        real_subprocess.check_output if hasattr(real_subprocess, 'check_output') else []
        if isinstance(cmd, list) and any("guardrail_check.py" in str(a) for a in cmd):
            raise RuntimeError("mock guardrail crash")
        return orig_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", _mock_run)

    plan = _plan()
    plan.workplan.groups[0].tasks[0].file_paths = ["src2/a.py"]
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        asyncio.run(run_execute_phase(
            plan, tmp_path / "run", asyncio.Semaphore(20), _intern_done
        ))


def test_guardrail_unparseable_output_blocks_task(tmp_path, monkeypatch):
    """Unparseable guardrail output (not JSON) sets ruff_failed and blocks."""
    _setup_staging(tmp_path)
    monkeypatch.setattr("factory.infra.control.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.context.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.execution.REPO_ROOT", tmp_path)

    orig_run = real_subprocess.run

    def _mock_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and any("guardrail_check.py" in str(a) for a in cmd):
            class FakeResult:
                stdout = "not valid json at all just warnings\nand more text"
                stderr = ""
                returncode = 0
            return FakeResult()
        return orig_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", _mock_run)

    plan = _plan()
    plan.workplan.groups[0].tasks[0].file_paths = ["src2/a.py"]
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        asyncio.run(run_execute_phase(
            plan, tmp_path / "run", asyncio.Semaphore(20), _intern_done
        ))


def test_runtime_load_gate_crash_logged(tmp_path, monkeypatch):
    """load_schema_gate.py crash is logged, not silently swallowed."""
    _setup_staging(tmp_path)
    monkeypatch.setattr("factory.infra.control.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.context.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.execution.REPO_ROOT", tmp_path)

    orig_run = real_subprocess.run
    calls = []

    def _mock_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and any("load_schema_gate.py" in str(a) for a in cmd):
            calls.append(("schema_gate", cmd))
            raise RuntimeError("mock schema gate crash")
        return orig_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", _mock_run)

    plan = _plan()
    plan.workplan.groups[0].tasks[0].file_paths = ["src2/a.py"]
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        asyncio.run(run_execute_phase(
            plan, tmp_path / "run", asyncio.Semaphore(20), _intern_done
        ))
    assert len(calls) >= 1, "load_schema_gate.py should have been called"
