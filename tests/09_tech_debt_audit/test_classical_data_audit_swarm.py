import os
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parents[2].resolve()
sys.path.append(str(project_root))

# LOCAL GEMINI CONFIGURATION
LOCAL_ENDPOINT = "http://localhost:18000/v1/chat/completions"
MODEL_NAME = "gemini-3.1-flash-lite"

# Debt Keywords to Audit
DEBT_KEYWORDS = ["BUG", "TODO", "FIXME", "HACK"]

class ProjectWideAuditor:
    """
    Scans the entire src/ directory for technical debt markers and
    prepares a verification report for the local Gemini model.
    """

    def __init__(self, search_dir: str):
        self.search_dir = Path(search_dir)
        self.report_path = project_root / "TEST" / "tech_debt" / "reports" / "project_debt_audit.md"
        self.results = {}

    def scan_project(self):
        """Recursively scans for debt markers in Python files."""
        print(f"Scanning directory: {self.search_dir}")

        for root, _, files in os.walk(self.search_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    self.scan_file(file_path)

    def scan_file(self, file_path: Path):
        """Identifies markers and captures context."""
        rel_path = file_path.relative_to(project_root)
        file_markers = []

        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                # Check for any of the keywords
                found_keyword = next((k for k in DEBT_KEYWORDS if k in line), None)
                if found_keyword:
                    # Capture 5 lines of context before and after
                    start_ctx = max(0, i - 2)
                    end_ctx = min(len(lines), i + 3)
                    context = "".join(lines[start_ctx:end_ctx])

                    file_markers.append({
                        "line": i + 1,
                        "keyword": found_keyword,
                        "content": line.strip(),
                        "context": context
                    })

            if file_markers:
                self.results[str(rel_path)] = file_markers

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

    def write_report(self):
        """Generates the project-wide audit report."""
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write("# Project-Wide Technical Debt Audit\n")
            f.write(f"Generated: {Path(__file__).name}\n")
            f.write(f"Scan Directory: `{self.search_dir.relative_to(project_root)}`\n\n")

            f.write("## Executive Summary\n")
            total_markers = sum(len(m) for m in self.results.values())
            f.write(f"- **Total Files with Debt**: {len(self.results)}\n")
            f.write(f"- **Total Markers Found**: {total_markers}\n")
            f.write("- **Verification Target**: Local Gemini (`v1`)\n\n")

            f.write("## Detailed Audit Log\n")
            for file_path, markers in self.results.items():
                f.write(f"### `{file_path}`\n")
                for m in markers:
                    f.write(f"#### L{m['line']} [{m['keyword']}]\n")
                    f.write(f"**Marker**: `{m['content']}`\n")
                    f.write("**Context**:\n")
                    f.write(f"```python\n{m['context']}```\n")
                    f.write("**Verification Action**:\n")
                    f.write("- [ ] Verify classical citations (if applicable)\n")
                    f.write("- [ ] Logic check for falsy-dict traps\n")
                    f.write("- [ ] Regression check with `test_bug_repro_suite.py`\n\n")
                f.write("---\n\n")

if __name__ == "__main__":
    src_dirs = [project_root / "src", project_root / "alt_src"]
    auditor = ProjectWideAuditor(str(project_root / "src")) # Dummy for backward compat

    # Actually use a list of directories
    print("--- Starting Multi-Directory Scan ---")
    for d in src_dirs:
        if d.exists():
            auditor.search_dir = d
            auditor.scan_project()

    print("--- Writing Report ---")
    auditor.write_report()
    print(f"Audit report generated: {auditor.report_path}")
