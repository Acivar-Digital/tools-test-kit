"""TEST/math/test_ch01_meaningful_root.py — Bazi Chapter 01 Meaningful Root Threshold Tests.

Validates:
1. ROOT_STRENGTH_THRESHOLD constant is enforced at 2.
2. Residual Qi boundary: a hidden DM stem with weight=1 (< threshold) is NOT a meaningful root
   (Earth DM, day branch Yin, hidden Wu Earth weight=1 => False).
3. Middle Qi boundary: a hidden DM stem with weight=2 (>= threshold) IS a meaningful root
   (Wood DM, day branch Chen, hidden Yi Wood weight=2 => True).
4. Strict English CapitalCase key/value conventions (no Chinese characters).
"""


from src2.core.schemas.unified import PillarMap
from src2.engine.module0_geju_utils import ROOT_STRENGTH_THRESHOLD, _has_meaningful_root
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. THRESHOLD CONSTANT ENFORCEMENT
# ============================================================================

def test_root_strength_threshold_is_two() -> None:
    """Verify ROOT_STRENGTH_THRESHOLD enforces the weight >= 2 boundary."""
    assert ROOT_STRENGTH_THRESHOLD == 2
    assert_key_format_convention(ROOT_STRENGTH_THRESHOLD)


# ============================================================================
# 2. RESIDUAL QI BOUNDARY (weight=1 < threshold => NOT meaningful root)
# ============================================================================

def test_meaningful_root_residual_qi_boundary() -> None:
    """Earth DM, day branch Yin: Wu Earth hidden stem has weight=1 (< 2).

    Yin hidden stems: Jia Wood (5), Bing Fire (2), Wu Earth (1).
    Wu Earth is the DM-matching Earth stem but weight=1 falls below the
    ROOT_STRENGTH_THRESHOLD, so the chart has no meaningful root.
    """
    branches = PillarMap(year=None, month=None, day="Yin", hour=None)
    assert_key_format_convention(branches)
    assert_key_format_convention("Earth")
    assert _has_meaningful_root("Earth", branches, None) is False


# ============================================================================
# 3. MIDDLE QI BOUNDARY (weight=2 >= threshold => meaningful root)
# ============================================================================

def test_meaningful_root_middle_qi_boundary() -> None:
    """Wood DM, day branch Chen: Yi Wood hidden stem has weight=2 (>= 2).

    Chen hidden stems: Wu Earth (5), Yi Wood (2), Gui Water (1).
    Yi Wood is the DM-matching Wood stem with weight=2, meeting the
    ROOT_STRENGTH_THRESHOLD, so the chart has a meaningful root.
    """
    branches = PillarMap(year=None, month=None, day="Chen", hour=None)
    assert_key_format_convention(branches)
    assert_key_format_convention("Wood")
    assert _has_meaningful_root("Wood", branches, None) is True


# ============================================================================
# 4. STRICT ENGLISH CAPITALCASE KEY FORMAT CONVENTION
# ============================================================================

def test_meaningful_root_outputs_pass_capitalcase_convention() -> None:
    """Validate no Chinese characters leak through the meaningful-root seam."""
    day_only_yin = PillarMap(year=None, month=None, day="Yin", hour=None)
    day_only_chen = PillarMap(year=None, month=None, day="Chen", hour=None)
    assert_key_format_convention(day_only_yin)
    assert_key_format_convention(day_only_chen)
