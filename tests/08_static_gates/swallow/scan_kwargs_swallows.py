#!/usr/bin/env python3
"""
Phase 2: **kwargs Black Hole Scanner

Detects functions that accept **kwargs (e.g., **kwargs) but never reference
the kwargs parameter anywhere in their body. This is a silent swallow:
callers pass keyword arguments that are silently discarded.

Usage:
    uv run python 08_static_gates/swallow/scan_kwargs_swallows.py
"""

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Annot: src2 is baziforecaster-only; honour KIT_PATH override, else kit-relative.
_kit_path = os.getenv("KIT_PATH", "")
TARGET_DIR = os.path.join(_kit_path, "src2") if _kit_path else str(Path(__file__).resolve().parents[4] / "baziforecaster" / "src2")


@dataclass
class Violation:
    filepath: str
    lineno: int
    func_name: str
    kwargs_name: str
    body_line_span: tuple[int, int] = field(default=(0, 0))

    def __str__(self) -> str:
        start, end = self.body_line_span
        span = f" (body lines {start}-{end})" if end > 0 else ""
        return (
            f"{self.filepath}:{self.lineno} "
            f"{self.func_name}(**{self.kwargs_name}){span} — "
            f"kwargs parameter never accessed in body"
        )


def collect_kwargs_references(func_node, kwargs_name: str):
    """
    Walk the function's body recursively and collect ast.Name nodes that
    reference the **kwargs parameter name (with ast.Load context).

    Nested function definitions are skipped because they introduce their own
    scope — a nested function's **kwargs is a different variable.
    """
    references = []

    def _walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Name):
                if child.id == kwargs_name and isinstance(child.ctx, ast.Load):
                    references.append(child)
            _walk(child)

    for stmt in func_node.body:
        if isinstance(stmt, ast.Name):
            if stmt.id == kwargs_name and isinstance(stmt.ctx, ast.Load):
                references.append(stmt)
        _walk(stmt)

    return references


def scan_file(filepath: str):
    """Scan a single Python file for **kwargs black holes."""
    violations = []
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        print(f"⚠️  SyntaxError in {filepath}: {e}", file=sys.stderr)
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.args is None or node.args.kwarg is None:
            continue

        kwargs_name = node.args.kwarg.arg
        refs = collect_kwargs_references(node, kwargs_name)

        if len(refs) == 0:
            body_start = node.body[0].lineno if node.body else node.lineno
            body_end = node.end_lineno or node.lineno
            violations.append(
                Violation(
                    filepath=filepath,
                    lineno=node.lineno,
                    func_name=node.name,
                    kwargs_name=kwargs_name,
                    body_line_span=(body_start, body_end),
                )
            )

    return violations


def scan_directory(directory: str):
    """Scan all Python files in a directory for **kwargs black holes."""
    all_violations = []
    for root, _dirs, files in os.walk(directory):
        for filename in sorted(files):
            if filename.endswith(".py"):
                filepath = os.path.join(root, filename)
                all_violations.extend(scan_file(filepath))
    return all_violations


def main():
    print(f"\n🔍 Scanning {TARGET_DIR}/ for **kwargs black holes...\n")
    if not os.path.exists(TARGET_DIR):
        print(f"⚠️  Target directory '{TARGET_DIR}' does not exist — skipping (baziforecaster-only).")
        return 0
    violations = scan_directory(TARGET_DIR)

    if violations:
        print(f"🚨 Found {len(violations)} violation(s):\n")
        for v in violations:
            print(f"  {v}")
        print(f"\n⚠️  Total: {len(violations)} black holes")
        return 1

    print("✅ No **kwargs black holes found. All **kwargs parameters are used.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
