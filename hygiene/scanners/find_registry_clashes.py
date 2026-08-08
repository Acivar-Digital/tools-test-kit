from __future__ import annotations

# kit-hygiene/scanners/find_registry_clashes.py
#
# Static + LLM + Runtime scanner: finds dict-style access on registry models
# from unified.py, which were converted from dicts to Pydantic models in Phase 1.
# Validates whether the call will crash based on the actual model API surface.
#
# Emits kit-hygiene/reports/registry_clashes.json

import ast
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import instructor
    import openai

import tenacity
from pydantic import BaseModel, Field

# Ensure repo root in sys.path
from _bootstrap import pkg_root  # noqa: F401,E402

from utils import get_src2_files
from control import ControlSheet, SystemSettings  # noqa: E402

# Initialize fast-json-repair if available
try:
    from fast_json_repair import repair_json
except ImportError:
    def repair_json(json_string: str, **kwargs: Any) -> Any: return json_string

# Configure logging with ANSI colors
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'INFO': '\033[94m',      # Blue
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[91m\033[1m' # Bold Red
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)

        # Make specific patterns bolder
        msg = record.getMessage()
        if msg.startswith("[") and "]" in msg:
            # Highlight progress like [1/25]
            end_idx = msg.find("]") + 1
            msg = f"{self.BOLD}{self.GREEN}{msg[:end_idx]}{self.RESET} {msg[end_idx:].strip()}"
        elif "AST scan complete" in msg:
            msg = f"{self.BOLD}{self.GREEN}{msg}{self.RESET}"
        elif "Scan complete" in msg or "Summary:" in msg:
            msg = f"{self.BOLD}{msg}{self.RESET}"

        return f"{color}[{record.levelname}]{self.RESET} {msg}"

handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger = logging.getLogger("RegistryScanner")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

CHECKPOINT_FILE = pkg_root / "reports" / "registry_clashes_checkpoint.jsonl"
REPORT_FILE = pkg_root / "reports" / "registry_clashes.json"
BANNED_METHODS = {"keys", "items", "values", "get", "pop", "popitem", "setdefault", "update", "clear", "copy"}


# =====================================================================
# SCHEMA DEFINITIONS
# =====================================================================

class CallSite(BaseModel):
    source_module: str = ""
    file_path: str
    line: int
    variable: str
    method: str
    expression: str
    context_lines: list[str]


class AnalysisVerdict(BaseModel):
    status: str = Field(..., description="CRASH, SILENT_BUG, OK, or UNCERTAIN")
    reason: str = Field(..., description="Detailed explanation of why it will crash or work")
    registry_class: str = Field(..., description="Name of the registry class in unified.py")
    suggested_fix: str = Field(default="", description="How to fix the code, if broken")


class LLMScanResult(BaseModel):
    file_path: str
    scanned: bool
    findings: list[dict[str, Any]]


# =====================================================================
# LAYER 1: REGISTRY INTROSPECTION
# =====================================================================

def build_registry_api_map() -> dict:
    """Introspect unified.py to find all registry objects and their API surfaces."""
    from src2.core.schemas import unified

    registry_map = {}

    for name, obj in vars(unified).items():
        if name.startswith('_'):
            continue

        if isinstance(obj, (unified.BaseModel,)):
            cls = type(obj)
            cls_name = cls.__name__

            # Map object name (e.g. STEMS) to its class and capabilities
            registry_map[name] = {
                "class_name": cls_name,
                "has_keys": hasattr(cls, 'keys') or hasattr(obj, 'keys'),
                "has_contains": hasattr(cls, '__contains__'),
                "has_getitem": hasattr(cls, '__getitem__'),
                "has_items": hasattr(cls, 'items') or hasattr(obj, 'items'),
                "has_values": hasattr(cls, 'values') or hasattr(obj, 'values'),
                "has_get": hasattr(cls, 'get') or hasattr(obj, 'get'),
                "is_root_model": issubclass(cls, unified.RootModel) or hasattr(cls, '__pydantic_root_model__')
            }

    return registry_map


# =====================================================================
# LAYER 2: AST STATIC DETECTION
# =====================================================================

def get_context_lines(path: Path, line_num: int, window: int = 5) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(0, line_num - window - 1)
        end = min(len(lines), line_num + window)
        return lines[start:end]
    except Exception:
        return []


def base_source(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{base_source(node.value)}.{node.attr}"
        return "?"


def scan_file_ast(path: Path, registry_map: dict) -> tuple[list[CallSite], dict[str, str]]:
    """AST-walk to find imports and suspicious dict calls."""
    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
    except Exception as e:
        print("❌ ERROR: " + f"AST parse failed for {path}: {e}")
        return [], {}

    # 1. Build import map for this file
    import_map = {}
    import_module_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local_name = alias.asname or alias.name
                import_map[local_name] = alias.name
                import_module_map[local_name] = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                import_map[local_name] = alias.name
                import_module_map[local_name] = alias.name
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Also catch inner imports
            for inner in ast.walk(node):
                if isinstance(inner, ast.ImportFrom) and inner.module:
                    for alias in inner.names:
                        local_name = alias.asname or alias.name
                        import_map[local_name] = alias.name
                        import_module_map[local_name] = inner.module

    # 2. Find dict-style access
    candidates: list[CallSite] = []
    rel_path = str(path.relative_to(pkg_root))

    for node in ast.walk(tree):
        # METHOD: obj.keys()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in BANNED_METHODS:
                base = base_source(node.func.value)
                var_name = base.split(".")[0]

                # Check if it matches an import or is an uppercase name (likely registry)
                if var_name in import_map or var_name.isupper():
                    candidates.append(CallSite(
                        file_path=rel_path,
                        line=node.lineno,
                        variable=var_name,
                        source_module=import_module_map.get(var_name, ""),
                        method=method,
                        expression=ast.unparse(node),
                        context_lines=get_context_lines(path, node.lineno)
                    ))

        # SUBSCRIPT: obj[key]
        elif isinstance(node, ast.Subscript):
            base = base_source(node.value)
            var_name = base.split(".")[0]
            if var_name in import_map or var_name.isupper():
                candidates.append(CallSite(
                    file_path=rel_path,
                    line=node.lineno,
                    variable=var_name,
                        source_module=import_module_map.get(var_name, ""),
                    method="__getitem__",
                    expression=ast.unparse(node),
                    context_lines=get_context_lines(path, node.lineno)
                ))

        # IN-OPERATOR: item in REGISTRY
        elif isinstance(node, ast.Compare):
            if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                for comparator in node.comparators:
                    base = base_source(comparator)
                    var_name = base.split(".")[0]
                    if var_name in import_map or var_name.isupper():
                        candidates.append(CallSite(
                            file_path=rel_path,
                            line=node.lineno,
                            variable=var_name,
                        source_module=import_module_map.get(var_name, ""),
                            method="__contains__",
                            expression=ast.unparse(node),
                            context_lines=get_context_lines(path, node.lineno)
                        ))

    return candidates, import_map


# =====================================================================
# LAYER 3: LLM EVALUATION
# =====================================================================

@tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_exponential(multiplier=1, min=2, max=10))
async def evaluate_call_site(client: instructor.AsyncInstructor, site: CallSite, import_map: dict, registry_map: dict) -> dict:
    """Ask LLM to classify the crash certainty."""

    # Resolve the original registry name from the import map
    orig_name = import_map.get(site.variable)
    if not orig_name and site.variable in registry_map:
        orig_name = site.variable

    if orig_name and orig_name in registry_map:
        reg_info = registry_map[orig_name]
        api_context = f"Variable '{site.variable}' is imported from unified.py as '{orig_name}' (class {reg_info['class_name']}).\n"
        api_context += f"Class Capabilities: has_keys={reg_info['has_keys']}, has_contains={reg_info['has_contains']}, has_getitem={reg_info.get('has_getitem', False)}, "
        api_context += f"has_items={reg_info['has_items']}, has_values={reg_info['has_values']}, is_root_model={reg_info['is_root_model']}\n"

        # Helper hint for the nasty __contains__ bug on BaseModel
        if site.method == "__contains__" and not reg_info['has_contains'] and not reg_info['is_root_model']:
            api_context += "CRITICAL NOTE: This is a BaseModel without __contains__. The 'in' operator will fallback to iterating BaseModel fields (yielding tuples of field_name, value). Checking if a string is 'in' this model will always silently return False. This is a SILENT_BUG.\n"
    else:
        api_context = f"Variable '{site.variable}' is NOT directly imported from unified.py registries in this file. It may be a regular dict or a propagated registry."
        reg_info = {"class_name": "unknown"}

    prompt = f"""
    Analyze this code snippet for a Pydantic migration dict-access clash.
    
    File: {site.file_path}
    Line: {site.line}
    Expression: {site.expression}
    
    API Context:
    {api_context}
    
    Code Context:
    ```python
    {chr(10).join(site.context_lines)}
    ```
    
    Determine if `{site.expression}` will raise an AttributeError/TypeError at runtime (CRASH), 
    is a silent logic bug returning False (SILENT_BUG), is perfectly safe (OK), 
    or if you cannot be certain without deeper type tracing (UNCERTAIN).
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model_name = ControlSheet.scanner_model.model_name
            response = await client.chat.completions.create(
                model=model_name,
                response_model=AnalysisVerdict,
                messages=[
                    {"role": "system", "content": "You are an expert Python code reviewer looking for bugs caused by migrating dictionaries to Pydantic BaseModels."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )

            return {
                "file_path": site.file_path,
                "line": site.line,
                "variable": site.variable,
                "method": site.method,
                "expression": site.expression,
                "status": response.status,
                "reason": response.reason,
                "registry_class": response.registry_class,
                "suggested_fix": response.suggested_fix
            }
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[93m⚠️  LLM timeout/error on {site.file_path}:{site.line} -> {e}. Retrying ({attempt+1}/{max_retries})...[0m")
                import asyncio
                await asyncio.sleep(2 ** attempt)  # exponential backoff
            else:
                print(f"[91m🚨 FATAL LLM ERROR on {site.file_path}:{site.line} after {max_retries} attempts: {e}[0m")
                return {
                    "file_path": site.file_path,
                    "line": site.line,
                    "variable": site.variable,
                    "method": site.method,
                    "expression": site.expression,
                    "status": "ERROR",
                    "reason": f"LLM error: {str(e)}",
                    "registry_class": reg_info.get("class_name", "unknown"),
                    "suggested_fix": ""
                }


# =====================================================================

def runtime_verify_pre(site, import_map) -> str:
    orig_name = import_map.get(site.variable) or site.variable

    # 1. Try to import from the file where it was defined (from AST)
    obj = None
    if site.source_module:
        try:
            import importlib
            mod = importlib.import_module(site.source_module)
            obj = getattr(mod, orig_name, None)
        except Exception:
            pass

    # 2. Try the file where the CallSite lives (if it was defined locally)
    if obj is None:
        try:
            import importlib
            local_mod_path = site.file_path.replace(".py", "").replace("/", ".")
            mod = importlib.import_module(local_mod_path)
            obj = getattr(mod, orig_name, None)
        except Exception:
            pass

    # 3. Fallback to unified
    if obj is None:
        try:
            from src2.core.schemas import unified
            obj = getattr(unified, orig_name, None)
        except Exception:
            pass

    if obj is None:
        return "UNVERIFIED"

    try:
        if site.method == "__contains__":
            if not hasattr(type(obj), "__contains__"):
                return "CONFIRMED_BUG"
            return "SAFE"
        elif site.method == "__getitem__":
            if not hasattr(type(obj), "__getitem__"):
                return "CONFIRMED_CRASH"
            return "SAFE"
        else:
            if hasattr(obj, site.method) or hasattr(type(obj), site.method):
                return "SAFE"
            else:
                return "CONFIRMED_CRASH"
    except Exception:
        return "UNVERIFIED"

# LAYER 4: RUNTIME VERIFICATION
# =====================================================================

def runtime_verify(finding: dict, registry_map: dict) -> dict:
    """Attempt to import unified.py and check hasattr directly."""
    orig_name = str(finding.get("variable", ""))

    if finding["status"] not in ("CRASH", "SILENT_BUG"):
        return finding

    try:
        from src2.core.schemas import unified
        obj = getattr(unified, orig_name, None)
        if not obj:
            finding["verified_status"] = "UNVERIFIED"
            return finding

        if finding["method"] == "__contains__":
            # Special check for BaseModel iteration bug
            if not hasattr(type(obj), "__contains__"):
                finding["verified_status"] = "CONFIRMED_BUG"
            else:
                finding["verified_status"] = "SAFE"
        elif finding["method"] == "__getitem__":
            # Check if subscriptable
            if not hasattr(type(obj), "__getitem__"):
                finding["verified_status"] = "CONFIRMED_CRASH"
            else:
                finding["verified_status"] = "SAFE"
        else:
            if hasattr(obj, finding["method"]) or hasattr(type(obj), finding["method"]):
                finding["verified_status"] = "LLM_MISMATCH_SAFE"
            else:
                finding["verified_status"] = "CONFIRMED_CRASH"

    except Exception as e:
        finding["verified_status"] = f"IMPORT_ERROR: {str(e)}"

    return finding


# =====================================================================
# ORCHESTRATOR
# =====================================================================

def load_checkpoint() -> set:
    if not CHECKPOINT_FILE.exists():
        return set()
    scanned = set()
    with open(CHECKPOINT_FILE) as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("scanned"):
                    scanned.add(data["file_path"])
            except (json.JSONDecodeError, KeyError):
                pass
    return scanned


def append_checkpoint(result: dict):
    with open(CHECKPOINT_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")


async def main_async(do_verify: bool, limit: int | None = None, scripts_only: bool = False):

    if os.getenv("KIT_ENABLE_REGISTRY_CLASHES", "false").lower() != "true":
        print("[INFO] registry clashes disabled")
        return

    print("🚀 Initializing Registry API Map...")
    registry_map = build_registry_api_map()
    print(f"📚 Loaded {len(registry_map)} registry schemas from unified.py")

    files = get_src2_files()
    print(f"🔍 Scanning {len(files)} files in src2/...")

    scanned_files = load_checkpoint()
    print(f"♻️ Resuming from checkpoint: {len(scanned_files)} already scanned")

    # Initialize Instructor client matching the exact provider for Gemini models
    # We use the openaic_client exposed by Pydantic-AI's OpenAIProvider if possible,
    # or build a direct openai async client using the exact controls.
    if os.getenv("KIT_ENABLE_REGISTRY_CLASHES", "false").lower() == "true":
        try:
            import openai
            import instructor

            s = SystemSettings()
            if not s.api_key or not s.api_key.strip():
                raise RuntimeError(
                    "KIT_ENABLE_REGISTRY_CLASHES=true but KIT_API_KEY is empty. "
                    "Set a valid API key in .env — fail-closed to prevent unauthenticated requests."
                )
            client = openai.AsyncOpenAI(
                base_url=s.base_url,
                api_key=s.api_key,
            )
            instructor_client = instructor.from_openai(client, mode=instructor.Mode.JSON)
        except Exception as e:
            print("❌ ERROR: " + f"Failed to initialize Instructor client: {e}")
            sys.exit(1)
    else:
        print("[INFO] registry clashes disabled")
        return

    # Extract candidates grouped by file
    files_with_candidates = []

    for path in files:
        if not path.is_absolute():
            path = pkg_root / path
        rel_path = str(path.relative_to(pkg_root))
        if rel_path in scanned_files:
            continue

        candidates, import_map = scan_file_ast(path, registry_map)
        if candidates:
            files_with_candidates.append((path, rel_path, candidates, import_map))

    total_files_to_scan = len(files_with_candidates)
    if total_files_to_scan == 0:
        print("✅ No candidates found or all files already scanned.")
    else:
        total_candidates = sum(len(c) for _, _, c, _ in files_with_candidates)
        print(f"🧠 AST scan complete. Found {total_candidates} candidates across {total_files_to_scan} files to audit.")
        if limit is not None:
            files_with_candidates = files_with_candidates[:limit]
            total_files_to_scan = len(files_with_candidates)
            total_candidates = sum(len(c) for _, _, c, _ in files_with_candidates)
            print(f"Limiting audit to first {total_files_to_scan} files ({total_candidates} candidates).")

    if scripts_only:
        print("Skipping LLM pass due to --scripts flag.")
        return

    all_findings = []

    candidates_done = 0
    total_candidates = sum(len(c) for _, _, c, _ in files_with_candidates)

    for index, (path, rel_path, candidates, import_map) in enumerate(files_with_candidates, 1):
        print(f"\n[{index}/{total_files_to_scan} files, {candidates_done}/{total_candidates} candidates] [start] 📂 {rel_path} ({len(candidates)} candidates)")

        results = []
        for c_idx, site in enumerate(candidates, 1):
            print(f"    -> 🛠️ [{c_idx}/{len(candidates)}] Checking `{site.variable}.{site.method}()` at line {site.line}...")

            pre_status = "UNVERIFIED"
            if do_verify:
                print("       -> ⚙️ Running runtime verification FIRST...")
                pre_status = runtime_verify_pre(site, import_map)

            if pre_status == "SAFE":
                print("       -> ✅ VERDICT: SAFE (Runtime verified, skipping LLM)")
                res = {
                    "file_path": rel_path,
                    "line": site.line,
                    "variable": site.variable,
                    "method": site.method,
                    "expression": site.expression,
                    "status": "OK",
                    "reason": "Dynamically verified safe. LLM skipped.",
                    "registry_class": import_map.get(site.variable, "?"),
                    "suggested_fix": None,
                    "verified_status": "LLM_MISMATCH_SAFE"
                }
            else:
                print(f"       -> 🧠 Runtime says {pre_status}. Contacting LLM for suggested fix/classification...")
                res = await evaluate_call_site(instructor_client, site, import_map, registry_map)
                if do_verify:
                    res["verified_status"] = pre_status
                    if pre_status in ("CONFIRMED_CRASH", "CONFIRMED_BUG"):
                        res["status"] = "CRASH"

                # Print outcome
                if res["status"] == "CRASH":
                    print(f"       -> 🔴 VERDICT: {res.get('verified_status', 'CRASH')} | {res.get('registry_class', '?')} has no attribute '{site.method}'")
                elif res["status"] == "ERROR":
                    print(f"       -> ⚠️ VERDICT: ERROR | {res['reason']}")
                else:
                    print(f"       -> ⚠️ VERDICT: {res.get('verified_status', 'UNVERIFIED')} | {res['status']} | {res['reason']}")

            results.append(res)
            candidates_done += 1

        # Save progress
        result_record = {"file_path": rel_path, "scanned": True, "findings": results}
        append_checkpoint(result_record)
        all_findings.extend(results)
        print(f"[{index}/{total_files_to_scan} files] [ok] ✅ {rel_path} checkpointed.")

    print("✅ Scan complete. Writing final report...")

    # Reload all findings from checkpoint for final report
    final_findings = []
    with open(CHECKPOINT_FILE) as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("findings"):
                    final_findings.extend(data["findings"])
            except (json.JSONDecodeError, KeyError):
                pass

    report = {
        "scanned_files_count": len(files),
        "clashes": [f for f in final_findings if f["status"] == "CRASH"],
        "surprises": [f for f in final_findings if f["status"] == "SILENT_BUG"],
        "suspects": [f for f in final_findings if f["status"] == "UNCERTAIN"],
        "ok": [f for f in final_findings if f["status"] == "OK"],
        "errors": [f for f in final_findings if f["status"] == "ERROR"],
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to {REPORT_FILE}")
    print("\n" + "="*50)
    print("🎯 FINAL SCAN SUMMARY")
    print("="*50)
    print(f"🔴 CRASH (Violations) : {len(report['clashes'])}")
    print(f"🟡 SILENT_BUG         : {len(report['surprises'])}")
    print(f"⚪ UNCERTAIN          : {len(report['suspects'])}")
    print(f"✅ OK (Safe)          : {len(report.get('ok', []))}")

    num_errors = len(report.get('errors', []))
    if num_errors > 0:
        print(f"\n\033[91m⚠️  API ERRORS OCCURRED: {num_errors}\033[0m")
        print(f"\033[91m   These {num_errors} candidates were skipped due to LLM connection failures.\033[0m")
        print("\033[91m   You MUST re-run the script to complete the scan.\033[0m")
    print("="*50 + "\n")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", action="store_true", help="AST only (skip LLM)")
    parser.add_argument("--diff", action="store_true", help="Only scan changed files")
    parser.add_argument("--verify", action="store_true", help="Run hasattr checks")
    args = parser.parse_args()

    asyncio.run(main_async(args.verify, None, args.scripts))


if __name__ == "__main__":
    main()
