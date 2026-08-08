import json
import subprocess
from pathlib import Path


def run_tool(args):
    result = subprocess.run(["uv", "run", "python", str(Path(__file__).parents[1] / f"{args[0]}.py")] + args[1:],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {args[0]}.py: {result.stderr}")
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from {args[0]}.py: {result.stdout}")
        return None
    if not isinstance(payload, dict) or not payload.get("success", False):
        print(f"Tool {args[0]}.py reported failure: {payload}")
        return None
    # Tools return a {success, message, data} envelope; unwrap data for assertions.
    return payload.get("data")


def test_read_file():
    print("Testing read_file...")
    # Use a known file like AGENTS.md
    res = run_tool(["read_file", "AGENTS.md"])
    return res is not None and "content" in res

def test_list_files():
    print("Testing list_files...")
    res = run_tool(["list_files", "."])
    return res is not None and isinstance(res.get("files"), list)

def test_get_repo_structure():
    print("Testing get_repo_structure...")
    res = run_tool(["get_repo_structure"])
    return res is not None and "structure" in res

def test_get_file_symbols():
    print("Testing get_file_symbols...")
    # Use a known python file
    res = run_tool(["get_file_symbols", str(Path(__file__).parents[1] / "read_file.py")])
    return res is not None and isinstance(res.get("symbols"), list)

def test_grep_codebase():
    print("Testing grep_codebase...")
    res = run_tool(["grep_codebase", "import"])
    return res is not None and isinstance(res.get("results"), list)

if __name__ == "__main__":
    tests = [test_read_file, test_list_files, test_get_repo_structure, test_get_file_symbols, test_grep_codebase]
    results = []
    for test in tests:
        results.append((test.__name__, test()))

    for name, res in results:
        print(f"{name}: {'PASS' if res else 'FAIL'}")
