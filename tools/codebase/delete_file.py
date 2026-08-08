#!/usr/bin/env python3
"""Delete a file safely (sandboxed to KIT_TARGET_ROOT)."""

import argparse
import json
import sys
from pathlib import Path

from _codebase_common import fail, ok, resolve_secure_path


def delete_file(relative_path: str) -> dict:
    try:
        path = resolve_secure_path(relative_path)
    except ValueError as e:
        return fail(f"Path escape detected: {e}")

    if not path.exists():
        return fail(f"File not found: {relative_path}")

    if path.is_dir():
        return fail(f"Path is a directory, not a file: {relative_path}")

    try:
        path.unlink()
        return ok(f"Deleted: {relative_path}", {"path": relative_path})
    except PermissionError:
        return fail(f"Permission denied: {relative_path}")
    except OSError as e:
        return fail(f"Failed to delete {relative_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Delete a file (sandboxed to KIT_TARGET_ROOT).")
    parser.add_argument("path", help="Relative path to file to delete")
    args = parser.parse_args()

    result = delete_file(args.path)
    print(json.dumps(result))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
