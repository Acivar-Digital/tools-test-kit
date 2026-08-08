from __future__ import annotations

# kit-hygiene/scanners/verify_dict_access_runtime.py
#
# Runtime Layer-1 verifier for dictionary-style access on Pydantic models.
#
# Pipeline:
#   static scanner (find_dict_access_on_models.py) -> dict_access_on_models.json
#     (each candidate carries `kind` = METHOD | SUBSCRIPT | SUBSCRIPT_ASSIGN
#      and `access` = the actual offending expression)
#   this harness -> executes the producing function, reproduces the REAL access
#      on the returned object, and reports:
#        CONFIRMED_CRASH : object rejected dict access -> it is a model -> real bug
#        SAFE_MODEL      : object tolerated dict access -> it is a dict -> no bug
#        SAFE_DICT       : producer returned a plain dict/list -> no bug
#        UNVERIFIABLE    : producer could not be executed (DB/network/state)
#
# This is the DEFINITIVE Layer 1: it proves crashes by execution, not guesswork.

import argparse
import ast
import asyncio
import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

# Add workspace root to sys.path to allow absolute imports
from _bootstrap import pkg_root, target_root  # noqa: F401,E402  (target_root on sys.path so src2.* resolves)

from pydantic import BaseModel

try:
    from src2.core.schemas.unified import (
        ChartProfile,
        DaYunOutput,
        Pillar,
    )
    _UNIFIED_AVAILABLE: bool = True
except ImportError:
    ChartProfile = DaYunOutput = Pillar = None  # type: ignore[assignment,misc]
    _UNIFIED_AVAILABLE = False

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


def build_sample_profile() -> ChartProfile | None:
    """Constructs a deterministic, valid ChartProfile for best-effort execution."""
    if not _UNIFIED_AVAILABLE:
        print("[INFO] src2.core.schemas.unified not importable on this repo — skipping runtime verification sample")
        return None
    return ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        day_pillar=Pillar(stem="Wu", branch="Chen"),
        hour_pillar=Pillar(stem="Geng", branch="Wu"),
        da_yun_pillar=Pillar(stem="Xin", branch="Wei"),
        favorable_elements=["Wood", "Water"],
        unfavorable_elements=["Metal", "Earth"],
        medicine=["Wood"],
        taboo=["Metal"],
        age=30,
        dob="1996-02-15",
        gender="M",
        da_yun=DaYunOutput(start_age=5, start_year=2001, direction="Forward", cycles=[]),
        day_stem_stream="Jia zi",
        elemental_concentration={"Wood": 40.0, "Fire": 20.0, "Earth": 20.0, "Metal": 10.0, "Water": 10.0},
        ge_ju_type="Normal",
        ge_ju_alignment_mod=1.0,
        shen_profile={},
        strength_profile={"spectrum_tier": "Neutral", "classification": "Mild Weak", "continuous_score": 5.0},
        dm_strength_type="Balanced",
        target_year=2026,
        da_yun_start_year=2026,
        neutral_elements=["Fire"],
        monthly_composite_score=75.5,
        domain_focus="General",
        months_into_dayun=12,
        macro_results={},
        compatibility_profile={},
        user_id="test_user",
        chat_id="test_chat",
        source="runtime_verifier",
    )


def workspace_root() -> Path:
    """Root of the repo being scanned (TARGET_ROOT env, else repo root)."""
    return target_root


def get_src2_files() -> list[Path]:
    """Recursively find all Python files in src2/."""
    src2_dir = workspace_root() / "src2"
    if not src2_dir.exists():
        return []
    return list(src2_dir.rglob("*.py"))


def discover_models(files: list[Path]) -> dict[str, str]:
    """Maps model class name -> module path (for instantiating annotated args)."""
    model_classes: dict[str, str] = {}
    for file_path in files:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except Exception:
            continue
        mod_path = str(file_path.relative_to(workspace_root())).replace("/", ".").replace(".py", "")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if (isinstance(base, ast.Name) and base.id == "BaseModel") or (
                        isinstance(base, ast.Attribute) and base.attr == "BaseModel"
                    ):
                        model_classes[node.name] = mod_path
                        break
    return model_classes


def module_path_for_file(file_path: str) -> str | None:
    full = workspace_root() / file_path
    if not full.exists():
        return None
    rel = full.with_suffix("").relative_to(workspace_root())
    return ".".join(rel.parts)


