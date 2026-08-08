"""Tests for the harness payload diet (ticket nz4ai).

Offline by design: no network, no LLM. Asserts that:
- ``pydantic_ai_default_block`` is LEAN — it returns ONLY the
  structured-output convention, never the pydantic-ai *coding* skill
  (agents are pydantic-ai AGENTS, they don't need the coding skill).
- ``_build_repo_map`` strips the JSON envelope and bounds the tree so the
  injected map stays small even for the unscoped (broadcast) roles that used to
  receive a 62KB depth-3 tree.
- The lean block + map keep a non-intern system prompt well under the 30KB
  acceptance ceiling.
"""
from __future__ import annotations

from factory.infra import tools as tools_mod
from factory.infra.control import PYDANTIC_AI_INSTRUCTIONS


def test_default_block_is_lean():
    """Default block must return ONLY the structured-output convention."""
    block = tools_mod.pydantic_ai_default_block()
    assert block == PYDANTIC_AI_INSTRUCTIONS
    # The agents are pydantic-ai AGENTS — the pydantic-ai *coding* skill
    # must never be injected (removed dead machinery).
    assert "SKILL" not in block or "PYDANTIC-AI FRAMEWORK SKILL" not in block


def test_build_repo_map_strips_envelope():
    """The map must inject the bare tree text, not the JSON envelope."""
    import json

    # Monkeypatch the underlying tool so the test is hermetic + deterministic.
    envelope = json.dumps(
        {
            "success": True,
            "message": "ok",
            "data": {"structure": "repo/\n├── src2/\n│   └── engine/"},
        }
    )
    saved = tools_mod._run_tool
    import factory.infra.tools_skill
    saved2 = factory.infra.tools_skill._run_tool

    def fake(name, args):
        if name == "get_repo_structure":
            return envelope
        return "[]"

    tools_mod._run_tool = fake
    factory.infra.tools_skill._run_tool = fake
    try:
        mp = tools_mod._build_repo_map()
    finally:
        tools_mod._run_tool = saved
        factory.infra.tools_skill._run_tool = saved2
    assert '"data"' not in mp
    assert '"success"' not in mp
    assert "repo/" in mp
    assert "## Tree" in mp


def test_unscoped_repo_map_is_small():
    """Broadcast (unscoped) roles must get a cheap, bounded orientation map."""
    mp = tools_mod._build_repo_map()
    # Was ~62KB of JSON envelope + depth-3 tree; must now be a fraction of that.
    assert len(mp.encode()) < 20_000


def test_scoped_repo_map_is_capped():
    """A scoped (intern) map must be length-capped to avoid payload blow-up."""
    mp = tools_mod._build_repo_map(scope_paths=["src2/engine/unified.py"])
    assert len(mp.encode()) < 20_000


def test_non_intern_system_prompt_under_ceiling():
    """Approximate non-intern system prompt must stay under the 30KB ceiling."""
    block = tools_mod.pydantic_ai_default_block()
    rm = tools_mod._build_repo_map()
    total = (
        len(block.encode())
        + len(tools_mod.CODING_PHILOSOPHY_BLOCK.encode())
        + len(PYDANTIC_AI_INSTRUCTIONS.encode())
        + len(rm.encode())
    )
    assert total < 30_000
