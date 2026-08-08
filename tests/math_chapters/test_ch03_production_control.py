"""TEST/math/test_ch03_production_control.py — Chapter 03 Production & Control Engine Math Tests.

Validates:
1. Ten God Taxonomy: TEN_GODS_MATRIX and get_ten_god() for all 10 Heavenly Stems and pairings.
2. Production and Control element interaction cycles (Wood, Fire, Earth, Metal, Water).
3. Anti-Vibe Test 3.3: Clash disrupts apparent strength (surfacing hidden stems, modifying support/control).
4. 3-Tier DM Strength Classification (Strong / Neutral / Weak) thresholds and calculate_dm_strength_tier1().
5. Strict English CapitalCase key-format conventions across all stems, branches, elements, and Ten Gods.
"""

from typing import Any

import pytest

from src2.core.schemas.unified import (
    CONTROL,
    PRODUCTION,
    ChartProfile,
    ClashAdjustedDmScore,
    DmStrengthTier1,
    Element,
    Pillar,
)
from src2.engine.classical_rules import get_control, get_production, get_ten_god
from src2.engine.module2_root import (
    calculate_clash_adjusted_dm_score,
    calculate_dm_strength_tier1,
    classify_dm_strength,
)
from src2.engine.module2_root import (
    test_anti_vibe_3_3 as engine_test_anti_vibe_3_3,
)

# Mapping between TEN_GODS_MATRIX English TitleCase strings and get_ten_god() return values
MATRIX_TO_GET_TEN_GOD_MAP: dict[str, str] = {
    "Bi Jian": "Friend",
    "Jie Cai": "Rob Wealth",
    "Shi Shen": "Eating God",
    "Shang Guan": "Hurt Officer",
    "Pian Cai": "Indirect Wealth",
    "Zheng Cai": "Direct Wealth",
    "Qi Sha": "7 Killings",
    "Zheng Guan": "Direct Officer",
    "Pian Yin": "Indirect Resource",
    "Zheng Yin": "Direct Resource",
}


# ============================================================================
# 1. TEN GOD TAXONOMY & MATRIX TESTS
# ============================================================================

def test_ten_gods_matrix_structure(
    heavenly_stems: tuple[str, ...],
    assert_key_format_convention: Any,
) -> None:
    """Verify that TEN_GODS_MATRIX maps all 10 Heavenly Stems x 10 target stems in CapitalCase."""
    from src2.core.schemas.unified import TEN_GODS_MATRIX

    assert len(TEN_GODS_MATRIX) == 10
    for dm in heavenly_stems:
        assert dm in TEN_GODS_MATRIX
        assert len(TEN_GODS_MATRIX[dm]) == 10
        for target in heavenly_stems:
            assert target in TEN_GODS_MATRIX[dm]
            ten_god_label = TEN_GODS_MATRIX[dm][target]
            assert isinstance(ten_god_label, str)
            assert ten_god_label in MATRIX_TO_GET_TEN_GOD_MAP

    assert_key_format_convention(TEN_GODS_MATRIX)


def test_get_ten_god_function(
    heavenly_stems: tuple[str, ...],
    assert_key_format_convention: Any,
) -> None:
    """Test get_ten_god() function for all 10 Heavenly Stems and canonical pairings."""
    from src2.core.schemas.unified import TEN_GODS_MATRIX

    # Canonical Jia Wood DM pairings
    assert get_ten_god("Jia", "Jia") == "Friend"
    assert get_ten_god("Jia", "Yi") == "Rob Wealth"
    assert get_ten_god("Jia", "Bing") == "Eating God"
    assert get_ten_god("Jia", "Ding") == "Hurt Officer"
    assert get_ten_god("Jia", "Wu") == "Indirect Wealth"
    assert get_ten_god("Jia", "Ji") == "Direct Wealth"
    assert get_ten_god("Jia", "Geng") == "7 Killings"
    assert get_ten_god("Jia", "Xin") == "Direct Officer"
    assert get_ten_god("Jia", "Ren") == "Indirect Resource"
    assert get_ten_god("Jia", "Gui") == "Direct Resource"

    # Cross-validate all 100 combinations between TEN_GODS_MATRIX and get_ten_god()
    for dm in heavenly_stems:
        for target in heavenly_stems:
            mat_value = TEN_GODS_MATRIX[dm][target]
            expected_fn_value = MATRIX_TO_GET_TEN_GOD_MAP[mat_value]
            actual_fn_value = get_ten_god(dm, target)
            assert actual_fn_value == expected_fn_value

    assert_key_format_convention(heavenly_stems)


