"""Shared fixtures for the orchestrator GOLD test suite (BIFR adoption).

Bootstraps the import path and gives every gold test a hermetic runtime dir so
Boundary/Freeze artifacts (io_*.log, fail_*.json, freeze_*.json) never touch the
real repo. See infra/testing_framework.md §GOLD TEST SUITE.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

_real_subprocess_run = subprocess.run

def _stub_bd_run(args, **kwargs):
    is_bd = False
    if args:
        if isinstance(args, list):
            first = str(args[0])
            if first == "./bd" or first.endswith("/bd") or "bd" in first:
                if "pytest" not in first and "python" not in first and "ruff" not in first and "pyright" not in first:
                    is_bd = True
            elif len(args) > 2 and args[0] == "uv" and args[1] == "run":
                for arg in args[2:]:
                    s = str(arg)
                    if s == "./bd" or s.endswith("/bd") or "/bd" in s:
                        is_bd = True
                        break
        elif isinstance(args, str):
            if args.startswith("./bd") or " bd " in args or "/bd " in args:
                is_bd = True
    if is_bd:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr=""
        )
    return _real_subprocess_run(args, **kwargs)

subprocess.run = _stub_bd_run

from factory.infra import _loopguard as loopguard_mod  # noqa: E402
from factory.infra import control as ctrl  # noqa: E402
from factory.infra import runner as runner_mod  # noqa: E402
from factory.infra import tools as tools_mod  # noqa: E402


@pytest.fixture
def orch_runtime(tmp_path, monkeypatch):
    """Redirect the harness runtime root to a temp dir (hermetic gold tests)."""
    rt = tmp_path / "orch"
    monkeypatch.setattr(ctrl, "ORCH_ROOT", rt)
    if hasattr(runner_mod, "ORCH_ROOT"):
        monkeypatch.setattr(runner_mod, "ORCH_ROOT", rt)
    monkeypatch.setattr(loopguard_mod, "ORCH_ROOT", rt)
    if hasattr(tools_mod, "ORCH_ROOT"):
        monkeypatch.setattr(tools_mod, "ORCH_ROOT", rt)
    (rt / "logs" / "runtime").mkdir(parents=True, exist_ok=True)
    return rt


@pytest.fixture
def freeze_dir(tmp_path) -> Path:
    d = tmp_path / "freeze"
    d.mkdir(parents=True, exist_ok=True)
    return d
