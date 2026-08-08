"""Golden-snapshot regression with a stub engine.

Pattern: a deterministic unit under test yields a JSON-serializable result. The
test compares it to a committed golden file and fails with a readable diff when
the snapshot drifts.

One dependency only: pytest (+ stdlib json / pathlib / difflib).
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent
GOLDEN = HERE / "snapshots" / "dashboard.json"


# --- stub engine (deterministic + pure) ---
def _score(month: int) -> int:
    return month * 3 + 1


def render_dashboard() -> dict:
    return {
        "score": _score(12),
        "label": "stub",
        "flags": [True, _score(1) > 0],
    }


def _normalize(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=2) + "\n"


def _diff(expected: str, actual: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile="golden",
            tofile="actual",
            lineterm="",
        )
    )


def test_snapshot_matches_golden() -> None:
    if not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(_normalize(render_dashboard()))
        pytest.skip("golden snapshot was missing and has been written; rerun to assert")

    expected = json.loads(GOLDEN.read_text())
    actual = render_dashboard()

    assert actual == expected
    assert _normalize(actual) == _normalize(expected), _diff(
        _normalize(expected), _normalize(actual)
    )


if __name__ == "__main__":
    print("02_snapshot_regression OK ->", render_dashboard())
