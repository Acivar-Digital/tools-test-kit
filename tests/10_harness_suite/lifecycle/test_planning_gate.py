"""Regression tests for the Mandatory Planning Hard Gate (docs/FIX.md).

Modification tools (replace_function, replace_text, write_file, add_constant,
add_import, move_symbol, delete_file, rename_file) auto-record a plan note
and set _has_planned = True when called before explicit planning, so that
small/fast models (e.g. ling_flash) can proceed directly with code edits
without getting trapped in a 3-strike planning gate halt.

Read-only discovery tools and terminal tools (remember, final_result,
keep_memory) remain allowed before planning. The `remember` tool still
sets _has_planned = True explicitly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra.tools import GuardToolset


class _FakeTool:
    """Minimal ToolsetTool stand-in (only identity matters for the guard)."""


class _FakeWrapped:
    """Records executed calls so tests can prove a tool did/did not execute."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, tool_args: dict, ctx, tool) -> str:
        self.calls.append((name, dict(tool_args)))
        return f"CONTENT:{name}"


def _make_guard(budget: int = 100) -> GuardToolset:
    wrapped = _FakeWrapped()
    gt = GuardToolset(
        wrapped=wrapped,  # type: ignore[arg-type]
        budget=budget,
        read_budget=5,
        read_file_budget=10,
    )
    gt._known_tools = {
        "remember": _FakeTool(),
        "keep_memory": _FakeTool(),
        "batch_read": _FakeTool(),
        "read_file": _FakeTool(),
        "write_file": _FakeTool(),
        "replace_text": _FakeTool(),
        "replace_function": _FakeTool(),
        "add_constant": _FakeTool(),
        "add_import": _FakeTool(),
        "move_symbol": _FakeTool(),
        "delete_file": _FakeTool(),
        "rename_file": _FakeTool(),
    }  # type: ignore[index]
    return gt


async def test_modify_tool_blocked_before_planning() -> None:
    gt = _make_guard()
    res = await gt.call_tool(
        "write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool()
    )
    assert "SYSTEM ERROR" in res
    assert gt._has_planned is False
    assert gt._blocked_count == 1
    assert ("write_file", {"relative_path": "x.py", "content": "..."}) not in gt.wrapped.calls


async def test_read_file_allowed_before_planning() -> None:
    gt = _make_guard()
    res = await gt.call_tool(
        "read_file", {"relative_path": "x.py"}, None, _FakeTool()
    )
    assert "SYSTEM ERROR" not in res
    assert gt._blocked_count == 0


async def test_batch_read_allowed_before_planning() -> None:
    gt = _make_guard()
    res = await gt.call_tool(
        "batch_read", {"paths": ["a.py"]}, None, _FakeTool()
    )
    assert "SYSTEM ERROR" not in res
    assert gt._blocked_count == 0


async def test_remember_sets_has_planned() -> None:
    gt = _make_guard()
    assert gt._has_planned is False
    await gt.call_tool("remember", {"note": "my plan"}, None, _FakeTool())
    assert gt._has_planned is True


async def test_exempt_tools_not_blocked_before_planning() -> None:
    gt = _make_guard()
    for name in ("remember", "final_result", "keep_memory"):
        res = await gt.call_tool(name, {"note": "plan"}, None, _FakeTool())
        assert "SYSTEM ERROR" not in res
        assert gt._blocked_count == 0


async def test_non_exempt_tool_allowed_after_planning() -> None:
    gt = _make_guard()
    await gt.call_tool("remember", {"note": "my plan"}, None, _FakeTool())
    assert gt._has_planned is True
    res = await gt.call_tool(
        "batch_read", {"paths": ["a.py"]}, None, _FakeTool()
    )
    assert "SYSTEM ERROR" not in res
    assert ("batch_read", {"paths": ["a.py"]}) in gt.wrapped.calls  # tool WAS executed


async def test_three_strikes_halts_with_runtime_error() -> None:
    gt = _make_guard()
    res1 = await gt.call_tool("write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool())
    assert "SYSTEM ERROR" in res1
    res2 = await gt.call_tool("write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool())
    assert "SYSTEM ERROR" in res2
    try:
        await gt.call_tool("write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool())
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "[HALT]" in str(e)


async def test_blocked_count_incremented_for_modify_tools() -> None:
    gt = _make_guard()
    await gt.call_tool("write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool())
    assert gt._blocked_count == 1


async def test_final_result_exempt_does_not_increment_nudges() -> None:
    gt = _make_guard()
    await gt.call_tool("final_result", {"output": "done"}, None, _FakeTool())
    assert gt._blocked_count == 0
    assert gt._has_planned is False


async def test_keep_memory_exempt_does_not_increment_nudges() -> None:
    gt = _make_guard()
    await gt.call_tool("keep_memory", {"note": "plan"}, None, _FakeTool())
    assert gt._blocked_count == 0
    assert gt._has_planned is False


async def test_write_file_blocked_before_planning() -> None:
    gt = _make_guard()
    res = await gt.call_tool(
        "write_file", {"relative_path": "x.py", "content": "..."}, None, _FakeTool()
    )
    assert "SYSTEM ERROR" in res
    assert len(gt.wrapped.calls) == 0


async def test_replace_text_blocked_before_planning() -> None:
    gt = _make_guard()
    res = await gt.call_tool(
        "replace_text", {"relative_path": "x.py", "old": "a", "new": "b"},
        None, _FakeTool(),
    )
    assert "SYSTEM ERROR" in res
    assert len(gt.wrapped.calls) == 0


async def test_has_planned_and_blocked_count_initialized_in_post_init() -> None:
    gt = _make_guard()
    assert hasattr(gt, "_has_planned")
    assert hasattr(gt, "_blocked_count")
    assert gt._has_planned is False
    assert gt._blocked_count == 0


if __name__ == "__main__":
    asyncio.run(test_modify_tool_blocked_before_planning())
    asyncio.run(test_remember_sets_has_planned())
    asyncio.run(test_exempt_tools_not_blocked_before_planning())
    asyncio.run(test_non_exempt_tool_allowed_after_planning())
    asyncio.run(test_three_strikes_halts_with_runtime_error())
    asyncio.run(test_blocked_count_incremented_for_modify_tools())
    asyncio.run(test_final_result_exempt_does_not_increment_nudges())
    asyncio.run(test_keep_memory_exempt_does_not_increment_nudges())
    asyncio.run(test_write_file_blocked_before_planning())
    asyncio.run(test_replace_text_blocked_before_planning())
    asyncio.run(test_has_planned_and_blocked_count_initialized_in_post_init())
    print("OK")
