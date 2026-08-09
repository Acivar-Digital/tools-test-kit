#!/usr/bin/env python3
"""
Studio LLM Hallucination Validator (Template)

Usage: uv run python find_hallucinations.py <original.py> <refactored.py>

Catches:
1. Hallucinated Pydantic model fields (used in refactored but not in original)
2. Missing required fields
3. Invalid import paths (imported symbols that don't exist in the module)
4. API misuse (.get() on non-dict objects like registry/enum types)
5. Call signature drift (function calls with wrong arg counts)

Configure the paths at the top of the __main__ block below.
"""
import ast
import importlib
import sys
from typing import Optional


def extract_model_field_usage(filepath: str) -> dict:
    """Extract all 'object.attr' field access patterns, keyed by variable name."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    usage = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            obj_name = node.value.id
            attr_name = node.attr
            if obj_name not in usage:
                usage[obj_name] = set()
            usage[obj_name].add(attr_name)
    return usage


def extract_imports(filepath: str) -> dict:
    """Extract all 'from X import Y' mappings: {symbol: module_path}."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.name] = node.module or ""
    return imports


def extract_function_signatures(filepath: str) -> dict:
    """Extract function definitions with their parameter names."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = []
            for arg in node.args.args:
                params.append(arg.arg)
            funcs[node.name] = params
    return funcs


def extract_calls(filepath: str) -> list:
    """Extract all function/method calls as (name, line, arg_count)."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append((node.func.id, node.lineno, len(node.args)))
            elif isinstance(node.func, ast.Attribute):
                calls.append((node.func.attr, node.lineno, len(node.args)))
    return calls


def validate_pydantic_fields(original_path: str, refactored_path: str) -> list:
    """Compare Pydantic model field access between original and refactored."""
    orig_usage = extract_model_field_usage(original_path)
    ref_usage = extract_model_field_usage(refactored_path)

    issues = []

    # Common Pydantic model variable names in BaZi orchestrator context
    pydantic_objects = {
        "chart_profile",
        "scoring_results",
        "module_6_model",
        "root_results",
        "interaction_results",
        "medicine_results",
        "macro_results",
        "shen_profile",
        "strength_profile",
        "causal_results",
        "oracle_results",
        "trigger_results_model",
        "dm_strength_tier1",
        "clash_activation_results",
        "accumulated_damage",
        "engine_output",
        "engine_outputs_payload",
    }

    for obj in pydantic_objects:
        if obj in ref_usage:
            ref_fields = ref_usage.get(obj, set())
            orig_fields = orig_usage.get(obj, set())

            if obj in orig_usage:
                hallucinated = ref_fields - orig_fields
                if hallucinated:
                    issues.append(
                        f"HALLUCINATED FIELDS on '{obj}': {sorted(hallucinated)}"
                    )

                missing = orig_fields - ref_fields
                if missing:
                    issues.append(
                        f"MISSING FIELDS on '{obj}': {sorted(missing)}"
                    )
            else:
                issues.append(
                    f"NEW OBJECT '{obj}': not in original — verify it exists and fields are valid"
                )

    return issues


def validate_import_paths(refactored_path: str) -> list:
    """Verify all imported symbols actually exist in their declared modules."""
    issues = []
    ref_imports = extract_imports(refactored_path)

    for symbol, module_path in ref_imports.items():
        if not module_path:
            continue  # Skip relative imports (relative module path)

        # Skip non-src2 imports
        if not module_path.startswith("src2"):
            continue

        try:
            mod = importlib.import_module(module_path)
            if not hasattr(mod, symbol):
                issues.append(
                    f"INVALID IMPORT: '{symbol}' from '{module_path}' "
                    f"— symbol does not exist in module"
                )
        except ImportError as e:
            issues.append(
                f"INVALID IMPORT: Cannot import '{module_path}': {e}"
            )
        except Exception as e:
            issues.append(
                f"IMPORT CHECK FAILED for '{symbol}' from '{module_path}': {e}"
            )

    return issues


