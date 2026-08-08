"""Tests for the new staging gates in runner.py (Pre-Review Staging Diff Gate, Pre-Review Runtime Load Gate, and Budget/Loopguard overrides).
"""
import sys
import json
import asyncio
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra.execution import run_execute_phase
from tests.test_gates import _plan


def test_staging_diff_gate_zero_diff(tmp_path, monkeypatch):
    """Verify that a task with zero-diff staged files is marked blocked."""
    # Create a dummy live file
    live_file = tmp_path / "src2" / "a.py"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_text("print('hello')")
    
    # Staged copy is identical -> zero diff
    staged_file = tmp_path / "admin" / "orchestrator" / "temp" / "src2" / "a.py"
    staged_file.parent.mkdir(parents=True, exist_ok=True)
    staged_file.write_text("print('hello')")
    
    # Patch REPO_ROOT in source modules
    monkeypatch.setattr("factory.infra.control.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.context.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.execution.REPO_ROOT", tmp_path)
    
    # Mock intern returning 'done' but identical files
    async def intern_fn(brief: str, task_id: str | None = None) -> str:
        return json.dumps({
            "status": "done",
            "task_id": "intern01",
            "files_changed": ["src2/a.py"],
            "diff_summary": "No changes",
            "notes": "Done"
        })
        
    # Prepare plan targeting src2/a.py
    plan = _plan()
    plan.workplan.groups[0].tasks[0].file_paths = ["src2/a.py"]
    
    # The execution phase should fail with RuntimeError because of the blocked status
    # The gate no longer raises (it recovers). The staging/load
    # gating is an EXECUTE-phase concern, so assert it directly at
    # run_execute_phase (strict=True still hard-halts direct callers).
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        asyncio.run(run_execute_phase(plan, tmp_path / "run", asyncio.Semaphore(20), intern_fn))


def test_runtime_load_gate_fails(tmp_path, monkeypatch):
    """Verify that a staged file with a syntax error fails schema validation and blocks."""
    live_file = tmp_path / "src2" / "a.py"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_text("class Foo: pass")
    
    # Staged copy has invalid syntax
    staged_file = tmp_path / "admin" / "orchestrator" / "temp" / "src2" / "a.py"
    staged_file.parent.mkdir(parents=True, exist_ok=True)
    staged_file.write_text("class Foo Pydantic syntax error!")
    
    monkeypatch.setattr("factory.infra.control.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.context.REPO_ROOT", tmp_path)
    monkeypatch.setattr("factory.infra.execution.REPO_ROOT", tmp_path)
    
    async def intern_fn(brief: str, task_id: str | None = None) -> str:
        return json.dumps({
            "status": "done",
            "task_id": "intern01",
            "files_changed": ["src2/a.py"],
            "diff_summary": "broken",
            "notes": "Done"
        })
        
    plan = _plan()
    plan.workplan.groups[0].tasks[0].file_paths = ["src2/a.py"]
    
    # The gate no longer raises (it recovers). The staging/load
    # gating is an EXECUTE-phase concern, so assert it directly at
    # run_execute_phase (strict=True still hard-halts direct callers).
    with pytest.raises(RuntimeError, match="EXECUTE phase incomplete"):
        asyncio.run(run_execute_phase(plan, tmp_path / "run", asyncio.Semaphore(20), intern_fn))
