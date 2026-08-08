"""Regression tests for 0xvqo: intern tool-budget hardening.

Root cause (session_crash.md): intern_1/intern_3 each re-read their 3 staging
files 6x (redundant batch_read) then probed blind, exhausting the flat 15-call
budget -> RuntimeHALT. Two fixes are guarded here, both testable WITHOUT LLM keys:

  * PER-FILE READ IDEMPOTENCY -- GuardToolset HARD-rejects a re-read of any
    file path already fetched this run (the staging copy is eviction-exempt,
    full content present). A re-read does NOT re-execute the read and does NOT
    consume the read bucket, but still ticks the global tool budget so a chatty
    model cannot loop on re-reads forever.
  * DYNAMIC INTERN BUDGET -- _intern_budget_for(num_files) = clamp(BASE + PER_FILE
    * num_files, MIN, MAX). Scales with the task's file count so multi-file
    refactors aren't starved, but clamped vs sprawl.

If a future change re-allows redundant re-reads or reverts to a flat intern
budget, these tests fail loudly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra.tools import (
    _READ_FATAL,
    _READ_REDUNDANT,
    GuardToolset,
    _intern_budget_for,
)


class _FakeTool:
    """Minimal ToolsetTool stand-in (only identity matters for the guard)."""


class _FakeWrapped:
    """Records executed calls so tests can prove a read did/didn't re-execute."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, tool_args: dict, ctx, tool) -> str:
        self.calls.append((name, dict(tool_args)))
        return f"CONTENT:{name}"


def _make_guard(read_budget: int = 5, read_file_budget: int = 10, budget: int = 100) -> GuardToolset:
    wrapped = _FakeWrapped()
    gt = GuardToolset(
        wrapped=wrapped,  # type: ignore[arg-type]
        budget=budget,
        read_budget=read_budget,
        read_file_budget=read_file_budget,
    )
    gt._known_tools = {"batch_read": _FakeTool(), "read_file": _FakeTool()}  # type: ignore[index]
    gt._has_planned = True  # bypass planning gate; these tests focus on read idempotency
    return gt


async def test_batch_read_new_paths_executes_and_records() -> None:
    gt = _make_guard()
    await gt.call_tool(
        "batch_read",
        {"paths": ["a.py", "b.py"], "line_ranges": {"a.py": "1-10", "b.py": "1-10"}},
        None,
        _FakeTool(),
    )
    assert gt.wrapped.calls == [
        ("batch_read", {"paths": ["a.py", "b.py"], "line_ranges": {"a.py": "1-10", "b.py": "1-10"}})
    ]
    assert gt._read_used == 1
    assert gt._read_paths == {"a.py", "b.py"}


async def test_batch_read_redundant_rejected_no_reexec() -> None:
    gt = _make_guard()
    await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "1-10"}}, None, _FakeTool()
    )
    # Distinct range on same file is ALLOWED
    await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "20-30"}}, None, _FakeTool()
    )
    assert len(gt.wrapped.calls) == 2  # Executed both because range was distinct
    assert gt._read_used == 2

    # Identical range on same file is REJECTED
    before = len(gt.wrapped.calls)
    res = await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "20-30"}}, None, _FakeTool()
    )
    assert _READ_REDUNDANT in res
    assert len(gt.wrapped.calls) == before  # NOT re-executed
    # 0lj69: a re-read now CONSUMES the read budget
    assert gt._read_used == 3


async def test_batch_read_partial_new_executes_only_new() -> None:
    gt = _make_guard()
    await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "1-10"}}, None, _FakeTool()
    )
    await gt.call_tool(
        "batch_read",
        {"paths": ["a.py", "b.py"], "line_ranges": {"a.py": "1-10", "b.py": "1-10"}},
        None,
        _FakeTool(),
    )
    # b.py was new -> executed; a.py redundant -> skipped (no extra call for a.py)
    assert gt._read_paths == {"a.py", "b.py"}
    assert gt._read_used == 2


async def test_read_file_redundant_rejected() -> None:
    gt = _make_guard()
    await gt.call_tool("read_file", {"relative_path": "x.py", "start_line": 1, "end_line": 10}, None, _FakeTool())
    
    # Distinct range on same file is ALLOWED
    await gt.call_tool("read_file", {"relative_path": "x.py", "start_line": 20, "end_line": 30}, None, _FakeTool())
    assert len(gt.wrapped.calls) == 2
    
    # Identical range on same file is REJECTED
    before = len(gt.wrapped.calls)
    res = await gt.call_tool("read_file", {"relative_path": "x.py", "start_line": 20, "end_line": 30}, None, _FakeTool())
    assert _READ_REDUNDANT in res
    assert len(gt.wrapped.calls) == before


