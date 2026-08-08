"""TEST/math/test_ch01_commanding_qi.py — Bazi Chapter 01 Commanding Qi Math Tests.

Validates:
1. Five-phase seasonal multipliers (Wang=1.5, Xiang=1.2, Xiu=1.0, Qiu=0.7, Si=0.4).
2. Deterministic seasonal phase classification (get_element_phase).
3. Tier-1 DM Strength calculation formula: (Root * 2.0) + Support - (Control * 1.5).
4. DM strength classification thresholds (Strong >= 4.0, Weak <= 2.0, Neutral).
5. Root scoring and dormancy multiplier calculations.
6. Strict English CapitalCase key/value conventions (no Chinese characters).
"""

import pytest

from src2.core.schemas.unified import ChartProfile, Pillar
from src2.engine.classical_rules import (
    get_element_phase_multiplier,
    get_month_ruling_element,
)
from src2.engine.element_phase import get_element_phase, get_phase_multiplier
from src2.engine.module2_root import (
    calculate_dm_strength_tier1,
    calculate_root_score,
    classify_dm_strength,
    get_dormancy_multiplier,
    get_seasonal_adjustment_factor,
)
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. FIVE-PHASE SEASONAL MULTIPLIERS (旺相休囚死)
# ============================================================================

def test_element_phase_multiplier_direct() -> None:
    """Verify numeric multipliers for each of the 5 seasonal prosperity states."""
    expected_multipliers = {
        "Wang": 1.5,
        "Xiang": 1.2,
        "Xiu": 1.0,
        "Qiu": 0.7,
        "Si": 0.4,
    }
    for phase, expected_mult in expected_multipliers.items():
        mult = get_element_phase_multiplier(phase)
        assert mult == expected_mult, f"Phase {phase} multiplier expected {expected_mult}, got {mult}"
        assert_key_format_convention(phase)

    # Unknown phase defaults to 1.0
    assert get_element_phase_multiplier("Unknown") == 1.0
    assert get_element_phase_multiplier("InvalidPhase") == 1.0


@pytest.mark.parametrize(
    "month_branch, ruling_element, wang_el, xiang_el, xiu_el, qiu_el, si_el",
    [
        ("Yin", "Wood", "Wood", "Fire", "Water", "Metal", "Earth"),
        ("Mao", "Wood", "Wood", "Fire", "Water", "Metal", "Earth"),
        ("Si", "Fire", "Fire", "Earth", "Wood", "Water", "Metal"),
        ("Wu", "Fire", "Fire", "Earth", "Wood", "Water", "Metal"),
        ("Shen", "Metal", "Metal", "Water", "Earth", "Fire", "Wood"),
        ("You", "Metal", "Metal", "Water", "Earth", "Fire", "Wood"),
        ("Hai", "Water", "Water", "Wood", "Metal", "Earth", "Fire"),
        ("Zi", "Water", "Water", "Wood", "Metal", "Earth", "Fire"),
        ("Chen", "Earth", "Earth", "Metal", "Fire", "Wood", "Water"),
        ("Xu", "Earth", "Earth", "Metal", "Fire", "Wood", "Water"),
        ("Chou", "Earth", "Earth", "Metal", "Fire", "Wood", "Water"),
        ("Wei", "Earth", "Earth", "Metal", "Fire", "Wood", "Water"),
    ],
)
def test_seasonal_phase_and_multiplier_by_month(
    month_branch: str,
    ruling_element: str,
    wang_el: str,
    xiang_el: str,
    xiu_el: str,
    qiu_el: str,
    si_el: str,
) -> None:
    """Verify get_phase_multiplier and get_seasonal_adjustment_factor for all 5 states across all 12 month branches."""
    phase_mapping = [
        (wang_el, "Wang", 1.5),
        (xiang_el, "Xiang", 1.2),
        (xiu_el, "Xiu", 1.0),
        (qiu_el, "Qiu", 0.7),
        (si_el, "Si", 0.4),
    ]

    for element, expected_phase, expected_mult in phase_mapping:
        phase = get_element_phase(element, month_branch)
        assert phase == expected_phase, (
            f"Element {element} in month {month_branch} expected phase {expected_phase}, got {phase}"
        )

        mult = get_phase_multiplier(element, month_branch)
        assert mult == pytest.approx(expected_mult), (
            f"Element {element} in month {month_branch} expected multiplier {expected_mult}, got {mult}"
        )

        adj_factor = get_seasonal_adjustment_factor(element, month_branch)
        assert adj_factor == pytest.approx(expected_mult), (
            f"Element {element} in month {month_branch} seasonal adj expected {expected_mult}, got {adj_factor}"
        )

        assert_key_format_convention(month_branch)
        assert_key_format_convention(element)
        assert_key_format_convention(phase)


# ============================================================================
# 2. GET_ELEMENT_PHASE AND MONTH RULING ELEMENT
# ============================================================================

def test_month_ruling_element_mapping() -> None:
    """Verify deterministic mapping of month branches to ruling elements."""
    expected_rulings = {
        "Yin": "Wood", "Mao": "Wood",
        "Si": "Fire", "Wu": "Fire",
        "Shen": "Metal", "You": "Metal",
        "Hai": "Water", "Zi": "Water",
        "Chen": "Earth", "Xu": "Earth", "Chou": "Earth", "Wei": "Earth",
    }
    for branch, expected_ruling in expected_rulings.items():
        ruling = get_month_ruling_element(branch)
        assert ruling == expected_ruling
        assert_key_format_convention(branch)
        assert_key_format_convention(ruling)

    # Case-insensitivity check (e.g. yin -> Wood)
    assert get_month_ruling_element("yin") == "Wood"
    assert get_month_ruling_element("INVALID") is None


