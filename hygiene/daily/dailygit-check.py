import json
import os
import subprocess
import sys
from pathlib import Path

# ANSI colors for nice terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_exceptions(exceptions_path: Path) -> list[str]:
    if not exceptions_path.exists():
        return []
    try:
        with open(exceptions_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{YELLOW}Warning: Failed to load exceptions.json: {e}{RESET}")
        return []


def get_changed_files() -> list[str]:
    """Get files changed in unstaged, staged, or unpushed commits."""
    files = set()

    # 1. Staged and unstaged changes
    r1 = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True)
    if r1.returncode == 0:
        for line in r1.stdout.splitlines():
            if line.strip():
                files.add(line.strip())

    # 2. Unpushed commits compared to upstream
    r2 = subprocess.run(["git", "diff", "--name-only", "@{u}", "HEAD"], capture_output=True, text=True)
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            if line.strip():
                files.add(line.strip())

    # Fallback to HEAD~1 if no upstream or no changes found (local commit checks)
    if not files:
        r3 = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], capture_output=True, text=True)
        if r3.returncode == 0:
            for line in r3.stdout.splitlines():
                if line.strip():
                    files.add(line.strip())

    return sorted(list(files))


def main():
    print(f"{BOLD}🛡️ Running Code Hygiene Gatekeeper (dailygit-check)...{RESET}")

    # 1. Get changed files
    changed_files = get_changed_files()
    if not changed_files:
        print(f"{GREEN}✅ No changed files detected in this push. Bypassing check.{RESET}")
        sys.exit(0)

    # 2. Load exceptions
    exceptions_path = Path(__file__).parent.parent / "exceptions.json"
    exceptions = load_exceptions(exceptions_path)

    # Filter files: must be Python files in src2/ or kit-hygiene/ and not in exceptions
    files_to_scan = []
    for f in changed_files:
        path = Path(f)
        if path.suffix == ".py" and (f.startswith("src2/") or f.startswith("kit-hygiene/")):
            if f not in exceptions:
                files_to_scan.append(f)

    if not files_to_scan:
        print(f"{GREEN}✅ No non-excepted Python files modified. Bypassing scanners.{RESET}")
        sys.exit(0)

    print("📦 Files queued for hygiene audit:")
    for f in files_to_scan:
        print(f"  - {f}")

    # 3. Setup environment override for scanners
    env = os.environ.copy()
    env["HYGIENE_FILES_TO_SCAN"] = ",".join(files_to_scan)
    # Configure Pydantic AI models to use low-latency / non-thinking configurations
    env["google_thinking_level"] = "off"
    env["google_include_thoughts"] = "false"

    scanners = [
        "kit-hygiene/scanners/find_async_hazards.py",
        "kit-hygiene/scanners/find_circular_deps.py",
        "kit-hygiene/scanners/find_dead_code.py",
        "kit-hygiene/scanners/find_duplication.py",
        "kit-hygiene/scanners/find_env_drift.py",
        "kit-hygiene/scanners/find_secrets.py",
        "kit-hygiene/scanners/find_silent_killers.py",
        "kit-hygiene/scanners/find_type_safety.py",
        "kit-hygiene/scanners/find_message_drift.py",
    ]

    failed = False

    # Run each scanner
    for scanner in scanners:
        scanner_path = Path(scanner)
        if not scanner_path.exists():
            continue

        print(f"\n🚀 Running {scanner_path.name}...")
        res = subprocess.run(["uv", "run", "python", str(scanner_path)], env=env, capture_output=True, text=True)

        # Output log
        if res.returncode != 0:
            print(f"{RED}❌ Scanner {scanner_path.name} failed with exit code {res.returncode}:{RESET}")
            print(res.stderr)
            failed = True
        else:
            # Print standard output summary
            lines = res.stdout.splitlines()
            summary = [
                line for line in lines if any(x in line.lower() for x in ["found", "complete", "result", "saved"])
            ]
            for s in summary:
                print(f"  {s}")

    # 4. Check JSON reports for blocking violations
    reports_dir = Path("kit-hygiene/reports")
    if reports_dir.exists():
        # Check async hazards report
        async_report = reports_dir / "async_hazards_audit.json"
        if async_report.exists():
            try:
                with open(async_report, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("audit_results", []):
                    # Only block on high-severity async hazards
                    if item.get("status") == "ASYNC_HAZARD" and item.get("severity") == "HIGH":
                        if item.get("file_path") in files_to_scan:
                            print(
                                f"{RED}🚨 BLOCKING VIOLATION: High-severity Async Hazard found in {item.get('file_path')}:{item.get('line')} ({item.get('name')}){RESET}"
                            )
                            print(f"  Reason: {item.get('reason')}")
                            failed = True
            except Exception as e:
                print(f"{YELLOW}Warning: Failed to parse async hazards report: {e}{RESET}")

        # Check circular dependencies report
        circ_report = reports_dir / "circular_deps_audit.json"
        if circ_report.exists():
            try:
                with open(circ_report, encoding="utf-8") as f:
                    data = json.load(f)
                # If any circular deps are detected in scanned files, block
                for item in data.get("circular_dependencies", []):
                    involved_files = item.get("path", [])
                    if any(f in files_to_scan for f in involved_files):
                        print(
                            f"{RED}🚨 BLOCKING VIOLATION: Circular Dependency chain detected: {' -> '.join(involved_files)}{RESET}"
                        )
                        failed = True
            except Exception:
                pass

        # Check secrets report
        secrets_report = reports_dir / "secrets_audit.json"
        if secrets_report.exists():
            try:
                with open(secrets_report, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("findings", []):
                    if item.get("file_path") in files_to_scan:
                        print(
                            f"{RED}🚨 BLOCKING VIOLATION: Potential Secret/Credentials leaked in {item.get('file_path')}:{item.get('line')}{RESET}"
                        )
                        failed = True
            except Exception:
                pass

        # Check env drift report
        env_report = reports_dir / "env_drift_audit.json"
        if env_report.exists():
            try:
                with open(env_report, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("audit_results", []):
                    if item.get("status") == "DRIFT_VIOLATION" and item.get("severity") == "HIGH":
                        if item.get("file_path") in files_to_scan:
                            print(
                                f"{RED}🚨 BLOCKING VIOLATION: Environment Drift / Undocumented Variable found in {item.get('file_path')}:{item.get('line')} ({item.get('name')}){RESET}"
                            )
                            print(f"  Reason: {item.get('reason')}")
                            failed = True
            except Exception as e:
                print(f"{YELLOW}Warning: Failed to parse env drift report: {e}{RESET}")

    if failed:
        print(f"\n{RED}❌ Git push rejected: Code hygiene audit failed. Please fix the violations listed above.{RESET}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✅ All code hygiene audits passed successfully! Proceeding with push.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
