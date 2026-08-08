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
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from {args[0]}.py: {result.stdout}")
        return None

def test_remember_fact():
    print("Testing remember_fact...")
    key = "test_key_123"
    val = "test_value_123"
    res = run_tool(["remember_fact", key, val])
    return res is not None

def test_recall_fact():
    print("Testing recall_fact...")
    key = "test_key_123"
    res = run_tool(["recall_fact", key])
    return res is not None and res.get("value") == "test_value_123"

def test_list_facts():
    print("Testing list_facts...")
    res = run_tool(["list_facts"])
    return res is not None and isinstance(res, list)

def test_create_execution_plan():
    print("Testing create_execution_plan...")
    plan = {"steps": [{"id": 1, "action": "test"}]}
    res = run_tool(["create_execution_plan", json.dumps(plan)])
    return res is not None

def test_build_repo_graph():
    print("Testing build_repo_graph...")
    res = run_tool(["build_repo_graph"])
    return res is not None

def test_explain_failure():
    print("Testing explain_failure...")
    res = run_tool(["explain_failure", "Some error message"])
    return res is not None

def test_count_lines():
    print("Testing count_lines...")
    res = run_tool(["count_lines", "AGENTS.md"])
    return res is not None and isinstance(res, dict)

def test_verify_file_path():
    print("Testing verify_file_path...")
    res = run_tool(["verify_file_path", "AGENTS.md"])
    return res is not None and res.get("exists") is True

def test_query_knowledge_graph():
    print("Testing query_knowledge_graph...")
    res = run_tool(["query_knowledge_graph", "What is this project?"])
    return res is not None

def test_get_code_hierarchy():
    print("Testing get_code_hierarchy...")
    res = run_tool(["get_code_hierarchy"])
    return res is not None

def test_graph_health():
    print("Testing graph_health...")
    res = run_tool(["graph_health"])
    return res is not None

def test_find_related_code():
    print("Testing find_related_code...")
    res = run_tool(["find_related_code", "Bazi"])
    return res is not None and isinstance(res.get("data", {}).get("results"), list)

if __name__ == "__main__":
    tests = [test_remember_fact, test_recall_fact, test_list_facts, test_create_execution_plan,
             test_build_repo_graph, test_explain_failure, test_count_lines, test_verify_file_path,
             test_query_knowledge_graph, test_get_code_hierarchy, test_graph_health, test_find_related_code]
    results = []
    for test in tests:
        results.append((test.__name__, test()))

    for name, res in results:
        print(f"{name}: {'PASS' if res else 'FAIL'}")
