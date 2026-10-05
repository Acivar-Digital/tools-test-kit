"""Generate a Markdown summary report from JSON test logs in a directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_log_file(path: Path) -> list[dict[str, Any]] | None:
    """Load and parse a single JSON test log file. Return None on failure."""
    try:
        raw: str = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Warning: cannot read {path}: {exc}", file=sys.stderr)
        return None
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Warning: invalid JSON in {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(parsed, list):
        print(f"Warning: expected JSON array in {path}", file=sys.stderr)
        return None
    return parsed


def extract_test_cases(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract test case dicts from a parsed JSON log list."""
    cases: list[dict[str, Any]] = []
    for entry in data:
        if isinstance(entry, dict):
            cases.append(entry)
    return cases


def _safe_float(value: Any) -> float:
    """Coerce a value to float, defaulting to 0.0 on failure."""
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _safe_str(value: Any) -> str:
    """Coerce a value to str, defaulting to 'unknown' on failure."""
    if isinstance(value, str):
        return value
    return "unknown"


def compute_summary_stats(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute total/pass/fail counts and average execution time."""
    total: int = len(cases)
    passed: int = 0
    failed: int = 0
    times: list[float] = []

    for case in cases:
        status: str = _safe_str(case.get("status"))
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
        times.append(_safe_float(case.get("duration", 0)))

    avg_time: float = sum(times) / total if total > 0 else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "average_time": avg_time,
    }


def build_error_distribution(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Count occurrences of each error/message type among failed cases."""
    errors: dict[str, int] = {}
    for case in cases:
        status: str = _safe_str(case.get("status"))
        if status != "failed":
            continue
        error_type: str = _safe_str(case.get("error_type")) or _safe_str(
            case.get("error_message", "unknown")
        )
        errors[error_type] = errors.get(error_type, 0) + 1
    return errors


def format_markdown_report(
    stats: dict[str, Any],
    errors: dict[str, int],
    file_count: int,
) -> str:
    """Render a Markdown-formatted summary report from computed stats."""
    lines: list[str] = []
    lines.append("# Test Report Summary")
    lines.append("")
    lines.append(f"- **Log files processed**: {file_count}")
    lines.append(f"- **Total test cases**: {stats['total']}")
    lines.append(f"- **Passed**: {stats['passed']}")
    lines.append(f"- **Failed**: {stats['failed']}")
    lines.append(f"- **Average execution time**: {stats['average_time']:.4f}s")
    lines.append("")
    lines.append("## Error Distribution")
    lines.append("")
    if not errors:
        lines.append("No failures recorded.")
    else:
        lines.append("| Error Type | Occurrences |")
        lines.append("|---|---|")
        for error_type, count in sorted(errors.items()):
            lines.append(f"| {error_type} | {count} |")
    lines.append("")
    return "\n".join(lines)


def create_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate a Markdown summary report from JSON test logs.",
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing JSON test log files (.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path for the Markdown report (default: stdout).",
    )
    parser.add_argument(
        "-e",
        "--extension",
        type=str,
        default=".json",
        help="File extension to filter log files (default: .json).",
    )
    return parser


def find_log_files(directory: Path, extension: str) -> list[Path]:
    """Return a sorted list of log files in the directory."""
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        return []
    files: list[Path] = sorted(directory.glob(f"*{extension}"))
    if not files:
        print(f"Warning: no '{extension}' files found in {directory}", file=sys.stderr)
    return files


def write_or_print_report(report: str, output: Path | None) -> None:
    """Write the report to a file or print to stdout."""
    if output is not None:
        try:
            output.write_text(report, encoding="utf-8")
        except OSError as exc:
            print(f"Error: cannot write output file {output}: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(report)


def main() -> None:
    """Entry point: parse args, process logs, emit report."""
    parser: argparse.ArgumentParser = create_argument_parser()
    args: argparse.Namespace = parser.parse_args()

    directory: Path = args.directory
    output: Path | None = args.output
    extension: str = args.extension

    log_files: list[Path] = find_log_files(directory, extension)
    if not log_files:
        sys.exit(1)

    all_cases: list[dict[str, Any]] = []
    for path in log_files:
        parsed: list[dict[str, Any]] | None = load_log_file(path)
        if parsed is not None:
            all_cases.extend(extract_test_cases(parsed))

    if not all_cases:
        print("Warning: no valid test cases found in any log file", file=sys.stderr)

    stats: dict[str, Any] = compute_summary_stats(all_cases)
    errors: dict[str, int] = build_error_distribution(all_cases)
    report: str = format_markdown_report(stats, errors, len(log_files))
    write_or_print_report(report, output)


if __name__ == "__main__":
    main()