def resolve_producing_function(file_path: str, line: int, variable: str) -> tuple[str | None, str | None]:
    """
    Finds the function that produced `variable` near `line`.
    Returns (function_name, resolution_type) where resolution_type is
    'function' (variable assigned from a call) or 'model_class' (variable is a
    function argument annotated with a model class).
    """
    full_path = workspace_root() / file_path
    if not full_path.exists():
        return None, None

    try:
        with open(full_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(full_path))
    except Exception:
        return None, None

    enclosing_func = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= line <= node.end_lineno:
                    enclosing_func = node
                    break

    if not enclosing_func:
        return None, None

    # Is it an argument to the enclosing function?
    for arg in enclosing_func.args.args + enclosing_func.args.kwonlyargs:
        if arg.arg == variable:
            if arg.annotation and isinstance(arg.annotation, ast.Name):
                return arg.annotation.id, "model_class"
            return None, None

    # Walk body to find the last assignment to `variable` that is a Call.
    last_call_name = None
    for node in ast.walk(enclosing_func):
        if hasattr(node, "lineno") and node.lineno <= line:
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if variable in targets and isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        last_call_name = node.value.func.id
                    elif isinstance(node.value.func, ast.Attribute):
                        last_call_name = node.value.func.attr
    return last_call_name, "function"


def _navigate(obj: Any, path: str) -> Any:
    """Walk `obj` through a dotted/bracketed path like a.b['c'] to reach the
    object that is actually subjected to the dict access."""
    cur = obj
    for m in re.finditer(r"\.([A-Za-z_][\w]*)|\[([^\]]*)\]", path):
        attr, idx = m.group(1), m.group(2)
        if attr:
            cur = getattr(cur, attr)
        else:
            key = idx.strip().strip("'\"") if idx.strip() else "__probe__"
            try:
                cur = cur[key]
            except Exception:
                cur = cur["__probe__"]
    return cur


def probe_access(obj: Any, candidate: dict[str, Any]) -> str:
    """
    Reproduce the REAL dict-style access on `obj`.
    Returns SAFE_MODEL if the object tolerates it (it is a dict -> no bug),
    or CONFIRMED_CRASH if it rejects it (it is a model -> real bug).
    """
    kind = candidate.get("kind", "")
    access = candidate.get("access", "")
    try:
        if kind == "METHOD":
            method = None
            target_path = access
            for m in BANNED_DICT_METHODS:
                idx = access.rfind(f".{m}(")
                if idx != -1:
                    method = m
                    target_path = access[:idx]
                    break
            target = _navigate(obj, target_path) if target_path else obj
            getattr(target, method)("__probe__")
        else:
            # SUBSCRIPT / SUBSCRIPT_ASSIGN -> subscript the (navigated) target.
            target_path = access.split("[", 1)[0]
            target = _navigate(obj, target_path) if target_path else obj
            target["__probe__"]
        return "SAFE_MODEL"
    except (AttributeError, TypeError):
        # Object has no dict method / is not subscriptable -> it is a model.
        return "CONFIRMED_CRASH"
    except KeyError:
        # Object IS subscriptable, just missing the dummy key -> it is a dict.
        return "SAFE_MODEL"


def instantiate_model(class_name: str, mod_path: str) -> BaseModel | None:
    try:
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, class_name)
        if class_name == "ChartProfile":
            return build_sample_profile()
        try:
            return cls()
        except Exception:
            # Model has required fields we cannot satisfy generically.
            # Returning a bare __new__ instance yields a half-built object whose
            # fields are missing, which makes probe_access falsely report a crash
            # (CONFIRMED_CRASH) on dict-typed fields like session.metadata.
            # Honest verdict is UNVERIFIABLE: we cannot reconstruct the object.
            return None
    except Exception:
        return None


def execute_and_verify(func_name: str, mod_path: str, candidate: dict[str, Any]) -> str:
    """Executes `func_name` in `mod_path` and probes the returned object."""
    try:
        mod = importlib.import_module(mod_path)
        func = getattr(mod, func_name)
    except Exception:
        return "UNVERIFIABLE"

    kwargs: dict[str, Any] = {}
    try:
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            ann = str(param.annotation)
            if "ChartProfile" in ann:
                kwargs[name] = build_sample_profile()
            elif "Pillar" in ann:
                kwargs[name] = Pillar(stem="Jia", branch="Zi")
            elif "dict" in ann.lower() or "Dict" in ann:
                kwargs[name] = {}
            elif "str" in ann.lower():
                kwargs[name] = ""
            elif "int" in ann.lower():
                kwargs[name] = 0
            elif "bool" in ann.lower():
                kwargs[name] = False
            elif "list" in ann.lower() or "List" in ann:
                kwargs[name] = []
            elif param.default != inspect.Parameter.empty:
                kwargs[name] = param.default
            else:
                kwargs[name] = None
    except Exception:
        return "UNVERIFIABLE"

    try:
        if inspect.iscoroutinefunction(func):
            result = asyncio.run(func(**kwargs))
        else:
            result = func(**kwargs)
    except Exception:
        # Fails due to network, missing DB, or strict validation of dummy data.
        return "UNVERIFIABLE"

    if isinstance(result, (dict, list)):
        return "SAFE_DICT"
    if isinstance(result, BaseModel):
        return probe_access(result, candidate)
    return "UNVERIFIABLE"


