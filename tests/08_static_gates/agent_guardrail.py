#!/usr/bin/env python3
"""agent_guardrail.py — Post-edit checkpoint → lint → sanitize pipeline.

Workflow:
    1. checkpoint   — snapshot the file before LLM edits
    2. [LLM edits]  — (external step, not handled here)
    3. lint         — uv run ruff check <file>
    3b. typecheck    — uv run pyright <file> (scoped to this file)
    3c. dupe-check   — anti-LLM-duplication gate
    3d. cc-check     — cyclomatic complexity gate (CC < 6)
    3e. pydantic-check — 100% pydantic compliance gate
    4. if lint/typecheck/dupe/cc/pydantic fails — diff vs checkpoint
    5. if all pass   — run agent_sanitizer to fix escape artifacts

Usage:
    uv run python 08_static_gates/agent_guardrail.py checkpoint <file>
    uv run python 08_static_gates/agent_guardrail.py validate <file>
    uv run python 08_static_gates/agent_guardrail.py diff <file>
    uv run python 08_static_gates/agent_guardrail.py full <file>
    uv run python 08_static_gates/agent_guardrail.py cc-check <file>
    uv run python 08_static_gates/agent_guardrail.py pydantic-check <file>
"""

import ast
import difflib
import importlib.util
import json
import logging
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AgentGuardrail")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHECKPOINT_DIR = PROJECT_ROOT / ".checkpoints"
SANITIZER = SCRIPT_DIR / "agent_sanitizer.py"
HARNESS_DIR = PROJECT_ROOT / "admin" / "orchestrator"  # Annot: baziforecaster-only; guarded by _index_harness_dir
_HARNESS_SCAN_DIRS = ("infra", "common")

CC_THRESHOLD = 6

PYDANTIC_BASES = frozenset({"BaseModel", "RootModel", "GenericModel", "BaseSettings"})
ALLOWED_NON_PYDANTIC_BASES = frozenset(
    {"Enum", "IntEnum", "StrEnum", "Exception", "ValueError", "TypeError", "KeyError"}
)
PYDANTIC_SUBCLASSES = frozenset({"IERResult"})
EXCEPTIONS_PATH = SCRIPT_DIR / "agent_guardrail.json"


def _load_exceptions() -> dict[str, set[str]]:
    if not EXCEPTIONS_PATH.exists():
        return {"pydantic": set(), "cc": set()}
    try:
        data = json.loads(EXCEPTIONS_PATH.read_text(encoding="utf-8"))
        pydantic_keys = {
            f"{e['file']}:{e['class']}" for e in data.get("pydantic_exceptions", [])
        }
        cc_keys = {
            f"{e['file']}:{e['function']}" for e in data.get("cc_exceptions", [])
        }
        return {"pydantic": pydantic_keys, "cc": cc_keys}
    except (json.JSONDecodeError, OSError):
        return {"pydantic": set(), "cc": set()}


_EXCEPTIONS = _load_exceptions()


def _is_pydantic_exception(file_path: str, class_name: str) -> bool:
    key = f"{file_path}:{class_name}"
    return key in _EXCEPTIONS["pydantic"]


def _is_cc_exception(file_path: str, func_name: str) -> bool:
    key = f"{file_path}:{func_name}"
    return key in _EXCEPTIONS["cc"]


class CheckResult(BaseModel):
    success: bool
    stage: str | None = None
    message: str = ""


class CCViolation(BaseModel):
    name: str
    cc: int
    line: int


class CCResult(CheckResult):
    violations: list[CCViolation] = []
    count: int = 0


class PydanticClass(BaseModel):
    name: str
    line: int
    bases: list[str]
    decorators: list[str]


class PydanticResult(CheckResult):
    file: str = ""
    total_classes: int = 0
    non_pydantic_classes: list[PydanticClass] = []


def _resolve(path: str) -> Path:
    return Path(path).resolve()


def checkpoint(file_path: str) -> str | None:
    path = _resolve(file_path)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return None
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = CHECKPOINT_DIR / f"{path.stem}_{ts}{path.suffix}.bak"
    shutil.copy2(str(path), str(backup_path))
    logger.info(f"Checkpoint created: {backup_path}")
    return str(backup_path)


def _ruff_cmd() -> list[str]:
    venv_ruff = PROJECT_ROOT / ".venv" / "bin" / "ruff"
    if venv_ruff.exists():
        return [str(venv_ruff), "check"]
    if shutil.which("uv"):
        return ["uv", "run", "ruff", "check"]
    return ["ruff", "check"]


