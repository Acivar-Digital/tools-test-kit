"""
Virtual AST Staging Buffer for In-Memory AST Transformations.

Provides AST-based function replacement, helper function deduplication,
and transactional rollback stack without mutating live files on disk.
"""

import ast
import copy

__all__ = [
    "FunctionReplacer",
    "VirtualASTBuffer",
    "ensure_pydantic_imports",
    "verify_class_structure_intact",
]


class FunctionReplacer(ast.NodeTransformer):
    """Replaces a target function node in the AST with new AST nodes."""

    def __init__(self, target_name: str, new_nodes: list[ast.AST]) -> None:
        self.target_name = target_name
        self.new_nodes = new_nodes
        self.replaced = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | list[ast.AST]:
        if node.name == self.target_name:
            self.replaced = True
            if len(self.new_nodes) == 1:
                return self.new_nodes[0]
            return self.new_nodes
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST | list[ast.AST]:
        if node.name == self.target_name:
            self.replaced = True
            if len(self.new_nodes) == 1:
                return self.new_nodes[0]
            return self.new_nodes
        return self.generic_visit(node)


class VirtualASTBuffer:
    """
    In-memory AST staging buffer for python modules.
    Tracks module AST modifications and maintains a rollback stack.
    """

    def __init__(self, source_code: str, file_path: str = "") -> None:
        self.file_path = file_path
        self.source_code = source_code
        self.tree: ast.Module = ast.parse(source_code)
        self.snapshots: list[ast.Module] = []
        self._inserted_helpers: set[str] = set()

    def push_checkpoint(self) -> None:
        """Pushes current tree state onto the snapshot stack."""
        self.snapshots.append(copy.deepcopy(self.tree))

    def pop_checkpoint(self) -> bool:
        """Discards top snapshot without restoring. Returns True if stack was non-empty."""
        if self.snapshots:
            self.snapshots.pop()
            return True
        return False

    def rollback(self) -> bool:
        """Restores tree to the previous snapshot state. Returns True if restored."""
        if self.snapshots:
            self.tree = self.snapshots.pop()
            self._inserted_helpers = {
                n.name
                for n in self.tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in self._inserted_helpers
            }
            return True
        return False

    def get_source(self) -> str:
        """Returns the unparsed Python source code from the current AST tree."""
        return ast.unparse(self.tree)

    def replace_function(
        self,
        target_name: str,
        refactored_code: str,
        helper_codes: list[str] | None = None,
    ) -> str:
        """
        Replaces target_name function with refactored_code AST node(s).
        Inserts or replaces helper functions by name in top-level module body.
        Returns the unparsed Python source code string.
        """
        refactored_tree = ast.parse(refactored_code)
        new_func_nodes: list[ast.AST] = []
        for stmt in refactored_tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                new_func_nodes.append(stmt)
                if stmt.name != target_name:
                    for node in self.tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if node.name == stmt.name and node.name != target_name and node.name not in self._inserted_helpers:
                                raise ValueError(
                                    f"helper_collision: Collision: helper function name '{stmt.name}' already exists in target module {self.file_path}"
                                )

        if not new_func_nodes:
            raise ValueError(f"No valid function definition found in refactored_code for `{target_name}`")

        replacer = FunctionReplacer(target_name, new_func_nodes)
        self.tree = replacer.visit(self.tree)
        ast.fix_missing_locations(self.tree)

        if helper_codes:
            self._upsert_helpers(helper_codes, target_name=target_name)

        return self.get_source()

    def _upsert_helpers(
        self,
        helper_codes: list[str],
        target_name: str | None = None,
    ) -> None:
        """Upserts (replaces existing or appends new) helper functions in top-level module body."""
        for h_code in helper_codes:
            if not h_code.strip():
                continue
            h_tree = ast.parse(h_code)
            for stmt in h_tree.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    h_name = stmt.name
                    # Check for helper collisions with pre-existing module function/class
                    for node in self.tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if node.name == h_name:
                                if node.name != target_name and node.name not in self._inserted_helpers:
                                    raise ValueError(
                                        f"helper_collision: Collision: helper function name '{stmt.name}' already exists in target module {self.file_path}"
                                    )

                    # Check if helper function already exists in module body
                    replaced = False
                    for i, node in enumerate(self.tree.body):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == h_name:
                            self.tree.body[i] = stmt
                            replaced = True
                            break
                    if not replaced:
                        self.tree.body.append(stmt)
                    self._inserted_helpers.add(h_name)
                    ast.fix_missing_locations(self.tree)


def verify_class_structure_intact(original_code: str, modified_code: str) -> bool:
    """Verifies that all (class_name, method_name) pairs from original_code still exist in modified_code."""
    try:
        orig_tree = ast.parse(original_code)
        mod_tree = ast.parse(modified_code)
        orig_methods = set()
        for node in ast.walk(orig_tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        orig_methods.add((node.name, item.name))
        mod_methods = set()
        for node in ast.walk(mod_tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mod_methods.add((node.name, item.name))
        for cls_name, method_name in orig_methods:
            if (cls_name, method_name) not in mod_methods:
                return False
        return True
    except Exception:
        return False


def ensure_pydantic_imports(source: str, ref_code: str) -> str:
    """
    Ensures BaseModel, Field, and Any imports exist in source if ref_code uses them.
    Intelligently places new imports after __future__ imports or module docstrings.
    """
    has_basemodel = False
    has_field = False
    has_any = False
    try:
        source_tree = ast.parse(source)
        for node in ast.walk(source_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pydantic":
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name == "BaseModel":
                        has_basemodel = True
                    elif name == "Field":
                        has_field = True
                    elif name == "Any":
                        has_any = True
            elif isinstance(node, ast.ImportFrom) and node.module == "typing":
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name == "Any":
                        has_any = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pydantic":
                        has_basemodel = True
                        has_field = True
                    elif alias.name == "typing":
                        has_any = True
    except Exception:
        pass

    uses_basemodel = False
    uses_field = False
    uses_any = False
    try:
        ref_tree = ast.parse(ref_code)
        for node in ast.walk(ref_tree):
            if isinstance(node, ast.Name):
                if node.id == "BaseModel":
                    uses_basemodel = True
                elif node.id == "Field":
                    uses_field = True
                elif node.id == "Any":
                    uses_any = True
    except Exception:
        pass

    needed = []
    if uses_basemodel and not has_basemodel:
        needed.append("BaseModel")
    if uses_field and not has_field:
        needed.append("Field")
    if uses_any and not has_any:
        needed.append("Any")
    if not needed:
        return source

    import_lines = [
        f"from {mod} import {', '.join(mod_needed)}"
        for mod, mod_needed in (
            ("pydantic", [n for n in needed if n in ("BaseModel", "Field")]),
            ("typing", [n for n in needed if n == "Any"]),
        )
        if mod_needed
    ]
    import_block = "\n".join(import_lines) + "\n"

    lines = source.splitlines(keepends=True)

    last_future_idx = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith("from __future__ import"):
            last_future_idx = idx

    if last_future_idx != -1:
        lines.insert(last_future_idx + 1, import_block)
        return "".join(lines)

    insert_idx = 0
    in_docstring = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and (stripped.startswith('"""') or stripped.startswith("'''")):
            if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                insert_idx = 1
                break
            in_docstring = True
            continue
        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                insert_idx = idx + 1
                break
            continue
        if stripped.startswith("#") or not stripped:
            continue
        insert_idx = idx
        break

    lines.insert(insert_idx, import_block)
    return "".join(lines)