def test_production_and_control_cycles(
    five_elements: tuple[str, ...],
    assert_key_format_convention: Any,
) -> None:
    """Validate elemental Production and Control cycles."""
    # Production cycle: Wood -> Fire -> Earth -> Metal -> Water -> Wood
    assert get_production(Element.WOOD) == Element.FIRE
    assert get_production(Element.FIRE) == Element.EARTH
    assert get_production(Element.EARTH) == Element.METAL
    assert get_production(Element.METAL) == Element.WATER
    assert get_production(Element.WATER) == Element.WOOD

    # Control cycle: Wood -> Earth -> Water -> Fire -> Metal -> Wood
    assert get_control(Element.WOOD) == Element.EARTH
    assert get_control(Element.EARTH) == Element.WATER
    assert get_control(Element.WATER) == Element.FIRE
    assert get_control(Element.FIRE) == Element.METAL
    assert get_control(Element.METAL) == Element.WOOD

    # Verify Pydantic schema model dictionaries
    assert PRODUCTION.wood == Element.FIRE
    assert PRODUCTION.fire == Element.EARTH
    assert PRODUCTION.earth == Element.METAL
    assert PRODUCTION.metal == Element.WATER
    assert PRODUCTION.water == Element.WOOD

    assert CONTROL.wood == Element.EARTH
    assert CONTROL.earth == Element.WATER
    assert CONTROL.water == Element.FIRE
    assert CONTROL.fire == Element.METAL
    assert CONTROL.metal == Element.WOOD

    assert_key_format_convention(five_elements)


# ============================================================================
# 2. ANTI-VIBE TEST 3.3 (CLASH DISRUPTS APPARENT STRENGTH)
# ============================================================================

def test_anti_vibe_3_3_engine_helper() -> None:
    """Verify built-in test_anti_vibe_3_3 engine sanity function."""
    assert engine_test_anti_vibe_3_3() is True


def test_anti_vibe_3_3_bing_fire_dm_roles(
    assert_key_format_convention: Any,
) -> None:
    """Anti-Vibe Test 3.3: Verify exact Ten God roles for Bing (Yang Fire) DM.

    Metal (Geng/Xin) is Wealth (NOT Control).
    Water (Ren/Gui) is Control (NOT Resource).
    Wood (Jia/Yi) is Resource / Support (produces Fire).
    Fire (Bing/Ding) is Friend / Rob Wealth (Root).
    """
    # Metal stems are Wealth
    assert get_ten_god("Bing", "Geng") == "Indirect Wealth"
    assert get_ten_god("Bing", "Xin") == "Direct Wealth"

    # Water stems are Control
    assert get_ten_god("Bing", "Ren") == "7 Killings"
    assert get_ten_god("Bing", "Gui") == "Direct Officer"

    # Wood stems are Resource
    assert get_ten_god("Bing", "Jia") == "Indirect Resource"
    assert get_ten_god("Bing", "Yi") == "Direct Resource"

    # Fire stems are Peer/Root
    assert get_ten_god("Bing", "Bing") == "Friend"
    assert get_ten_god("Bing", "Ding") == "Rob Wealth"

    bing_profile = ChartProfile(
        day_master="Bing",
        dm_element="Fire",
        year_pillar=Pillar(stem="Geng", branch="Shen"),
        month_pillar=Pillar(stem="Ren", branch="Zi"),
        day_pillar=Pillar(stem="Bing", branch="Wu"),
        hour_pillar=Pillar(stem="Jia", branch="Yin"),
    )

    # Unclashed vs Clashed branch scores
    unclashed: ClashAdjustedDmScore = calculate_clash_adjusted_dm_score(
        bing_profile, clashed_branches=[]
    )
    clashed: ClashAdjustedDmScore = calculate_clash_adjusted_dm_score(
        bing_profile, clashed_branches=["Zi", "Wu"]
    )

    assert isinstance(unclashed, ClashAdjustedDmScore)
    assert isinstance(clashed, ClashAdjustedDmScore)

    # Branch clash Zi-Wu surfaces hidden stems and modifies branch control factor,
    # causing clash score to differ from unclashed baseline.
    assert unclashed.score != clashed.score
    assert unclashed.root_dm < clashed.root_dm  # Hidden Ding Fire surfaces in Wu branch
    assert unclashed.control_dm != clashed.control_dm

    assert_key_format_convention(bing_profile)
    assert_key_format_convention(unclashed)
    assert_key_format_convention(clashed)


