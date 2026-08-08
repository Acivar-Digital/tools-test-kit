import argparse
import ast
import json
import sys
from pathlib import Path

from _codebase_common import _normalize_content, fail, ok, resolve_secure_path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _import_node(import_code: str) -> ast.stmt:
    stripped = import_code.strip()
    if not (stripped.startswith("import ") or stripped.startswith("from ")):
        raise ValueError(f"Not a valid import statement: {import_code!r}")
    tree = ast.parse(stripped)
    return tree.body[0]


def _insert_index(tree: ast.Module) -> int:
    """Index after any leading shebang/encoding comments and existing imports."""
    for i, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        return i
    return len(tree.body)


def main():
    parser = argparse.ArgumentParser(description="Add a new import to the top of a file using AST manipulation.")
    parser.add_argument("relative_path", help="Path to Python file.")
    parser.add_argument("import_code", help="Import line (e.g. 'from os import path').")
    args = parser.parse_args()

    try:
        path = resolve_secure_path(args.relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        return

    if not path.exists():
        print(json.dumps(fail(f"File not found: {args.relative_path}"), indent=2))
        return
    if path.suffix != ".py":
        print(json.dumps(fail("Not a Python file."), indent=2))
        return

    try:
        content = _normalize_content(path.read_text(encoding="utf-8"))
        tree = ast.parse(content)
        new_node = _import_node(args.import_code)

        existing = {ast.dump(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))}
        if ast.dump(new_node) in existing:
            print(json.dumps(ok(f"Import already present in {args.relative_path}",
                                {"file_path": args.relative_path, "changed": False}), indent=2))
            return

        idx = _insert_index(tree)
        tree.body.insert(idx, new_node)
        ast.fix_missing_locations(tree)
        updated = ast.unparse(tree)
        path.write_text(updated + "\n", encoding="utf-8")
        print(json.dumps(ok(f"Added import to {args.relative_path}",
                            {"file_path": args.relative_path, "changed": True,
                             "import": args.import_code}), indent=2))
    except Exception as e:
        print(json.dumps(fail(f"Failed to add import: {e}"), indent=2))


if __name__ == "__main__":
    main()
