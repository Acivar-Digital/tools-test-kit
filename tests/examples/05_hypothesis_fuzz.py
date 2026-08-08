"""Hypothesis property test for a NaN/Inf guard.

Demonstrates a property test that finds a real bug (division producing NaN/Inf)
via hypothesis-driven input search, together with the guard that makes it pass.

Dependencies: pytest + hypothesis.
"""
from __future__ import annotations

import math

from hypothesis import given, settings, strategies as st


def safe_ratio(a: float, b: float) -> float:
    # Guard: never let NaN / Inf / zero-division leak out of a numeric API.
    if b == 0 or math.isnan(b) or math.isinf(b):
        return 0.0
    if math.isnan(a) or math.isinf(a):
        return 0.0
    r = a / b
    return r if math.isfinite(r) else 0.0


@given(st.floats(), st.floats())
@settings(max_examples=200, deadline=None)
def test_ratio_is_always_finite(a: float, b: float) -> None:
    assert math.isfinite(safe_ratio(a, b))


if __name__ == "__main__":
    for b in (0.0, float("nan"), float("inf"), -float("inf")):
        assert math.isfinite(safe_ratio(12.0, b))
    print("05_hypothesis_fuzz OK")
