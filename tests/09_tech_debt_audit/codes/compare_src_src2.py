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
    def __init__(self):
        self.definitions = []  # List of tuples: (name, type, line)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "function", node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "async_function", node.lineno))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not node.name.startswith("__"):
            self.definitions.append((node.name, "class", node.lineno))
        self.generic_visit(node)

def get_definitions(file_path: Path) -> dict[str, tuple[str, int]]:
    """Return a dict of name -> (type, line) for definitions in the file."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        collector = DefinitionCollector()
        collector.visit(tree)
        return {name: (t, line) for name, t, line in collector.definitions}
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return {}

def is_imported_in_dir(directory: str, file_rel_path: str, name: str) -> bool:
    """Check if `name` from `file_rel_path` is imported or referenced in `directory`."""
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    files = get_files(directory)

    # We want to check if it's imported in other files
    def_mod = file_rel_path.replace("/", ".").replace(".py", "")

    for f in files:
        f_rel = str(f)
        if f_rel == file_rel_path:
            continue

        try:
            with open(f, encoding="utf-8", errors="ignore") as file_obj:
                content = file_obj.read()
            if pattern.search(content):
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name == def_mod or alias.name.startswith(def_mod + "."):
                                    return True
                        elif isinstance(node, ast.ImportFrom):
                            imported_mod = ""
                            if node.level > 0:
                                ref_parts = f.parent.parts
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
                except Exception:
                    pass
        except Exception:
            pass
    return False

def main():
    print("Collecting files from src and src2...")
    src_files = get_files("src")
    src2_files = get_files("src2")

    src_rel_to_path = {str(p.relative_to("src")): p for p in src_files}
    src2_rel_to_path = {str(p.relative_to("src2")): p for p in src2_files}

    # Load existing audit json if available
    audit_results = {}
    audit_path = Path("TEST/codes/dead_code_audit.json")
    if audit_path.exists():
        try:
            with open(audit_path, encoding="utf-8") as f:
                audit_data = json.load(f)
                for item in audit_data.get("audit_results", []):
                    audit_results[(item["file_path"], item["name"])] = item
        except Exception as e:
            print(f"Error loading audit JSON: {e}")

    missing_in_src2 = []
    dead_in_src2_but_alive_in_src = []

    print("Analyzing and comparing definitions...")
    for rel_path, src_file in src_rel_to_path.items():
        src2_file = src2_rel_to_path.get(rel_path)

        src_defs = get_definitions(src_file)
        src2_defs = get_definitions(src2_file) if src2_file else {}

        # 1. Check if src2 file is missing entirely
        if not src2_file:
            for name, (t, line) in src_defs.items():
                rel_src_path = str(src_file)
                was_alive = is_imported_in_dir("src", rel_src_path, name)
                missing_in_src2.append({
                    "name": name,
                    "type": t,
                    "src_file": rel_src_path,
                    "src_line": line,
                    "status": "FILE_MISSING",
                    "was_alive_in_src": was_alive
                })
            continue

        # 2. Check if specific functions in src are missing in src2
        for name, (t, line) in src_defs.items():
            rel_src_path = str(src_file)
            rel_src2_path = str(src2_file) if src2_file else ""

            if name not in src2_defs:
                was_alive = is_imported_in_dir("src", rel_src_path, name)
                missing_in_src2.append({
                    "name": name,
                    "type": t,
                    "src_file": rel_src_path,
                    "src_line": line,
                    "src2_file": rel_src2_path,
                    "status": "FUNCTION_MISSING",
                    "was_alive_in_src": was_alive
                })
            else:
                # 3. Check if the function exists in both, but is marked CONFIRMED_DEAD in src2
                audit_key = (rel_src2_path, name)
                if audit_key in audit_results:
                    audit_item = audit_results[audit_key]
                    if audit_item.get("status") == "CONFIRMED_DEAD":
                        was_alive = is_imported_in_dir("src", rel_src_path, name)
                        if was_alive:
                            dead_in_src2_but_alive_in_src.append({
                                "name": name,
                                "type": t,
                                "src_file": rel_src_path,
                                "src_line": line,
                                "src2_file": rel_src2_path,
                                "src2_line": src2_defs[name][1],
                                "reason_in_src2": audit_item.get("reason"),
                                "was_alive_in_src": True
                            })

    # Output report
    print("\n" + "="*60)
    print("COMPARISON REPORT: src vs src2")
    print("="*60)

    print(f"\n[1] Missing in src2 ({len(missing_in_src2)} items):")
    for item in sorted(missing_in_src2, key=lambda x: (not x["was_alive_in_src"], x["src_file"])):
        alive_str = "ALIVE/IMPORTED in src 🟢" if item["was_alive_in_src"] else "dead/unused in src ⚪"
        if item["status"] == "FILE_MISSING":
            print(f"  - {item['type']} `{item['name']}` (defined in {item['src_file']}:{item['src_line']})")
            print(f"    Reason: File is missing in src2. [{alive_str}]")
        else:
            print(f"  - {item['type']} `{item['name']}` (defined in {item['src_file']}:{item['src_line']})")
            print(f"    Reason: Missing from {item['src2_file']}. [{alive_str}]")

    print(f"\n[2] Dead in src2 but was ALIVE in src ({len(dead_in_src2_but_alive_in_src)} items):")
    print("These symbols are marked CONFIRMED_DEAD in src2, but were imported/referenced in the original src!")
    for item in sorted(dead_in_src2_but_alive_in_src, key=lambda x: x["src_file"]):
        print(f"  - {item['type']} `{item['name']}` (in {item['src2_file']}:{item['src2_line']})")
        print(f"    Original: {item['src_file']}:{item['src_line']}")
        print(f"    Audit Reason in src2: {item['reason_in_src2']}")

if __name__ == "__main__":
    main()