def test_get_element_phase_invalid_inputs() -> None:
    """Verify get_element_phase handles invalid elements or branches gracefully."""
    assert get_element_phase("InvalidElement", "Yin") == "Unknown"
    assert get_element_phase("Wood", "InvalidBranch") == "Unknown"
    assert get_element_phase("", "") == "Unknown"


# ============================================================================
# 3. TIER-1 DM STRENGTH FORMULA & CLASSIFICATION
# ============================================================================

def test_calculate_dm_strength_tier1_strong() -> None:
    """Test Tier-1 DM Strength formula for a Strong Day Master profile."""
    # Jia Wood DM in Spring (Mao month) with heavy Wood support
    profile = ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Jia", branch="Yin"),
        month_pillar=Pillar(stem="Yi", branch="Mao"),
        day_pillar=Pillar(stem="Jia", branch="Yin"),
        hour_pillar=Pillar(stem="Bing", branch="Chen"),
    )

    result = calculate_dm_strength_tier1(profile)
    assert_key_format_convention(result)

    # DM_score = (Root_DM * 2.0) + Support_DM - (Control_DM * 1.5)
    root_dm = result.components["root_dm"]
    support_dm = result.components["support_dm"]
    control_dm = result.components["control_dm"]

    expected_score = round((root_dm * 2.0) + support_dm - (control_dm * 1.5), 2)
    assert result.score == expected_score
    assert result.score >= 4.0
    assert result.classification == "Strong"


def test_calculate_dm_strength_tier1_weak() -> None:
    """Test Tier-1 DM Strength formula for a Weak Day Master profile."""
    # Jia Wood DM in Autumn (You month) surrounded by Heavy Metal (Geng/Xin/Shen/You)
    profile = ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Geng", branch="Shen"),
        month_pillar=Pillar(stem="Xin", branch="You"),
        day_pillar=Pillar(stem="Jia", branch="Xu"),
        hour_pillar=Pillar(stem="Geng", branch="Shen"),
    )

    result = calculate_dm_strength_tier1(profile)
    assert_key_format_convention(result)

    root_dm = result.components["root_dm"]
    support_dm = result.components["support_dm"]
    control_dm = result.components["control_dm"]

    expected_score = round((root_dm * 2.0) + support_dm - (control_dm * 1.5), 2)
    assert result.score == expected_score
    assert result.score <= 2.0
    assert result.classification == "Weak"


@pytest.mark.parametrize(
    "score, expected_classification",
    [
        (6.5, "Strong"),
        (4.0, "Strong"),
        (3.99, "Neutral"),
        (3.0, "Neutral"),
        (2.01, "Neutral"),
        (2.0, "Weak"),
        (0.5, "Weak"),
        (-1.5, "Weak"),
    ],
)
def test_classify_dm_strength(score: float, expected_classification: str) -> None:
    """Verify threshold classification for Tier-1 DM strength scores."""
    classification = classify_dm_strength(score)
    assert classification == expected_classification
    assert_key_format_convention(classification)


# ============================================================================
# 4. ROOT SCORE & DORMANCY MULTIPLIER
# ============================================================================

def test_calculate_root_score() -> None:
    """Verify Tier-1 root score calculation: surface_roots + (hidden_roots * 0.3)."""
    res1 = calculate_root_score(surface_roots=1, hidden_roots=2)
    assert res1.score == pytest.approx(1.6)
    assert res1.surface_roots == 1
    assert res1.hidden_roots == 2
    assert_key_format_convention(res1)

    res2 = calculate_root_score(surface_roots=0, hidden_roots=3)
    assert res2.score == pytest.approx(0.9)

    res3 = calculate_root_score(surface_roots=2, hidden_roots=0)
    assert res3.score == pytest.approx(2.0)


def test_get_dormancy_multiplier() -> None:
    """Verify branch dormancy multiplier evaluation."""
    # Zi has hidden stem Gui with weight 5 (>= 2), so not dormant
    dorm_zi = get_dormancy_multiplier("Zi")
    assert dorm_zi.branch == "Zi"
    assert dorm_zi.multiplier == 1.0
    assert not dorm_zi.is_dormant
    assert_key_format_convention(dorm_zi)

    # Yin has hidden stem Jia (5), Bing (2), Wu (1) -> active
    dorm_yin = get_dormancy_multiplier("Yin")
    assert dorm_yin.multiplier == 1.0
    assert not dorm_yin.is_dormant

    # Invalid branch has no hidden stems -> dormant (0.3)
    dorm_invalid = get_dormancy_multiplier("Unknown")
    assert dorm_invalid.multiplier == 0.3
    assert dorm_invalid.is_dormant


# ============================================================================
# 5. STRICT ENGLISH CAPITALCASE KEY FORMAT CONVENTION
# ============================================================================

def test_all_outputs_pass_capitalcase_convention() -> None:
    """Comprehensive test validating that no Chinese characters are leaked in test artifacts."""
    sample_profile = ChartProfile(
        day_master="Bing",
        dm_element="Fire",
        year_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        day_pillar=Pillar(stem="Bing", branch="Wu"),
        hour_pillar=Pillar(stem="Wu", branch="Shen"),
    )
    result = calculate_dm_strength_tier1(sample_profile)
    assert_key_format_convention(sample_profile)
    assert_key_format_convention(result)
