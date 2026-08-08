import ast
import sys
from pathlib import Path


def has_terminal_node(body):
    for stmt in body:
        for child in ast.walk(stmt):
            if isinstance(child, (ast.Raise, ast.Return, ast.Continue, ast.Break)):
                return True
    return False


def scan_file(filepath):
    violations = []
    with open(filepath) as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return violations
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if not has_terminal_node(handler.body):
                    violations.append((filepath, handler.lineno))
    return violations


def main():
    engine_dir = Path(__file__).resolve().parent.parent.parent / "src2" / "engine"
    all_violations = []
    for py_file in sorted(engine_dir.rglob("*.py")):
        violations = scan_file(py_file)
        all_violations.extend(violations)
    if all_violations:
        print("=== Silent Swallow Violations ===")
        for filepath, lineno in all_violations:
            print(f"  {filepath}:{lineno} — except block does not terminate with raise or return")
        print(f"\nTotal violations: {len(all_violations)}")
        sys.exit(1)
    else:
        print("No silent swallow violations found in src2/engine/")
        sys.exit(0)


if __name__ == "__main__":
    main()
