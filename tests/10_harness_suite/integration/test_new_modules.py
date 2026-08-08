"""Tests for the new orchestrator modules (ledger/shadow_tools/factory/gatekeeper/
time_machine/bazi_policy/bazirag_client/subagent_discipline/orchestrator).

Offline by design: no network, no LLM keys. The gatekeeper/rollback tests either
route through real local tooling (ruff/git) in throwaway dirs or assert behaviour
without touching the real repo.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra import (
    gatekeeper,
    models,
    shadow_tools,
    time_machine,
)


def test_agent_dependencies():
    """AgentDependencies + YieldSignal instantiate with frozen defaults."""
    deps = models.AgentDependencies()
    assert deps.tool_budget == 15
    assert deps.tools_used == 0
    assert deps.modified_files == set()
    assert deps.global_decisions == []

    # YieldSignal.reason has no default in the frozen model; pass an explicit
    # (empty) reason and assert the only defaulted field (`yielded`).
    sig = models.YieldSignal(reason="")
    assert sig.yielded is True
    assert sig.reason == ""


def test_enforce_budget():
    """enforce_budget yields None under budget, FATAL sentinel when over."""

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    # Under budget: tool_budget=15, tools_used starts at 0 -> 1, no trip.
    ok_deps = models.AgentDependencies()
    ok_ctx = Ctx(ok_deps)
    assert shadow_tools.enforce_budget(ok_ctx) is None
    assert ok_deps.tools_used == 1

    # Over budget: seed tools_used == budget so the +1 increment trips `>`.
    over_deps = models.AgentDependencies()
    over_deps.tools_used = over_deps.tool_budget
    over_ctx = Ctx(over_deps)
    result = shadow_tools.enforce_budget(over_ctx)
    assert result == "FATAL: Tool budget exhausted. You MUST output your final result now."


def test_run_gate_fails_on_bad_file(tmp_path):
    """run_gate returns (False, ...) for a file with a non-autofixable ruff error."""
    bad = tmp_path / "bad_scratch_module_xyz.py"
    # F821 undefined name: ruff can report but NOT autofix -> gate fails.
    bad.write_text("def broken():\n    return some_undefined_symbol_xyz\n")

    passed, report = gatekeeper.run_gate([str(bad)])
    assert passed is False
    assert "GATE: FAILED" in report


def test_rollback_removes_new_file(tmp_path, monkeypatch):
    """rollback_node removes a NEW untracked file via `git clean -fd`."""
    scratch = tmp_path / "scratch_repo"
    scratch.mkdir()
    subprocess.run(["git", "init", "-q", str(scratch)], check=True)

    # Isolate the module's REPO_ROOT so no real-repo git state is touched.
    monkeypatch.setattr(time_machine, "REPO_ROOT", scratch)

    new_file = scratch / "new_scratch_file.py"
    new_file.write_text("x = 1\n")

    time_machine.rollback_node([new_file.name])

    assert not new_file.exists()
