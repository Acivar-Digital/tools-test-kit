import argparse
import sys

from _codebase_common import _normalize_content, resolve_secure_path

sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="Read a specific line range of a file in the repo.")
    parser.add_argument("relative_path", help="Path relative to project root.")
    parser.add_argument("--start-line", type=int, help="First line to read (1-indexed).")
    parser.add_argument("--end-line", type=int, help="Last line to read (inclusive).")
    args = parser.parse_args()

    try:
        path = resolve_secure_path(args.relative_path)
    except ValueError as e:
        print(f"ERROR: {e}")
        return

    if not path.exists():
        print(f"ERROR: File not found: {args.relative_path}")
        return

    try:
        content = _normalize_content(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: Failed to read {args.relative_path}: {e}")
        return

    lines = content.splitlines()
    total_lines = len(lines)
    s = (args.start_line - 1) if args.start_line else 0
    e = args.end_line if args.end_line else total_lines
    paged = lines[s:e]

    # Emit SCOPED PLAIN content (with a light header) — NOT a JSON envelope.
    # The old {"success": true, "data": {"content": ...}} envelope leaked
    # verbatim into the transcript (.md) and poisoned the model context; nothing
    # in the live harness parses it (see _run_tool: it returns stdout as-is).
    print(f"=== File read: {args.relative_path} (lines {s + 1}-{min(e, total_lines)} of {total_lines}) ===")
    print("\n".join(paged))


if __name__ == "__main__":
    main()