def _run_ruff(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*_ruff_cmd(), str(path)],
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        text=True,
        timeout=30,
    )


def _syntax_ok(path: Path) -> bool:
    return path.suffix == ".py"


def _lint_result(path: Path) -> CheckResult:
    result = _run_ruff(path)
    if result.returncode == 0:
        return CheckResult(success=True, message="Ruff check passed.")
    output = result.stdout[-1000:] if result.stdout else (result.stderr[-1000:] if result.stderr else "")
    return CheckResult(success=False, stage="lint", message=f"Ruff failed:\n{output}")


def _lint_precheck(path: Path) -> CheckResult | None:
    if not path.exists():
        return CheckResult(success=False, message=f"File not found: {path}")
    if path.suffix != ".py":
        return CheckResult(success=True, message="Skipped ruff check for non-Python file.")
    return None


def lint_file(file_path: str) -> CheckResult:
    path = _resolve(file_path)
    pre = _lint_precheck(path)
    if pre is not None:
        return pre
    if not _syntax_ok(path):
        return CheckResult(success=False, message="Syntax error in file.")
    return _lint_result(path)


def _pyright_errors(path: Path, output: str) -> list[str]:
    fname = path.name
    return [ln for ln in output.splitlines() if fname in ln and "error" in ln.lower()]


def _typecheck_run(path: Path) -> subprocess.CompletedProcess | None:
    if shutil.which("uv") is None or shutil.which("pyright") is None:
        return None
    return subprocess.run(
        ["uv", "run", "pyright", str(path)],
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        text=True,
        timeout=180,
    )


def _typecheck_result(path: Path, result: subprocess.CompletedProcess) -> CheckResult:
    output = (result.stdout or "") + (result.stderr or "")
    errors = _pyright_errors(path, output)
    if errors:
        return CheckResult(
            success=False,
            stage="typecheck",
            message=f"Pyright errors in {path.name}:\n" + "\n".join(errors),
        )
    return CheckResult(success=True, message="No type errors in this file.")


def _typecheck_precheck(path: Path) -> CheckResult | None:
    if not path.exists():
        return CheckResult(success=True, message=f"File not found: {path} (skipped)")
    if path.suffix != ".py":
        return CheckResult(success=True, message="Skipped type check for non-Python file.")
    return None


def typecheck_file(file_path: str) -> CheckResult:
    path = _resolve(file_path)
    pre = _typecheck_precheck(path)
    if pre is not None:
        return pre
    result = _typecheck_run(path)
    if result is None:
        return CheckResult(success=True, message="pyright not installed; skipped.")
    return _typecheck_result(path, result)


def _get_base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return _get_subscript_base(node)


def _get_subscript_base(node: ast.AST) -> str:
    if isinstance(node, ast.Subscript):
        return _get_base_name(node.value)
    return ""


def _has_pydantic_base(base_names: list[str]) -> bool:
    return bool(set(base_names) & PYDANTIC_BASES)


def _has_allowed_base(base_names: list[str]) -> bool:
    return bool(set(base_names) & ALLOWED_NON_PYDANTIC_BASES)


def _has_pydantic_subclass(base_names: list[str]) -> bool:
    return bool(set(base_names) & PYDANTIC_SUBCLASSES)


def _class_is_pydantic(node: ast.ClassDef) -> bool:
    base_names = [_get_base_name(b) for b in node.bases]
    return _has_pydantic_base(base_names) or _has_allowed_base(base_names) or _has_pydantic_subclass(base_names)


def _decorator_name(dec: ast.AST) -> str | None:
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return f"{_get_base_name(dec.value)}.{dec.attr}"
    return None


def _get_decorator_names(decorator_list: Sequence[ast.AST]) -> list[str]:
    return [n for d in decorator_list if (n := _decorator_name(d)) is not None]


def _inspect_class(node: ast.ClassDef) -> PydanticClass | None:
    decorator_names = _get_decorator_names(node.decorator_list)
    is_dc = "pydantic.dataclass" in decorator_names
    if _class_is_pydantic(node) or is_dc:
        return None
    return PydanticClass(
        name=node.name,
        line=node.lineno,
        bases=[_get_base_name(b) for b in node.bases],
        decorators=decorator_names,
    )


def _is_non_pydantic_class(node: ast.AST) -> PydanticClass | None:
    if not isinstance(node, ast.ClassDef):
        return None
    return _inspect_class(node)


