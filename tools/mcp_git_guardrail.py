#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Annotated, Any

# Setup paths so we can import guardrail_check.py
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(WORKSPACE_ROOT))

from fastmcp import FastMCP  # noqa: E402

from guardrail_check import checkpoint, validate  # noqa: E402

mcp = FastMCP(os.getenv("KIT_MCP_NAME", "kit-tools"))

def _resolve_path(relative_path: str) -> Path:
    root = WORKSPACE_ROOT.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escape detected: {relative_path}")
    return target

@mcp.tool()
def checkpoint_file(
    relative_path: Annotated[str, "File path relative to repository root."]
) -> dict[str, Any]:
    """Create a checkpoint snapshot of the specified file before making edits."""
    try:
        target_path = _resolve_path(relative_path)
        backup = checkpoint(str(target_path))
        if backup:
            return {"success": True, "checkpoint_path": backup, "message": f"Successfully checkpointed {relative_path}"}
        return {"success": False, "message": f"Failed to checkpoint {relative_path}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@mcp.tool()
def validate_file(
    relative_path: Annotated[str, "File path relative to repository root."]
) -> dict[str, Any]:
    """Validate python file syntax and run ruff checks/formatting sanitization after making edits."""
    try:
        target_path = _resolve_path(relative_path)
        res = validate(str(target_path))
        return res
    except Exception as e:
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()
