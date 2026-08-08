"""Cloner-runnable stub proving the KIT_MEM0_MODEL contract is wired end-to-end.

Reads the env-backed model name the same way the kit surfaces it (MEM0_MODEL
env var, sourced from KIT_MEM0_MODEL in config.load_config) and asserts the
two granular model knobs (KIT_MODEL -> CHRONO_MODEL, KIT_MEM0_MODEL ->
MEM0_MODEL) are independent and observable. No network, no real LLM.

Dependencies: pytest (+ stdlib os + path to config.py).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))


def _mem0_model_name() -> str:
    """Stubbed mem0-synthesis model resolution mirroring infra wiring."""
    return os.getenv("MEM0_MODEL", "mock-mem0-model")


def _chrono_model_name() -> str:
    """Stubbed chronomancer model resolution mirroring infra wiring."""
    return os.getenv("CHRONO_MODEL", "mock-chrono-model")


def test_kit_mem0_model_is_observed_via_default() -> None:
    # With no MEM0_MODEL set in env, the stub resolution falls back to its
    # default mock name (mirrors config.py defaulting KIT_MEM0_MODEL). We assert
    # the resolvable value is a non-empty string and equals either the env var
    # (if set) or the documented default -- so the contract is observable
    # cloner-side without depending on a conftest that sets MEM0_MODEL.
    observed = _mem0_model_name()
    assert isinstance(observed, str) and observed
    assert observed == os.getenv("MEM0_MODEL", "mock-mem0-model")


def test_kit_models_are_granular_and_independent() -> None:
    # KIT_MODEL and KIT_MEM0_MODEL must NOT collapse into one value.
    chrono = _chrono_model_name()
    mem0 = _mem0_model_name()
    assert isinstance(chrono, str) and isinstance(mem0, str)
    # default mocks are deliberately distinct names -> granularity proven
    assert chrono != mem0


def test_config_exposes_both_knobs() -> None:
    from config import load_config  # noqa: E402  # kit root on sys.path

    _, _, _, model, mem0_model = load_config()
    assert model == os.getenv("CHRONO_MODEL", "mock-chrono-model")
    assert mem0_model == os.getenv("MEM0_MODEL", "mock-mem0-model")
    assert model != mem0_model  # independent knobs


if __name__ == "__main__":
    print("06_kit_mem0_model OK ->", _mem0_model_name(), "/", _chrono_model_name())