def load_candidates() -> list[dict[str, Any]]:
    reports_dir = pkg_root / "reports"
    json_path = reports_dir / "dict_access_on_models.json"
    sample_path = pkg_root / "studio" / "upload" / "dict_access_on_models_sample.json"

    for path in (json_path, sample_path):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cands = data.get("verified", []) + data.get("failed", [])
                if cands:
                    return cands
            except Exception:
                continue
    return []


def main():
    parser = argparse.ArgumentParser(description="Runtime Verifier for Dict Access on Pydantic Models")
    parser.add_argument("--scripts", action="store_true", help="List candidates without executing")
    args = parser.parse_args()

    candidates = load_candidates()
    if not candidates:
        print("No candidate JSON found. Run find_dict_access_on_models.py first.")
        sys.exit(1)

    if args.scripts:
        for idx, c in enumerate(candidates, 1):
            print(
                f"[{idx}] {c.get('file_path')}:{c.get('line')} `{c.get('variable')}` {c.get('kind', '')}: {c.get('access', '')}"
            )
        sys.exit(0)

    files = get_src2_files()
    model_classes = discover_models(files)

    results = []
    tallies = {"CONFIRMED_CRASH": 0, "SAFE_DICT": 0, "SAFE_MODEL": 0, "UNVERIFIABLE": 0}

    print(f"Starting runtime verification for {len(candidates)} candidates...")

    for idx, candidate in enumerate(candidates, 1):
        file_path = candidate.get("file_path")
        line = candidate.get("line")
        variable = candidate.get("variable")

        func_name, res_type = resolve_producing_function(file_path, line, variable)

        verdict = "UNVERIFIABLE"
        detail = "Could not resolve producing function"
        if func_name and res_type == "model_class" and func_name in model_classes:
            inst = instantiate_model(func_name, model_classes[func_name])
            if inst is not None:
                verdict = probe_access(inst, candidate)
                detail = f"Annotated arg of model class {func_name}"
        elif func_name:
            mod_path = module_path_for_file(file_path)
            if mod_path:
                verdict = execute_and_verify(func_name, mod_path, candidate)
                detail = f"Resolved to {func_name}"

        tallies[verdict] += 1
        results.append(
            {
                "file_path": file_path,
                "line": line,
                "variable": variable,
                "verdict": verdict,
                "kind": candidate.get("kind", ""),
                "access": candidate.get("access", ""),
                "detail": detail,
            }
        )
        print(f"[{idx}/{len(candidates)}] {file_path}:{line} `{variable}` -> {verdict}")

    reports_dir = pkg_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_json = reports_dir / "dict_access_runtime.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    out_md = reports_dir / "dict_access_runtime.md"
    lines = [
        "# 🏃 Runtime Verification: Dict Access on Pydantic Models\n",
        f"**Summary:** CONFIRMED_CRASH: {tallies['CONFIRMED_CRASH']} | "
        f"SAFE_DICT: {tallies['SAFE_DICT']} | "
        f"SAFE_MODEL: {tallies['SAFE_MODEL']} | "
        f"UNVERIFIABLE: {tallies['UNVERIFIABLE']}\n",
    ]
    by_file: dict[str, list] = {}
    for r in results:
        by_file.setdefault(r["file_path"], []).append(r)
    for fp, items in sorted(by_file.items()):
        lines.append(f"\n## 📂 `{fp}`\n")
        for item in sorted(items, key=lambda x: x["line"]):
            icon = (
                "💥"
                if item["verdict"] == "CONFIRMED_CRASH"
                else "✅"
                if item["verdict"] in ("SAFE_DICT", "SAFE_MODEL")
                else "⚠️"
            )
            lines.append(
                f"- {icon} **L{item['line']}** `{item['variable']}`: **{item['verdict']}** "
                f"({item['kind']} `{item['access']}` — {item['detail']})\n"
            )
    out_md.write_text("".join(lines), encoding="utf-8")

    print(
        f"\nLayer 1 Runtime Verification complete. "
        f"CONFIRMED_CRASH: {tallies['CONFIRMED_CRASH']}, "
        f"SAFE_DICT: {tallies['SAFE_DICT']}, "
        f"SAFE_MODEL: {tallies['SAFE_MODEL']}, "
        f"UNVERIFIABLE: {tallies['UNVERIFIABLE']}"
    )
    print(f"Reports written to {out_json} and {out_md}")


if __name__ == "__main__":
    main()
