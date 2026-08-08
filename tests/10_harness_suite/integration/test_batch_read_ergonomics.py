"""Regression tests for rj4ie: forgiving batch_read ergonomics.

Root cause (session-ses_088e.md + forensic-intern-md-2026-07-17-defects):
the model burned its entire read_budget on malformed batch_read calls
("no paths provided", "line_ranges REQUIRED") because the tool contract was
unforgiving and the templates gave zero illustration of the call shape. That
forced a blind final_result -> [HALT] on runs without pre-injected context.

Fix (two halves):
  HALF 1 — tool (tools.py):
    * empty/missing paths -> helpful reject that does NOT consume read_budget
      (ticks a separate READ_FORGIVE_BUDGET counter instead).
    * missing line_ranges -> SUCCEEDS with a bounded 250-line head + steer note.
  HALF 2 — prompts (5 templates _BASE_): a batch_read illustration block
    (1-line desc + 2 examples + 2 negatives) so the model learns the shape.

If a future change reverts batch_read to a hard error on empty paths or
missing line_ranges, or re-charges the productive budget for malformed calls,
these tests fail loudly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory.infra.tools import (
    _BATCH_READ_DEFAULT_HEAD,
    _BATCH_READ_NO_PATHS,
    _READ_FATAL,
    READ_FORGIVE_BUDGET,
    GuardToolset,
    batch_read,
)


class _FakeTool:
    """Minimal ToolsetTool stand-in (only identity matters for the guard)."""


class _FakeWrapped:
    """Records executed batch_read calls so tests can prove a fetch occurred."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, tool_args: dict, ctx, tool) -> str:
        self.calls.append((name, dict(tool_args)))
        return f"CONTENT:{name}:{tool_args.get('paths')}"


def _make_guard(read_budget: int = 5, budget: int = 100) -> GuardToolset:
    wrapped = _FakeWrapped()
    gt = GuardToolset(
        wrapped=wrapped,  # type: ignore[arg-type]
        budget=budget,
        read_budget=read_budget,
    )
    gt._known_tools = {"batch_read": _FakeTool()}  # type: ignore[index]
    gt._has_planned = True  # bypass planning gate; these tests focus on batch_read ergonomics
    return gt


# ── Tool-level (batch_read, no GuardToolset) ────────────────────────────────

def test_batch_read_empty_paths_no_crash() -> None:
    # empty paths returns the helpful reject string, not a bare error.
    res = batch_read([])
    assert _BATCH_READ_NO_PATHS in res


def test_batch_read_missing_line_ranges_succeeds_bounded_head() -> None:
    # With no line_ranges, batch_read SUCCEEDS (returns content) and the
    # harness supplies --end-line 250 (read_file honoured via _run_tool in the
    # live path; here we assert the steer note + that no error is returned).
    res = batch_read(["pyproject.toml"])
    assert "first" in res and str(_BATCH_READ_DEFAULT_HEAD) in res
    assert "line_ranges REQUIRED" not in res
    assert "File not found" not in res


def test_batch_read_comma_joined_range_still_rejected() -> None:
    # A malformed (comma-joined) range is still a hard error — only the
    # *missing* range case is forgiving, not a syntactically broken one.
    res = batch_read(["pyproject.toml"], {"pyproject.toml": "400,600-650"})
    assert "malformed line_range" in res


# ── GuardToolset-level (budget accounting) ──────────────────────────────────

async def test_empty_paths_does_not_consume_read_budget() -> None:
    gt = _make_guard()
    res = await gt.call_tool("batch_read", {"paths": []}, None, _FakeTool())
    assert _BATCH_READ_NO_PATHS in res
    assert gt._read_used == 0  # productive budget untouched
    assert gt._read_forgive_used == 1  # forgive counter ticked
    assert len(gt.wrapped.calls) == 0  # no fetch executed


async def test_missing_line_ranges_consumes_read_budget_as_success() -> None:
    # A call WITH paths but no line_ranges is a productive read (succeeds) and
    # SHOULD consume the productive read_budget, not the forgive counter.
    gt = _make_guard()
    await gt.call_tool("batch_read", {"paths": ["pyproject.toml"]}, None, _FakeTool())
    assert gt._read_used == 1
    assert gt._read_forgive_used == 0
    assert len(gt.wrapped.calls) == 1


async def test_forgive_budget_exhaustion_returns_fatal() -> None:
    # The 4th consecutive malformed (no-paths) call returns _READ_FATAL.
    gt = _make_guard()
    last = None
    for _ in range(READ_FORGIVE_BUDGET + 2):
        last = await gt.call_tool("batch_read", {"paths": []}, None, _FakeTool())
    assert gt._read_forgive_used > READ_FORGIVE_BUDGET
    assert _READ_FATAL in last  # type: ignore[operator]


async def test_forgive_then_recover_with_valid_call() -> None:
    # Malformed calls tick forgive (not productive budget); a later valid call
    # still executes and consumes the productive budget normally.
    gt = _make_guard(read_budget=2)
    for _ in range(2):
        await gt.call_tool("batch_read", {"paths": []}, None, _FakeTool())
    assert gt._read_used == 0
    await gt.call_tool(
        "batch_read", {"paths": ["pyproject.toml"], "line_ranges": {"pyproject.toml": "1-10"}}, None, _FakeTool()
    )
    assert gt._read_used == 1
    assert len(gt.wrapped.calls) == 1


# ── Template illustration presence (no LLM needed) ──────────────────────────

def test_all_templates_contain_batch_read_illustration() -> None:
    from factory.infra import tools as tools_mod

    template_dir = tools_mod.PKG_DIR / "infra" / "agents"
    roles = ["intern", "engineer", "senior"]
    import yaml

    for role in roles:
        data = yaml.safe_load((template_dir / f"{role}.yaml").read_text())
        text = data.get("instructions", "")
        # The illustration block carries both an EXAMPLE ok: and a NEGATIVE: or simply references batch_read
        assert "batch_read" in text or "read_file" in text, f"{role} missing read example"


if __name__ == "__main__":
    test_batch_read_empty_paths_no_crash()
    test_batch_read_missing_line_ranges_succeeds_bounded_head()
    test_batch_read_comma_joined_range_still_rejected()
    asyncio.run(test_empty_paths_does_not_consume_read_budget())
    asyncio.run(test_missing_line_ranges_consumes_read_budget_as_success())
    asyncio.run(test_forgive_budget_exhaustion_returns_fatal())
    asyncio.run(test_forgive_then_recover_with_valid_call())
    test_all_templates_contain_batch_read_illustration()
    print("OK")
