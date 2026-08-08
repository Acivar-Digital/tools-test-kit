"""AST scanner: detects dictionary ``get()`` calls with default fallback values in math engines.

Targets ``src2/engine/``. Walks the AST to find ``ast.Call`` nodes whose function
is an ``ast.Attribute`` named ``get``. If such a call carries a second positional
argument (or a ``default`` keyword), it supplies a fallback value — e.g.
``data.get("multiplier", 1.0)``. In a deterministic engine this masks a missing
key by silently substituting a guessed constant instead of raising ``KeyError``.

Such calls must be replaced with strict bracket notation (``data["multiplier"]``)
so that missing variables fail loudly.
"""
import ast
import sys
from pathlib import Path

from _swallow_utils import scan_tree


def find_get_defaults(tree: ast.Module) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "get":
            continue
        has_default_arg = len(node.args) >= 2
        has_default_kwarg = any(
            kw.arg == "default" for kw in node.keywords
        )
        if has_default_arg or has_default_kwarg:
            if has_default_arg:
                default = node.args[1]
                default_src = ast.unparse(default)
                violations.append((
                    node.lineno,
                    f".get(…, {default_src}) — dictionary call with a default "
                    "fallback value silently substitutes a guessed constant; use "
                    "strict bracket notation [key] to trigger KeyError instead",
                ))
            else:
                default_src = ast.unparse(
                    next(kw.value for kw in node.keywords if kw.arg == "default")
                )
                violations.append((
                    node.lineno,
                    f".get(…, default={default_src}) — dictionary call with a "
                    "default fallback value silently substitutes a guessed "
                    "constant; use strict bracket notation [key] to trigger "
                    "KeyError instead",
                ))
    return violations


def main() -> None:
    engine_dir = Path(__file__).resolve().parent.parent.parent / "src2" / "engine"
    all_violations = scan_tree(engine_dir, find_get_defaults)
    if all_violations:
        print("=== Dictionary .get() Fallback Trap Violations ===")
        for filepath, lineno, msg in all_violations:
            print(f"  {filepath}:{lineno} — {msg}")
        print(f"\nTotal violations: {len(all_violations)}")
        sys.exit(1)
    else:
        print("No dictionary .get() fallback violations found in src2/engine/")
        sys.exit(0)


if __name__ == "__main__":
    main()
