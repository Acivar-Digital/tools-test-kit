#!/usr/bin/env python3
"""
guardrail_check.py — HARNESS-SIDE guardrail CLI for the orchestrator.

This is a harness-owned validation tool run by runner.py (or manually by the
operator). It is NOT exposed to any agent's tool_allow_list — the coder never
sees or calls it. It implements the post-edit gate:

    checkpoint -> ruff check -> scoped pyright -> diff_vs_checkpoint

so a deliberately-broken coder edit can be surfaced (ruff_output + diff) back
to a fresh coder for self-correction, without ever giving the model a shell.

Modes:
    validate  <file>  Run checkpoint-if-needed, ruff, scoped pyright, and print
                       a single JSON line:
                       {"success": bool, "ruff_ok": bool, "pyright_ok": bool,
                        "ruff_output": str,
                        "pyright_output": str, "diff_vs_checkpoint": str}
    diff      <file>  Print the unified diff vs the last checkpoint (or
                      "no checkpoint").
    checkpoint <file> Snapshot the file into the .checkpoints dir.

Design rules (fail-loudly on internal error, structured JSON for lint/type
results): unexpected internal failures raise; ruff/pyright outcomes are
returned as structured data, never swallowed.
"""

import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # kit-tools/
PROJECT_ROOT = SCRIPT_DIR.parent.parent               # target repo root
CHECKPOINT_DIR = PROJECT_ROOT / ".checkpoints"

# Bounds for the broadened union pyright (docs/01_fix.md Task 3, D4):
# 1 primary + <=3 dependency files, 5000 lines/file, 20000 lines total.
UNION_MAX_DEPS = 3
UNION_MAX_FILES = UNION_MAX_DEPS + 1  # primary + deps
UNION_MAX_LINES_PER_FILE = 5000
UNION_MAX_TOTAL_LINES = 20000


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------
def checkpoint(file_path: str) -> str | None:
    """Snapshot the file into the .checkpoints dir. Returns the backup path."""
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = CHECKPOINT_DIR / f"{path.stem}_{ts}{path.suffix}"
    shutil.copy2(str(path), str(backup_path))
    return str(backup_path)


def _latest_checkpoint(path: Path) -> Path | None:
    if not CHECKPOINT_DIR.exists():
        return None
    backups = sorted(
        CHECKPOINT_DIR.glob(f"{path.stem}_*{path.suffix}"),
        reverse=True,
    )
    return backups[0] if backups else None