def _scan_pydantic(tree: ast.Module) -> tuple[int, list[PydanticClass]]:
    total = 0
    non_pydantic: list[PydanticClass] = []
    for node in ast.walk(tree):
        pydantic_class = _is_non_pydantic_class(node)
        if pydantic_class is None:
            continue
        total += 1
        non_pydantic.append(pydantic_class)
    return total, non_pydantic


def _pydantic_scan(path: Path) -> PydanticResult:
    if not path.exists() or not path.is_file():
        return PydanticResult(success=False, file=str(path), message=f"File not found: {path}")
    tree = _parse_file(path)
    if tree is None:
        return PydanticResult(success=False, file=str(path), message="Parse error in file.")
    total, non_pydantic = _scan_pydantic(tree)
    rel = str(path.relative_to(PROJECT_ROOT))
    non_pydantic = [
        pc for pc in non_pydantic
        if not _is_pydantic_exception(rel, pc.name)
    ]
    ok = len(non_pydantic) == 0
    return PydanticResult(
        success=ok,
        file=str(path),
        total_classes=total,
        non_pydantic_classes=non_pydantic,
        message="100% Pydantic compliant." if ok else f"{len(non_pydantic)} non-Pydantic class(es) found.",
    )


def pydantic_check(file_path: str) -> PydanticResult:
    path = _resolve(file_path)
    if not path.exists():
        return PydanticResult(success=False, file=file_path, message=f"File not found: {path}")
    return _pydantic_scan(path)


def _get_cc_violations(source: str) -> list[CCViolation]:
    from radon.complexity import cc_visit
    results = cc_visit(source)
    return [
        CCViolation(name=v.name, cc=v.complexity, line=v.lineno)
        for v in results
        if v.complexity >= CC_THRESHOLD
    ]


def _format_violations(violations: list[CCViolation]) -> str:
    lines = [f"  CC {v.cc} `{v.name}` line {v.line}" for v in violations]
    return "\n".join(lines)


def _cc_message(violations: list[CCViolation]) -> str:
    count = len(violations)
    return (
        f"CC check failed — {count} function(s) with CC >= {CC_THRESHOLD}.\n"
        + _format_violations(violations)
    )


def _cc_precheck(path: Path) -> CCResult | None:
    result = _cc_precheck_guard(path)
    if result is not None:
        return result
    tree = _parse_file(path)
    if tree is None:
        return CCResult(success=False, message="Syntax error in file.")
    return None


def _cc_precheck_guard(path: Path) -> CCResult | None:
    if not path.exists():
        return CCResult(success=False, message=f"File not found: {path}")
    if not _radon_available():
        return CCResult(success=True, message="radon not available; skipping CC check.")
    return None


def check_cc(file_path: str) -> CCResult:
    path = _resolve(file_path)
    pre = _cc_precheck(path)
    if pre is not None:
        return pre
    source = path.read_text(encoding="utf-8")
    violations = _get_cc_violations(source)
    rel = str(path.relative_to(PROJECT_ROOT))
    violations = [
        v for v in violations
        if not _is_cc_exception(rel, v.name)
    ]
    violations.sort(key=lambda v: v.cc, reverse=True)
    if violations:
        return CCResult(
            success=False,
            stage="cc-check",
            count=len(violations),
            violations=violations,
            message=_cc_message(violations),
        )
    return CCResult(success=True, message=f"All functions have CC < {CC_THRESHOLD}.")


def _radon_available() -> bool:
    return importlib.util.find_spec("radon") is not None


def _latest_backup(path: Path) -> Path | None:
    if not CHECKPOINT_DIR.exists():
        return None
    backups = sorted(CHECKPOINT_DIR.glob(f"{path.stem}_*{path.suffix}.bak"), reverse=True)
    return backups[0] if backups else None


def diff_against_checkpoint(file_path: str) -> str:
    path = _resolve(file_path)
    if not path.exists():
        return f"Error: File not found: {path}"
    latest = _latest_backup(path)
    if latest is None:
        return "Error: No checkpoint found"
    old = latest.read_text(encoding="utf-8").splitlines(keepends=True)
    new = path.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(old, new, fromfile=f"checkpoint/{latest.name}", tofile=f"current/{path.name}", lineterm="")
    text = "\n".join(diff)
    return text if text else "No changes detected."


def _index_harness_dir(sub: str) -> dict[str, set[str]]:
    d = HARNESS_DIR / sub
    if not d.is_dir():
        return {}
    result: dict[str, set[str]] = {}
    for p in sorted(d.glob("*.py")):
        _add_harness_file(p, result)
    return result


def _add_harness_file(p: Path, result: dict[str, set[str]]) -> None:
    tree = _parse_file(p)
    if tree is not None:
        result[str(p)] = _module_level_funcs(tree)


