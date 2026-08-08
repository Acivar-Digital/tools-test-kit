"""Shared helpers for the anti-silent-swallow AST auditing suite."""
from __future__ import annotations

import ast
from pathlib import Path


def scan_tree(directory: Path, find_violations) -> list[tuple]:
    """Walk every ``*.py`` under *directory*, parse its AST, delegate to *find_violations*.

    *find_violations* is a callable ``(ast.Module) -> list[tuple[int, str]]``
    where each returned tuple is ``(lineno, message)``.

    Returns a list of ``(filepath, lineno, message)`` tuples across all files.
    """
    results: list[tuple] = []
    base = Path(directory)
    for py_file in sorted(base.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        for lineno, msg in find_violations(tree):
            results.append((py_file, lineno, msg))
    return results
