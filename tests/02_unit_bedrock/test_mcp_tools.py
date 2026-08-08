#!/usr/bin/env python3
"""
Diagnostic Test Script for Codebase MCP Tools
============================================
Checks if all codebase MCP tools (grep, read, list, graph, Qdrant search)
are working properly and returning valid data structures.

Usage:
    uv run python 02_unit_bedrock/test_mcp_tools.py
"""

import os
import sys
from pathlib import Path

# Annot: infra/codebase is the ai-factory codebase server (sibling of ai-factory/).
# Set KIT_CODEBASE_DIR env var to its location; skips gracefully if absent in kit.
_kit_codebase = os.getenv("KIT_CODEBASE_DIR")
CODEBASE_SERVER_DIR = Path(_kit_codebase) if _kit_codebase else None
if CODEBASE_SERVER_DIR:
    sys.path.append(str(CODEBASE_SERVER_DIR))

try:
    import mcp_codebase
except ImportError as e:
    _loc = str(CODEBASE_SERVER_DIR) if CODEBASE_SERVER_DIR else "(KIT_CODEBASE_DIR not set)"
    print(f"❌ Failed to import mcp_codebase from {_loc}: {e}")
    sys.exit(1)

def run_test(tool_name: str, func, *args, **kwargs):
    print(f"\n🔍 Testing tool: {tool_name} ...")
    print("-" * 50)
    try:
        res = func(*args, **kwargs)
        if isinstance(res, dict) and res.get("success"):
            print(f"✅ SUCCESS: {res.get('message')}")
            # Print a snippet of the data
            data = res.get("data", {})
            keys = list(data.keys())
            print(f"   Returned Keys: {keys}")
            for k in keys:
                val = data[k]
                if isinstance(val, list):
                    print(f"   - '{k}': List of {len(val)} items (first 1-2 shown below):")
                    for item in val[:2]:
                        print(f"     {str(item)[:150]}...")
                else:
                    print(f"   - '{k}': {str(val)[:150]}...")
            return True
        else:
            print(f"❌ FAILED: {res.get('message') if isinstance(res, dict) else res}")
            return False
    except Exception as e:
        import traceback
        print(f"💥 CRASHED: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def main():
    print("🚀 Running Codebase MCP Tools Integration Diagnostics...")
    print("=" * 60)
    print(f"Project Root: {mcp_codebase.PROJECT_ROOT}")
    print(f"Infra Root  : {mcp_codebase.INFRA_ROOT}")
    print(f"Graph JSON  : {mcp_codebase.GRAPH_JSON}")
    print(f"Qdrant URL  : {mcp_codebase.QDRANT_URL}")
    print(f"BGEM3 URL   : {mcp_codebase.BGEM3_URL}")
    print("=" * 60)

    all_passed = True

    # 1. Test list_files
    all_passed &= run_test(
        "list_files",
        mcp_codebase.list_files,
        directory="src2/core/memory",
        recursive=False,
        limit=5
    )

    # 2. Test read_file
    all_passed &= run_test(
        "read_file",
        mcp_codebase.read_file,
        relative_path="src2/core/memory/memory_manager.py",
        start_line=1,
        end_line=20
    )

    # 3. Test grep_codebase
    all_passed &= run_test(
        "grep_codebase",
        mcp_codebase.grep_codebase,
        pattern="MemoryManager",
        directory="src2/core/memory",
        max_results=3
    )

    # 4. Test query_knowledge_graph
    all_passed &= run_test(
        "query_knowledge_graph",
        mcp_codebase.query_knowledge_graph,
        query="memory manager",
        max_entities=3
    )

    # 5. Test search_codebase (Qdrant + Embeddings)
    all_passed &= run_test(
        "search_codebase",
        mcp_codebase.search_codebase,
        query="how does key rotation work?",
        limit=3
    )

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL MCP TOOLS VERIFIED AND WORKING PROPERLY!")
    else:
        print("⚠️ SOME MCP TOOLS FAILED OR ARE UNCONFIGURED. See details above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
