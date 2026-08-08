"""Tests for context compaction budget gating and orchestrator state fields.

Covers factory-wo56 Phase 1 hardening: the ratio-based compaction trigger in
``compact_context_if_needed``, the ``consolidation_offset`` field on ``OrchestratorState``,
and the ``revert_state`` checkpoint reader that mirrors ``_persist_checkpoint``.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from factory.infra.control import COMPACTION_CONFIG
from factory.infra.context import calculate_tokens, compact_context_if_needed
from factory.infra.models import OrchestratorState
from factory.infra.pipeline import revert_state


def _budget_tokens() -> int:
    """Mirror the budget computation used inside ``compact_context_if_needed``."""
    raw = int(COMPACTION_CONFIG.CONTEXT_COMPACT_CEILING * COMPACTION_CONFIG.compact_at_fraction)
    return min(raw, COMPACTION_CONFIG.hard_max_tokens)


def test_compaction_offset_defaults_to_zero():
    state = OrchestratorState(bd_id="run-1", run_dir="/tmp/run-1")
    assert state.consolidation_offset == 0


async def test_compact_below_budget_returns_unchanged():
    text = "short prompt, well below the compaction budget"
    assert calculate_tokens(text) <= _budget_tokens()
    result = await compact_context_if_needed(text)
    assert result == text


async def test_compact_above_budget_triggers_compaction():
    # The gate must derive its budget from COMPACTION_CONFIG's ratio + hard-max,
    # then compact once the prompt exceeds that config-driven budget.
    raw_budget = int(COMPACTION_CONFIG.CONTEXT_COMPACT_CEILING * COMPACTION_CONFIG.compact_at_fraction)
    expected_budget = min(raw_budget, COMPACTION_CONFIG.hard_max_tokens)
    assert _budget_tokens() == expected_budget
    assert COMPACTION_CONFIG.compact_at_fraction > 0.0
    assert COMPACTION_CONFIG.hard_max_tokens > 0

    # len(text)//4 must strictly exceed the budget -> "x" * ((budget + 1) * 4).
    text = "x" * ((expected_budget + 1) * 4)
    assert calculate_tokens(text) > expected_budget

    mock_summary = MagicMock()
    mock_summary.output = "COMPACTED EXECUTION SUMMARY"
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_summary)
    with patch("pydantic_ai.Agent", return_value=mock_agent):
        result = await compact_context_if_needed(text)

    assert result.startswith("[COMPACTED CONTEXT SUMMARY]")
    assert "COMPACTED EXECUTION SUMMARY" in result


def test_revert_state_restores_checkpoint(tmp_path):
    chkpt = tmp_path / "checkpoint_state.json"
    payload = {
        "locked_functions": ["foo", "bar"],
        "staged_path": "src2/foo.py",
        "function_name": "foo",
    }
    chkpt.write_text(json.dumps(payload), encoding="utf-8")
    result = revert_state(chkpt)
    assert result == payload


def test_revert_state_returns_empty_when_missing(tmp_path):
    assert revert_state(tmp_path / "does_not_exist.json") == {}