#!/usr/bin/env python3
"""
Kill-Tries Apply Script: Applies approved refactorings from checkpoint to src2/.

Reads kit-hygiene/reports/kill_tries_checkpoint.jsonl and applies
APPROVED refactorings atomically (per-function with ruff validation).
"""

import ast
import json
import logging
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from virtual_ast_buffer import (  # noqa: E402
    VirtualASTBuffer,
    ensure_pydantic_imports,
    verify_class_structure_intact,
)

CHECKPOINT_FILE = pkg_root / "reports" / "kill_tries_checkpoint.jsonl"
SRC2_DIR = pkg_root.parent / "src2"

def _deduplicate_top_level(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    seen_names: dict[str, int] = {}
    indices_to_remove: list[int] = []
    for i, node in enumerate(tree.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name in seen_names:
                indices_to_remove.append(i)
            else:
                seen_names[name] = i
    if not indices_to_remove:
        return source
    new_body = [node for i, node in enumerate(tree.body) if i not in indices_to_remove]
    tree.body = new_body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _cleanup_local_imports(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    module_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_imports.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                module_imports.add(alias.asname or alias.name)
    if not module_imports:
        return source
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            new_body: list[ast.stmt] = []
            skip_next = False
            for i, stmt in enumerate(node.body):
                if skip_next:
                    skip_next = False
                    continue
                if isinstance(stmt, ast.Global):
                    to_remove_names: list[str] = []
                    for name in stmt.names:
                        if name in module_imports:
                            to_remove_names.append(name)
                    if to_remove_names == stmt.names and i + 1 < len(node.body):
                        next_stmt = node.body[i + 1]
                        if isinstance(next_stmt, ast.Import):
                            import_names = {a.asname or a.name for a in next_stmt.names}
                            if import_names == set(to_remove_names):
                                skip_next = True
                            elif import_names.issubset(set(to_remove_names)):
                                remaining = [a for a in next_stmt.names if (a.asname or a.name) not in to_remove_names]
                                if remaining:
                                    next_stmt.names = remaining
                                    new_body.append(next_stmt)
                                skip_next = True
                            else:
                                new_body.append(stmt)
                        else:
                            new_body.append(stmt)
                    else:
                        new_body.append(stmt)
                else:
                    new_body.append(stmt)
            node.body = new_body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _clean_hallucinated_code(source: str) -> str:
    source = _deduplicate_top_level(source)
    source = _cleanup_local_imports(source)
    return source


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logger = logging.getLogger("KillTriesApply")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


REPORT_FILE = pkg_root / "reports" / "kill_tries.json"

def save_checkpoint_item(item: dict):
    """Append single result item to CHECKPOINT_FILE."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")


def load_checkpoint() -> dict[str, dict]:
    completed = {}
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    key = f"{item['file_path']}:{item['function_name']}"
                    completed[key] = item
        logger.info(f"Loaded {len(completed)} entries from checkpoint JSONL.")

    if REPORT_FILE.exists():
        with open(REPORT_FILE, encoding="utf-8") as f:
            data = json.load(f)
            for item in data.get("approved", []):
                key = f"{item['file_path']}:{item['function_name']}"
                item["status"] = "APPROVED"
                if key not in completed:
                    completed[key] = item
        logger.info(f"Merged total {len(completed)} entries from report JSON.")

    return completed


def test_file_with_ruff(file_path: Path) -> tuple[bool, str]:
    import subprocess
    try:
        res = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "F821,E9,F63,F7", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return (res.returncode == 0, res.stdout + res.stderr)
    except Exception as e:
        return (False, str(e))


def find_relevant_test_file(rel_path: str) -> str | None:
    path_obj = Path(rel_path)
    stem = path_obj.stem.lower()
    test_dir = pkg_root / "TEST" / "unit"
    if not test_dir.exists():
        return None
    for p in test_dir.rglob("*.py"):
        p_stem = p.stem.lower().replace("test_", "")
        if stem == p_stem or stem in p_stem or p_stem in stem:
            return str(p.relative_to(pkg_root))
    return None


def test_suite_with_pytest(rel_path: str | None = None) -> bool:
    """Run unit test suite for relevant test file if it exists."""
    if not rel_path:
        test_target = "TEST/unit/"
    else:
        rel_test = find_relevant_test_file(rel_path)
        if not rel_test:
            logger.info(f"   ℹ️ No relevant unit test file found for {rel_path} in TEST/unit/. Skipping pytest gate.")
            return True
        test_target = rel_test

    import subprocess
    try:
        res = subprocess.run(
            ["uv", "run", "pytest", test_target],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def apply_checkpoint_to_files(approved_items: list[dict], allow_engine: bool = False, skip_pytest: bool = False) -> int:
    """Apply a specific list of APPROVED refactorings to source files in src2/."""
    if not approved_items:
        return 0

    by_file = defaultdict(list)
    for item in approved_items:
        by_file[item["file_path"]].append(item)

    applied_count = 0
    for rel_path, items in by_file.items():
        if not allow_engine and (rel_path.startswith("src2/engine/") or "src2/engine/" in rel_path):
            logger.info(f"🛡️ Engine read-only policy: Skipping apply to {rel_path} (use --allow-engine to override)")
            continue
        file_path = pkg_root / rel_path
        if not file_path.exists():
            logger.warning(f"File not found: {rel_path}")
            continue

        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except Exception as e:
            logger.error(f"Cannot parse {rel_path}: {e}")
            continue

        lines = source.splitlines()
        file_modified = False
        all_ref_codes = []
        all_helpers_for_file = []
        applied_targets = 0

        for item in items:
            fname = item["function_name"]
            ref_code = item["refactored_code"].rstrip()
            helpers = item.get("helper_functions", [])

            # Re-parse current lines to get fresh AST and line numbers
            current_source = "\n".join(lines)
            try:
                tree = ast.parse(current_source)
            except Exception as e:
                logger.error(f"Cannot parse current state of {rel_path}: {e}")
                continue

            target_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fname:
                    target_node = node
                    break

            if not target_node:
                logger.warning(f"Function {fname} not found in current AST of {rel_path}")
                continue

            lines_backup = list(lines)
            try:
                buf = VirtualASTBuffer("\n".join(lines) + "\n", str(rel_path))
                test_source = buf.replace_function(fname, ref_code, helpers)
                test_source = ensure_pydantic_imports(test_source, ref_code + ("\n\n" + "\n\n".join(h.rstrip() for h in helpers) if helpers else ""))
                lines = test_source.splitlines()
            except Exception as e:
                logger.error(f"Failed to replace function {fname} via VirtualASTBuffer: {e}")
                continue

            try:
                ast.parse(test_source)
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py")
                try:
                    with open(tmp_path, "w", encoding="utf-8") as _tf:
                        _tf.write(test_source)
                    passed, ruff_out = test_file_with_ruff(Path(tmp_path))
                    if passed:
                        all_ref_codes.append(ref_code + ("\n\n" + "\n\n".join(h.rstrip() for h in helpers) if helpers else ""))
                        if helpers:
                            all_helpers_for_file.extend(helpers)
                        file_modified = True
                        applied_targets += 1
                        applied_count += 1
                        logger.info(f"   ✅ Applied {fname} in {rel_path}")
                    else:
                        lines = lines_backup
                        logger.warning(f"   ⚠️ Ruff check failed for {fname} in {rel_path}: {ruff_out.strip()}. Skipping this refactoring.")
                        fail_item = dict(item)
                        fail_item["status"] = "FAILED_RUNTIME"
                        fail_item["verification_msg"] = f"Ruff check failed for {fname} in {rel_path}:\n{ruff_out.strip()}"
                        save_checkpoint_item(fail_item)
                finally:
                    os.unlink(tmp_path)
            except Exception as e:
                lines = lines_backup
                logger.error(f"   ❌ AST verification failed for {fname} in {rel_path}: {e}. Skipping.")
                fail_item = dict(item)
                fail_item["status"] = "FAILED_RUNTIME"
                fail_item["verification_msg"] = f"AST verification failed for {fname} in {rel_path}: {e}"
                save_checkpoint_item(fail_item)

        if file_modified:
            new_source = "\n".join(lines) + "\n"
            new_source = _clean_hallucinated_code(new_source)
            try:
                ast.parse(new_source)
                if not verify_class_structure_intact(source, new_source):
                    logger.warning(f"⚠️ Class structure verification failed for {rel_path}. Reverting file.")
                    file_path.write_text(source, encoding="utf-8")
                else:
                    file_path.write_text(new_source, encoding="utf-8")
                    if not skip_pytest:
                        logger.info(f"⏳ Running Pytest integration checks for {rel_path}...")
                        if not test_suite_with_pytest(rel_path):
                            logger.warning(f"⚠️ Pytest integration check failed after applying {rel_path}. Reverting file changes.")
                            file_path.write_text(source, encoding="utf-8")
                            for item in items:
                                fail_item = dict(item)
                                fail_item["status"] = "FAILED_RUNTIME"
                                fail_item["verification_msg"] = f"Pytest integration check failed for {rel_path} after applying helper extractions."
                                save_checkpoint_item(fail_item)
                        else:
                            logger.info(f"✅ Successfully wrote {applied_targets} refactored function(s) to {rel_path} and passed Pytest gate.")
                    else:
                        logger.info(f"✅ Successfully wrote {applied_targets} refactored function(s) to {rel_path} (Pytest gate skipped via --skip-pytest).")
            except Exception as e:
                file_path.write_text(source, encoding="utf-8")
                logger.error(f"❌ Failed AST verification after modifying {rel_path}: {e}. Reverting file changes.")

    return applied_count


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply approved kill-tries refactorings to src2/ with per-function ruff validation."
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Filter for a specific file path (e.g. src2/engine/coordinator.py)",
    )
    parser.add_argument(
        "--allow-engine",
        action="store_true",
        help="Allow applying approved refactorings to src2/engine/ files",
    )
    parser.add_argument(
        "--skip-pytest",
        "--no-pytest",
        action="store_true",
        dest="skip_pytest",
        help="Skip Pytest integration check (useful when full suite has pre-existing errors)",
    )
    args = parser.parse_args()

    checkpoint = load_checkpoint()
    all_approved = [v for v in checkpoint.values() if v.get("status") == "APPROVED"]
    if not all_approved:
        logger.info("No APPROVED refactorings found in checkpoint.")
        return

    filter_rel_path = args.file
    display = [v for v in all_approved if not filter_rel_path or v.get("file_path") == filter_rel_path]
    if not display:
        logger.info(f"No APPROVED refactorings found for filter: {filter_rel_path}")
        return

    logger.info(f"Applying {len(display)} approved refactorings to src2/...")
    applied_count = apply_checkpoint_to_files(display, allow_engine=args.allow_engine, skip_pytest=args.skip_pytest)
    logger.info(f"Done. Applied {applied_count} refactoring(s).")


if __name__ == "__main__":
    main()
