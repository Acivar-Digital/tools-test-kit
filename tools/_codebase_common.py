"""Shared stdlib helpers for the shadow CLI codebase tools.

Replaces the legacy external ``infra/codebase/mcp_codebase.py`` dependency so the
/tools CLI wrappers are fully self-contained within the repo (no libcst, no
out-of-repo imports). Keeps the ``{success, message, data}`` JSON envelope that the
orchestrator harness (admin/orchestrator/infra/tools.py ``_run_tool``) consumes as a
raw stdout string, and that the test suite asserts against.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".agent", ".gemini"}
INCLUDE_EXTENSIONS = {".py", ".md", ".json", ".txt", ".yaml", ".yml", ".toml", ".sql", ".sh"}


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _normalize_content(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def resolve_secure_path(relative_path: str) -> Path:
    """Resolve a path and ensure it stays within PROJECT_ROOT."""
    root = PROJECT_ROOT.resolve()
    if relative_path.startswith(f"{root.name}/"):
        relative_path = relative_path[len(f"{root.name}/") :]
    elif relative_path == root.name:
        relative_path = ""
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escape detected: {relative_path}")
    return target


def ok(message: str, data: dict) -> dict:
    return {"success": True, "message": message, "data": data}


def fail(message: str) -> dict:
    return {"success": False, "message": message}
