"""KIT_LIVE=true fail-fast attestation smoke test (cloner-runnable, no network).

This is the 7th cloner-safe stub. It proves the honest KIT_LIVE=true journey
claimed in README.md / QUICKSTART.md by running the real `config.py` in a
subsystem with a controlled env:

  - KIT_LIVE=false (or unset)  -> `import config` is clean, no raise.
  - KIT_LIVE=true + missing required vars -> `config.py` raises RuntimeError
    at import, naming the missing var(s) (KIT_PATH, KIT_BASE_URL, KIT_MODEL,
    KIT_API_KEY). This is the fail-fast gate.

No network, no real LLM, no `.env` required to run this stub. Dependencies:
stdlib only (+ pytest, which is a pinned dep in pyproject.toml).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_config_import(env_overlay: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Import `config.py` in a fresh interpreter with a controlled env.

    We isolate via subprocess because config.py performs its fail-fast check
    at import time (module-level), so in-process import would abort collection.
    """
    env = os.environ.copy()
    # Drop the kit-facing vars so we control exactly what config.py sees.
    for var in ("KIT_LIVE", "KIT_PATH", "KIT_BASE_URL", "KIT_MODEL", "KIT_API_KEY",
                "KIT_MEM0_MODEL", "MEM0_MODEL", "CHRONO_MODEL"):
        env.pop(var, None)
    env.update(env_overlay)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def test_kit_live_false_imports_cleanly() -> None:
    """KIT_LIVE=false (default) => config.py imports without raising."""
    res = _run_config_import({"KIT_LIVE": "false"})
    assert res.returncode == 0, res.stderr
    assert "RuntimeError" not in res.stderr


def test_kit_live_unset_imports_cleanly() -> None:
    """KIT_LIVE unset => defaults to off => config.py imports without raising."""
    res = _run_config_import({})
    assert res.returncode == 0, res.stderr
    assert "RuntimeError" not in res.stderr


def test_kit_live_true_missing_vars_raises_runtime_error_naming_them() -> None:
    """KIT_LIVE=true + missing required vars => RuntimeError naming the missing vars."""
    res = _run_config_import({"KIT_LIVE": "true"})
    assert res.returncode != 0
    assert "RuntimeError" in res.stderr
    # fail-fast message must NAME the missing var(s), not a generic blurb
    assert any(v in res.stderr for v in
               ("KIT_PATH", "KIT_BASE_URL", "KIT_MODEL", "KIT_API_KEY"))


def test_kit_live_true_with_all_vars_imports_cleanly() -> None:
    """KIT_LIVE=true + all required vars supplied => config.py imports clean."""
    res = _run_config_import({
        "KIT_LIVE": "true",
        "KIT_PATH": str(ROOT),
        "KIT_BASE_URL": "https://example.test",
        "KIT_MODEL": "gemma-2",
        "KIT_MEM0_MODEL": "gemma-2-vision",
        "KIT_API_KEY": "sk-test",
    })
    assert res.returncode == 0, res.stderr
    assert "RuntimeError" not in res.stderr


if __name__ == "__main__":
    print("test_kit_live_smoke: KIT_LIVE fail-fast attestation stub OK")
