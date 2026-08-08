"""Regression tests for docs/FIX.md — KG injection + Option B."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ------------------------------------------------------------------
# Task 1: query_knowledge_graph.py — no libcst dependency, exit 0
# ------------------------------------------------------------------

def test_kg_query_no_libcst_dependency():
    """The CLI wrapper must import and run without libcst / qdrant_client."""
    cmd = [
        sys.executable,
        "factory/tools/query_knowledge_graph.py",
        "test query",
        "--max-entities", "3",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    # Must exit 0 (greenfield / no crash) and emit JSON.
    assert result.returncode == 0, (
        f"KG cli crashed (libcst?) rc={result.returncode} stderr={result.stderr}"
    )
    output = result.stdout
    assert '"success"' in output
    # Either graph present or greenfield empty result — both OK.
    assert ("entities" in output) and ("relationships" in output)


def test_kg_query_missing_file_graceful():
    """When the graph JSON is missing, the CLI returns exit 0 (greenfield)."""
    cmd = [
        sys.executable,
        "factory/tools/query_knowledge_graph.py",
        "anything",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"Expected exit 0 for missing graph; got {result.returncode}"
    output = result.stdout
    assert '"success": true' in output
    assert '"entities": []' in output


# ------------------------------------------------------------------
# Task 2: get_file_symbols.py — greenfield missing file = exit 0
# ------------------------------------------------------------------

def test_get_file_symbols_missing_file_exit_0():
    """Missing .py file for greenfield creation must return exit 0, empty symbols."""
    cmd = [
        sys.executable,
        "factory/tools/get_file_symbols.py",
        "nonexistent_file_for_greenfield_99999.py",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    # Option B: exit 0 for missing file (greenfield), NOT non-zero.
    assert result.returncode == 0, f"Expected exit 0; got {result.returncode} stderr={result.stderr}"
    output = result.stdout
    assert '"success": true' in output
    assert '"symbols": []' in output


# ------------------------------------------------------------------
# Task 4: ledger.py — fail loudly (no swallow of RuntimeError)
# ------------------------------------------------------------------

def test_ledger_kg_for_file_does_not_swallow():
    """_kg_for_file must not have a try/except that swallows RuntimeError."""
    source = (Path(__file__).resolve().parents[1] / "factory" / "infra" / "ledger.py").read_text()
    # The function should reference _run_tool directly (no try/except wrapper).
    assert "_run_tool(\"query_knowledge_graph\"" in source
    # There should be NO try...except RuntimeError around the KG call.
    # We verify by counting try blocks in the file and ensuring the old swallow is gone.
    lines = source.splitlines()
    # Find the _kg_for_file function and check its body.
    in_kg = False
    for ln in lines:
        if "def _kg_for_file" in ln:
            in_kg = True
        if in_kg:
            # After removing the swallow, the function should just have a return.
            if "try:" in ln:
                # There should be NO try block inside _kg_for_file.
                raise AssertionError("_kg_for_file still has a try block — Option B not applied")
            if "return _unwrap_tool_output" in ln:
                break
