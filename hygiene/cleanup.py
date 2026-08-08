#!/usr/bin/env python3
"""
Codebase Hygiene Cleanup Automator (AST-First)
==============================================
Runs purely locally (0 tokens) to:
1. Auto-sync Environment Drift: Parses all os.getenv/os.environ usage in src2/
   and appends missing keys to .env.example.
2. Auto-strip Confirmed Dead Code: Reads dead_code_audit.json and surgically
   removes functions/classes marked as 'CONFIRMED_DEAD' using indentation-based block parsing.

Usage:
    uv run python kit-hygiene/cleanup.py
"""

import ast
import json
import re
import sys
from pathlib import Path

# Workspace root
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC2_DIR = ROOT_DIR / "src2"
ENV_EXAMPLE = ROOT_DIR / ".env.example"
DEAD_CODE_JSON = ROOT_DIR / "kit-hygiene" / "reports" / "dead_code_audit.json"


# =====================================================================
# PART 1: ENVIRONMENT DRIFT AUTO-SYNC
# =====================================================================
def sync_environment_drift():
    print("🔍 Scanning src2/ for environment variable usage...")
    env_vars = set()

    # Regex patterns for getenv and environ
    getenv_pattern = re.compile(r"os\.getenv\(\s*['\"]([A-Z0-9_]+)['\"]")
    environ_pattern = re.compile(r"os\.environ\[\s*['\"]([A-Z0-9_]+)['\"]")
    environ_get_pattern = re.compile(r"os\.environ\.get\(\s*['\"]([A-Z0-9_]+)['\"]")

    for py_file in SRC2_DIR.glob("**/*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            # Find all matches
            for m in getenv_pattern.finditer(content):
                env_vars.add(m.group(1))
            for m in environ_pattern.finditer(content):
                env_vars.add(m.group(1))
            for m in environ_get_pattern.finditer(content):
                env_vars.add(m.group(1))
        except Exception as e:
            print(f"  Warning reading {py_file}: {e}")

    if not env_vars:
        print("  No environment variables found in src2/.")
        return

    print(f"  Found {len(env_vars)} environment variables in use.")

    # Read .env.example
    if not ENV_EXAMPLE.exists():
        print(f"  Creating missing {ENV_EXAMPLE.name}")
        ENV_EXAMPLE.write_text("# Environment Template\n", encoding="utf-8")

    example_content = ENV_EXAMPLE.read_text(encoding="utf-8")
    existing_vars = set()
    for line in example_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            # Match VAR=value or VAR = value
            m = re.match(r"^([A-Z0-9_]+)\s*=", line)
            if m:
                existing_vars.add(m.group(1))
        elif line.startswith("#"):
            # Match commented out # VAR=
            m = re.match(r"^#\s*([A-Z0-9_]+)\s*=", line)
            if m:
                existing_vars.add(m.group(1))

    missing_vars = sorted(list(env_vars - existing_vars))

    if missing_vars:
        print(f"  Appending {len(missing_vars)} missing variables to .env.example...")
        with open(ENV_EXAMPLE, "a", encoding="utf-8") as f:
            f.write("\n# ── AUTO-SYNCED MISSING VARIABLES ───────────────────────────\n")
            for var in missing_vars:
                f.write(f"# {var}=\n")
        print("  .env.example updated successfully.")
    else:
        print("  ✅ .env.example is fully up-to-date. No environment drift detected.")


# =====================================================================
# PART 2: SURGICAL DEAD CODE STRIPPER
# =====================================================================
class LogTee:
    """Tee all prints to cleanup.log and stdout."""
    def __init__(self, log_path: Path):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def find_definition_node(tree: ast.AST, name: str, def_type: str) -> ast.AST | None:
    """Recursively search for the AST node defining the target function/class."""
    target_types = {
        "function": (ast.FunctionDef, ast.AsyncFunctionDef),
        "async_function": (ast.AsyncFunctionDef,),
        "class": (ast.ClassDef,)
    }.get(def_type, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))

    for node in ast.walk(tree):
        if isinstance(node, target_types) and node.name == name:
            return node
    return None


def strip_dead_code_block(file_path: Path, name: str, def_type: str) -> bool:
    """
    Surgically remove a function/class definition block from a file
    using AST end_lineno for perfect accuracy.
    """
    if not file_path.exists():
        print(f"  Warning: File {file_path} not found.")
        return False

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"  Error parsing AST for {file_path.name}: {e}")
        return False

    # Find target node
    node = find_definition_node(tree, name, def_type)
    if not node:
        print(f"  Warning: Could not locate AST node for {def_type} '{name}' in {file_path.name}.")
        return False

    # Get lines of the file
    lines = content.splitlines()

    # Determine bounds
    start_line = node.lineno
    # If decorators are present, start from the first decorator
    if hasattr(node, "decorator_list") and node.decorator_list:
        start_line = min(dec.lineno for dec in node.decorator_list)

    end_line = getattr(node, "end_lineno", start_line)

    start_idx = start_line - 1
    end_idx = end_line  # end_lineno is 1-indexed, inclusive, so end_idx matches the exclusive stop index

    # Post-clean trailing whitespace/newlines that might be left over
    # (e.g., if there's a trailing empty line right after the function block)
    while end_idx < len(lines) and not lines[end_idx].strip():
        end_idx += 1

    print(f"  Removing {def_type} '{name}' from {file_path.name} (Lines {start_idx + 1} to {end_idx})")

    # Delete the slice of lines
    new_lines = lines[:start_idx] + lines[end_idx:]

    # Save file
    file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Verify syntax compiler check
    try:
        ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        return True
    except Exception as e:
        print(f"  ❌ Syntax check failed after removing '{name}' from {file_path.name}: {e}")
        print("  Reverting changes...")
        file_path.write_text(content, encoding="utf-8")
        return False



def strip_dead_code():
    print("\n🔍 Checking dead_code_audit.json for CONFIRMED_DEAD candidates...")
    if not DEAD_CODE_JSON.exists():
        print(f"  Error: {DEAD_CODE_JSON} not found. Please run the scanner first.")
        return

    try:
        data = json.loads(DEAD_CODE_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  Error reading {DEAD_CODE_JSON}: {e}")
        return

    results = data.get("audit_results", [])
    dead_items = [r for r in results if r.get("status") == "CONFIRMED_DEAD"]

    if not dead_items:
        print("  No 'CONFIRMED_DEAD' code blocks found in the audit report.")
        return

    print(f"  Found {len(dead_items)} dead code blocks to remove.")
    success_count = 0

    for item in dead_items:
        name = item.get("name")
        file_path_str = item.get("file_path")
        def_type = item.get("type", "function")

        if not name or not file_path_str:
            continue

        file_path = ROOT_DIR / file_path_str
        if strip_dead_code_block(file_path, name, def_type):
            success_count += 1

    print(f"\n  Finished. Surgically removed {success_count}/{len(dead_items)} dead code blocks.")


def main():
    log_dir = ROOT_DIR / "kit-hygiene"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "cleanup.log"

    # Enable Tee logging
    tee = LogTee(log_path)
    sys.stdout = tee

    print("🧹 Starting Codebase Hygiene Cleanup Pipeline (Phase 1)...")
    print("=" * 60)

    try:
        # 1. Sync environment drift variables
        sync_environment_drift()

        # 2. Surgically strip confirmed dead code
        strip_dead_code()

        print("\n✅ Phase 1 Cleanup Completed.")
    finally:
        sys.stdout = tee.terminal
        tee.log.close()


if __name__ == "__main__":
    main()

