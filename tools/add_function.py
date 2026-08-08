import argparse
import ast
import difflib
import json
import sys
from pathlib import Path

from _codebase_common import _normalize_content, fail, ok, resolve_secure_path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _function_node(function_code: str) -> ast.stmt:
    stripped = function_code.strip()
    tree = ast.parse(stripped)
    if not tree.body:
        raise ValueError(f"Empty function code: {function_code!r}")
    node = tree.body[0]
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(
            f"add_function expects a function definition, got {type(node).__name__}"
        )
    return node


def _find_function(
    tree: ast.Module, name: str, class_name: str | None = None
) -> tuple[ast.AST | None, bool]:
    if class_name is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == name:
                        return sub, True
        return None, False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node, True
    return None, False


def _insert_after(
    body: list[ast.stmt], target_name: str, new_node: ast.stmt, class_name: str | None = None
) -> bool:
    if class_name is not None:
        for node in body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for i, sub in enumerate(node.body):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == target_name:
                        node.body.insert(i + 1, new_node)
                        return True
        return False
    for i, node in enumerate(body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_name:
            body.insert(i + 1, new_node)
            return True
        if isinstance(node, ast.ClassDef) and node.name == target_name:
            body.insert(i + 1, new_node)
            return True
    return False


def _bounded_diff(old_text: str, new_text: str, context: int = 15) -> str:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a new function to a Python file using AST manipulation."
    )
    parser.add_argument("relative_path", help="Path to Python file relative to project root.")
    parser.add_argument("function_code", help="Full function source code to add.")
    parser.add_argument(
        "--class-name", default=None, help="Optional enclosing class to add the method into."
    )
    parser.add_argument(
        "--insert-after", default=None, help="Insert after this function or class name."
    )
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

    try:
        new_node = _function_node(args.function_code)
        content = _normalize_content(path.read_text(encoding="utf-8"))
        tree = ast.parse(content)
        func_name = new_node.name  # type: ignore[attr-defined]

        _, found = _find_function(tree, func_name, args.class_name)
        if found:
            print(
                json.dumps(
                    ok(
                        f"Function {func_name} already exists in {args.relative_path}",
                        {"file_path": args.relative_path, "changed": False},
                    ),
                    indent=2,
                )
            )
            return

        target_body: list[ast.stmt]
        if args.class_name is not None:
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == args.class_name:
                    target_body = node.body
                    break
            else:
                target_body = tree.body
        else:
            target_body = tree.body

        if args.insert_after is not None:
            inserted = _insert_after(
                target_body, args.insert_after, new_node, args.class_name
            )
            if not inserted:
                target_body.append(new_node)
        else:
            target_body.append(new_node)

        ast.fix_missing_locations(tree)
        updated = ast.unparse(tree)
        old_content = content
        path.write_text(updated + "\n", encoding="utf-8")
        diff = _bounded_diff(old_content, updated)
        print(
            json.dumps(
                ok(
                    f"Added function {func_name} to {args.relative_path}",
                    {
                        "file_path": args.relative_path,
                        "changed": True,
                        "function": func_name,
                        "diff": diff,
                    },
                ),
                indent=2,
            )
        )
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps(fail(f"add_function failed: {e}"), indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
