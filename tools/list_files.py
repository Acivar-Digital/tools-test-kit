import argparse
import json
import os
import sys
from pathlib import Path

from _codebase_common import (
    EXCLUDE_DIRS,
    INCLUDE_EXTENSIONS,
    PROJECT_ROOT,
    _safe_relative,
    fail,
    ok,
    resolve_secure_path,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="List files in a repo directory with pagination.")
    parser.add_argument("directory", nargs="?", default="", help="Relative path to directory (empty = project root).")
    parser.add_argument("--extension-filter", default=None, help="Only return files with this extension, e.g. '.py'.")
    parser.add_argument("--recursive", action="store_true", default=True, help="Recurse into subdirectories.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum number of files to return.")
    parser.add_argument("--offset", type=int, default=0, help="Number of files to skip for pagination.")
    args = parser.parse_args()

    try:
        base = resolve_secure_path(args.directory) if args.directory else PROJECT_ROOT
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        return

    if not base.exists():
        print(json.dumps(fail(f"Directory not found: {args.directory}"), indent=2))
        return

    all_found: list[str] = []
    walker = os.walk(base) if args.recursive else [(str(base), [], os.listdir(base))]

    for root, dirs, files in walker:
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in sorted(files):
            fp = Path(root) / f
            if args.extension_filter:
                if fp.suffix != args.extension_filter:
                    continue
            elif fp.suffix not in INCLUDE_EXTENSIONS:
                continue
            all_found.append(_safe_relative(fp))

    all_found.sort()
    total_count = len(all_found)
    paged = all_found[args.offset : args.offset + args.limit]

    print(json.dumps(ok(
        f"Found {total_count} files in {args.directory or 'root'}",
        {
            "files": paged,
            "metadata": {
                "total": total_count,
                "returned": len(paged),
                "offset": args.offset,
                "limit": args.limit,
                "is_truncated": (args.offset + args.limit) < total_count,
            },
        },
    ), indent=2))


if __name__ == "__main__":
    main()
