#!/usr/bin/env python3
import argparse
import ast
import sys
from pathlib import Path

from radon.complexity import cc_visit


def get_function_cc(filepath: str, min_cc: int = 1):
    source = Path(filepath).read_text()
    try:
        ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return []

    results = cc_visit(source)
    results = [r for r in results if r.complexity >= min_cc]
    results.sort(key=lambda r: (r.complexity, r.name), reverse=True)
    return results


def get_all_cc(filepath: str):
    source = Path(filepath).read_text()
    try:
        ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return []

    results = cc_visit(source)
    results.sort(key=lambda r: (r.complexity, r.name), reverse=True)
    return results


def _format_results(all_results: list, min_cc: int) -> str:
    lines = [f"Functions with CC >= {min_cc}: {len(all_results)}"]
    lines.append(f"{'File':<60} {'Function':<40} {'Line':>5} {'CC':>4}")
    lines.append("-" * 110)
    for v in all_results:
        func_name = v.name.split(".")[-1]
        src_file = getattr(v, "_src_file", v.fullname)
        lines.append(f"{src_file:<60} {func_name:<40} {v.lineno:>5} {v.complexity:>4}")
    return "\n".join(lines)


def _collect_results(files: list[str], min_cc: int) -> list:
    all_results = []
    for filepath in files:
        p = Path(filepath)
        if not p.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            continue
        results = get_function_cc(str(p), min_cc)
        for r in results:
            r._src_file = str(p)
        all_results.extend(results)
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Find functions exceeding cyclomatic complexity threshold")
    parser.add_argument("--min-cc", type=int, default=6, help="Minimum CC threshold (default: 6)")
    parser.add_argument("files", nargs="+", help="Python files to analyze")
    args = parser.parse_args()

    all_results = _collect_results(args.files, args.min_cc)
    all_results.sort(key=lambda r: (r.complexity, r.name), reverse=True)

    if all_results:
        print(_format_results(all_results, args.min_cc))
    else:
        print(f"No functions with CC >= {args.min_cc} found.")

    return 1 if all_results else 0


if __name__ == "__main__":
    sys.exit(main())
