import subprocess
import sys
from pathlib import Path


def main():
    print("=== Running Narrative Drift Analysis ===")
    gold_dir = Path(__file__).resolve().parent
    ui_files = list(gold_dir.glob("*/UI.md"))

    has_drift = False
    for ui_file in ui_files:
        # Run git diff against the index for the UI.md file
        res = subprocess.run(
            ["git", "diff", "--color=never", str(ui_file)],
            capture_output=True,
            text=True
        )
        if res.stdout.strip():
            print(f"\n⚠️ Narrative drift detected in {ui_file.relative_to(gold_dir.parent.parent)}:")
            print(res.stdout)
            has_drift = True

    if has_drift:
        print("\n❌ Narrative drift check FAILED. Please review the changes above.")
        sys.exit(1)
    else:
        print("\n✅ No narrative drift detected. All outputs match the gold standard.")
        sys.exit(0)

if __name__ == "__main__":
    main()
