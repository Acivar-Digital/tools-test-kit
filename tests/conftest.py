"""Root conftest for the standalone community-test-kit.

Responsibilities (cloner-safe, no src2.* import, no SQL mocks):
  1. collect_ignore — the 10 baziforecaster-only slices that hardcode TEST/GOLD
     or import src2.*; they are excluded from default collection so a fresh
     download runs `uv run pytest -q` (== `examples`) with zero friction.
  2. The canonical KIT_* -> legacy-env bridge (CHRONO_MODEL / MEM0_MODEL /
     LLM_*). Lives here so EVERY cloner entry point sees it — `pytest examples`,
     `pytest -c infra/pytest.ini`, and `python examples/xx.py`. This is the
     single source of truth for the model knobs the stubs assert against.

Fails loud at import when KIT_LIVE=true and a required var is missing
(config.load_config raises RuntimeError naming the var).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# kit root must be importable for `from config import load_config` below
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(_ROOT))

collect_ignore = [
    "01_gold_snapshots",
    "02_unit_bedrock",
    "03_regression_locks",
    "04_bug_repros",
    "05_integration_e2e",
    "06_property_fuzz",
    "07_mutation_testing",
    "08_static_gates",
    "09_tech_debt_audit",
    "10_harness_suite",
]

# --- canonical KIT_* -> legacy-env bridge (single source of truth) ---
# Source kit-facing vars HERE so a downloading user only fills kit-tests/.env.
from config import load_config  # noqa: E402

_path, _base_url, _api_key, _model, _mem0_model = load_config()
os.environ.setdefault("KIT_PATH", _path or str(_ROOT))
os.environ.setdefault("KIT_BASE_URL", _base_url)
os.environ.setdefault("KIT_API_KEY", _api_key)
os.environ.setdefault("KIT_MODEL", _model)
os.environ.setdefault("KIT_MEM0_MODEL", _mem0_model)
# legacy-layer mappings surfaced to stubs/tests that still read the old names
os.environ.setdefault("LLM_BASE_URL", _base_url)
os.environ.setdefault("LLM_API_KEY", _api_key)
os.environ.setdefault("CHRONO_MODEL", _model)
os.environ.setdefault("CHRONO_URL", _base_url)
os.environ.setdefault("MEM0_MODEL", _mem0_model)
