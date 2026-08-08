#!/usr/bin/env python3
"""
Phase 3: Validator Silencer — AST scanner for Pydantic validators that mutate input data.

Targets ``src2/``. Walks the AST for ``ast.FunctionDef`` and
``ast.AsyncFunctionDef`` nodes decorated with ``@model_validator`` or
``@field_validator``. Within the validator body, flags:

1. Subscript assignments (e.g. ``data['gender'] = 'M'``) — mutates the
   dict/list passed into a ``model_validator(mode='before')``, silently
   rewriting upstream data instead of rejecting it.
2. Name assignments matching the ``field_validator`` value parameter
   (e.g. ``v = str(v)``) — reassigns the field value parameter, masking
   type coercion that should be the caller's responsibility.
3. Augmented / annotated assignments covering the same patterns.

Validators should validate and raise ``ValueError`` (or return a transformed
*copy*), not silently sweep upstream data corruption under the rug.
"""

import ast
import sys
from pathlib import Path

from _swallow_utils import scan_tree

VALIDATOR_NAMES = {"model_validator", "field_validator"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decorator_name(node):
    """Return the validator decorator name if *node* is decorated, else None.

    Handles bare decorators (``@model_validator``) as well as called
    decorators (``@model_validator(mode='before')``) and qualified
    decorators (``@pydantic.model_validator``).
    """
    for dec in node.decorator_list:
        func = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(func, ast.Name) and func.id in VALIDATOR_NAMES:
            return func.id
        if isinstance(func, ast.Attribute) and func.attr in VALIDATOR_NAMES:
            return func.attr
    return None


def _second_param(node):
    """Return the name of the second positional parameter (index 1).

    ``model_validator`` before-handlers receive ``(cls, data)``;
    ``field_validator`` callbacks receive ``(cls, v)``.
    """
    args = node.args
    all_args = list(args.posonlyargs) + list(args.args)
    if len(all_args) >= 2:
        return all_args[1].arg
    return None


def _is_subscript_on(param_name, target):
    """True if *target* is ``<param_name>[...]`` — a dict/list mutation."""
    if not isinstance(target, ast.Subscript):
        return False
    return isinstance(target.value, ast.Name) and target.value.id == param_name


def _is_name(param_name, target):
    """True if *target* is a bare ``param_name`` assignment."""
    return isinstance(target, ast.Name) and target.id == param_name


# ---------------------------------------------------------------------------
# Violation finder
# ---------------------------------------------------------------------------

def find_validator_mutations(tree: ast.Module) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        dec = _decorator_name(node)
        if dec is None:
            continue

        param_name = _second_param(node)
        if param_name is None:
            continue

        for stmt in ast.walk(node):
            # --- ast.Assign ---
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if _is_subscript_on(param_name, target):
                        violations.append((
                            stmt.lineno,
                            f"@model_validator mutates input dict «{param_name}[...]» "
                            f"— {ast.unparse(stmt)}",
                        ))
                    if _is_name(param_name, target):
                        violations.append((
                            stmt.lineno,
                            f"@{dec} reassigns value parameter «{param_name}» "
                            f"— {ast.unparse(stmt)}",
                        ))

            # --- ast.AugAssign (e.g. v += 1, data['k'] += 1) ---
            elif isinstance(stmt, ast.AugAssign):
                if _is_subscript_on(param_name, stmt.target):
                    violations.append((
                        stmt.lineno,
                        f"@model_validator aug-mutates input dict «{param_name}[...]» "
                        f"— {ast.unparse(stmt)}",
                    ))
                if _is_name(param_name, stmt.target):
                    violations.append((
                        stmt.lineno,
                        f"@{dec} aug-reassigns value parameter «{param_name}» "
                        f"— {ast.unparse(stmt)}",
                    ))

            # --- ast.AnnAssign (e.g. v: str = str(v)) ---
            elif isinstance(stmt, ast.AnnAssign):
                target = stmt.target
                if _is_name(param_name, target):
                    violations.append((
                        stmt.lineno,
                        f"@{dec} annotated-reassigns value parameter «{param_name}» "
                        f"— {ast.unparse(stmt)}",
                    ))
                if _is_subscript_on(param_name, target):
                    violations.append((
                        stmt.lineno,
                        f"@model_validator mutates input dict «{param_name}[...]]» "
                        f"— {ast.unparse(stmt)}",
                    ))

    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    src2 = root / "src2"
    all_violations = scan_tree(src2, find_validator_mutations)

    if all_violations:
        print("=== Validator Mutation Violations ===")
        for filepath, lineno, msg in all_violations:
            print(f"  {filepath}:{lineno} — {msg}")
        print(f"\nTotal violations: {len(all_violations)}")
        sys.exit(1)
    else:
        print("No validator mutation violations found in src2/")
        sys.exit(0)


if __name__ == "__main__":
    main()
