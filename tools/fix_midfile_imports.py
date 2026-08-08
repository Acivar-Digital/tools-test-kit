#!/usr/bin/env python3
"""
fix_midfile_imports.py — AST tool to fix E402 mid-file imports and remove duplicate definitions.
Moves all mid-file imports to the top of python files in src2/.
"""

import ast
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
src2_dir = repo_root / "src2"


def fix_file_imports(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return False

    lines = content.splitlines(keepends=True)
    mid_file_import_lines = []

    # Find mid-file imports
    first_non_import_lineno = None
    for stmt in tree.body:
        # Skip module docstring
        if stmt is tree.body[0] and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        # Skip __future__
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            continue

        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            if first_non_import_lineno is None:
                first_non_import_lineno = stmt.lineno
        else:
            if first_non_import_lineno is not None and stmt.lineno > first_non_import_lineno:
                # This import is mid-file!
                start_line = stmt.lineno - 1
                end_line = getattr(stmt, "end_lineno", stmt.lineno)
                mid_file_import_lines.append((start_line, end_line, ast.unparse(stmt)))

    if not mid_file_import_lines:
        return False

    # Remove mid-file import lines in reverse line order
    mid_file_import_lines.sort(key=lambda x: x[0], reverse=True)
    imports_to_add = set()

    for start_line, end_line, stmt_code in mid_file_import_lines:
        imports_to_add.add(stmt_code)
        del lines[start_line:end_line]

    # Insert imports at top (after __future__ / docstring)
    new_source = "".join(lines)
    try:
        new_tree = ast.parse(new_source)
        insert_line_idx = 0
        for stmt in new_tree.body:
            if stmt is new_tree.body[0] and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                insert_line_idx = stmt.end_lineno
                continue
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                insert_line_idx = stmt.end_lineno
                continue
            break

        top_imports_code = "\n".join(sorted(imports_to_add)) + "\n"
        new_lines = new_source.splitlines(keepends=True)
        new_lines.insert(insert_line_idx, top_imports_code)
        final_code = "".join(new_lines)

        ast.parse(final_code)
        file_path.write_text(final_code, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Failed fixing imports for {file_path.name}: {e}")
        return False


def main():
    fixed_count = 0
    for py_file in sorted(src2_dir.rglob("*.py")):
        if py_file.is_file():
            if fix_file_imports(py_file):
                fixed_count += 1
    print(f"🎉 Moved mid-file imports to top in {fixed_count} file(s).")


if __name__ == "__main__":
    main()
