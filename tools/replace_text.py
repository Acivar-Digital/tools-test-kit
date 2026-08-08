import argparse
import difflib
import json
import re
import sys

from _codebase_common import (
    _normalize_content,
    fail,
    ok,
    resolve_secure_path,
)

ALLOWED_EXTENSIONS = {
    ".py", ".md", ".json", ".txt", ".yaml", ".yml", ".toml", ".sql", ".sh",
}


def _bounded_diff(old_text, new_text, context=3):
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
    parser = argparse.ArgumentParser(
        description="Replace exact text or regex in a repo file."
    )
    parser.add_argument("relative_path", help="Path relative to project root.")
    parser.add_argument("target_text", help="Text (or regex) to find.")
    parser.add_argument("replacement_text", help="Replacement text.")
    parser.add_argument("--is-regex", action="store_true", help="Treat target as regex.")
    parser.add_argument("--case-insensitive", action="store_true")
    parser.add_argument("--ignore-whitespace", action="store_true")
    args = parser.parse_args()

    try:
        path = resolve_secure_path(args.relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        sys.exit(1)

    if not path.exists():
        print(json.dumps(fail(f"File not found: {args.relative_path}"), indent=2))
        sys.exit(1)
    if path.suffix not in ALLOWED_EXTENSIONS:
        print(json.dumps(fail(f"Unsupported file type: {path.suffix}"), indent=2))
        sys.exit(1)

    try:
        old_text = _normalize_content(path.read_text(encoding="utf-8"))
        new_text = old_text
        if args.is_regex:
            flags = re.IGNORECASE if args.case_insensitive else 0
            new_text, n = re.subn(
                args.target_text,
                args.replacement_text,
                old_text,
                flags=flags,
            )
        else:
            target = args.target_text
            if args.ignore_whitespace:
                target = re.sub(r"\s+", r"\\s+", re.escape(target))
                new_text, n = re.subn(target, args.replacement_text, old_text)
            else:
                if args.case_insensitive:
                    n = old_text.lower().count(target.lower())
                    new_text = old_text
                    if n:
                        low_old = old_text.lower()
                        low_t = target.lower()
                        out = []
                        start = 0
                        while True:
                            idx = low_old.find(low_t, start)
                            if idx == -1:
                                break
                            out.append(old_text[start:idx])
                            out.append(args.replacement_text)
                            start = idx + len(target)
                        out.append(old_text[start:])
                        new_text = "".join(out)
                else:
                    n = old_text.count(target)
                    new_text = old_text.replace(target, args.replacement_text)

        if n == 0:
            print(
                json.dumps(
                    ok(f"No match found in {args.relative_path}", {"changed": False}),
                    indent=2,
                )
            )
            return

        path.write_text(new_text, encoding="utf-8")
        print(
            json.dumps(
                ok(
                    f"Replaced {n} occurrence(s) in {args.relative_path}",
                    {
                        "changed": True,
                        "count": n,
                        "diff": _bounded_diff(old_text, new_text),
                    },
                ),
                indent=2,
            )
        )
    except Exception as e:
        print(json.dumps(fail(f"replace_text failed: {e}"), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