def _harness_names() -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for sub in _HARNESS_SCAN_DIRS:
        index.update(_index_harness_dir(sub))
    return index


def _parse_file(path: Path) -> ast.Module | None:
    if not path.exists():
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return None


def _module_level_funcs(tree: ast.Module) -> set[str]:
    return {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and getattr(n, "col_offset", 0) == 0
    }


def _module_level_defs(file_path: str) -> list[str]:
    tree = _parse_file(Path(file_path))
    if tree is None:
        return []
    return sorted(_module_level_funcs(tree))


def _latest_checkpoint(file_path: str) -> str | None:
    path = Path(file_path)
    if not CHECKPOINT_DIR.exists():
        return None
    backups = sorted(CHECKPOINT_DIR.glob(f"{path.stem}_*{path.suffix}.bak"), reverse=True)
    return str(backups[0]) if backups else None


def _find_new_dups(edited: set[str], before: set[str], existing: set[str]) -> set[str]:
    return {n for n in edited - before if n in existing}


def _find_within_dups(edited_list: list[str]) -> set[str]:
    seen: dict[str, int] = {}
    for n in edited_list:
        seen[n] = seen.get(n, 0) + 1
    return {n for n, c in seen.items() if c > 1}


def _collect_dups(
    edited_list: list[str], checkpoint_path: str | None, existing: set[str]
) -> tuple[set[str], set[str]]:
    edited = set(edited_list)
    within = _find_within_dups(edited_list)
    new_dups: set[str] = set()
    if checkpoint_path:
        before = set(_module_level_defs(checkpoint_path))
        new_dups = _find_new_dups(edited, before, existing)
    return new_dups, within


def _build_existing(index: dict[str, set[str]], target: Path) -> set[str]:
    existing: set[str] = set()
    for fpath, names in index.items():
        if Path(fpath).resolve() == target:
            continue
        existing |= names
    return existing


def _dup_message(new_dups: set[str], within: set[str]) -> str:
    parts: list[str] = []
    if new_dups:
        parts.append("NEW duplicate — import canonical from admin.orchestrator.common: " + ", ".join(sorted(new_dups)))
    if within:
        parts.append("defined more than once in this file: " + ", ".join(sorted(within)))
    return "; ".join(parts)


def detect_duplicate_functions(file_path: str, checkpoint_path: str | None = None) -> CheckResult:
    target = _resolve(file_path)
    index = _harness_names()
    existing = _build_existing(index, target)
    edited_list = _module_level_defs(str(target))
    new_dups, within = _collect_dups(edited_list, checkpoint_path, existing)
    if not within and not new_dups:
        return CheckResult(success=True, message="No duplicate function definitions.")
    return CheckResult(success=False, stage="dup-check", message=_dup_message(new_dups, within))


def sanitize(file_path: str) -> CheckResult:
    path = _resolve(file_path)
    if not path.exists():
        return CheckResult(success=False, message=f"File not found: {path}")
    try:
        result = subprocess.run(
            [sys.executable, str(SANITIZER), str(path)],
            capture_output=True,
            cwd=str(PROJECT_ROOT),
            text=True,
            timeout=15,
        )
        output = result.stdout.strip()
        return CheckResult(success=result.returncode == 0, message=output)
    except subprocess.TimeoutExpired:
        return CheckResult(success=False, message="Sanitizer timed out")
    except Exception as e:
        return CheckResult(success=False, message=str(e))


def full_pipeline(file_path: str) -> CheckResult:
    path = _resolve(file_path)
    logger.info(f"Guardrail pipeline for: {path.name}")
    cp_path = checkpoint(str(path))
    if not cp_path:
        return CheckResult(success=False, stage="checkpoint", message="Failed to create checkpoint")
    logger.info("Checkpoint saved. Edit the file, then run validate.")
    return CheckResult(success=True, stage="checkpoint", message="Checkpoint created.")


def _run_cc_check(path: Path) -> CheckResult:
    cc_result = check_cc(str(path))
    if not cc_result.success:
        logger.error(f"CC check failed for {path.name}: {cc_result.message}")
    return cc_result


def _run_lint_check(path: Path) -> CheckResult:
    lint_result = lint_file(str(path))
    if not lint_result.success:
        logger.error(f"Lint failed for {path.name}: {lint_result.message}")
        diff_text = diff_against_checkpoint(str(path))
        logger.info(f"Diff for LLM context:\n{diff_text}")
    return lint_result


