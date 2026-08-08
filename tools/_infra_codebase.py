import importlib
import os
import sys
from pathlib import Path

_infra_root = os.getenv("KIT_INFRA_ROOT")
if not _infra_root:
    raise RuntimeError(
        "KIT_INFRA_ROOT is required — set it in kit-tools/.env to the "
        "infra/codebase directory path (parent of infra/codebase/mcp_codebase.py)."
    )
sys.path.insert(0, str(Path(_infra_root).resolve()))

try:
    _mod = importlib.import_module("infra.codebase.mcp_codebase")
    index_repository = _mod.index_repository
    query_knowledge_graph = _mod.query_knowledge_graph
    graph_health = _mod.graph_health
    verify_file_path = _mod.verify_file_path
except ImportError:
    raise ImportError(
        "KIT_INFRA_ROOT must point to the infra/codebase directory "
        "containing infra/codebase/mcp_codebase.py"
    )
