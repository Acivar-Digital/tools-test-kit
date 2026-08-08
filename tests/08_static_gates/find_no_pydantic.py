import ast
import os
from pathlib import Path
from typing import Any

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# Annot: src2 is baziforecaster-only; honour KIT_PATH override, else kit-relative.
_kit_path = os.getenv("KIT_PATH", "")
TARGET_DIR = Path(_kit_path) / "src2" if _kit_path else Path(__file__).resolve().parents[3] / "baziforecaster" / "src2"

# Allowed Pydantic base classes
PYDANTIC_BASES = {"BaseModel", "RootModel", "GenericModel", "BaseSettings"}

# Non-Pydantic base classes that are allowed (e.g., Enums or custom Exceptions)
# Clear this set or set to set() if you want STRICT non-pydantic flags for everything.
ALLOWED_NON_PYDANTIC_BASES = {
    "Enum",
    "IntEnum",
    "StrEnum",
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
}

# Pydantic subclasses that should also be treated as Pydantic bases
PYDANTIC_SUBCLASSES = {
    "IERResult",
}

# If True, files without any class definitions will also be flagged
FLAG_FILES_WITHOUT_CLASSES = False
# ==============================================================================


def get_base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.Subscript):
        return get_base_name(node.value)
    return ""


def _build_attr_string(node: ast.AST) -> str:
    """Helper to reconstruct full decorator paths like pydantic.dataclasses.dataclass"""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_build_attr_string(node.value)}.{node.attr}"
    return ""


def _has_pydantic_base(base_names: set[str]) -> bool:
    return bool(base_names & PYDANTIC_BASES)


def _has_allowed_base(base_names: set[str]) -> bool:
    return bool(base_names & ALLOWED_NON_PYDANTIC_BASES)


def _has_pydantic_subclass(base_names: set[str]) -> bool:
    return bool(base_names & PYDANTIC_SUBCLASSES)


def _class_is_pydantic(node: ast.ClassDef) -> bool:
    base_names = {get_base_name(base) for base in node.bases}
    decorator_names = set(_get_decorator_names(node.decorator_list))
    
    # Check if any decorator is a known Pydantic dataclass variant
    is_pydantic_dataclass = any(
        dec in {"pydantic.dataclass", "pydantic.dataclasses.dataclass"} 
        for dec in decorator_names
    )

    return (
        _has_pydantic_base(base_names)
        or is_pydantic_dataclass
        or _has_allowed_base(base_names)
        or _has_pydantic_subclass(base_names)
    )


def _get_decorator_names(decorators: list[ast.expr]) -> list[str]:
    names = []
    for dec in decorators:
        # If the decorator is called with arguments like @dataclass(kw_only=True)
        # unwrap the ast.Call to get to the actual function name
        if isinstance(dec, ast.Call):
            dec = dec.func
            
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.append(_build_attr_string(dec))
    return names


def _build_non_pydantic_entry(node: ast.ClassDef) -> dict[str, Any]:
    return {
        "name": node.name,
        "line": node.lineno,
        "bases": [get_base_name(base) for base in node.bases],
        "decorators": _get_decorator_names(node.decorator_list),
    }


def _finalize_pydantic_result(
    non_pydantic_classes: list[dict[str, Any]], total_classes: int
) -> bool:
    is_100_percent_pydantic = len(non_pydantic_classes) == 0
    if FLAG_FILES_WITHOUT_CLASSES and total_classes == 0:
        is_100_percent_pydantic = False
    return is_100_percent_pydantic


def check_file(file_path: Path) -> dict[str, Any]:
    """Parses a Python file and returns Pydantic compliance metrics."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return {
            "file": file_path,
            "valid": False,
            "error": str(e),
            "non_pydantic_classes": [],
            "total_classes": 0,
            "is_100_percent_pydantic": False,
        }

    non_pydantic_classes: list[dict[str, Any]] = []
    total_classes = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            total_classes += 1
            if not _class_is_pydantic(node):
                non_pydantic_classes.append(_build_non_pydantic_entry(node))

    return {
        "file": file_path,
        "valid": True,
        "total_classes": total_classes,
        "non_pydantic_classes": non_pydantic_classes,
        "is_100_percent_pydantic": _finalize_pydantic_result(non_pydantic_classes, total_classes),
    }


def _categorize_files(py_files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pydantic_files = []
    non_pydantic_files = []
    for py_file in py_files:
        res = check_file(py_file)
        if not res["valid"]:
            print(f"Could not parse: {py_file} - Syntax/Read Error: {res['error']}")
            continue
        if res["is_100_percent_pydantic"]:
            pydantic_files.append(res)
        else:
            non_pydantic_files.append(res)
    return pydantic_files, non_pydantic_files


def _format_class_entry(cls: dict[str, Any]) -> str:
    bases = f" (inherits: {', '.join(cls['bases'])})" if cls['bases'] else ""
    decs = f" [decorators: {', '.join(cls['decorators'])}]" if cls['decorators'] else ""
    return f"   Line {cls['line']}: class {cls['name']}{bases}{decs}"


def _print_class_details(res: dict[str, Any]) -> None:
    if res["non_pydantic_classes"]:
        for cls in res["non_pydantic_classes"]:
            print(_format_class_entry(cls))
    elif FLAG_FILES_WITHOUT_CLASSES and res["total_classes"] == 0:
        print("   Reason: File contains no class definitions.")


def _print_non_pydantic_files(non_pydantic_files: list[dict[str, Any]], target_path: Path) -> None:
    if not non_pydantic_files:
        print("All Python files are 100% Pydantic compliant!")
        return
    for res in non_pydantic_files:
        rel_path = res["file"].relative_to(target_path)
        print(f"\n{rel_path}")
        _print_class_details(res)


def _print_summary(py_files: list[Path], pydantic_files: list[dict[str, Any]], non_pydantic_files: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Files Analyzed : {len(py_files)}")
    print(f"100% Pydantic Files  : {len(pydantic_files)}")
    print(f"Non-Pydantic Files   : {len(non_pydantic_files)}")


def main() -> int:
    target_path = Path(TARGET_DIR)

    if not target_path.exists():
        print(f"Error: Directory '{TARGET_DIR}' does not exist.")
        return 1

    py_files = sorted(list(target_path.glob("**/*.py")))
    print(f"Scanning {len(py_files)} Python file(s) in: {TARGET_DIR}\n")

    pydantic_files, non_pydantic_files = _categorize_files(py_files)

    print("=" * 80)
    print("FILES NOT 100% PYDANTIC")
    print("=" * 80)
    _print_non_pydantic_files(non_pydantic_files, target_path)
    _print_summary(py_files, pydantic_files, non_pydantic_files)

    return len(non_pydantic_files)


if __name__ == "__main__":
    count = main()
    if count is not None and count > 0:
        raise SystemExit(1)
