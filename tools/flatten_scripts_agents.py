#!/usr/bin/env python3
"""
Automated Python Code Flattener (Concurrent AST Pipeline + Pyright Post-Pass).

Hyper-fast pipeline:
  Phase 1 — Concurrent Fast Loop (ThreadPoolExecutor):
    1. Ruff (SIM, RET, UP, F, ERA) — auto-fixes nesting, early returns,
       modern syntax, dead code, and unused vars/imports.
    2. Refurb — static analysis for simplifiable constructs (reports only).
    3. ast.parse — in-process syntax validation in microseconds.
    4. ruff format — normalizes final style on changed files.
  Phase 2 — Pyright Post-Pass (BULK):
    Pyright has a 1-2s Node.js cold-start per invocation. Running it
    per-file (214×) makes the pipeline crawl. Instead, ONE pyright
    --outputjson runs on ALL modified files at once. Broke files are
    auto-reverted and their errors added to the JSON handoff.
  Phase 3 — JSON Handoff:
    Unfixed Ruff/Refurb issues and Pyright failures are collected into
    flatten_scripts_agents.json for your IDE's RAM-loaded LLM to handle.

Thread-safe output: logs are batched per-file inside FileResult and printed
via as_completed(), so the terminal stays clean and readable.

Fails LOUDLY on bad config / missing tools.
"""
import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SCOPE = os.environ.get("KIT_SOURCE_ROOT", "src")
JSON_REPORT_FILE = "flatten_scripts_agents.json"

# ==========================================
# CONDITION C: TOOL CONFIG
# ==========================================
RUFF_CMD = ["ruff", "check", "--select", "SIM,RET,UP,F,ERA", "--fix"]
RUFF_FORMAT_CMD = ["ruff", "format"]
REFURB_CMD = ["refurb"]
PYRIGHT_CMD = ["pyright"]


# ==========================================
# DATA MODEL
# ==========================================
@dataclass
class FileResult:
    """Batches per-file output so thread-safe printing stays clean."""
    path: Path
    status: str = "skipped"
    needs_llm: bool = False
    issues: str = ""
    logs: list[str] = field(default_factory=list)
    original_code: str = ""


# ==========================================
# WORKFLOW FUNCTIONS
# ==========================================
def check_tools_available() -> None:
    """FAIL LOUDLY if a required tool is missing before starting the pool."""
    for cmd in [RUFF_CMD, RUFF_FORMAT_CMD, REFURB_CMD, PYRIGHT_CMD]:
        tool_name = cmd[0]
        if shutil.which(tool_name) is None:
            print(
                f"🚨 FATAL: Required tool '{tool_name}' is not installed or not on PATH.",
                file=sys.stderr,
            )
            sys.exit(1)


def process_file(file_path: Path, dry_run: bool, idx: int, total: int) -> FileResult:
    """The concurrent fast-pipeline executed per-file inside a thread.

    Layers 1-3 (Ruff, Refurb, ast.parse) run per-file concurrently.
    Layer 4 (Pyright) runs ONCE in bulk after the pool finishes (see main()).

    Returns a FileResult with logs, status, and any issues needing LLM attention.
    """
    res = FileResult(path=file_path)
    res.logs.append(f"🔍 [{idx}/{total}] --- Processing: {file_path.name} ---")

    # Read original code FIRST — needed for Pyright post-pass revert + ast.parse compare.
    with open(file_path, encoding="utf-8") as f:
        original_code = f.read()
    res.original_code = original_code

    if dry_run:
        res.logs.append(f"  🧪 [DRY RUN] Would execute Ruff & Refurb on {file_path.name}.")
        res.status = "dry_run"
        return res

    # --- Layer 1: Ruff (SIM, RET, UP, F, ERA) ---
    ruff_res = subprocess.run(
        RUFF_CMD + [str(file_path)],
        capture_output=True, text=True,
    )
    # Ruff exits 1 when unfixed issues remain — collect them for the LLM handoff.
    if ruff_res.returncode != 0 and ruff_res.stdout.strip():
        res.needs_llm = True
        res.issues += f"--- Ruff Unfixed Issues ---\n{ruff_res.stdout.strip()}\n\n"

    # --- Layer 2: Refurb (reports only) ---
    refurb_res = subprocess.run(
        REFURB_CMD + [str(file_path)],
        capture_output=True, text=True,
    )
    if refurb_res.stdout.strip():
        res.needs_llm = True
        res.issues += f"--- Refurb Suggestions ---\n{refurb_res.stdout.strip()}\n\n"

    # Check if ruff actually changed the file.
    with open(file_path, encoding="utf-8") as f:
        refactored_code = f.read()

    if original_code == refactored_code:
        res.logs.append("  ⏭️  [SKIP] AST tools made no changes. Code is already flat/clean.")
        res.status = "skipped"
        return res

    # --- Layer 3: ast.parse — validate syntax in microseconds ---
    try:
        ast.parse(refactored_code)
        res.logs.append("  ✅ [SYNTAX] ast.parse passed.")
    except SyntaxError as e:
        res.logs.append("  🚨 [FATAL] Ruff generated invalid Python syntax! Reverting.")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_code)
        res.status = "error"
        res.needs_llm = True
        res.issues += f"--- AST Syntax Error ---\n{e}\n"
        return res

    # --- Layer 4: ruff format — normalize style (Pyright runs in post-pass) ---
    subprocess.run(
        RUFF_FORMAT_CMD + [str(file_path)],
        capture_output=True, text=True,
    )
    res.logs.append("  🎨 [FORMAT] ruff format applied.")
    res.logs.append(f"  ✨ [SUCCESS] Updated {file_path.name} with flattened code.")
    res.status = "modified"

    if res.needs_llm:
        res.logs.append("  📝 [LLM QUEUE] Unfixed complexities tagged for IDE LLM.")

    return res


