#!/usr/bin/env python3
"""
Phase 2: Async Fire-and-Forget Swallow Scanner
==============================================

Detects unhandled ``asyncio.create_task()`` calls in ``src2/interfaces/``
(and async orchestration layers) that silently swallow task exceptions.

Rules
-----
1. Every ``asyncio.create_task(...)`` must either:
   a. Have an attached ``add_done_callback(...)`` call on the result, OR
   b. Be tracked in a set/list (e.g. ``tracking_set.add(task)``) used for
      ``asyncio.gather`` / liveness.
2. Callbacks must **not be silent** — i.e. they must not be bare
   ``set.discard()`` / ``set.remove()`` / ``set.clear()`` calls that
   never inspect ``task.exception()``.

Vulnerabilities detected
------------------------
- **Fire-and-forget** — ``create_task`` called without callback or tracking.
- **Silent callback** — ``add_done_callback`` uses only ``set.discard`` /
  ``set.remove`` / ``set.clear``, which silently discards the task without
  logging or routing the exception.

Usage
-----
    uv run python 08_static_gates/swallow/scan_async_tasks.py
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

TARGET_DIR = Path(__file__).resolve().parent.parent.parent / "src2" / "interfaces"

# Method names that indicate a *silent* callback — the task's exception
# is never inspected, so it is silently swallowed.
SILENT_CALLBACK_ATTRS = frozenset({"discard", "remove", "clear"})

# Method names that indicate a *tracking* operation — the task is kept
# alive in a collection so it won't be GC'd.
TRACKING_ATTRS = frozenset({"add", "append"})


# --------------------------------------------------------------------------- #
#  AST helpers                                                                #
# --------------------------------------------------------------------------- #

def _dotted_name(func: ast.expr) -> str:
    """Return the dotted attribute name, e.g. ``asyncio.create_task``."""
    parts: list[str] = []
    node: ast.expr = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    return ".".join(parts)


def _is_create_task(node: ast.expr) -> bool:
    """True if *node* is a Call to ``asyncio.create_task`` / ``create_task``."""
    if not isinstance(node, ast.Call):
        return False
    return _dotted_name(node.func) in (
        "asyncio.create_task",
        "create_task",
        "loop.create_task",
    )


def _is_add_done_callback(node: ast.expr) -> bool:
    """True if *node* is a Call to ``*.add_done_callback``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr == "add_done_callback"


def _is_silent_callback(arg: ast.expr) -> bool:
    """True if *arg* is a ``set.discard`` / ``set.remove`` / ``set.clear`` reference."""
    return isinstance(arg, ast.Attribute) and arg.attr in SILENT_CALLBACK_ATTRS


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


# --------------------------------------------------------------------------- #
#  Violation data class                                                       #
# --------------------------------------------------------------------------- #

@dataclass
class Violation:
    filepath: Path
    lineno: int
    message: str

    def __str__(self) -> str:
        return f"  {self.filepath}:{self.lineno} — {self.message}"


# --------------------------------------------------------------------------- #
#  Core scanner                                                               #
# --------------------------------------------------------------------------- #

def scan_tree(tree: ast.Module, filepath: Path) -> list[Violation]:
    """Scan a parsed AST module for async task swallow violations."""
    violations: list[Violation] = []

    all_calls: list[ast.Call] = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]

    # --- Phase 1: collect every add_done_callback call ---------------------- #
    #   Stores: (object_node, callback_arg, lineno)
    adc_info: list[tuple[ast.expr, ast.expr | None, int]] = []
    for call in all_calls:
        if _is_add_done_callback(call):
            obj = call.func.value  # the object .add_done_callback is called on
            cb_arg = call.args[0] if call.args else None
            adc_info.append((obj, cb_arg, call.lineno))

    # --- Phase 2: find create_task calls and analyse context ----------------- #
    create_task_calls = [c for c in all_calls if _is_create_task(c)]

    for ct in create_task_calls:
        # 2a — Chained: asyncio.create_task(...).add_done_callback(cb)
        is_chained = False
        for obj, cb_arg, lineno in adc_info:
            if isinstance(obj, ast.Call) and obj is ct:
                is_chained = True
                if cb_arg is not None and _is_silent_callback(cb_arg):
                    violations.append(Violation(
                        filepath=filepath,
                        lineno=ct.lineno,
                        message="chained .add_done_callback() uses silent callback "
                                f"({cb_arg.attr}) — task exceptions silently discarded",
                    ))
                break
        if is_chained:
            continue

        # 2b — Assigned: task = asyncio.create_task(...)
        var_name = _find_assignment_target(tree, ct)

        if var_name is not None:
            has_callback = False
            has_non_silent_callback = False
            has_tracking = False

            for obj, cb_arg, lineno in adc_info:
                if isinstance(obj, ast.Name) and obj.id == var_name:
                    has_callback = True
                    if cb_arg is not None and not _is_silent_callback(cb_arg):
                        has_non_silent_callback = True

            # Check for tracking: set.add(var) / list.append(var)
            for call in all_calls:
                if isinstance(call.func, ast.Attribute) and call.func.attr in TRACKING_ATTRS:
                    for arg in call.args:
                        if isinstance(arg, ast.Name) and arg.id == var_name:
                            has_tracking = True
                            break

            if not has_callback and not has_tracking:
                violations.append(Violation(
                    filepath=filepath,
                    lineno=ct.lineno,
                    message=f"create_task assigned to '{var_name}' but never given "
                            "add_done_callback or tracking — fire-and-forget",
                ))
            elif has_callback and not has_non_silent_callback:
                violations.append(Violation(
                    filepath=filepath,
                    lineno=ct.lineno,
                    message=f"create_task assigned to '{var_name}' — all "
                            "add_done_callback callbacks are silent (set discard/remove/clear) "
                            "— task exceptions silently swallowed",
                ))

        else:
            # 2c — Inline / standalone: asyncio.create_task(...) as a bare expression
            violations.append(Violation(
                filepath=filepath,
                lineno=ct.lineno,
                message="create_task called as fire-and-forget — no add_done_callback "
                        "and no tracking",
            ))

    return violations


def _find_assignment_target(tree: ast.Module, target_call: ast.Call) -> str | None:
    """Return the variable name if *target_call* is the value of an Assign node."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.value is target_call:
            for tgt in node.targets:
                n = _name(tgt)
                if n is not None:
                    return n
    return None


# --------------------------------------------------------------------------- #
#  File / directory helpers                                                   #
# --------------------------------------------------------------------------- #

def scan_file(filepath: Path) -> list[Violation]:
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        print(f"⚠️  SyntaxError in {filepath}: {exc}", file=sys.stderr)
        return []
    return scan_tree(tree, filepath)


def scan_directory(directory: Path) -> list[Violation]:
    all_violations: list[Violation] = []
    for py_file in sorted(directory.rglob("*.py")):
        all_violations.extend(scan_file(py_file))
    return all_violations


# --------------------------------------------------------------------------- #
#  Entry point                                                                #
# --------------------------------------------------------------------------- #

def main() -> int:
    print(f"\n🔍 Scanning {TARGET_DIR}/ for unhandled async task creation...\n")

    violations = scan_directory(TARGET_DIR)

    if violations:
        print(f"🚨 Found {len(violations)} violation(s):\n")
        for v in violations:
            print(v)
        print(f"\n⚠️  Total: {len(violations)} violations")
        return 1

    print("✅ No unhandled async task creation found. All tasks have exception-tracking callbacks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
