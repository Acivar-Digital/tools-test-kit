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
from collections import defaultdict

# Common Pydantic model variable names in BaZi orchestrator context
PYDANTIC_OBJECTS: set[str] = {
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

# Safe .get() targets (dicts, dict-like vars)
SAFE_GET_OBJECTS: set[str] = {
    "dict",
    "kwargs",
    "data",
    "payload",
    "config",
    "environ",
    "options",
    "env",
    "cache",
    "headers",
}


def extract_model_field_usage(filepath: str) -> dict[str, set[str]]:
    """Extract all 'object.attr' field access patterns, keyed by variable name."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    usage: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            usage[node.value.id].add(node.attr)
    return dict(usage)


def extract_imports(filepath: str) -> dict[str, str]:
    """Extract all 'from X import Y' mappings: {symbol: module_path}."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.name] = node.module or ""
    return imports


def extract_function_signatures(filepath: str) -> dict[str, list[str]]:
    """Extract function definitions with their parameter names."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    funcs: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = [arg.arg for arg in node.args.args]
    return funcs


def _extract_call_node(node: ast.Call) -> tuple[str, int, int] | None:
    if isinstance(node.func, ast.Name):
        return (node.func.id, node.lineno, len(node.args))
    if isinstance(node.func, ast.Attribute):
        return (node.func.attr, node.lineno, len(node.args))
    return None


def extract_calls(filepath: str) -> list[tuple[str, int, int]]:
    """Extract all function/method calls as (name, line, arg_count)."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    calls: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            info = _extract_call_node(node)
            if info:
                calls.append(info)
    return calls


def _check_object_fields(
    obj: str,
    orig_usage: dict[str, set[str]],
    ref_usage: dict[str, set[str]],
) -> list[str]:
    ref_fields = ref_usage.get(obj, set())
    orig_fields = orig_usage.get(obj, set())

    if obj not in orig_usage:
        return [
            f"NEW OBJECT '{obj}': not in original — verify it exists and fields are valid"
        ]

    issues: list[str] = []
    hallucinated = ref_fields - orig_fields
    if hallucinated:
        issues.append(f"HALLUCINATED FIELDS on '{obj}': {sorted(hallucinated)}")

    missing = orig_fields - ref_fields
    if missing:
        issues.append(f"MISSING FIELDS on '{obj}': {sorted(missing)}")

    return issues


def validate_pydantic_fields(
    original_path: str, refactored_path: str
) -> list[str]:
    """Compare Pydantic model field access between original and refactored."""
    orig_usage = extract_model_field_usage(original_path)
    ref_usage = extract_model_field_usage(refactored_path)

    issues: list[str] = []
    for obj in PYDANTIC_OBJECTS:
        if obj in ref_usage:
            issues.extend(_check_object_fields(obj, orig_usage, ref_usage))

    return issues


def _import_module_and_verify(symbol: str, module_path: str) -> str | None:
    try:
        mod = importlib.import_module(module_path)
        if not hasattr(mod, symbol):
            return (
                f"INVALID IMPORT: '{symbol}' from '{module_path}' "
                f"— symbol does not exist in module"
            )
    except ImportError as e:
        return f"INVALID IMPORT: Cannot import '{module_path}': {e}"
    except Exception as e:  # noqa: BLE001
        return f"IMPORT CHECK FAILED for '{symbol}' from '{module_path}': {e}"
    return None


def _check_import_symbol(symbol: str, module_path: str) -> str | None:
    if not module_path or not module_path.startswith("src2"):
        return None
    return _import_module_and_verify(symbol, module_path)


def validate_import_paths(refactored_path: str) -> list[str]:
    """Verify all imported symbols actually exist in their declared modules."""
    issues: list[str] = []
    ref_imports = extract_imports(refactored_path)

    for symbol, module_path in ref_imports.items():
        issue = _check_import_symbol(symbol, module_path)
        if issue:
            issues.append(issue)

    return issues


def _get_attribute_name(node: ast.Call) -> tuple[str, str] | None:
    if not isinstance(node.func, ast.Attribute):
        return None
    if not isinstance(node.func.value, ast.Name):
        return None
    return node.func.value.id, node.func.attr


def _check_suspicious_call(
    obj_name: str, attr_name: str, line: int, imported_symbols: set[str]
) -> str | None:
    if attr_name != "get" or not obj_name:
        return None
    if obj_name in SAFE_GET_OBJECTS or obj_name not in imported_symbols:
        return None
    return (
        f"Line {line}: '.{obj_name}.get()' — "
        f"verify '{obj_name}' is dict-like "
        f"(not a registry/enum/Pydantic model)"
    )


def validate_api_usage(refactored_path: str) -> list[str]:
    """Flag suspicious API patterns indicating hallucination."""
    issues: list[str] = []
    ref_imports = extract_imports(refactored_path)
    imported_symbols = set(ref_imports.keys())

    with open(refactored_path) as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = _get_attribute_name(node)
            if target:
                obj_name, attr_name = target
                issue = _check_suspicious_call(
                    obj_name, attr_name, node.lineno, imported_symbols
                )
                if issue:
                    issues.append(issue)

    return issues


def _build_orig_call_counts(
    orig_calls: list[tuple[str, int, int]],
) -> dict[str, int]:
    orig_call_counts: dict[str, int] = {}
    for name, _line, count in orig_calls:
        if name not in orig_call_counts:
            orig_call_counts[name] = count
    return orig_call_counts


def _check_call_signature(
    name: str, line: int, count: int, orig_call_counts: dict[str, int]
) -> str | None:
    if name not in orig_call_counts:
        return None
    expected_count = orig_call_counts[name]
    if expected_count > 0 and count != expected_count:
        return (
            f"Line {line}: Call to '{name}' has {count} args, "
            f"original typically uses {expected_count} — "
            f"possible signature mismatch"
        )
    return None


def validate_call_signatures(
    original_path: str, refactored_path: str
) -> list[str]:
    """Compare function call argument counts between files."""
    orig_calls = extract_calls(original_path)
    ref_calls = extract_calls(refactored_path)

    orig_call_counts = _build_orig_call_counts(orig_calls)
    issues: list[str] = []

    for name, line, count in ref_calls:
        issue = _check_call_signature(name, line, count, orig_call_counts)
        if issue:
            issues.append(issue)

    return issues


def check_try_count(refactored_path: str) -> list[str]:
    """Flag excessive try/except blocks (CC bloat pattern)."""
    with open(refactored_path) as f:
        tree = ast.parse(f.read())

    try_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try))

    if try_count >= 3:
        return [f"TRY COUNT = {try_count} (>= 3) — may need refactoring"]

    return []


