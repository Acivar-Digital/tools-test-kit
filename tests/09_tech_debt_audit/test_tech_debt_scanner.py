import os
import re
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".gemini", "artifacts", "dist", "build"}
EXCLUDE_EXTENSIONS = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".json", ".md", ".txt", ".yaml", ".yml", ".log", ".sql", ".sqlite",
    ".dylib", ".so", ".dll", ".exe", ".bin", ".zip", ".tar", ".gz"
}
DEBT_KEYWORDS = ["TODO", "FIXME", "HACK", "XXX", "BUG"]
FILE_SIZE_THRESHOLD = 500  # Lines
INDENT_THRESHOLD = 4      # Tab/Space levels
# Updated to point to TEST directory
REPORT_DIR = Path(__file__).parent / "reports"

class TechDebtScanner:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        # Compile regex for keywords with word boundaries to avoid 'DEBUG' matching 'BUG'
        self.keyword_regex = re.compile(r"\b(" + "|".join(DEBT_KEYWORDS) + r")\b", re.IGNORECASE)
        self.results = {
            "summary": {
                "total_files_scanned": 0,
                "total_debt_markers": 0,
                "oversized_files": 0,
                "total_score": 0
            },
            "files": []
        }

    def _is_binary(self, file_path: Path) -> bool:
        """Check if a file is binary by looking for null bytes."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True

    def _get_indent_depth(self, line: str) -> int:
        leading_spaces = len(line) - len(line.lstrip())
        # Detect tabs vs spaces
        if line.startswith("\t"):
            return len(line) - len(line.lstrip("\t"))
        return leading_spaces // 4

    def scan_file(self, file_path: Path):
        # Only scan Python files for technical debt markers
        if file_path.suffix.lower() != ".py":
            return
        if self._is_binary(file_path):
            return

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        self.results["summary"]["total_files_scanned"] += 1
        file_debt = {
            "path": str(file_path.relative_to(self.root_dir)),
            "markers": [],
            "oversized": len(lines) > FILE_SIZE_THRESHOLD,
            "max_indent": 0,
            "score": 0
        }

        for i, line in enumerate(lines, 1):
            # Keyword matching with regex
            matches = self.keyword_regex.findall(line)
            for match in matches:
                file_debt["markers"].append({"line": i, "type": match.upper(), "content": line.strip()})
                file_debt["score"] += 10

            # Indentation depth
            depth = self._get_indent_depth(line)
            if depth > file_debt["max_indent"]:
                file_debt["max_indent"] = depth

        if file_debt["oversized"]:
            self.results["summary"]["oversized_files"] += 1
            file_debt["score"] += 20

        if file_debt["max_indent"] > INDENT_THRESHOLD:
            file_debt["score"] += (file_debt["max_indent"] - INDENT_THRESHOLD) * 5

        if file_debt["score"] > 0:
            self.results["summary"]["total_debt_markers"] += len(file_debt["markers"])
            self.results["summary"]["total_score"] += file_debt["score"]
            self.results["files"].append(file_debt)

    def generate_report(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"tech_debt_{timestamp}.md"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Technical Debt Report (Refined)\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("## Summary\n")
            f.write(f"- Total Files Scanned: {self.results['summary']['total_files_scanned']}\n")
            f.write(f"- Total Debt Markers (TODO/FIXME/etc): {self.results['summary']['total_debt_markers']}\n")
            f.write(f"- Oversized Files (> {FILE_SIZE_THRESHOLD} lines): {self.results['summary']['oversized_files']}\n")
            f.write(f"- Total Project Debt Score: {self.results['summary']['total_score']}\n\n")

            f.write("## Top Offenders\n")
            # Sort by score descending
            sorted_files = sorted(self.results["files"], key=lambda x: x["score"], reverse=True)
            for file in sorted_files[:20]:
                f.write(f"### `{file['path']}` (Score: {file['score']})\n")
                if file["oversized"]:
                    f.write("- ⚠️ File is oversized.\n")
                if file["max_indent"] > INDENT_THRESHOLD:
                    f.write(f"- ⚠️ Deep nesting detected (Max: {file['max_indent']})\n")
                if file["markers"]:
                    f.write("- Markers:\n")
                    for m in file["markers"][:10]:
                        f.write(f"  - L{m['line']} [{m['type']}]: {m['content'][:120]}\n")
                f.write("\n")

        return report_path

    def scan(self):
        for root, dirs, files in os.walk(self.root_dir):
            # Prune directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                self.scan_file(Path(root) / file)

if __name__ == "__main__":
    # Resolve the project root dynamically
    project_root = Path(__file__).parents[2]
    scanner = TechDebtScanner(project_root)
    scanner.scan()
    report = scanner.generate_report()
    print(f"Scan complete. Report generated: {report}")
