import argparse
import difflib
import json
import sys

from _codebase_common import (
    _normalize_content,
    fail,
    ok,
    resolve_secure_path,
)


def _bounded_diff(old_text, new_text, context=15):
    if old_text and not old_text.endswith("\n"):
        old_text += "\n"
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            old_lines, new_lines, fromfile="a", tofile="b", n=context, lineterm="\n"
        )
    )
    if not diff:
        return "(no changes detected)"
    return "".join(diff)


def main():
    parser = argparse.ArgumentParser(description="Write content to a file in the repo.")
    parser.add_argument("relative_path", help="Path relative to project root.")
    parser.add_argument("content", help="The full text content to write.")

    args = parser.parse_args()

    try:
        path = resolve_secure_path(args.relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        sys.exit(1)

    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
    new_text = _normalize_content(args.content)
    if not new_text.endswith("\n"):
        new_text += "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")

    print(
        json.dumps(
            ok(
                f"Wrote {args.relative_path}",
                {
                    "path": args.relative_path,
                    "diff": _bounded_diff(old_text, new_text),
                },
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