async def test_redundant_read_still_ticks_global_budget() -> None:
    # global budget = 2: 1st call (new) ticks to 1, 2nd (redundant) ticks to 2.
    gt = _make_guard(budget=2)
    await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "1-10"}}, None, _FakeTool()
    )
    res = await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "1-10"}}, None, _FakeTool()
    )
    assert gt._used == 2
    assert gt.exhausted is True
    assert "FATAL" in res


async def test_redundant_reads_exhaust_read_budget_force_final_result() -> None:
    # 0lj69 regression: a model that re-reads the SAME files over
    # and over (the session_crash.md hbh1 intern looped 12x on 2 files) must be
    # force-stopped. Re-reads now count against READ_BUDGET, so the Nth redundant
    # read returns _READ_FATAL ("emit final_result NOW") instead of looping until
    # request_limit=40 kills the whole run.
    gt = _make_guard(read_budget=5)
    await gt.call_tool(
        "batch_read", {"paths": ["a.py", "b.py"], "line_ranges": {"a.py": "1-10", "b.py": "1-10"}}, None, _FakeTool()
    )
    last_res = ""
    for _ in range(10):  # 10 redundant re-reads of the same 2 files
        last_res = await gt.call_tool(
            "batch_read", {"paths": ["a.py", "b.py"], "line_ranges": {"a.py": "1-10", "b.py": "1-10"}}, None, _FakeTool()
        )
    assert gt._read_used > gt.read_budget
    assert gt.read_exhausted is True
    assert _READ_FATAL in last_res  # force-stopped, not silently looping
    assert _READ_REDUNDANT not in last_res  # once over budget it's FATAL, not advisory


async def test_read_budget_exhaustion_returns_fatal() -> None:
    gt = _make_guard(read_budget=1)
    await gt.call_tool(
        "batch_read", {"paths": ["a.py"], "line_ranges": {"a.py": "1-10"}}, None, _FakeTool()
    )
    await gt.call_tool(
        "batch_read", {"paths": ["b.py"], "line_ranges": {"b.py": "1-10"}}, None, _FakeTool()
    )
    # 3rd DISTINCT batch_read exceeds read_budget=1 -> FATAL (not redundant).
    res = await gt.call_tool(
        "batch_read", {"paths": ["c.py"], "line_ranges": {"c.py": "1-10"}}, None, _FakeTool()
    )
    assert _READ_FATAL in res


def test_intern_budget_dynamic_scales_and_clamps() -> None:
    # 1 file -> 16 (12+4, clamped to MIN)
    assert _intern_budget_for(1) == 16
    # 3 files -> 24 (matches the session_crash task shape, no longer 15)
    assert _intern_budget_for(3) == 24
    # 0 files -> treat as 1 -> 16
    assert _intern_budget_for(0) == 16
    # 2 files -> 20
    assert _intern_budget_for(2) == 20
    # 10 files -> 12+40=52 clamped to MAX 30
    assert _intern_budget_for(10) == 30
    # monotonic: more files never yields fewer calls
    assert _intern_budget_for(5) >= _intern_budget_for(1)


async def test_path_normalization_deduplication() -> None:
    from factory.infra.tools import normalize_read_path
    # test normalize_read_path directly
    from factory.infra.control import REPO_ROOT
    assert normalize_read_path(f"{REPO_ROOT}/src2/core/schemas/unified.py") == "src2/core/schemas/unified.py"
    assert normalize_read_path("factory/temp/src2/core/schemas/unified.py") == "src2/core/schemas/unified.py"
    assert normalize_read_path("src2/core/schemas/unified.py") == "src2/core/schemas/unified.py"

    # test that tools.py call_tool normalizes paths correctly for deduplication
    gt = _make_guard()
    # First call with staging prefix
    await gt.call_tool("read_file", {"relative_path": "factory/temp/src2/foo.py"}, None, _FakeTool())
    # Second call with relative path should be REDUNDANT
    res = await gt.call_tool("read_file", {"relative_path": "src2/foo.py"}, None, _FakeTool())
    assert _READ_REDUNDANT in res


if __name__ == "__main__":
    asyncio.run(test_batch_read_new_paths_executes_and_records())
    asyncio.run(test_batch_read_redundant_rejected_no_reexec())
    asyncio.run(test_batch_read_partial_new_executes_only_new())
    asyncio.run(test_read_file_redundant_rejected())
    asyncio.run(test_redundant_read_still_ticks_global_budget())
    asyncio.run(test_read_budget_exhaustion_returns_fatal())
    test_intern_budget_dynamic_scales_and_clamps()
    asyncio.run(test_path_normalization_deduplication())
    print("OK")

