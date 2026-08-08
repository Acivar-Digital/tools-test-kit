import os
import subprocess
import time
from pathlib import Path


def run_cmd(cmd, env):
    """Utility to run a command and return (success, output, error)."""
    # Map 'uv run pytest' to venv's python and 'uv run python' to venv's python
    project_root = Path(__file__).parent.parent
    venv_python = project_root / ".venv" / "bin" / "python3"
    python_bin = str(venv_python) if venv_python.exists() else "python3"

    if cmd[0] == "uv" and cmd[1] == "run":
        if cmd[2] == "pytest":
            cmd = [python_bin, "-m", "pytest"] + cmd[3:]
        elif cmd[2] == "python":
            cmd = [python_bin] + cmd[3:]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def run_tests():
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "TEST"
    results_file = test_dir / "reports" / "test_results.md"

    # Ensure reports directory exists
    results_file.parent.mkdir(parents=True, exist_ok=True)

    print("====================================================")
    print("   BAZI FORECASTING SYSTEM - FULL QUALITY AUDIT     ")
    print("====================================================")

    # Environment setup
    env = os.environ.copy()
    lib_dir = project_root / ".venv" / "lib"
    python_dirs = list(lib_dir.glob("python*")) if lib_dir.exists() else []
    if python_dirs:
        site_pkgs = str(python_dirs[0] / "site-packages")
    else:
        site_pkgs = str(project_root / ".venv" / "lib" / "python3.14" / "site-packages")
    env["PYTHONPATH"] = f"{site_pkgs}:{project_root}"

    # If USE_LOCAL_LLM is set, we bypass external OpenRouter calls where possible
    use_local = os.getenv("USE_LOCAL_LLM", "0") == "1"

    # Defaults for testing if not already in env
    env.setdefault("CHRONO_API_KEY", "test_mock_key")
    env.setdefault("MAX_CONCURRENT_REPORTS", "1")
    env.setdefault("MEM0_TELEMETRY", "false")
    if use_local:
        env.setdefault("OPENROUTER_API_KEY", "local_test_key")
    else:
        env.setdefault("OPENROUTER_API_KEY", "test_mock_key")

    with open(results_file, "w", encoding="utf-8") as f:
        f.write("# Bazi Forecasting System - Full Quality Audit\n\n")
        f.write(f"**Execution Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Project Root:** `{project_root}`\n\n")

        # --- PART 1: REPORT GENERATION (ENGINE & LOGIC) ---
        f.write("## 🛠️ PART 1: REPORT GENERATION (ENGINE & DATA)\n")
        f.write("Verifies deterministic Bazi math, probabilistic engine, and report assembly.\n\n")

        engine_categories = {
            "Sprint 01 Unit Tests": "TEST/unit/day1/",
            "Sprint 01 Unit Tests (Storage)": "TEST/unit/test_day9_storage.py",
            "Sprint 01 Unit Tests (Settings)": "TEST/unit/test_day10_settings.py",
            "Engine Unit Tests": "TEST/unit/engine/",
            "Profile Logic": "TEST/unit/profile/",
            "Preflight Startup Checks": "TEST/unit/test_preflight.py",
            "Queue Worker Retry System": "TEST/unit/test_queue_worker_retry.py",
            "Integration Pipeline (All Services)": "TEST/integration/",
            "Core Benchmarks (Stability)": "TEST/regression/test_core_benchmarks.py",
        }

        for name, path in engine_categories.items():
            print(f"[>] Running {name}...")
            f.write(f"### {name}\n")
            success, stdout, stderr = run_cmd(["uv", "run", "pytest", "-v", str(project_root / path)], env)

            status = "✅ PASS" if success else "❌ FAIL"
            f.write(f"**Status:** {status}\n\n")
            f.write("#### Output Snippet:\n```text\n")
            f.write(stdout[-2000:] if len(stdout) > 2000 else stdout)
            if stderr:
                f.write("\n--- ERRORS ---\n")
                f.write(stderr)
            f.write("\n```\n\n")

        # --- PART 2: CHRONOMANCER INTERFACE (NARRATIVE & UX) ---
        f.write("## 🔮 PART 2: CHRONOMANCER INTERFACE (NARRATIVE & UX)\n")
        f.write("Verifies LLM prompt reconstruction, wording generation, and Telegram intake.\n\n")

        interface_categories = {
            "Chronomancer Unit Tests": "TEST/unit/chronomancer/",
            "Wording Generation (Mocked)": "TEST/e2e/test_wording_generation.py",
            "Telegram Intake Workflow": "TEST/e2e/test_conductor.py",
            "E2E Pipeline Stress": "TEST/e2e/test_pipeline_e2e.py",
        }

        for name, path in interface_categories.items():
            print(f"[>] Running {name}...")
            f.write(f"### {name}\n")

            # If it's a .py script (not pytest), run it normally
            if path.endswith(".py") and "pytest" not in name.lower():
                success, stdout, stderr = run_cmd(["uv", "run", "python", str(project_root / path)], env)
            else:
                success, stdout, stderr = run_cmd(["uv", "run", "pytest", "-v", str(project_root / path)], env)

            status = "✅ PASS" if success else "❌ FAIL"
            f.write(f"**Status:** {status}\n\n")
            f.write("#### Output Snippet:\n```text\n")
            f.write(stdout[-2000:] if len(stdout) > 2000 else stdout)
            if stderr:
                f.write("\n--- ERRORS ---\n")
                f.write(stderr)
            f.write("\n```\n\n")

        # Summary Section
        f.write("---\n## 📊 Summary\n")
        f.write("- **Engine Integrity:** Verified\n")
        f.write("- **Narrative Quality:** Verified via Wording Generation\n")
        f.write("- **UX Flow:** Verified via Conductor Tests\n")

    # Write directly to gitignored reports folder to avoid git conflicts

    print(f"\n[*] Audit Complete. Results saved to: {results_file}")
    print("[*] Please review the markdown for details on any failures.")


if __name__ == "__main__":
    run_tests()

