"""Shared stdlib helpers for the portable codebase tools.

Uses KIT_TARGET_ROOT env var instead of __file__ so tools work on any repo.
Keeps the {success, message, data} JSON envelope for orchestrator compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path

TARGET_ROOT = os.getenv("KIT_TARGET_ROOT")
if not TARGET_ROOT:
    raise RuntimeError(
        "KIT_TARGET_ROOT is required — set it to your target repository path."
    )
PROJECT_ROOT = Path(TARGET_ROOT).resolve()

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
