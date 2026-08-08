"""AST scanner: detects silent default (constant) fallback returns inside `except` handlers.

Targets `src2/engine/`. Flags an `ast.Return` inside an `except` block whose
returned value is an `ast.Constant` — e.g. `return 0`, `return 0.0`, `return None`,
`return False`, `return ""`. These silently swallow the exception and substitute a
hardcoded primitive, masking real failures in a deterministic math engine.
"""
import ast
import sys
from pathlib import Path

from _swallow_utils import scan_tree


def find_constant_returns(tree: ast.Module) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                for child in ast.walk(handler):
                    if isinstance(child, ast.Return) and isinstance(child.value, ast.Constant):
                        const_val = child.value.value
                        violations.append((
                            child.lineno,
                            (
                                f"return {const_val!r} inside except handler "
                                f"(handler line {handler.lineno}) — "
                                "silent default fallback swallows the exception"
                            ),
                        ))
    return violations


def main() -> None:
    engine_dir = Path(__file__).resolve().parent.parent.parent / "src2" / "engine"
    all_violations = scan_tree(engine_dir, find_constant_returns)
    if all_violations:
        print("=== Fallback-Default Swallow Violations ===")
        for filepath, lineno, msg in all_violations:
            print(f"  {filepath}:{lineno} — {msg}")
        print(f"\nTotal violations: {len(all_violations)}")
        sys.exit(1)
    else:
        print("No fallback-default swallow violations found in src2/engine/")
        sys.exit(0)


if __name__ == "__main__":
    main()
