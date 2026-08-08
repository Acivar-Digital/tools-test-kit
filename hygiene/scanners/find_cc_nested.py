import os
import sys
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from radon.complexity import cc_visit  # noqa: E402


def get_all_python_files(root: Path) -> list[Path]:
    ignore_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", ".eggs", "venv", ".venv", "env"}
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(Path(dirpath) / fname)
    return py_files


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Find files with functions exceeding CC > 5 using radon, "
                    "scoped to src2/, aligned with kill_tries.py."
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of top files to show (default: 10)")
    parser.add_argument("--min-cc", type=int, default=6, help="Minimum per-function CC threshold (default: 6 = >5)")
    parser.add_argument("--target-dir", type=str, default="src2", help="Directory to scan (default: src2)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    target = root / args.target_dir
    if not target.exists():
        print(f"Error: target directory '{target}' does not exist.")
        sys.exit(1)

    py_files = get_all_python_files(target)

    results = []
    for fpath in py_files:
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except Exception:
            continue

        try:
            blocks = cc_visit(source)
        except Exception:
            continue

        if not blocks:
            continue

        dirty = [b for b in blocks if b.complexity >= args.min_cc]
        if not dirty:
            continue

        rel = str(fpath.relative_to(root))
        worst_cc = max(b.complexity for b in dirty)
        results.append((rel, worst_cc, len(dirty), dirty))

    results.sort(key=lambda x: x[1], reverse=True)
    top = results[: args.limit]

    print(f"\n{'=' * 70}")
    print(f"  Top {len(top)} Files in {args.target_dir}/ with Functions CC >= {args.min_cc}")
    print(f"  (Aligned with kill_tries.py: CC > 5 per function)")
    print(f"{'=' * 70}\n")
    print(f"  {'Rank':<5} {'Worst':<7} {'Violators':<10} {'File'}")
    print(f"  {'-' * 5} {'-' * 6} {'-' * 10} {'-' * 50}")

    for rank, (rel, worst_cc, count, dirty) in enumerate(top, 1):
        print(f"  {rank:<5} {worst_cc:<7} {count:<10} {rel}")
        for b in sorted(dirty, key=lambda x: x.complexity, reverse=True):
            print(f"        CC {b.complexity}  {b.name} (line {b.lineno})")

    total_violations = sum(len(r[3]) for r in results)
    print(f"\n{'=' * 70}")
    print(f"  Scanned {len(py_files)} Python files in {args.target_dir}/, {len(results)} have CC >= {args.min_cc}")
    print(f"  Total violations: {total_violations}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()