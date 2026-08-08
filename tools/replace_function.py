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
    # Guarantee a trailing newline so difflib emits a lineterm on the final
    # source line (ast.unparse output has none, which would otherwise fuse
    # the last two hunk lines together).
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


def _find_function(tree, name, class_name=None):
    import ast

    if class_name:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == name:
                        return sub, True
        return None, False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node, True
    return None, False


def main():
    parser = argparse.ArgumentParser(
        description="Replace a function's source via AST manipulation."
    )
    parser.add_argument("relative_path", help="Path relative to project root.")
    parser.add_argument("function_name", help="Function name to replace.")
    parser.add_argument("new_function_code", help="Full new function source.")
    parser.add_argument("--class-name", default=None, help="Optional enclosing class.")
    args = parser.parse_args()

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

    import ast

    try:
        content = _normalize_content(path.read_text(encoding="utf-8"))
        tree = ast.parse(content)
        new_func = ast.parse(args.new_function_code)
        if not new_func.body or not isinstance(
            new_func.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            print(
                json.dumps(
                    fail("new_function_code must be a single function definition."),
                    indent=2,
                )
            )
            sys.exit(1)
        new_node = new_func.body[0]

        target, found = _find_function(tree, args.function_name, args.class_name)
        if not found:
            print(
                json.dumps(
                    fail(
                        f"Function {args.function_name}"
                        + (f" in class {args.class_name}" if args.class_name else "")
                        + " not found."
                    ),
                    indent=2,
                )
            )
            sys.exit(1)

        new_tree = ast.parse(content)
        if args.class_name:
            for node in ast.walk(new_tree):
                if isinstance(node, ast.ClassDef) and node.name == args.class_name:
                    for i, sub in enumerate(node.body):
                        if (
                            isinstance(sub, ast.FunctionDef)
                            and sub.name == args.function_name
                        ):
                            node.body[i] = new_node
        else:
            for i, node in enumerate(new_tree.body):
                if isinstance(node, ast.FunctionDef) and node.name == args.function_name:
                    new_tree.body[i] = new_node

        ast.fix_missing_locations(new_tree)
        updated = ast.unparse(new_tree)
        # Diff ONLY the replaced function (old vs new source), not the whole
        # module — ast.unparse re-emits the entire file and normalises
        # formatting (quote/import/blank-line churn), which would otherwise
        # make the diff claim the whole file changed.
        assert target is not None  # guarded by the `found` check above
        old_src = ast.unparse(target)
        new_src = ast.unparse(new_node)
        path.write_text(updated + "\n", encoding="utf-8")
        print(
            json.dumps(
                ok(
                    f"Replaced function {args.function_name} in {args.relative_path}",
                    {
                        "changed": True,
                        "diff": _bounded_diff(old_src, new_src),
                    },
                ),
                indent=2,
            )
        )
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps(fail(f"replace_function failed: {e}"), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
