import subprocess
import sys
from pathlib import Path


def run_test_script(script_name):
    print(f"--- Running {script_name} ---")
    result = subprocess.run(["uv", "run", "python", str(Path(__file__).parent / f"{script_name}.py")],
                            capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"Errors in {script_name}:\n{result.stderr}")

    # Count PASS and FAIL in output
    pass_count = result.stdout.count("PASS")
    fail_count = result.stdout.count("FAIL")
    return pass_count, fail_count

def main():
    test_scripts = [
        "test_discovery",
        "test_modifications",
        "test_knowledge",
        "test_indexing"
    ]

    summary = []
    total_pass = 0
    total_fail = 0

    for script in test_scripts:
        p, f = run_test_script(script)
        summary.append((script, p, f))
        total_pass += p
        total_fail += f

    print("\n" + "="*40)
    print(f"{'Script':<25} | {'Pass':<5} | {'Fail':<5}")
    print("-" * 40)
    for script, p, f in summary:
        print(f"{script:<25} | {p:<5} | {f:<5}")
    print("-" * 40)
    print(f"{'TOTAL':<25} | {total_pass:<5} | {total_fail:<5}")
    print("="*40)

    if total_fail > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
