import argparse
import ast
import json
import sys
from pathlib import Path

from _codebase_common import _normalize_content, fail, ok, resolve_secure_path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _constant_node(constant_code: str) -> ast.stmt:
    stripped = constant_code.strip()
    tree = ast.parse(stripped)
    node = tree.body[0]
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        raise ValueError(f"Not a valid constant assignment: {constant_code!r}")
    return node


def _existing_constant(tree: ast.Module, constant_name: str) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == constant_name:
                    return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == constant_name:
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Add a top-level constant to a Python file using AST manipulation.")
    parser.add_argument("relative_path", help="Path to Python file.")
    parser.add_argument("constant_name", help="Name of the constant to add.")
    parser.add_argument("constant_code", help="Full assignment line or value code for the constant.")
    args = parser.parse_args()

    if not args.constant_code or not args.constant_code.strip():
        print(json.dumps(fail("add_constant failed: no value supplied — pass a simple "
                              "constant assignment, e.g. MY_CONST = 'value' (use write_file "
                              "or replace_text for class/function definitions)"), indent=2))
        sys.exit(1)

    try:
        path = resolve_secure_path(args.relative_path)
    except ValueError as e:
        print(json.dumps(fail(str(e)), indent=2))
        sys.exit(1)

    if not path.exists():
        print(json.dumps(fail(f"File not found: {args.relative_path}"), indent=2))
        sys.exit(1)
    if path.suffix != ".py":
        print(json.dumps(fail("Not a Python file."), indent=2))
        sys.exit(1)

    try:
        new_node = _constant_node(args.constant_code)
        content = _normalize_content(path.read_text(encoding="utf-8"))
        tree = ast.parse(content)

        if _existing_constant(tree, args.constant_name):
            print(json.dumps(ok(f"Constant already present in {args.relative_path}",
                                {"file_path": args.relative_path, "changed": False,
                                 "constant": args.constant_name}), indent=2))
            return

        tree.body.append(new_node)
        ast.fix_missing_locations(tree)
        updated = ast.unparse(tree)
        path.write_text(updated + "\n", encoding="utf-8")
        print(json.dumps(ok(f"Added constant to {args.relative_path}",
                            {"file_path": args.relative_path, "changed": True,
                             "constant": args.constant_name}), indent=2))
    except Exception as e:
        print(json.dumps(fail(f"add_constant failed: {e}"), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