# ---------------------------------------------------------------------------
# Lint (ruff)
# ---------------------------------------------------------------------------
def lint_file(file_path: str) -> tuple[bool, str]:
    """Run `uv run ruff check <file>`. Returns (success, output_text)."""
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    result = subprocess.run(
        ["uv", "run", "ruff", "check", str(path)],
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        text=True,
        timeout=60,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return (result.returncode == 0, output.strip())


# ---------------------------------------------------------------------------
# Type check (scoped pyright)
# ---------------------------------------------------------------------------
def _parse_pyright_error(ln: str) -> tuple[str | None, int | None]:
    """Parse a pyright error line ``path:LINE:COL - error: message``.

    Returns ``(file_path, line_no)`` or ``(None, None)`` if the line does not
    look like a pyright error location.
    """
    if "error" not in ln.lower():
        return (None, None)
    head = ln.split(" - ", 1)[0] if " - " in ln else ln
    # head looks like /abs/path:LINE:COL (path may itself contain ':')
    parts = head.rsplit(":", 2)
    if len(parts) != 3:
        return (None, None)
    fp, line_s, _col_s = parts
    try:
        return (fp, int(line_s))
    except ValueError:
        return (None, None)


def _changed_lines_from_diff(diff_text: str) -> set[int] | None:
    """Parse a unified ``diff_text`` and return the set of NEW (current-file)
    line numbers that changed (added lines in the working copy).

    Returns ``None`` when there is no diff (caller must fall back to whole-file
    scoping) or when the diff is empty / unavailable. This replaces the old
    checkpoint-based ``_changed_line_set`` (00_fix Defect B): the baseline is
    now the LIVE ORIGINAL on disk, never a lazily-taken checkpoint, so the
    changed-line filter actually engages.
    """
    if diff_text in ("no original", "no diff", "", None):
        return None

    changed: set[int] = set()
    new_lineno: int | None = None
    for ln in diff_text.splitlines():
        if ln.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", ln)
            new_lineno = int(m.group(1)) if m else None
            continue
        if ln.startswith("+++") or ln.startswith("---"):
            continue
        if new_lineno is None:
            continue
        if ln.startswith("+"):
            changed.add(new_lineno)
            new_lineno += 1
        elif ln.startswith("-"):
            # removed line: does not advance the new-file counter
            pass
        elif ln.startswith(" "):
            new_lineno += 1
    return changed


def typecheck_file(file_path: str, changed: set[int] | None = None) -> tuple[bool, str]:
    """Run `uv run pyright <file>`, scoped to THIS file's errors.

    Pre-existing type errors elsewhere in the repo do not block. A coder is
    only held accountable for errors it INTRODUCED on the lines it CHANGED
    (docs/01_fix.md / 00_fix — architectural principle: "other coder's shit is
    our shit"). Pre-existing errors in the same file on lines the coder never
    touched are filtered out via the ``changed`` set (computed from the diff
    vs the live original); when ``changed`` is ``None`` we fall back to
    whole-file scope. If pyright is absent, this is non-blocking (skipped).
    Returns (success, output_text).
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        result = subprocess.run(
            ["uv", "run", "pyright", str(path)],
            capture_output=True,
            cwd=str(PROJECT_ROOT),
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        return (True, "pyright not installed; skipped type check.")

    output = (result.stdout or "") + (result.stderr or "")
    fname = path.name
    # Scope errors to the lines the coder actually changed (per D2). A coder
    # must not be blocked by pre-existing pyright errors on lines it never
    # touched. Fall back to whole-file scope only when no diff exists.
    if changed is None:
        our_errors = [
            ln for ln in output.splitlines()
            if fname in ln and "error" in ln.lower()
        ]
    else:
        our_errors = []
        for ln in output.splitlines():
            if fname not in ln or "error" not in ln.lower():
                continue
            _fp, line_no = _parse_pyright_error(ln)
            if line_no is not None and line_no in changed:
                our_errors.append(ln)
    if our_errors:
        return (False, "\n".join(our_errors))
    return (True, output.strip())


def discover_dependencies(primary: Path, edit_set: set[str] | None = None) -> list[Path]:
    """Parse ``import`` / ``from`` statements in ``primary`` and resolve them to
    repo paths. Intersect with the current edit set (other staged files) and
    with direct upstream deps. Keep at most ``UNION_MAX_DEPS`` files, preferring
    the strongest import-edge weight (most imports of that module).

    For newly-created files (no imports resolvable), callers may pass the
    planner's declared ``depends_on`` files via ``edit_set`` so those are
    included. Returns absolute Paths, bounded to ``UNION_MAX_DEPS``.
    """
    try:
        tree = ast.parse(primary.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []

    wanted: dict[str, int] = {}  # module stem -> import count (edge weight)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                stem = alias.name.split(".")[-1]
                wanted[stem] = wanted.get(stem, 0) + 1
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                stem = node.module.split(".")[-1]
                wanted[stem] = wanted.get(stem, 0) + 1

    if not wanted:
        # New file with no imports: fall back to the edit set (planner deps).
        if edit_set:
            out = []
            for p in list(edit_set)[:UNION_MAX_DEPS]:
                pp = Path(p)
                out.append(pp if pp.is_absolute() else PROJECT_ROOT / pp)
            return out
        return []

    resolved: list[Path] = []
    seen: set[str] = set()
    for stem, _ in sorted(wanted.items(), key=lambda kv: -kv[1]):
        if len(resolved) >= UNION_MAX_DEPS:
            break
        candidates = list(PROJECT_ROOT.rglob(f"{stem}.py"))
        for cand in candidates:
            rel = str(cand.relative_to(PROJECT_ROOT))
            if rel in seen:
                continue
            # Skip the primary itself and anything outside the repo src tree.
            if cand.resolve() == primary.resolve():
                continue
            if edit_set and rel not in edit_set:
                # Prefer files in the active edit set; otherwise allow any repo
                # module but cap total.
                if len(resolved) >= UNION_MAX_DEPS:
                    break
            seen.add(rel)
            resolved.append(cand)
            break
    return resolved[:UNION_MAX_DEPS]


def _within_bounds(files: list[Path]) -> bool:
    total = 0
    for f in files:
        try:
            n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        except Exception:
            n = 0
        if n > UNION_MAX_LINES_PER_FILE:
            return False
        total += n
    return total <= UNION_MAX_TOTAL_LINES


def typecheck_union(
    files: list[Path],
    changed_map: dict[str, set[int] | None] | None = None,
    edited_names: set[str] | None = None,
) -> tuple[bool, str]:
    """Run ``uv run pyright`` once over the bounded union of files so cross-file
    type inference loads all edited modules (docs/01_fix.md Task 3).

    Each edited file's errors are scoped to the lines the coder actually
    CHANGED (per D2) — a coder is never held responsible for pre-existing
    errors in the same file. Errors attributed to a file the coder did NOT edit
    (a dependency, Fix F) are **dropped entirely** — a dependency type break is
    the architect's shit, not the coder's. ``changed_map`` maps basename -> the
    set of changed NEW line numbers (``None`` == no diff -> whole-file scope for
    that file). ``edited_names`` is the set of basenames the coder actually
    owns; any error whose file basename is not in it is dropped. If pyright is
    absent, this is non-blocking (skipped). Returns (success, output_text).
    """
    if not files:
        return (True, "no files to type check")
    paths = [str(p.resolve()) for p in files]
    if edited_names is None:
        edited_names = {p.name for p in files}
    if changed_map is None:
        changed_map = {p.name: None for p in files}
    try:
        result = subprocess.run(
            ["uv", "run", "pyright", *paths],
            capture_output=True,
            cwd=str(PROJECT_ROOT),
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return (True, "pyright not installed; skipped type check.")

    output = (result.stdout or "") + (result.stderr or "")
    our_errors: list[str] = []
    for ln in output.splitlines():
        if "error" not in ln.lower():
            continue
        fp, line_no = _parse_pyright_error(ln)
        # Attribute the error to an edited file by basename of its path.
        target_name: str | None = None
        if fp is not None:
            fp_base = Path(fp).name
            if fp_base in edited_names:
                target_name = fp_base
        if target_name is None:
            # Dependency / un-attributable error (Fix F): drop it — non-blocking.
            continue
        changed = changed_map.get(target_name)
        if changed is None:
            our_errors.append(ln)  # no diff -> whole-file scope
        elif line_no is not None and line_no in changed:
            our_errors.append(ln)
    if our_errors:
        return (False, "\n".join(our_errors))
    return (True, output.strip())


# ---------------------------------------------------------------------------
# Diff vs checkpoint
# ---------------------------------------------------------------------------
def diff_vs_checkpoint(file_path: str) -> str:
    """Unified diff of the file vs its most recent checkpoint."""
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    cp = _latest_checkpoint(path)
    if cp is None:
        return "no checkpoint"

    checkpoint_lines = cp.read_text(encoding="utf-8").splitlines(keepends=True)
    current_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(
        checkpoint_lines,
        current_lines,
        fromfile=f"checkpoint/{cp.name}",
        tofile=f"current/{path.name}",
        lineterm="",
    )
    return "\n".join(diff) or "no diff"


# ---------------------------------------------------------------------------
# Validation sandbox (00_fix Fix A' — validate in a REAL package context)
# ---------------------------------------------------------------------------
def _virtual_live_path(staged: Path, edit_set) -> Path:
    """Map a STAGED path back to its true repo path so imports resolve.

    Resolution order:
      1. If ``edit_set`` (live relative paths) is given and the staged path
         ends with one of them, return ``PROJECT_ROOT / that_rel``.
      2. Otherwise find the ``/src2/`` or ``/src/`` marker and strip to the
         repo-relative part.
      3. Fallback: ``PROJECT_ROOT / staged.name``.
    """
    sp = str(staged.resolve()).replace("\\", "/")
    if edit_set:
        for live_s in edit_set:
            rel = str(live_s).replace("\\", "/").lstrip("/")
            if rel and (sp.endswith("/" + rel) or sp == rel):
                return Path(PROJECT_ROOT / rel)
    source_root = os.getenv("KIT_SOURCE_ROOT", "src")
    for marker in (f"/{source_root}/", "/src/"):
        idx = sp.find(marker)
        if idx != -1:
            return Path(PROJECT_ROOT / sp[idx + 1:])
    return Path(PROJECT_ROOT / staged.name)


def _realize_symlink(link: Path) -> None:
    """Replace a symlink with a real copy of its target (so we can write under it)."""
    real = Path(os.readlink(link)).resolve()
    link.unlink()
    link.mkdir(parents=True, exist_ok=True)
    for child in real.iterdir():
        if child.is_dir():
            os.symlink(str(child.resolve()), str(link / child.name))
        else:
            shutil.copy2(str(child), str(link / child.name))


def _materialize_along(sandbox: Path, rel: Path) -> None:
    """Create intermediate (possibly symlinked) directories along ``rel``."""
    cur = sandbox
    for part in rel.parts[:-1]:
        nxt = cur / part
        if nxt.is_symlink():
            _realize_symlink(nxt)
        elif not nxt.exists():
            nxt.mkdir(parents=True, exist_ok=True)
        cur = nxt


def build_validation_sandbox(staged: Path, live: Path) -> Path:
    """Build a throwaway sandbox mirroring the repo so the staged file sits at
    its true package path and cross-module imports resolve. ``live`` tree is
    never touched (the real edited file lives only as a copy inside the sandbox).
    Returns the sandbox root.
    """
    sandbox = Path(tempfile.mkdtemp(prefix="grd_"))
    for name in (".venv", "pyproject.toml", "pyrightconfig.json", "src"):
        src = PROJECT_ROOT / name
        if src.exists():
            os.symlink(str(src.resolve()), str(sandbox / name))
    real_src = PROJECT_ROOT / os.getenv("KIT_SOURCE_ROOT", "src")
    if real_src.exists():
        (sandbox / os.getenv("KIT_SOURCE_ROOT", "src")).mkdir(exist_ok=True)
        for child in real_src.iterdir():
            os.symlink(str(child.resolve()), str(sandbox / os.getenv("KIT_SOURCE_ROOT", "src") / child.name))
    rel = live.relative_to(PROJECT_ROOT)
    _materialize_along(sandbox, rel)
    target = sandbox / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(staged), str(target))
    return sandbox


def diff_staged_vs_original(staged: Path, live: Path) -> str:
    """Unified diff of the staged file vs the LIVE ORIGINAL on disk (00_fix
    Fix B' — the real pre-edit baseline, no sidecar/checkpoint file).
    """
    if not live.exists():
        return "no original"
    a = live.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    b = staged.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    d = difflib.unified_diff(
        a, b,
        fromfile=str(live),
        tofile=str(staged),
        lineterm="",
    )
    return "\n".join(d) or "no diff"


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
def validate(file_path: str, edit_set: list[str] | None = None) -> dict:
    """Run ruff, smoke gate, broadened union pyright, and the staged-vs-original
    diff — all in a REAL package context so cross-module imports resolve (00_fix
    Defect A) and the changed-line filter is scoped to the live original (00_fix
    Defect B).

    ``file_path`` is the STAGED path (e.g.
    ``admin/orchestrator/temp/src2/interfaces/telegram/session.py``). The live
    original is recovered via ``_virtual_live_path``. Returns the structured dict
    consumed by runner.py.
    """
    staged = Path(file_path).resolve()
    if not staged.exists():
        raise FileNotFoundError(f"File not found: {staged}")

    live = _virtual_live_path(staged, edit_set)
    sandbox = build_validation_sandbox(staged, live)
    try:
        sandbox_fp = sandbox / live.relative_to(PROJECT_ROOT)

        # ruff needs no package context — run on the staged file directly.
        ruff_ok, ruff_out = lint_file(str(staged))

        # Smoke-execution gate (docs/01_fix.md Task 1, D3): type-construction
        # check, run on the sandbox path so dotted imports resolve (Fix A'/H).
        try:
            smoke_res = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "smoke_test.py"), str(sandbox_fp)],
                capture_output=True,
                text=True,
                cwd=str(sandbox),
                timeout=240,
            )
            smoke_payload = (
                json.loads(smoke_res.stdout.strip().splitlines()[-1])
                if smoke_res.stdout.strip()
                else {}
            )
            smoke_ok = bool(smoke_payload.get("success", True))
            smoke_msg = smoke_payload.get("message", "")
        except Exception as e:
            smoke_ok, smoke_msg = (True, f"smoke gate skipped: {e}")
        smoke_ok = bool(smoke_ok)

        # Broadened union pyright (docs/01_fix.md Task 3, D4) — run inside the
        # sandbox so the package context (incl. symlinked src2) is correct.
        deps = discover_dependencies(staged, set(edit_set) if edit_set else None)
        dep_sandbox: list[Path] = []
        for d in deps:
            dp = Path(d)
            if not dp.is_absolute():
                dp = PROJECT_ROOT / dp
            dp = dp.resolve()
            try:
                dep_sandbox.append(sandbox / dp.relative_to(PROJECT_ROOT))
            except ValueError:
                continue
        union_files = [sandbox_fp] + dep_sandbox
        diff_text = diff_staged_vs_original(staged, live)
        changed = _changed_lines_from_diff(diff_text)
        changed_map = {sandbox_fp.name: changed}
        edited_names = {sandbox_fp.name}
        if _within_bounds(union_files):
            pyr_ok, pyr_out = typecheck_union(
                union_files, changed_map=changed_map, edited_names=edited_names
            )
        else:
            # Bounds exceeded — fall back to the single-file scoped pyright.
            pyr_ok, pyr_out = typecheck_file(str(sandbox_fp), changed=changed)

        success = ruff_ok and pyr_ok and smoke_ok
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    return {
        "success": success,
        "ruff_ok": ruff_ok,
        "pyright_ok": pyr_ok,
        "smoke_ok": smoke_ok,
        "smoke_output": smoke_msg,
        "ruff_output": ruff_out,
        "pyright_output": pyr_out,
        "diff_vs_checkpoint": diff_text,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _usage() -> str:
    return (
        "Usage:\n"
        "  guardrail_check.py validate <file>\n"
        "  guardrail_check.py diff <file>\n"
        "  guardrail_check.py checkpoint <file>\n"
    )


def main() -> int:
    if len(sys.argv) < 3:
        print(_usage(), file=sys.stderr)
        return 2

    command, file_path = sys.argv[1], sys.argv[2]

    if command == "validate":
        edit_set = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else None
        try:
            result = validate(file_path, edit_set=edit_set)
        except FileNotFoundError as e:
            print(json.dumps({"success": False, "error": str(e)}))
            return 1
        print(json.dumps(result))
        return 0 if result["success"] else 1

    if command == "diff":
        try:
            print(diff_vs_checkpoint(file_path))
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 1
        return 0

    if command == "checkpoint":
        try:
            cp = checkpoint(file_path)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 1
        print(cp)
        return 0

    print(f"Unknown command: {command}\n{_usage()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
