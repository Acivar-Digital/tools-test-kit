"""Tests for the MD-twin per-turn re-injection bridge (ticket mb1k5).

Offline by design: no network, no LLM keys. We build a hermetic artefacts tree
(via the ``ORCHESTRATOR_ARTEFACTS_DIR`` env override) containing `.md` twins and
assert ``build_md_bridge`` resolves the EXACT twin (no mtime-glob), returns None
on cold spawn, and honours per-internN isolation.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from factory.common.md_bridge import build_md_bridge


def _write_md(art_dir: Path, role_folder: str, stem: str, text: str) -> None:
    folder = art_dir / "history" / role_folder
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.md").write_text(text, encoding="utf-8")


def test_cold_spawn_returns_none(tmp_path, monkeypatch):
    """No twin yet -> bridge returns None (no HALT, fresh agent)."""
    art = tmp_path / "artefacts"
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(art))
    assert build_md_bridge("engineer") is None
    assert build_md_bridge("intern", agent_id="intern3") is None


def test_role_md_bridge_injects_exact_twin(tmp_path, monkeypatch):
    """A non-intern role's `.md` twin is wrapped as a single ModelRequest."""
    art = tmp_path / "artefacts"
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(art))
    _write_md(art, "engineer", "engineer", "# Engineer journal\n- did X\n- did Y")

    bridge = build_md_bridge("engineer")
    assert bridge is not None
    assert len(bridge) == 1
    assert isinstance(bridge[0], ModelRequest)
    part = bridge[0].parts[0]
    assert isinstance(part, UserPromptPart)
    assert "Engineer journal" in part.content
    # The MD_LEDGER sentinel marks the journal injection channel.
    assert "<!-- MD_LEDGER -->" in part.content


def test_intern_agent_isolation(tmp_path, monkeypatch):
    """intern + agent_id resolves the isolated internN.md; no sibling leakage."""
    art = tmp_path / "artefacts"
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(art))
    _write_md(art, "intern", "intern3", "intern3 private work")
    # A DIFFERENT intern's twin must NOT be picked up for agent_id intern3.
    _write_md(art, "intern", "intern7", "intern7 private work - MUST NOT LEAK")

    bridge = build_md_bridge("intern", agent_id="intern3")
    assert bridge is not None
    content = bridge[0].parts[0].content
    assert "intern3 private work" in content
    assert "intern7" not in content


def test_unknown_role_returns_none(tmp_path, monkeypatch):
    """ops is excluded from ROLE_FOLDER -> no twin, returns None."""
    art = tmp_path / "artefacts"
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(art))
    assert build_md_bridge("ops") is None


def test_import_error_loudly_raised(tmp_path, monkeypatch):
    """A broken artefacts module (missing symbols) MUST propagate, not be swallowed.

    ``_read_exact_md`` catches ``ModuleNotFoundError`` (module genuinely absent)
    and returns None. But an ``ImportError`` from a module that *exists* but has
    missing symbols must propagate loudly — violating fail-loudly is not allowed.
    """
    mock_artefacts = types.ModuleType("factory.infra.artefacts")
    mock_artefacts.__package__ = "factory.infra"
    mock_artefacts.__path__ = []
    monkeypatch.setitem(sys.modules, "factory.infra.artefacts", mock_artefacts)

    with pytest.raises(ImportError):
        build_md_bridge("engineer")
