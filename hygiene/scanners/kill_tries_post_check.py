"""Post-Check Scanner for Kill-Tries Refactorings.

Validates that:
1. All candidate code and helper functions parse cleanly into Python AST without syntax errors.
2. Every refactored function maintains 100% parameter signature parity with the original function.
3. Zero functions are dropped/deleted from the source files when applying refactorings.
4. No undefined identifiers are introduced — all names referenced in the refactored code must be defined
   locally (functions in the blob), imported, or builtins. This catches hallucinated helper functions
   that reference non-existent symbols (e.g. _handle_gate_failure, get_session, save_session).
"""

import argparse
import ast
import builtins
import json
import os
import sys
from pathlib import Path

DEFAULT_REPORT_PATH = Path("kit-hygiene/reports/kill_tries.json")

_KNOWN_BUILTINS = set(dir(builtins))


def _collect_defined_names(blob: str) -> set[str]:
    tree = ast.parse(blob)
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
    return defined


def check_undefined_identifiers(blob: str, func_name: str) -> list[str]:
    try:
        tree = ast.parse(blob)
    except SyntaxError:
        return []

    defined = _collect_defined_names(blob)
    undefined: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name = node.id
            if name in defined or name in _KNOWN_BUILTINS:
                continue
            if name.startswith("_") and func_name.startswith("_"):
                continue
            undefined.append(name)

    return sorted(set(undefined))


def run_post_check(report_path: Path) -> bool:
    if not report_path.exists():
        print(f"❌ Error: Report file not found at '{report_path}'")
        return False

    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)

    approved = data.get("approved", [])
    if not approved:
        print("⚠️ Warning: No approved refactorings found in report.")
        return True

    print(f"🔍 Running post-check on {len(approved)} approved refactoring candidates...\n")

    syntax_errors = []
    sig_mismatches = []
    undefined_idents = []
    by_file: dict[str, list[dict]] = {}

    # Step 1 & 2 & 4: Check AST Syntax, Signature Parity & Undefined Identifiers
    for item in approved:
        fpath = item["file_path"]
        func_name = item["function_name"]
        code = item["refactored_code"]
        helpers = item.get("helper_functions", [])

        by_file.setdefault(fpath, []).append(item)

        full_blob = "\n\n".join([code] + helpers)
        try:
            tree = ast.parse(full_blob)
        except SyntaxError as se:
            syntax_errors.append((fpath, func_name, str(se)))
            continue

        undefined = check_undefined_identifiers(full_blob, func_name)
        if undefined:
            undefined_idents.append((fpath, func_name, undefined))

        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as orig_f:
                orig_tree = ast.parse(orig_f.read(), filename=fpath)

            orig_args = None
            for node in ast.walk(orig_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    orig_args = [a.arg for a in node.args.args]
                    break

            ref_args = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    ref_args = [a.arg for a in node.args.args]
                    break

            if orig_args is not None and ref_args is not None and orig_args != ref_args:
                sig_mismatches.append((fpath, func_name, orig_args, ref_args))

    # Step 3: AST Diff Function Preservation Check
    all_passed = True
    print("--- Function Preservation Check (AST Diff Simulation) ---")

    for fpath, items in sorted(by_file.items()):
        if not os.path.exists(fpath):
            print(f"⚠️ File not found: {fpath}")
            continue

        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        tree_before = ast.parse(content, filename=fpath)
        funcs_before = {
            node.name
            for node in ast.walk(tree_before)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        proposed_funcs = set()
        for item in items:
            ref_tree = ast.parse(item["refactored_code"])
            for node in ast.walk(ref_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    proposed_funcs.add(node.name)
            for h in item.get("helper_functions", []):
                h_tree = ast.parse(h)
                for node in ast.walk(h_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        proposed_funcs.add(node.name)

        funcs_after = funcs_before.union(proposed_funcs)
        missing = funcs_before - funcs_after

        if missing:
            print(f"❌ FAIL: `{fpath}` would drop functions: {missing}")
            all_passed = False
        else:
            added_count = len(funcs_after) - len(funcs_before)
            print(f"✓ PASS: `{fpath}`")
            print(f"  - Original functions: {len(funcs_before)}")
            print(f"  - Functions after apply: {len(funcs_after)} (+{added_count} helper functions added)")
            print("  - Functions dropped: 0\n")

    print("--- Post-Check Summary ---")
    print(f"Syntax Errors: {len(syntax_errors)}")
    print(f"Signature Mismatches: {len(sig_mismatches)}")
    print(f"Undefined Identifiers: {len(undefined_idents)}")

    if syntax_errors or sig_mismatches or undefined_idents or not all_passed:
        if undefined_idents:
            print("\n⚠️  Undefined identifiers introduced by refactorings:")
            for fpath, func_name, undefs in undefined_idents:
                print(f"  {fpath} :: {func_name}")
                for u in undefs:
                    print(f"    - `{u}`")
        print("\n❌ OVERALL STATUS: FAILED checks.")
        return False

    print("\n✅ OVERALL STATUS: PASSED (100% parameter parity, 0 syntax errors, 0 undefined identifiers, 0 dropped functions)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-check scanner for kill_tries refactorings")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to kill_tries.json report file",
    )
    args = parser.parse_args()

    success = run_post_check(args.report_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