# ============================================================================
# 3. 3-TIER DM STRENGTH CLASSIFICATION TESTS
# ============================================================================

@pytest.mark.parametrize(
    ("score", "expected_classification"),
    [
        (10.0, "Strong"),
        (4.5, "Strong"),
        (4.0, "Strong"),  # Boundary: score >= 4.0 is Strong
        (3.99, "Neutral"),
        (3.0, "Neutral"),
        (2.01, "Neutral"),
        (2.0, "Weak"),  # Boundary: score <= 2.0 is Weak
        (1.5, "Weak"),
        (0.0, "Weak"),
        (-5.0, "Weak"),
    ],
)
def test_classify_dm_strength_thresholds(
    score: float,
    expected_classification: str,
    assert_key_format_convention: Any,
) -> None:
    """Test 3-tier DM strength classification threshold boundaries.

    Strong: score >= 4.0
    Neutral: 2.0 < score < 4.0
    Weak: score <= 2.0
    """
    result = classify_dm_strength(score)
    assert result == expected_classification
    assert_key_format_convention(result)


def test_calculate_dm_strength_tier1_strong_chart(
    strong_dm_chart: dict[str, dict[str, str]],
    assert_key_format_convention: Any,
) -> None:
    """Test calculate_dm_strength_tier1() on a Strong Day Master profile."""
    profile = ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem=strong_dm_chart["year"]["stem"], branch=strong_dm_chart["year"]["branch"]),
        month_pillar=Pillar(stem=strong_dm_chart["month"]["stem"], branch=strong_dm_chart["month"]["branch"]),
        day_pillar=Pillar(stem=strong_dm_chart["day"]["stem"], branch=strong_dm_chart["day"]["branch"]),
        hour_pillar=Pillar(stem=strong_dm_chart["hour"]["stem"], branch=strong_dm_chart["hour"]["branch"]),
    )

    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)
    assert isinstance(result, DmStrengthTier1)
    assert result.classification == "Strong"
    assert result.score >= 4.0
    assert result.components["root_dm"] > 0.0

    assert_key_format_convention(result)


def test_calculate_dm_strength_tier1_weak_chart(
    weak_dm_chart: dict[str, dict[str, str]],
    assert_key_format_convention: Any,
) -> None:
    """Test calculate_dm_strength_tier1() on a Weak Day Master profile."""
    profile = ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem=weak_dm_chart["year"]["stem"], branch=weak_dm_chart["year"]["branch"]),
        month_pillar=Pillar(stem=weak_dm_chart["month"]["stem"], branch=weak_dm_chart["month"]["branch"]),
        day_pillar=Pillar(stem=weak_dm_chart["day"]["stem"], branch=weak_dm_chart["day"]["branch"]),
        hour_pillar=Pillar(stem=weak_dm_chart["hour"]["stem"], branch=weak_dm_chart["hour"]["branch"]),
    )

    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)
    assert isinstance(result, DmStrengthTier1)
    assert result.classification == "Weak"
    assert result.score <= 2.0
    assert result.components["control_dm"] > 0.0

    assert_key_format_convention(result)


# ============================================================================
# 4. CAPITALCASE & KEY-FORMAT CONVENTION ASSERTIONS
# ============================================================================

def test_english_capitalcase_convention(
    heavenly_stems: tuple[str, ...],
    earthly_branches: tuple[str, ...],
    five_elements: tuple[str, ...],
    assert_key_format_convention: Any,
) -> None:
    """Assert all stem, branch, element, and Ten God keys adhere strictly to English CapitalCase."""
    for s in heavenly_stems:
        assert s[0].isupper()
        assert_key_format_convention(s)

    for b in earthly_branches:
        assert b[0].isupper()
        assert_key_format_convention(b)

    for e in five_elements:
        assert e[0].isupper()
        assert_key_format_convention(e)

    for key, value in MATRIX_TO_GET_TEN_GOD_MAP.items():
        assert_key_format_convention(key)
        assert_key_format_convention(value)
