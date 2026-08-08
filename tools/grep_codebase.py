import argparse
import json
import os
import re
import sys
from pathlib import Path

from _codebase_common import (
    EXCLUDE_DIRS,
    INCLUDE_EXTENSIONS,
    PROJECT_ROOT,
    _normalize_content,
    _safe_relative,
    fail,
    ok,
    resolve_secure_path,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="Search for a literal string or regex across the repo.")
    parser.add_argument("pattern", help="Text or regex to search for.")
    parser.add_argument("directory", nargs="?", default="", help="Limit search to this subdirectory (empty = whole repo).")
    parser.add_argument("--extension-filter", default=None, help="Only search files with this extension, e.g. '.py'.")
    parser.add_argument("--case-sensitive", action="store_true", default=False, help="Default False.")
    parser.add_argument("--max-results", type=int, default=50, help="Cap results (default 50).")
    args = parser.parse_args()

    try:
        base = resolve_secure_path(args.directory) if args.directory else PROJECT_ROOT
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        return

    results = []
    flags = 0 if args.case_sensitive else re.IGNORECASE

    try:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                fp = Path(root) / f
                if args.extension_filter and fp.suffix != args.extension_filter:
                    continue
                if fp.suffix not in INCLUDE_EXTENSIONS:
                    continue
                try:
                    content = _normalize_content(fp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for i, line in enumerate(content.splitlines()):
                    if re.search(args.pattern, line, flags):
                        results.append({"file_path": _safe_relative(fp), "line": i + 1, "text": line.strip()})
                        if len(results) >= args.max_results:
                            print(json.dumps(ok(f"Found max {args.max_results} results",
                                                {"results": results}), indent=2))
                            return
        print(json.dumps(ok(f"Found {len(results)} results", {"results": results}), indent=2))
    except Exception as e:
        print(json.dumps(fail(f"Grep failed: {e}"), indent=2))


if __name__ == "__main__":
    main()
