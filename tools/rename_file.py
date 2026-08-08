import argparse
import json
import os
import sys
from pathlib import Path

from _codebase_common import fail, ok, resolve_secure_path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="Rename/move a file within the repo.")
    parser.add_argument("source_relative_path", help="Source path relative to repo root.")
    parser.add_argument("destination_relative_path", help="Destination path relative to repo root.")
    args = parser.parse_args()

    try:
        src = resolve_secure_path(args.source_relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        sys.exit(1)

    if not src.exists():
        print(json.dumps(fail("Source not found"), indent=2))
        sys.exit(1)

    try:
        dst = resolve_secure_path(args.destination_relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        sys.exit(1)

    if dst.exists():
        print(json.dumps(fail("Destination already exists"), indent=2))
        sys.exit(1)

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        print(json.dumps(ok(f"Renamed {args.source_relative_path} -> {args.destination_relative_path}",
                            {"from": args.source_relative_path,
                             "to": args.destination_relative_path}), indent=2))
    except Exception as e:
        print(json.dumps(fail(f"rename_file failed: {e}"), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
