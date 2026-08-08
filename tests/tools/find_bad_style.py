#!/usr/bin/env python3
import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path


class GoogleStyleVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: dict[str, list] = {
            "mutable_defaults": [],
            "missing_type_hints": [],
            "unsafe_open": [],
        }
        self.safe_opens: set[int] = set()

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                call = item.context_expr
                if isinstance(call.func, ast.Name) and call.func.id == "open":
                    self.safe_opens.add(call.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.lineno not in self.safe_opens:
                self.violations["unsafe_open"].append(node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        all_defaults = list(node.args.defaults)
        all_defaults += [d for d in node.args.kw_defaults if d is not None]
        for default in all_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.violations["mutable_defaults"].append((node.name, node.lineno))

        has_missing = False

        if not node.returns and node.name not in ("__init__", "__new__"):
            has_missing = True

        all_args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        for arg in all_args:
            if arg.arg not in ("self", "cls") and not arg.annotation:
                has_missing = True

        if has_missing:
            self.violations["missing_type_hints"].append((node.name, node.lineno))


def analyze_file(filepath: str) -> dict[str, list]:
    try:
        source = Path(filepath).read_text(encoding="utf-8")
    except (OSError, SyntaxError) as e:
        print(f"Could not read {filepath}: {e}", file=sys.stderr)
        return {}

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return {}

    visitor = GoogleStyleVisitor(filepath)
    visitor.visit(tree)
    return visitor.violations


def analyze_files(files: list[str]) -> dict[str, dict[str, list]]:
    violating_files: dict[str, dict[str, list]] = defaultdict(dict)

    for filepath in files:
        p = Path(filepath)
        if not p.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            continue

        violations = analyze_file(filepath)
        if violations:
            total = sum(len(v) for v in violations.values())
            if total > 0:
                violating_files[filepath] = violations

    return dict(violating_files)


def print_report(violating: dict[str, dict[str, list]]) -> None:
    print("=" * 60)
    print("Google Style Violations Report")
    print("=" * 60)

    if not violating:
        print("No violations found. Clean codebase!")
        return

    for filepath, violations in violating.items():
        print(f"\n{filepath}:")

        if violations["mutable_defaults"]:
            print("  Mutable Default Arguments Found (e.g., def func(x=[]):)")
            for name, line in violations["mutable_defaults"]:
                print(f"     - Function '{name}' at line {line}")

        if violations["unsafe_open"]:
            print("  Unsafe File Management (open() used without 'with' context manager)")
            for line in violations["unsafe_open"]:
                print(f"     - Line {line}")

        if violations["missing_type_hints"]:
            print("  Missing Type Annotations (Args or Return type missing)")
            for name, line in violations["missing_type_hints"]:
                print(f"     - Function '{name}' at line {line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Python files for Google Style Guide violations: mutable defaults, missing type hints, and unsafe open() calls"
    )
    parser.add_argument("--files", nargs="+", required=True, help="Python files to analyze")
    args = parser.parse_args()

    violating = analyze_files(args.files)
    print_report(violating)

    total_violations = sum(
        sum(len(v) for v in violations.values()) for violations in violating.values()
    )

    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
