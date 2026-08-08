import os
import re
from pathlib import Path

# Thresholds from tech_debt_scanner.py logic
OVERSIZED_THRESHOLD = 500
DEEP_NESTING_THRESHOLD = 5

class DebtVerifier:
    """
    Verifies that the technical debt items reported in the latest scan are real.
    """

    def __init__(self, report_path: str):
        self.report_path = Path(report_path)
        # Resolve the project root dynamically (two levels up from TEST/tech_debt)
        self.project_root = Path(__file__).parents[2].resolve()
        self.verification_results = []

    def normalize_path(self, path_str: str) -> Path:
        """Normalizes file paths from the report to local OS paths."""
        # Remove backticks and normalize separators
        clean_path = path_str.strip("`").replace("\\", os.sep).replace("/", os.sep)
        # Handle cases where path might already be absolute or relative
        p = Path(clean_path)
        if p.is_absolute():
            return p
        return self.project_root / clean_path

    def get_indentation_level(self, line: str) -> int:
        """Calculates indentation level based on 4-space tabs."""
        leading_spaces = len(line) - len(line.lstrip())
        return leading_spaces // 4

    def verify(self):
        if not self.report_path.exists():
            print(f"Error: Report not found at {self.report_path}")
            return

        print(f"--- Verifying Tech Debt Report: {self.report_path.name} ---")

        with open(self.report_path, encoding="utf-8") as f:
            content = f.read()

        # Extract Top Offenders sections
        offenders = re.findall(r"### `(.*?)` \(Score: \d+\)\n(.*?)(?=\n### |$)", content, re.DOTALL)

        for file_rel_path, details in offenders:
            full_path = self.normalize_path(file_rel_path)
            print(f"\nChecking: {file_rel_path}")

            if not full_path.exists():
                print(f"  [MISSING] File does not exist: {full_path}")
                continue

            # Check Structural Debt
            try:
                with open(full_path, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"  [ERROR] Could not read file: {e}")
                continue

            line_count = len(lines)
            max_nesting = 0
            for line in lines:
                if line.strip():
                    nesting = self.get_indentation_level(line)
                    if nesting > max_nesting:
                        max_nesting = nesting

            # Verify Oversized
            if "⚠️ File is oversized" in details:
                if line_count > OVERSIZED_THRESHOLD:
                    print(f"  [VERIFIED] Oversized: {line_count} lines (Threshold: {OVERSIZED_THRESHOLD})")
                else:
                    print(f"  [RESOLVED?] Not oversized: {line_count} lines")

            # Verify Deep Nesting
            if "⚠️ Deep nesting detected" in details:
                if max_nesting >= DEEP_NESTING_THRESHOLD:
                    print(f"  [VERIFIED] Deep nesting: Level {max_nesting} (Threshold: {DEEP_NESTING_THRESHOLD})")
                else:
                    print(f"  [RESOLVED?] Nesting level: {max_nesting}")

            # Verify Markers
            # Match markers like: - L491 [TODO]: "core_elements": ["Metal"],  # TODO: Verify core_elements from classical source
            # The regex needs to be careful with quotes and trailing content
            marker_pattern = r"- L(\d+) \[(.*?)\]: \"(.*?)\""
            markers = re.findall(marker_pattern, details)

            for lnum_str, tag, snippet in markers:
                lnum = int(lnum_str)
                if lnum <= len(lines):
                    actual_line = lines[lnum - 1].strip()
                    # Check if snippet or tag is in the line (snippet might be truncated in report)
                    # We check if the snippet provided in the report matches a portion of the line
                    if tag in actual_line and snippet.split('#')[0].strip() in actual_line:
                        print(f"  [VERIFIED] Marker L{lnum} [{tag}]: Found matching content.")
                    else:
                        print(f"  [MISMATCH] Marker L{lnum} [{tag}]: Expected snippet not found.")
                        print(f"    Expected: {snippet}")
                        print(f"    Actual:   {actual_line}")
                else:
                    print(f"  [OUT_OF_BOUNDS] Marker L{lnum} [{tag}]: File only has {len(lines)} lines.")

if __name__ == "__main__":
    # Automatically target the latest report in the reports directory
    current_dir = Path(__file__).parent
    report_dir = current_dir / "reports"

    if not report_dir.exists():
        # Fallback to the root tech_debt folder if no reports dir exists
        latest_report = current_dir / "test_debt_report.md"
    else:
        # Find the latest .md file in the reports directory
        reports = sorted(report_dir.glob("tech_debt_*.md"))
        if reports:
            latest_report = reports[-1]
        else:
            latest_report = current_dir / "test_debt_report.md"

    verifier = DebtVerifier(latest_report)
    verifier.verify()
