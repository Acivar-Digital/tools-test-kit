# kit-hygiene/scanners/find_dict_access_on_models.py
#
# Static Layer-1 scanner: finds dictionary-style access on variables that may
# be Pydantic models (which reject dict access -> real crash).
#
# Emits kit-hygiene/reports/dict_access_on_models.json with the schema
# consumed by verify_dict_access_runtime.py:
#   { "verified": [...], "failed": [...] }
# each candidate:
#   { "file_path": str, "line": int, "variable": str,
#     "kind": "METHOD" | "SUBSCRIPT" | "SUBSCRIPT_ASSIGN", "access": str }

import ast
import json
import sys
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from utils import get_src2_files  # noqa: E402

BANNED_DICT_METHODS = {
    "get",
    "items",
    "keys",
    "values",
    "pop",
    "popitem",
    "setdefault",
    "update",
    "clear",
    "copy",
}


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def relative_path(path: Path) -> str:
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.relative_to(workspace_root()))
    except ValueError:
        return str(path)


def base_source(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{base_source(node.value)}.{node.attr}"
        return "?"


def scan_file(path: Path) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return []

    candidates: list[dict] = []
    rel = relative_path(path)

    for node in ast.walk(tree):
        # METHOD: obj.banned_method(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in BANNED_DICT_METHODS:
                base = base_source(node.func.value)
                candidates.append(
                    {
                        "file_path": rel,
                        "line": node.lineno,
                        "variable": base.split(".")[0],
                        "kind": "METHOD",
                        "access": f"{base}.{method}(",
                    }
                )
        # SUBSCRIPT: obj[key]  (and assignment target)
        elif isinstance(node, ast.Subscript):
            base = base_source(node.value)
            kind = "SUBSCRIPT"
            # SUBSCRIPT_ASSIGN: target of an assignment
            for parent in ast.walk(tree):
                if isinstance(parent, ast.Assign):
                    for t in parent.targets:
                        if t is node:
                            kind = "SUBSCRIPT_ASSIGN"
                            break
                if kind == "SUBSCRIPT_ASSIGN":
                    break
            candidates.append(
                {
                    "file_path": rel,
                    "line": node.lineno,
                    "variable": base.split(".")[0],
                    "kind": kind,
                    "access": f"{base}[...]",
                }
            )

    return candidates


def main() -> None:
    files = get_src2_files()
    all_candidates: list[dict] = []
    for f in files:
        all_candidates.extend(scan_file(f))

    # De-duplicate by (file_path, line, variable, kind, access)
    seen = set()
    deduped = []
    for c in all_candidates:
        key = (c["file_path"], c["line"], c["variable"], c["kind"], c["access"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    reports_dir = workspace_root() / "kit-hygiene" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "dict_access_on_models.json"
    out.write_text(json.dumps({"verified": deduped, "failed": []}, indent=2), encoding="utf-8")
    print(f"Scanned {len(files)} files -> {len(deduped)} dict-access candidates -> {out}")


if __name__ == "__main__":
    main()
