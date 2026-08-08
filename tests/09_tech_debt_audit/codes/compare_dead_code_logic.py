import ast
import json
import re
import subprocess
from pathlib import Path


def get_files(directory: str) -> list[Path]:
    """Get all Python files under the directory that are not ignored by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", directory],
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [Path(line.strip()) for line in result.stdout.strip().split("\n") if line.strip()]
        return [p for p in paths if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"]
    except Exception:
        return [
            p
            for p in Path(directory).rglob("*.py")
            if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
        ]

class DefinitionCollector(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.definitions = []  # List of tuples: (name, type, line)
        self.whitelisted_names = set()

    def _check_decorators(self, node, name: str):
        for decorator in node.decorator_list:
            dec_name = ""
            if isinstance(decorator, ast.Name):
                dec_name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                dec_name = decorator.attr
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    dec_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    dec_name = decorator.func.attr
            keywords = ["router", "app", "message", "command", "webhook", "post", "get", "put", "delete", "handler"]
            if any(k in dec_name.lower() for k in keywords):
                self.whitelisted_names.add(name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "function", node.lineno))
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "async_function", node.lineno))
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "class", node.lineno))
            self._check_decorators(node, node.name)
        self.generic_visit(node)

def get_definitions(file_path: Path) -> tuple[dict[str, tuple[str, int]], set[str]]:
    """Return a dict of name -> (type, line) and set of decorator-whitelisted names."""
    if not file_path.exists():
        return {}, set()
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        collector = DefinitionCollector(file_path)
        collector.visit(tree)
        return {name: (t, line) for name, t, line in collector.definitions}, collector.whitelisted_names
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return {}, set()

def is_module_imported(ref_tree: ast.AST, ref_file: Path, def_file: Path, name: str) -> bool:
    """Check if the referencing file actually imports the module containing the definition."""
    def_parts = def_file.with_suffix("").parts
    def_mod = ".".join(def_parts)
    ref_parts = ref_file.parent.parts

    for node in ast.walk(ref_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == def_mod or alias.name.startswith(def_mod + "."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            imported_mod = ""
            if node.level > 0:
                slice_len = len(ref_parts) - (node.level - 1)
                base_parts = ref_parts[:slice_len]
                if node.module:
                    imported_mod = ".".join(base_parts + (node.module,))
                else:
                    imported_mod = ".".join(base_parts)
            else:
                if node.module:
                    imported_mod = node.module

            if imported_mod == def_mod:
                for alias in node.names:
                    if alias.name == name or alias.name == "*":
                        return True
            elif def_mod.startswith(imported_mod + "."):
                remaining = def_mod[len(imported_mod) + 1 :]
                next_part = remaining.split(".")[0]
                for alias in node.names:
                    if alias.name == next_part or alias.name == "*":
                        return True
    return False

def check_static_references(directory: str, file_contents: dict, ast_trees: dict, file_rel_path: str, name: str) -> bool:
    """Check if the symbol has any static reference/import in other files of the directory."""
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    def_file_path = Path(file_rel_path)

    for other_file, content in file_contents.items():
        if other_file == file_rel_path:
            continue

        if pattern.search(content):
            other_tree = ast_trees.get(other_file)
            other_file_path = Path(other_file)
            if other_tree and is_module_imported(other_tree, other_file_path, def_file_path, name):
                return True
    return False

def main():
    print("Collecting file and AST info from src...")
    src_files = get_files("src")
    src_contents = {}
    src_ast_trees = {}
    src_defs_map = {}
    src_decorator_whitelists = set()

    for f in src_files:
        f_str = str(f)
        try:
            content = f.read_text(errors="ignore")
            src_contents[f_str] = content
            tree = ast.parse(content)
            src_ast_trees[f_str] = tree
            defs, whitelist = get_definitions(f)
            src_decorator_whitelists.update(whitelist)
            for name, (t, line) in defs.items():
                src_defs_map[name] = (f_str, t, line)
        except Exception as e:
            print(f"Error parsing {f}: {e}")

    # Standard global whitelist
    global_whitelist = {
        "main", "telegram_webhook", "agent_webhook", "debug_session",
        "process_webhook_logic", "define_system_prompt", "add_the_users_name", "add_the_date"
    }
    global_whitelist.update(src_decorator_whitelists)

    # Load src2 audit report
    audit_path = Path("TEST/codes/dead_code_audit.json")
    if not audit_path.exists():
        print("Error: TEST/codes/dead_code_audit.json not found. Run the audit first.")
        return

    with open(audit_path, encoding="utf-8") as f:
        audit_data = json.load(f)

    audit_results = audit_data.get("audit_results", [])

    truly_dead = []
    accidentally_dropped = []
    false_positives_same = []
    new_in_src2 = []

    for item in audit_results:
        name = item["name"]
        file_path_src2 = item["file_path"]
        status_src2 = item["status"]  # CONFIRMED_DEAD or FALSE_POSITIVE
        t = item["type"]

        # Check if it existed in src
        if name not in src_defs_map:
            new_in_src2.append({
                "name": name,
                "type": t,
                "file_path_src2": file_path_src2,
                "status_src2": status_src2,
                "reason_src2": item.get("reason", "")
            })
            continue

        file_path_src, _, line_src = src_defs_map[name]

        # Determine status in src (alive if statically referenced, globally whitelisted, or decorator whitelisted)
        is_alive_src = False
        if name in global_whitelist:
            is_alive_src = True
        else:
            is_alive_src = check_static_references("src", src_contents, src_ast_trees, file_path_src, name)

        if status_src2 == "CONFIRMED_DEAD":
            if is_alive_src:
                accidentally_dropped.append({
                    "name": name,
                    "type": t,
                    "file_path_src": file_path_src,
                    "line_src": line_src,
                    "file_path_src2": file_path_src2,
                    "reason_src2": item.get("reason", "")
                })
            else:
                truly_dead.append({
                    "name": name,
                    "type": t,
                    "file_path_src": file_path_src,
                    "line_src": line_src,
                    "file_path_src2": file_path_src2
                })
        elif status_src2 == "FALSE_POSITIVE":
            # False Positive means alive in src2
            false_positives_same.append({
                "name": name,
                "type": t,
                "file_path_src": file_path_src,
                "is_alive_src": is_alive_src,
                "file_path_src2": file_path_src2,
                "reason_src2": item.get("reason", "")
            })

    # Render unified report
    print("\n" + "="*80)
    print("📋 MATRIX ALIGNMENT REPORT: src vs src2")
    print("="*80)

    print(f"\n🛑 [DEAD in both] Truly Dead Legacy Code ({len(truly_dead)} items):")
    print("These existed in src but were already unused/dead there, and are safe to delete in src2.")
    for item in sorted(truly_dead[:15], key=lambda x: x["name"]):
        print(f"  - {item['type']} `{item['name']}` (defined in {item['file_path_src']}:{item['line_src']})")
    if len(truly_dead) > 15:
        print(f"  ... and {len(truly_dead) - 15} more items.")

    print(f"\n⚠️ [DEAD in src2, ALIVE in src] ACCIDENTALLY DROPPED ({len(accidentally_dropped)} items):")
    print("CRITICAL: These were referenced/imported in the original src, but their callers were dropped in src2!")
    for item in sorted(accidentally_dropped, key=lambda x: x["name"]):
        print(f"  - {item['type']} `{item['name']}`")
        print(f"    Original: {item['file_path_src']}:{item['line_src']}")
        print(f"    Current:  {item['file_path_src2']}")
        print(f"    src2 Audit Reason: {item['reason_src2']}")

    print(f"\n✅ [FALSE_POSITIVE in src2] Alive status ({len(false_positives_same)} items):")
    # Group by whether they were also alive in src
    same_count = sum(1 for x in false_positives_same if x["is_alive_src"])
    diff_count = len(false_positives_same) - same_count
    print(f"  - Consistent (Alive in both): {same_count}")
    print(f"  - Discrepancy (Alive in src2, Dead in src): {diff_count}")
    for item in false_positives_same:
        if not item["is_alive_src"]:
            print(f"    * Note: `{item['name']}` ({item['type']}) is active in src2 but was dead in src. (New dynamic reference or refactoring).")

    print(f"\n🆕 [Added in src2] New definitions ({len(new_in_src2)} items):")
    new_dead = [x for x in new_in_src2 if x["status_src2"] == "CONFIRMED_DEAD"]
    new_alive = [x for x in new_in_src2 if x["status_src2"] == "FALSE_POSITIVE"]
    print(f"  - New but Dead in src2: {len(new_dead)}")
    print(f"  - New and Alive in src2: {len(new_alive)}")
    if new_dead:
        print("  Top new dead items:")
        for item in sorted(new_dead[:10], key=lambda x: x["name"]):
            print(f"    * {item['type']} `{item['name']}` in {item['file_path_src2']}")

if __name__ == "__main__":
    main()