def validate_api_usage(refactored_path: str) -> list:
    """Flag suspicious API patterns indicating hallucination."""
    issues = []
    ref_imports = extract_imports(refactored_path)

    with open(refactored_path) as f:
        tree = ast.parse(f.read())

    # Safe .get() targets (dicts, dict-like vars)
    safe_get_objects = {
        "dict", "kwargs", "data", "payload", "config",
        "environ", "options", "env", "cache", "headers",
    }

    imported_symbols = ref_imports.keys()

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and
              isinstance(node.func, ast.Attribute) and
              node.func.attr == "get"):

            obj_name = ""
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id

            if obj_name and obj_name not in safe_get_objects:
                if obj_name in imported_symbols:
                    issues.append(
                        f"Line {node.lineno}: '.{obj_name}.get()' — "
                        f"verify '{obj_name}' is dict-like "
                        f"(not a registry/enum/Pydantic model)"
                    )

    return issues


def validate_call_signatures(original_path: str, refactored_path: str) -> list:
    """Compare function call argument counts between files."""
    orig_calls = extract_calls(original_path)
    ref_calls = extract_calls(refactored_path)

    issues = []
    orig_call_counts = {}

    for name, line, count in orig_calls:
        if name not in orig_call_counts:
            orig_call_counts[name] = count

    # Check refactored calls against original patterns
    for name, line, count in ref_calls:
        if name in orig_call_counts and orig_call_counts[name] != count:
            if orig_call_counts[name] > 0:  # Skip zero-arg calls (unreliable)
                issues.append(
                    f"Line {line}: Call to '{name}' has {count} args, "
                    f"original typically uses {orig_call_counts[name]} — "
                    f"possible signature mismatch"
                )

    return issues


def check_try_count(refactored_path: str) -> list:
    """Flag excessive try/except blocks (CC bloat pattern)."""
    issues = []
    with open(refactored_path) as f:
        tree = ast.parse(f.read())

    try_count = sum(1 for n in ast.walk(tree) if type(n).__name__ == "Try")

    if try_count >= 3:
        issues.append(
            f"TRY COUNT = {try_count} (>= 3) — may need refactoring"
        )

    return issues


def main(original_path: str, refactored_path: str) -> int:
    """Run all validation checks and report results."""
    print("=== STUDIO HALLUCINATION CHECK ===")
    print(f"Original:  {original_path}")
    print(f"Refactored: {refactored_path}")

    field_issues = validate_pydantic_fields(original_path, refactored_path)
    import_issues = validate_import_paths(refactored_path)
    api_issues = validate_api_usage(refactored_path)
    sig_issues = validate_call_signatures(original_path, refactored_path)
    try_issues = check_try_count(refactored_path)

    all_issues = field_issues + import_issues + api_issues + sig_issues + try_issues

    if field_issues:
        print("\n🔴 PYDANTIC FIELD MISMATCHES:")
        for issue in field_issues:
            print(f"  {issue}")

    if import_issues:
        print("\n🔴 INVALID IMPORTS:")
        for issue in import_issues:
            print(f"  {issue}")

    if api_issues:
        print("\n🟡 SUSPICIOUS API USAGE:")
        for issue in api_issues:
            print(f"  {issue}")

    if sig_issues:
        print("\n🟡 CALL SIGNATURE DRIFT:")
        for issue in sig_issues:
            print(f"  {issue}")

    if try_issues:
        print("\n🟡 TRY COUNT CHECK:")
        for issue in try_issues:
            print(f"  {issue}")

    if all_issues:
        print(f"\n💥 {len(all_issues)} issues found — Studio output needs review!")
        return 1
    else:
        print("\n✅ No hallucinations detected")
        return 0


if __name__ == "__main__":
    # === CONFIGURE PATHS HERE ===
    original_path = "original.py"
    refactored_path = "refactored.py"
    # =============================

    if len(sys.argv) == 3:
        original_path = sys.argv[1]
        refactored_path = sys.argv[2]

    sys.exit(main(original_path, refactored_path))