# ==========================================
# CONDITION D & B: CLI FLAGS & DRY FUNCTION
# ==========================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightning Fast Concurrent Python Code Flattener."
    )

    # --- Scope ---
    parser.add_argument(
        "--scope",
        type=str,
        default=DEFAULT_SCOPE,
        help=f"Only process files under this subdir within --folder (default: {DEFAULT_SCOPE}).",
    )

    # --- Standard flags ---
    parser.add_argument("-f", "--file", type=str, help="Specific python file to flatten.")
    parser.add_argument(
        "-d", "--folder", type=str, help="Folder containing python files to flatten."
    )
    parser.add_argument(
        "--dry",
        action="store_true",
        help="Run in dry mode (no files will be changed).",
    )

    args = parser.parse_args()

    # Unbuffered output: concurrent threads need real-time terminal feedback.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    # Validate inputs
    if not args.file and not args.folder:
        parser.print_help()
        print("\nError: You must specify either --file or --folder.")
        sys.exit(1)

    # Fail LOUDLY if tools are missing — before touching any files.
    check_tools_available()

    # Build target list
    targets: list[Path] = []

    if args.file:
        p = Path(args.file)
        if p.is_file() and p.suffix == ".py":
            targets.append(p)
        else:
            print(f"Error: {args.file} is not a valid Python file.")
            sys.exit(1)

    if args.folder:
        p = Path(args.folder)
        if not p.is_dir():
            print(f"Error: {args.folder} is not a valid directory.")
            sys.exit(1)
        all_files = list(p.rglob("*.py"))
        if args.scope:
            scope_dir = p / args.scope
            targets.extend(
                f for f in all_files if f.is_relative_to(scope_dir)
            )
        else:
            targets.extend(all_files)

    if not targets:
        print("No Python files matched the given file/folder/scope.")
        sys.exit(1)

    total_files = len(targets)
    print(f"\n📂 [CONFIG] Found {total_files} file(s) to process.")

    if args.dry:
        print("========== 🧪 DRY RUN MODE INITIATED ==========")
        print("No files will be modified. Checking target queue...\n")
        # Dry run is fast enough to stay serial — no subprocess overhead needed.
        stats = {"modified": 0, "skipped": 0, "dry_run": 0, "error": 0}
        for idx, target in enumerate(targets, start=1):
            res = process_file(target, args.dry, idx, total_files)
            print("\n".join(res.logs))
            stats[res.status] += 1
        _print_report(stats, total_files, args.dry, [], [])
        return

    print("🚀 Firing off concurrent workers...\n")

    # CONCURRENT EXECUTION
    # subprocess.run releases the GIL, so ThreadPool gives near-linear speedup.
    max_workers = min(8, os.cpu_count() or 4)
    stats: dict[str, int] = {"modified": 0, "skipped": 0, "dry_run": 0, "error": 0}
    llm_queue: list[dict] = []
    processed: list[str] = []

    all_results: list[FileResult] = []
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_file, t, args.dry, i, total_files): t
                for i, t in enumerate(targets, start=1)
            }

            # as_completed yields files the instant they finish — no blocking.
            for future in as_completed(futures):
                res: FileResult = future.result()
                all_results.append(res)
                # Thread-safe — print each file's batched logs atomically.
                print("\n".join(res.logs))
                stats[res.status] += 1
                processed.append(res.path.name)
                if res.needs_llm:
                    llm_queue.append({
                        "file": str(res.path),
                        "issues": res.issues,
                    })
    except KeyboardInterrupt:
        print("\n🚨 Pipeline interrupted by user!")

    # ==========================================
    # THE PYRIGHT POST-PASS (BULK EXECUTION)
    # ==========================================
    # Pyright has a 1-2s Node.js cold-start PER invocation. Running it
    # per-file (214×) is what made the original script crawl.
    # Instead, we fire off ONE pyright --outputjson on ALL modified files.
    # Pyright boots Node once, loads stubs once, checks all files, returns JSON.
    if not args.dry and all_results:
        modified_paths = [r.path for r in all_results if r.status == "modified"]
        if modified_paths:
            print(f"\n🛡️  [TYPE CHECK] Bulk Pyright scan on {len(modified_paths)} modified file(s)...")
            pyright_cmd = ["pyright", "--outputjson"] + [str(p) for p in modified_paths]
            pyright_res = subprocess.run(pyright_cmd, capture_output=True, text=True)

            try:
                pyright_data = json.loads(pyright_res.stdout)
                diagnostics = pyright_data.get("generalDiagnostics", [])

                # Map errors by file path (only "error" severity — ignore warnings)
                errors_by_file: dict[str, list[str]] = {}
                for diag in diagnostics:
                    if diag.get("severity") == "error":
                        fpath = diag.get("file", "")
                        msg = diag.get("message", "")
                        errors_by_file.setdefault(fpath, []).append(msg)

                # Revert files that broke + queue for IDE LLM
                for fpath_str, errors in errors_by_file.items():
                    res_match = next((r for r in all_results if str(r.path) == fpath_str), None)
                    if res_match:
                        print(f"  🚨 [PYRIGHT FATAL] Type error introduced in {res_match.path.name}. Reverting!")
                        with open(res_match.path, "w", encoding="utf-8") as f:
                            f.write(res_match.original_code)
                        stats["modified"] -= 1
                        stats["error"] += 1
                        res_match.status = "error"
                        res_match.needs_llm = True
                        res_match.issues += "--- Pyright Post-Pass Errors ---\n" + "\n".join(errors) + "\n\n"
                        llm_queue.append({
                            "file": str(res_match.path),
                            "issues": "--- Pyright Post-Pass Errors ---\n" + "\n".join(errors),
                        })
                    else:
                        print(f"  🚨 [PYRIGHT FATAL] Error in unknown file: {fpath_str}")

                if not errors_by_file:
                    print("  ✅ [TYPE CHECK] All modified files passed Pyright — no type/scoping errors.")
                else:
                    ok_count = len(modified_paths) - len(errors_by_file)
                    print(f"  ✅ {ok_count} file(s) passed. {len(errors_by_file)} file(s) reverted.")

            except json.JSONDecodeError:
                print(f"  ⚠️  [PYRIGHT] Failed to parse JSON output. stdout: {pyright_res.stdout[:500]}")

    # ALWAYS print the report (even on interrupt) via shared helper.
    _print_report(stats, total_files, args.dry, llm_queue, processed)


