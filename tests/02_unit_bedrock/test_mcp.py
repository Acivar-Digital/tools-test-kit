#!/usr/bin/env python3
"""
Comprehensive Test Suite for MCP Codebase Server
Tests all exposed tools in mcp_codebase.py
"""

import sys
from pathlib import Path

MCP_CODEBASE_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "codebase"
sys.path.insert(0, str(MCP_CODEBASE_DIR))

import mcp_codebase as m  # noqa: E402


def call_tool(tool_name, **kwargs):
    """Call an MCP tool by looking it up as a module-level function."""
    fn = getattr(m, tool_name, None)
    if fn is None:
        raise ValueError(f"Tool '{tool_name}' not found in mcp_codebase module")
    return fn(**kwargs)


passed = 0
failed = 0
errors = []


def run_test(name, fn):
    global passed, failed
    print(f"\n[TEST] {name}")
    try:
        fn()
        print("  ✓ PASSED")
        passed += 1
    except AssertionError as e:
        import traceback
        traceback.print_exc()
        print(f"  ✗ FAILED: {e}")
        failed += 1
        errors.append((name, str(e)))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ✗ ERROR: {type(e).__name__}: {e}")
        failed += 1
        errors.append((name, f"{type(e).__name__}: {e}"))


# ── Search Lane ──────────────────────────────────────────────

def test_search_codebase():
    result = call_tool("search_codebase", query="telegram bot", limit=3)
    assert result.get("success") is True, f"Search failed: {result.get('message')}"
    data = result.get("data", {})
    assert "results" in data
    print(f"    Found {len(data.get('results', []))} results")
    for r in data["results"][:2]:
        print(f"    - {r.get('file_path', '?')} (score: {r.get('score', 0)})")


def test_grep_codebase():
    result = call_tool("grep_codebase", pattern="def main", directory="", extension_filter=".py", max_results=5)
    assert result.get("success") is True, f"Grep failed: {result.get('message')}"
    print(f"    Found {result.get('count', 0)} matches")


def test_get_file_symbols():
    result = call_tool("get_file_symbols", relative_path="baziforecaster/src/bot/app.py")
    assert result.get("success") is True, f"get_file_symbols failed: {result.get('message')}"
    symbols = result.get("symbols", [])
    print(f"    Found {len(symbols)} symbols")
    for s in symbols[:3]:
        print(f"    - {s['name']} ({s['type']}) at line {s['line']}")


def test_get_repo_structure():
    result = call_tool("get_repo_structure", max_depth=2)
    assert result.get("success") is True, f"get_repo_structure failed: {result.get('message')}"
    structure = result.get("structure", "")
    line_count = len(structure.splitlines())
    print(f"    Structure has {line_count} lines")


# ── Read Lane ────────────────────────────────────────────────

def test_read_file():
    result = call_tool("read_file", relative_path="baziforecaster/src/bot/app.py", start_line=1, end_line=10)
    assert result.get("success") is True, f"read_file failed: {result.get('message')}"
    print(f"    Read {result.get('total_lines', 0)} total lines, showed lines {result.get('start_line')}-{result.get('end_line')}")


def test_list_files():
    result = call_tool("list_files", directory="baziforecaster/src/bot")
    assert result.get("success") is True, f"list_files failed: {result.get('message')}"
    items = result.get("items", [])
    print(f"    Found {len(items)} items in baziforecaster/src/bot")


# ── Edit Lane ────────────────────────────────────────────────

def test_write_and_read_file():
    test_path = "baziforecaster/_test_write_file.py"
    test_content = "# test file\nprint('hello from test')\n"
    result = call_tool("write_file", relative_path=test_path, content=test_content)
    assert result.get("success") is True, f"write_file failed: {result.get('message')}"

    result = call_tool("read_file", relative_path=test_path)
    assert result.get("success") is True
    assert "hello from test" in result.get("data", {}).get("content", "")

    # Cleanup
    call_tool("delete_file", relative_path=test_path)
    print("    Write + read + delete round-trip OK")


def test_replace_in_file():
    test_path = "baziforecaster/_test_replace_file.py"
    call_tool("write_file", relative_path=test_path, content="old_value = 1\n")

    result = call_tool("replace_in_file", relative_path=test_path, target_text="old_value", replacement_text="new_value")
    assert result.get("success") is True

    result = call_tool("read_file", relative_path=test_path)
    assert "new_value" in result.get("data", {}).get("content", "")

    # Cleanup
    call_tool("delete_file", relative_path=test_path)
    print("    Replace in file OK")


def test_rename_file():
    test_path = "baziforecaster/_test_rename_old.py"
    renamed_path = "baziforecaster/_test_rename_new.py"
    call_tool("write_file", relative_path=test_path, content="# rename test\n")

    result = call_tool("rename_file", source_relative_path=test_path, destination_relative_path=renamed_path)
    assert result.get("success") is True, f"rename_file failed: {result.get('message')}"

    # Verify old gone, new exists
    check_old = call_tool("read_file", relative_path=test_path)
    assert check_old.get("success") is False, "Old file should not exist after rename"
    check_new = call_tool("read_file", relative_path=renamed_path)
    assert check_new.get("success") is True, "New file should exist after rename"

    # Cleanup
    call_tool("delete_file", relative_path=renamed_path)
    print("    Rename file OK")


# ── Cleanup Lane ─────────────────────────────────────────────

def test_ast_clean_imports():
    test_path = "baziforecaster/_test_imports.py"
    call_tool("write_file", relative_path=test_path, content="import os\nimport sys\nimport json\nprint('hi')\n")
    result = call_tool("ast_clean_imports", relative_path=test_path)
    assert result.get("success") is True, f"ast_clean_imports failed: {result.get('message')}"
    # Cleanup
    call_tool("delete_file", relative_path=test_path)
    print("    Import cleaning OK")


# ── Info Lane ────────────────────────────────────────────────

def test_count_lines():
    result = call_tool("count_lines", files=["baziforecaster/src/bot/app.py", "baziforecaster/src/engine/bazi_data.py"])
    assert isinstance(result, dict)
    for f, count in result.items():
        print(f"    {f}: {count} lines")


def test_explain_failure():
    result = call_tool("explain_failure", error_message="ModuleNotFoundError: foo")
    assert isinstance(result, str) and len(result) > 0
    print(f"    Explanation length: {len(result)} chars")


# ── Main ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("MCP Codebase Server - Comprehensive Test Suite")
    print("=" * 60)

    # Search Lane
    run_test("search_codebase (semantic search)", test_search_codebase)
    run_test("grep_codebase (regex search)", test_grep_codebase)
    run_test("get_file_symbols (AST symbols)", test_get_file_symbols)
    run_test("get_repo_structure (tree outline)", test_get_repo_structure)

    # Read Lane
    run_test("read_file", test_read_file)
    run_test("list_files", test_list_files)

    # Edit Lane
    run_test("write_file + read + delete round-trip", test_write_and_read_file)
    run_test("replace_in_file", test_replace_in_file)
    run_test("rename_file", test_rename_file)


    # Cleanup Lane
    run_test("ast_clean_imports", test_ast_clean_imports)

    # Info Lane
    run_test("count_lines", test_count_lines)
    run_test("explain_failure", test_explain_failure)

    # Summary
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {total} tests")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