def _run_typecheck(path: Path) -> CheckResult:
    tc_result = typecheck_file(str(path))
    if not tc_result.success:
        logger.error(f"Type check failed for {path.name}: {tc_result.message}")
    return tc_result


def _run_dup_check(path: Path, dup_cp: str | None) -> CheckResult:
    dup_result = detect_duplicate_functions(str(path), dup_cp)
    if not dup_result.success:
        logger.error(f"Duplicate check failed for {path.name}: {dup_result.message}")
    return dup_result


def _run_pydantic_check(path: Path) -> CheckResult:
    pydantic_result = pydantic_check(str(path))
    if not pydantic_result.success:
        logger.error(f"Pydantic check failed for {path.name}: {pydantic_result.message}")
    return pydantic_result


def _run_sanitize(path: Path) -> None:
    san_result = sanitize(str(path))
    if san_result.success:
        logger.info(f"Sanitizer: {san_result.message}")
    else:
        logger.warning(f"Sanitizer issue: {san_result.message}")


def _check_or_fail(
    result: CheckResult, stage: str, pass_msg: str, path: Path
) -> CheckResult | None:
    if not result.success:
        return CheckResult(success=False, stage=stage, message=result.message)
    logger.info(f"{pass_msg} for {path.name}")
    return None


def _run_checks(path: Path) -> CheckResult | None:
    checks = [
        (_run_cc_check(path), "cc-check", "CC check passed"),
        (_run_lint_check(path), "lint", "Lint passed"),
        (_run_typecheck(path), "typecheck", "Type check passed"),
        (_run_dup_check(path, _latest_checkpoint(str(path))), "dup-check", "Duplicate check passed"),
    ]
    for result, stage, msg in checks:
        failed = _check_or_fail(result, stage, msg, path)
        if failed is not None:
            return failed

    return _run_pydantic_and_sanitize(path)


def _run_pydantic_and_sanitize(path: Path) -> CheckResult | None:
    pydantic_result = _run_pydantic_check(path)
    if not pydantic_result.success:
        return CheckResult(success=False, stage="pydantic-check", message=pydantic_result.message)
    logger.info(f"Pydantic check passed for {path.name}")

    _run_sanitize(path)
    return None


def validate(file_path: str) -> CheckResult:
    path = _resolve(file_path)
    logger.info(f"Validating: {path.name}")

    failed = _run_checks(path)
    if failed is not None:
        return failed

    return CheckResult(success=True, stage="complete", message="All checks passed.")


def _check_result_exit(result: CheckResult) -> int:
    return 0 if result.success else 1


def _result_to_exit(result: CheckResult | int | str | None) -> int:
    if isinstance(result, CheckResult):
        return _check_result_exit(result)
    if isinstance(result, str | None):
        return 0 if result else 1
    return 0 if result else 1


def _dispatch(command: str, file_path: str) -> int:
    return _result_to_exit(_handle_command(command, file_path))


def _cmd_sanitize(file_path: str) -> int:
    result = sanitize(file_path)
    print(result.message)
    return 0 if result.success else 1


def _cmd_cc_check(file_path: str) -> int:
    result = check_cc(file_path)
    print(result.message)
    return 0 if result.success else 1


def _cmd_pydantic_check(file_path: str) -> int:
    result = pydantic_check(file_path)
    print(result.message)
    return 0 if result.success else 1


def _cmd_checkpoint(file_path: str) -> str | None:
    return checkpoint(file_path)


def _cmd_validate(file_path: str) -> CheckResult:
    return validate(file_path)


def _cmd_diff(file_path: str) -> int:
    print(diff_against_checkpoint(file_path))
    return 0


def _handle_command(command: str, file_path: str) -> CheckResult | int | str | None:
    handlers: dict[str, object] = {
        "checkpoint": _cmd_checkpoint,
        "validate": _cmd_validate,
        "diff": _cmd_diff,
        "sanitize": _cmd_sanitize,
        "cc-check": _cmd_cc_check,
        "pydantic-check": _cmd_pydantic_check,
        "full": full_pipeline,
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"Unknown command: {command}")
        return None
    return handler(file_path)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nCommands:")
        print("  checkpoint <file>  — Create pre-edit checkpoint")
        print("  validate <file>    — Run all checks")
        print("  diff <file>        — Show diff vs last checkpoint")
        print("  sanitize <file>    — Run sanitizer only")
        print("  cc-check <file>    — Check CC only")
        print("  pydantic-check <file> — Check pydantic compliance only")
        print("  full <file>        — Checkpoint then validate")
        sys.exit(1)
    sys.exit(_dispatch(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
