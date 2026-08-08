"""Property-based fuzzing tests for BaZi math boundary functions.

Targets:
- get_prior_log_odds: log-odds transformation with edge-case probabilities
- _sigmoid: sigmoid function with extreme float inputs
- _get_spectrum_tier: boundary classification with extreme scores
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.engine.module11_probability import _sigmoid, get_prior_log_odds
from src2.engine.module13_spectrum import _get_spectrum_tier


@given(x=st.floats(allow_nan=False, allow_infinity=True))
@settings(max_examples=200)
def test_sigmoid_no_crash(x):
    """Fuzz _sigmoid with extreme float values — must not raise and must return finite probabilities."""
    result = _sigmoid(x)

    assert isinstance(result, float)
    assert not math.isnan(result), f"_sigmoid({x}) leaked NaN!"
    assert not math.isinf(result), f"_sigmoid({x}) leaked Infinity!"
    assert 0.0 <= result <= 1.0, f"_sigmoid({x}) returned out-of-range value {result}"


@given(event_type=st.text(min_size=1, max_size=50))
@settings(max_examples=200)
def test_get_prior_log_odds_no_crash(event_type):
    """Fuzz get_prior_log_odds with arbitrary strings — must not raise and must return finite floats."""
    result = get_prior_log_odds(event_type)

    assert isinstance(result, float)
    assert not math.isnan(result), f"get_prior_log_odds({event_type!r}) leaked NaN!"
    assert not math.isinf(result), f"get_prior_log_odds({event_type!r}) leaked Infinity!"


@given(score=st.floats(allow_nan=False, allow_infinity=False, min_value=-200.0, max_value=200.0))
@settings(max_examples=300)
def test_get_spectrum_tier_no_crash(score):
    """Fuzz _get_spectrum_tier with extreme scores — must not raise and must return a valid tier."""
    result = _get_spectrum_tier(score)

    assert isinstance(result, str)
    assert result in ("Vibrant", "Strong", "Mild Strong", "Balanced", "Mild Weak", "Weak", "Follower"), (
        f"_get_spectrum_tier({score}) returned invalid tier {result!r}"
    )


@given(score=st.floats(allow_nan=False, allow_infinity=False, min_value=-200.0, max_value=200.0))
@settings(max_examples=300)
def test_get_spectrum_tier_monotonic(score):
    """Fuzz _get_spectrum_tier monotonicity — higher scores must never map to weaker tiers."""
    tier = _get_spectrum_tier(score)
    tier_order = {"Vibrant": 0, "Strong": 1, "Mild Strong": 2, "Balanced": 3, "Mild Weak": 4, "Weak": 5, "Follower": 6}
    assert tier_order[tier] <= 6


@given(
    score_a=st.floats(allow_nan=False, allow_infinity=False, min_value=-200.0, max_value=200.0),
    score_b=st.floats(allow_nan=False, allow_infinity=False, min_value=-200.0, max_value=200.0),
)
@settings(max_examples=200)
def test_get_spectrum_tier_boundary_consistency(score_a, score_b):
    """Fuzz _get_spectrum_tier boundary consistency — if score_a > score_b, tier_a must be >= tier_b."""
    tier_a = _get_spectrum_tier(score_a)
    tier_b = _get_spectrum_tier(score_b)
    tier_order = {"Vibrant": 0, "Strong": 1, "Mild Strong": 2, "Balanced": 3, "Mild Weak": 4, "Weak": 5, "Follower": 6}
    if score_a > score_b:
        assert tier_order[tier_a] <= tier_order[tier_b], (
            f"Monotonicity violated: score_a={score_a} → {tier_a}, score_b={score_b} → {tier_b}"
        )
