"""AST scanner: detects Context Managers that silently swallow exceptions in ``__exit__``.

Targets ``src2/``. Walks the AST to find ``ast.FunctionDef`` (and
``ast.AsyncFunctionDef``) nodes named ``__exit__`` / ``__aexit__``. If such a
method contains an ``ast.Return`` node whose value is an ``ast.Constant`` with
value ``True``, Python interprets this as an explicit instruction to suppress
the exception that was raised inside the ``with`` block — a silent swallow.
"""
import ast
import sys
from pathlib import Path

from _swallow_utils import scan_tree


def find_exit_swallows(tree: ast.Module) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in ("__exit__", "__aexit__"):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                val = child.value
                if isinstance(val, ast.Constant) and val.value is True:
                    violations.append((
                        child.lineno,
                        f"{node.name} returns True — explicitly swallows exceptions "
                        f"in the with block (context manager {node.name})",
                    ))
    return violations


def main() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    src2 = root / "src2"
    all_violations = scan_tree(src2, find_exit_swallows)
    if all_violations:
        print("=== Context Manager Swallow Violations ===")
        for filepath, lineno, msg in all_violations:
            print(f"  {filepath}:{lineno} — {msg}")
        print(f"\nTotal violations: {len(all_violations)}")
        sys.exit(1)
    else:
        print("No context-manager swallow violations found in src2/")
        sys.exit(0)


if __name__ == "__main__":
    main()