def _print_report(
    stats: dict[str, int],
    total_files: int,
    dry_run: bool,
    llm_queue: list[dict],
    processed: list[str],
) -> None:
    """Print the final status report and dump JSON handoff if needed."""
    print("\n" + "=" * 50)
    print("📊 FLATTENER PIPELINE STATUS REPORT")
    print("=" * 50)
    print(f"  Total Files Scanned   : {total_files}")
    print(f"  ✨ Successfully Fixed  : {stats['modified']}")
    print(f"  ⏭️  Skipped (Clean)     : {stats['skipped']}")
    print(f"  🚨 Syntax Errors       : {stats['error']}")
    if dry_run:
        print(f"  🧪 Dry Run Evaluated  : {stats['dry_run']}")
    print("-" * 50)
    if llm_queue and not dry_run:
        with open(JSON_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(llm_queue, f, indent=2)
        print(f"  📝 IDE HANDOFF: {len(llm_queue)} file(s) queued for LLM.")
        print(f"     Saved to -> {JSON_REPORT_FILE}")
    elif stats["modified"] > 0:
        print("  🎉 RESULT: ALL FILES PROCESSED SUCCESSFULLY")
    elif dry_run:
        print("  ✅ RESULT: DRY RUN COMPLETE")
    else:
        print("  ✅ RESULT: CODEBASE IS ALREADY FLAT")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
