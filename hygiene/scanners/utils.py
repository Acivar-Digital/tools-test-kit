import os
import subprocess
import sys
from pathlib import Path


def _is_under_path(path: Path, root: Path) -> bool:
    """Check if *path* is the same as or nested under *root* (both relative or absolute)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


def _resolve_scan_roots() -> list[Path]:
    """Resolve SCAN_ROOTS env var into a list of Path objects.

    Each entry is relative to AIB_FACTORY_ROOT or absolute.
    Falls back to ``["src2"]`` for backward compatibility when SCAN_ROOTS is unset.
    """
    scan_roots_env = os.environ.get("SCAN_ROOTS")
    if not scan_roots_env:
        return [Path("src2")]

    factory_root = os.environ.get("AIB_FACTORY_ROOT")
    roots: list[Path] = []
    for raw in scan_roots_env.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if Path(raw).is_absolute():
            roots.append(Path(raw))
        elif factory_root:
            roots.append(Path(factory_root) / raw)
        else:
            roots.append(Path(raw))
    return roots


def _is_py_file(rel_path: str) -> bool:
    """True if *rel_path* is a ``.py`` file that is not ``__init__.py``
    and does not live inside ``__pycache__``."""
    p = Path(rel_path)
    return (
        p.suffix == ".py"
        and p.name != "__init__.py"
        and "__pycache__" not in p.parts
    )


def get_src2_files() -> list[Path]:
    """Get all Python files under configured scan roots, or override via env.

    Honors:
      - HYGIENE_FILES_TO_SCAN: optional comma list of explicit file paths.
      - SCAN_ROOTS: comma list of roots (relative to AIB_FACTORY_ROOT or absolute).
      - AIB_FACTORY_ROOT: base directory for relative SCAN_ROOTS entries.
      - ``--diff``: git-changed files only, filtered to SCAN_ROOTS.

    When SCAN_ROOTS is unset, falls back to scanning ``src2`` (backward compat).
    """
    use_diff = False
    if "--diff" in sys.argv:
        use_diff = True
        sys.argv.remove("--diff")

     # Honor explicit override first — validate paths stay within TARGET_ROOT
    if "HYGIENE_FILES_TO_SCAN" in os.environ:
        paths_str = os.environ["HYGIENE_FILES_TO_SCAN"]
        if not paths_str:
            return []
        target_root = os.environ.get("TARGET_ROOT")
        resolved_paths = []
        for p in paths_str.split(","):
            p = p.strip()
            if not p:
                continue
            path = Path(p)
            if not path.is_absolute() and target_root:
                path = Path(target_root) / path
            path = path.resolve()
            if target_root:
                try:
                    path.relative_to(Path(target_root).resolve())
                except (ValueError, OSError):
                    raise ValueError(
                        f"HYGIENE_FILES_TO_SCAN path '{p}' escapes TARGET_ROOT '{target_root}'"
                    )
            resolved_paths.append(path)
        return resolved_paths

    scan_roots = _resolve_scan_roots()

    if use_diff:
        try:
            changed_files: set[str] = set()
            res1 = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True
            )
            if res1.returncode == 0:
                changed_files.update(res1.stdout.strip().split("\n"))
            res2 = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
            )
            if res2.returncode == 0:
                changed_files.update(res2.stdout.strip().split("\n"))

            paths: list[Path] = []
            for line in sorted(changed_files):
                line = line.strip()
                if not line or not _is_py_file(line):
                    continue
                path = Path(line)
                if any(_is_under_path(path, root) for root in scan_roots) and path.is_file():
                    paths.append(path)
            return paths
        except Exception as e:
            print(f"Error getting git diff files: {e}", file=sys.stderr)
            return []

    try:
        all_paths: list[Path] = []
        for root in scan_roots:
            result = subprocess.run(
                [
                    "git", "ls-files", "--cached", "--others",
                    "--exclude-standard", str(root),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and _is_py_file(line):
                    all_paths.append(Path(line))

        # Deduplicate by path string
        seen: set[str] = set()
        unique: list[Path] = []
        for p in all_paths:
            key = str(p)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return [p for p in unique if p.is_file()]
    except Exception as e:
        print(f"Error getting git files: {e}", file=sys.stderr)
        # Fallback: recursively walk each root excluding __pycache__
        all_paths = []
        for root in scan_roots:
            if root.is_dir():
                all_paths.extend(
                    p for p in root.rglob("*.py")
                    if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
                )
        seen = set()
        unique = []
        for p in all_paths:
            key = str(p)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique


def is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary by searching for null bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return False
