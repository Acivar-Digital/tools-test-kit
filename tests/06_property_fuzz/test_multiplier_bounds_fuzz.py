"""Property-based fuzzing tests for multiplier math bounds (Chapters 05 & 07).

Targets:
- calculate_clash_integrated_severity: extreme dm_tier1_score fed into the clash severity multiplier chain
- calculate_trigger_potency: extreme base_trigger, luck_dm_harmony, seasonal_support fed into the potency formula

Properties asserted:
1. Results must never be NaN or Infinity
2. Severity/potency must never be negative
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.engine.module3_interaction import calculate_clash_integrated_severity
from src2.engine.module9_triggers import calculate_trigger_potency


@given(
    dm_tier1_score=st.floats(allow_infinity=True),
)
@settings(max_examples=200)
def test_clash_integrated_severity_no_nan_or_inf(dm_tier1_score):
    """Fuzz calculate_clash_integrated_severity with extreme dm_tier1_score — must not leak NaN or Infinity."""
    result = calculate_clash_integrated_severity(
        b1="Zi",
        b2="Wu",
        month_branch="Mao",
        dm_tier1_score=dm_tier1_score,
    )

    assert isinstance(result, float)
    assert not math.isnan(result), f"calculate_clash_integrated_severity leaked NaN with dm_tier1_score={dm_tier1_score}!"
    assert not math.isinf(result), f"calculate_clash_integrated_severity leaked Infinity with dm_tier1_score={dm_tier1_score}!"
    assert result >= 0.0, f"calculate_clash_integrated_severity returned negative severity {result} with dm_tier1_score={dm_tier1_score}!"


@given(
    base_trigger=st.floats(allow_infinity=True),
    luck_dm_harmony=st.floats(allow_infinity=True),
    seasonal_support=st.floats(allow_infinity=True),
)
@settings(max_examples=200)
def test_trigger_potency_no_nan_or_inf(base_trigger, luck_dm_harmony, seasonal_support):
    """Fuzz calculate_trigger_potency with extreme float multiplier inputs — must not leak NaN or Infinity."""
    result = calculate_trigger_potency(
        base_trigger=base_trigger,
        luck_dm_harmony=luck_dm_harmony,
        seasonal_support=seasonal_support,
    )

    assert isinstance(result.potency, float)
    assert not math.isnan(result.potency), (
        f"calculate_trigger_potency leaked NaN with base={base_trigger}, "
        f"harmony={luck_dm_harmony}, seasonal={seasonal_support}!"
    )
    assert not math.isinf(result.potency), (
        f"calculate_trigger_potency leaked Infinity with base={base_trigger}, "
        f"harmony={luck_dm_harmony}, seasonal={seasonal_support}!"
    )
    assert result.potency >= 0.0, (
        f"calculate_trigger_potency returned negative potency {result.potency} "
        f"with base={base_trigger}, harmony={luck_dm_harmony}, seasonal={seasonal_support}!"
    )
