#!/usr/bin/env python3
import argparse
import ast
import sys
from pathlib import Path
from typing import Any


class GoogleStyleVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.violations: dict[str, list[Any]] = {
            "mutable_defaults": [],
            "missing_type_hints": [],
            "unsafe_open": [],
        }
        self.safe_opens: set[int] = set()

    def _extract_open_call(self, item: ast.withitem) -> int | None:
        if isinstance(item.context_expr, ast.Call):
            call = item.context_expr
            if isinstance(call.func, ast.Name) and call.func.id == "open":
                return call.lineno
        return None

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            lineno = self._extract_open_call(item)
            if lineno is not None:
                self.safe_opens.add(lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "open"
            and node.lineno not in self.safe_opens
        ):
            self.violations["unsafe_open"].append(node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_mutable_defaults(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        all_defaults: list[ast.expr] = list(node.args.defaults)
        all_defaults.extend([d for d in node.args.kw_defaults if d is not None])
        for default in all_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.violations["mutable_defaults"].append((node.name, node.lineno))

    def _has_missing_return_hint(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        if node.name in ("__init__", "__new__"):
            return False
        return node.returns is None

    def _has_missing_arg_hint(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        all_args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        for arg in all_args:
            if arg.arg not in ("self", "cls") and not arg.annotation:
                return True
        return False

    def _check_type_hints(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        if self._has_missing_return_hint(node) or self._has_missing_arg_hint(node):
            self.violations["missing_type_hints"].append((node.name, node.lineno))

    def _check_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self._check_mutable_defaults(node)
        self._check_type_hints(node)


def analyze_file(filepath: str) -> dict[str, list[Any]]:
    try:
        source = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
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


def _has_violations(violations: dict[str, list[Any]]) -> bool:
    return any(bool(v) for v in violations.values())


def _process_file(filepath: str) -> tuple[str, dict[str, list[Any]]] | None:
    if not Path(filepath).exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        return None
    violations = analyze_file(filepath)
    if _has_violations(violations):
        return filepath, violations
    return None


def analyze_files(files: list[str]) -> dict[str, dict[str, list[Any]]]:
    violating_files: dict[str, dict[str, list[Any]]] = {}
    for filepath in files:
        result = _process_file(filepath)
        if result is not None:
            path_key, violations = result
            violating_files[path_key] = violations
    return violating_files


def _print_mutable_defaults(entries: list[tuple[str, int]]) -> None:
    if not entries:
        return
    print("  Mutable Default Arguments Found (e.g., def func(x=[]):)")
    for name, line in entries:
        print(f"     - Function '{name}' at line {line}")


def _print_unsafe_opens(lines: list[int]) -> None:
    if not lines:
        return
    print("  Unsafe File Management (open() used without 'with' context manager)")
    for line in lines:
        print(f"     - Line {line}")


def _print_missing_type_hints(entries: list[tuple[str, int]]) -> None:
    if not entries:
        return
    print("  Missing Type Annotations (Args or Return type missing)")
    for name, line in entries:
        print(f"     - Function '{name}' at line {line}")


def _print_file_violations(
    filepath: str, violations: dict[str, list[Any]]
) -> None:
    print(f"\n{filepath}:")
    _print_mutable_defaults(violations.get("mutable_defaults", []))
    _print_unsafe_opens(violations.get("unsafe_open", []))
    _print_missing_type_hints(violations.get("missing_type_hints", []))


def print_report(violating: dict[str, dict[str, list[Any]]]) -> None:
    print("=" * 60)
    print("Google Style Violations Report")
    print("=" * 60)

    if not violating:
        print("No violations found. Clean codebase!")
        return

    for filepath, violations in violating.items():
        _print_file_violations(filepath, violations)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check Python files for Google Style Guide violations: "
            "mutable defaults, missing type hints, and unsafe open() calls"
        )
    )
    parser.add_argument(
        "--files", nargs="+", required=True, help="Python files to analyze"
    )
    args = parser.parse_args()

    violating = analyze_files(args.files)
    print_report(violating)

    total_violations = sum(
        sum(len(v) for v in violations.values()) for violations in violating.values()
    )

    return 1 if total_violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