def _print_issue_section(title: str, issues: list[str]) -> None:
    if issues:
        print(title)
        for issue in issues:
            print(f"  {issue}")


def main(original_path: str, refactored_path: str) -> int:
    """Run all validation checks and report results."""
    print("=== STUDIO HALLUCINATION CHECK ===")
    print(f"Original:  {original_path}")
    print(f"Refactored: {refactored_path}")

    sections = [
        (
            "\n🔴 PYDANTIC FIELD MISMATCHES:",
            validate_pydantic_fields(original_path, refactored_path),
        ),
        ("\n🔴 INVALID IMPORTS:", validate_import_paths(refactored_path)),
        ("\n🟡 SUSPICIOUS API USAGE:", validate_api_usage(refactored_path)),
        (
            "\n🟡 CALL SIGNATURE DRIFT:",
            validate_call_signatures(original_path, refactored_path),
        ),
        ("\n🟡 TRY COUNT CHECK:", check_try_count(refactored_path)),
    ]

    all_issues: list[str] = []
    for title, issues in sections:
        _print_issue_section(title, issues)
        all_issues.extend(issues)

    if all_issues:
        print(
            f"\n💥 {len(all_issues)} issues found — Studio output needs review!"
        )
        return 1

    print("\n✅ No hallucinations detected")
    return 0


if __name__ == "__main__":
    orig_path = "original.py"
    ref_path = "refactored.py"

    if len(sys.argv) == 3:
        orig_path = sys.argv[1]
        ref_path = sys.argv[2]

    sys.exit(main(orig_path, ref_path))
