import json
import os
import subprocess
from pathlib import Path


def run_tool(args):
    result = subprocess.run(["uv", "run", "python", str(Path(__file__).parents[1] / f"{args[0]}.py")] + args[1:],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {args[0]}.py: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from {args[0]}.py: {result.stdout}")
        return None

def test_index_repository():
    print("Testing index_repository...")
    res = run_tool(["index_repository", os.getenv("KIT_TARGET_ROOT_NAME", "codebase")])
    return res is not None and res.get("success") is True

def test_delete_collection():
    print("Testing delete_collection...")
    res = run_tool(["delete_collection", "test_collection"])
    return res is not None

def test_get_collection_stats_tool():
    print("Testing get_collection_stats_tool...")
    res = run_tool(["get_collection_stats_tool", "codebase"])
    return res is not None

if __name__ == "__main__":
    tests = [test_index_repository, test_delete_collection, test_get_collection_stats_tool]
    results = []
    for test in tests:
        results.append((test.__name__, test()))

    for name, res in results:
        print(f"{name}: {'PASS' if res else 'FAIL'}")
