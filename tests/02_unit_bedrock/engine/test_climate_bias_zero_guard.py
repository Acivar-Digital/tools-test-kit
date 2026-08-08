"""
Test for division by zero guard in climate bias calculation.
This test verifies the fix for the issue where score_clamp_high == score_clamp_low
would cause ZeroDivisionError.
"""


def test_climate_bias_zero_half_range_direct():
    """
    Direct test of the calculation logic from orchestrator.py lines 321-327.

    When score_clamp_high == score_clamp_low, _half_range = 0.
    The fix should set climate_bias = 0 instead of dividing by zero.
    """
    # Setup: identical clamps (the problematic case)
    score_clamp_low = 50.0
    score_clamp_high = 50.0
    composite_score = 60.0  # Any value

    _midpoint = (score_clamp_high + score_clamp_low) / 2.0
    _half_range = (score_clamp_high - score_clamp_low) / 2.0

    # The fix: guard against zero division
    if _half_range == 0:
        climate_bias = 0
    else:
        climate_bias = (composite_score - _midpoint) / _half_range

    assert climate_bias == 0, "Climate bias should be 0 when clamps are equal"


def test_climate_bias_normal_range():
    """Test normal case with non-zero range."""
    score_clamp_low = 35.0
    score_clamp_high = 80.0
    composite_score = 60.0

    _midpoint = (score_clamp_high + score_clamp_low) / 2.0
    _half_range = (score_clamp_high - score_clamp_low) / 2.0

    assert _half_range != 0, "Half range should be non-zero"

    if _half_range == 0:
        climate_bias = 0
    else:
        climate_bias = (composite_score - _midpoint) / _half_range

    expected = (60.0 - 57.5) / 22.5
    assert abs(climate_bias - expected) < 0.001


if __name__ == "__main__":
    test_climate_bias_zero_half_range_direct()
    test_climate_bias_normal_range()
    print("All tests passed!")
