"""TEST/math/test_ch12_master_cases.py — Chapter 12 Master Cases & Spectrum Integration Test Suite.

Tests 5 canonical master charts, DMScoreWithOutput validator/drain calculation,
and spectrum tier scoring integration. Enforces English CapitalCase conventions
(e.g., 'Jia', 'Zi', 'Wood') for all stem, branch, and element keys.
"""

import pytest
from pydantic import ValidationError

from src2.core.schemas.unified import (
    ChartProfile,
    DMScoreWithOutput,
    GeJuOutput,
    GeJuValidation,
    Pillar,
    SpectrumInput,
    SpectrumOutput,
)
from src2.engine.module13_spectrum import (
    _get_spectrum_tier,
    calculate_strength_profile,
)
from TEST.math.conftest import assert_key_format_convention


def _create_master_profile(
    day_master: str,
    dm_element: str,
    year_stem: str,
    year_branch: str,
    month_stem: str,
    month_branch: str,
    day_stem: str,
    day_branch: str,
    hour_stem: str,
    hour_branch: str,
    gender: str = "M",
) -> ChartProfile:
    """Helper to construct a ChartProfile for master case charts."""
    return ChartProfile(
        day_master=day_master,
        dm_element=dm_element,
        year_pillar=Pillar(stem=year_stem, branch=year_branch),
        month_pillar=Pillar(stem=month_stem, branch=month_branch),
        day_pillar=Pillar(stem=day_stem, branch=day_branch),
        hour_pillar=Pillar(stem=hour_stem, branch=hour_branch),
        gender=gender,
    )


# ============================================================================
# 1. CANONICAL MASTER CASE CHARTS TESTS (5 MASTER CASES)
# ============================================================================

def test_master_case_12_1_wu_earth_clash() -> None:
    """Case 12.1: DM = Wu (Yang Earth), Chart: Jia Zi | Bing Yin | Wu Shen | Geng Shen.

    Tests DM strength and spectrum calculation under Yin-Shen branch clash.
    """
    profile = _create_master_profile(
        day_master="Wu",
        dm_element="Earth",
        year_stem="Jia",
        year_branch="Zi",
        month_stem="Bing",
        month_branch="Yin",
        day_stem="Wu",
        day_branch="Shen",
        hour_stem="Geng",
        hour_branch="Shen",
    )
    assert_key_format_convention(profile)

    spectrum_in = SpectrumInput(
        profile=profile,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)

    assert isinstance(output.continuous_score, float)
    assert output.spectrum_tier in ("Vibrant", "Strong", "Mild Strong", "Balanced", "Mild Weak", "Weak", "Follower")
    assert output.special_pattern_override is None


def test_master_case_12_2_gui_water_output_drain() -> None:
    """Case 12.2: DM = Gui (Yin Water), Chart: Gui Mao | Yi Mao | Gui You | Ding Si.

    Tests DM strength with Mao-You clash and Wood Output drain.
    """
    profile = _create_master_profile(
        day_master="Gui",
        dm_element="Water",
        year_stem="Gui",
        year_branch="Mao",
        month_stem="Yi",
        month_branch="Mao",
        day_stem="Gui",
        day_branch="You",
        hour_stem="Ding",
        hour_branch="Si",
        gender="F",
    )
    assert_key_format_convention(profile)

    spectrum_in = SpectrumInput(
        profile=profile,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)

    assert isinstance(output.continuous_score, float)
    assert output.spectrum_tier in ("Vibrant", "Strong", "Mild Strong", "Balanced", "Mild Weak", "Weak", "Follower")


def test_master_case_12_3_xin_metal_heavy_output() -> None:
    """Case 12.3: DM = Xin (Yin Metal), Chart: Yi Mao | Ji Mao | Xin Mao | Gui Mao.

    Tests DM strength with extreme Wood Output/Wealth drain and reverse Luck Pillar.
    """
    profile = _create_master_profile(
        day_master="Xin",
        dm_element="Metal",
        year_stem="Yi",
        year_branch="Mao",
        month_stem="Ji",
        month_branch="Mao",
        day_stem="Xin",
        day_branch="Mao",
        hour_stem="Gui",
        hour_branch="Mao",
        gender="M",
    )
    assert_key_format_convention(profile)

    spectrum_in = SpectrumInput(
        profile=profile,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)

    assert isinstance(output.continuous_score, float)
    assert output.spectrum_tier in ("Vibrant", "Strong", "Mild Strong", "Balanced", "Mild Weak", "Weak", "Follower")


def test_master_case_12_4_ren_water_neutral() -> None:
    """Case 12.4: DM = Ren (Yang Water), Chart: Bing Zi | Geng Yin | Ren Chen | Xin Mao.

    Tests DM strength with balanced Metal support and Wood output in Spring.
    """
    profile = _create_master_profile(
        day_master="Ren",
        dm_element="Water",
        year_stem="Bing",
        year_branch="Zi",
        month_stem="Geng",
        month_branch="Yin",
        day_stem="Ren",
        day_branch="Chen",
        hour_stem="Xin",
        hour_branch="Mao",
        gender="M",
    )
    assert_key_format_convention(profile)

    spectrum_in = SpectrumInput(
        profile=profile,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)

    assert isinstance(output.continuous_score, float)
    assert output.spectrum_tier in ("Vibrant", "Strong", "Mild Strong", "Balanced", "Mild Weak", "Weak", "Follower")


def test_master_case_12_5_special_vibrant_structure() -> None:
    """Case 12.5: DM = Jia (Wood), Chart: Jia Yin | Bing Yin | Jia Yin | Bing Yin.

    Tests special structure override (Zhuan Wang Ge / Vibrant Pattern).
    """
    profile = _create_master_profile(
        day_master="Jia",
        dm_element="Wood",
        year_stem="Jia",
        year_branch="Yin",
        month_stem="Bing",
        month_branch="Yin",
        day_stem="Jia",
        day_branch="Yin",
        hour_stem="Bing",
        hour_branch="Yin",
    )
    ge_ju = GeJuOutput(
        pattern_name="Zhuan Wang Ge",
        is_special=True,
        special_structure_validation=GeJuValidation(
            is_special_structure=True,
            seasonal_supported=True,
            reason="Zhuan Wang Ge pattern",
        ),
        ge_ju_alignment_mod=10.0,
        pattern_key="zhuan_wang_ge",
    )
    assert_key_format_convention(profile)
    assert_key_format_convention(ge_ju)

    spectrum_in = SpectrumInput(
        profile=profile,
        ge_ju=ge_ju,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)

    assert output.special_pattern_override == "Vibrant"
    assert output.continuous_score == 90.0
    assert output.spectrum_tier == "Vibrant"


# ============================================================================
# 2. DMSCOREWITHOUTPUT DRAIN VALIDATOR & CALCULATION TESTS
# ============================================================================

def test_dm_score_with_output_calculation() -> None:
    """Test DMScoreWithOutput model validator and final score calculation.

    final_score = dm_strength - (output_dm * 1.0) + clash_adjustment
    """
    score1 = DMScoreWithOutput(dm_strength=4.0, output_dm=1.0, clash_adjustment=0.5)
    assert score1.final_score == 3.5

    score2 = DMScoreWithOutput(dm_strength=1.3, output_dm=1.0, clash_adjustment=-0.5)
    assert pytest.approx(score2.final_score) == -0.2

    score3 = DMScoreWithOutput(dm_strength=0.0, output_dm=2.0, clash_adjustment=0.0)
    assert score3.final_score == -2.0


def test_dm_score_with_output_validation_constraints() -> None:
    """Test DMScoreWithOutput Pydantic Field validation for ge=0.0 constraints."""
    with pytest.raises(ValidationError):
        DMScoreWithOutput(dm_strength=-1.0, output_dm=1.0, clash_adjustment=0.0)

    with pytest.raises(ValidationError):
        DMScoreWithOutput(dm_strength=2.0, output_dm=-0.5, clash_adjustment=0.0)


# ============================================================================
# 3. SPECTRUM TIER SCORING INTEGRATION TESTS
# ============================================================================

@pytest.mark.parametrize(
    ("score", "expected_tier"),
    [
        (85.0, "Vibrant"),
        (80.0, "Vibrant"),
        (50.0, "Strong"),
        (40.0, "Strong"),
        (25.0, "Mild Strong"),
        (10.0, "Mild Strong"),
        (0.0, "Balanced"),
        (-10.0, "Balanced"),
        (-20.0, "Mild Weak"),
        (-40.0, "Mild Weak"),
        (-60.0, "Weak"),
        (-80.0, "Weak"),
        (-90.0, "Follower"),
    ],
)
def test_spectrum_tier_boundaries(score: float, expected_tier: str) -> None:
    """Test _get_spectrum_tier helper across all score boundaries."""
    assert _get_spectrum_tier(score) == expected_tier


def test_spectrum_tier_special_pattern_follower_override() -> None:
    """Test spectrum tier scoring for Follower special pattern override (Cong Cai Ge)."""
    profile = _create_master_profile(
        day_master="Xin",
        dm_element="Metal",
        year_stem="Yi",
        year_branch="Mao",
        month_stem="Yi",
        month_branch="Mao",
        day_stem="Xin",
        day_branch="Mao",
        hour_stem="Yi",
        hour_branch="Mao",
    )
    ge_ju = GeJuOutput(
        pattern_name="Cong Cai Ge",
        is_special=True,
        special_structure_validation=GeJuValidation(
            is_special_structure=True,
            seasonal_supported=True,
            reason="Cong Cai Ge pattern",
        ),
        ge_ju_alignment_mod=10.0,
        pattern_key="cong_cai_ge",
    )
    spectrum_in = SpectrumInput(
        profile=profile,
        ge_ju=ge_ju,
        self_punished_branches=[],
    )
    output: SpectrumOutput = calculate_strength_profile(spectrum_in)

    assert output.special_pattern_override == "Follower"
    assert output.continuous_score == -90.0
    assert output.spectrum_tier == "Follower"


# ============================================================================
# 4. CAPITALCASE CONVENTION & KEY FORMAT CONVENTION ASSERTIONS
# ============================================================================

def test_english_capitalcase_convention_assertions() -> None:
    """Assert English CapitalCase for all stem/branch/element keys in models."""
    sample_dm_score = DMScoreWithOutput(dm_strength=3.0, output_dm=1.0, clash_adjustment=0.0)
    assert_key_format_convention(sample_dm_score)

    profile = _create_master_profile(
        day_master="Geng",
        dm_element="Metal",
        year_stem="Geng",
        year_branch="Shen",
        month_stem="Ji",
        month_branch="Chou",
        day_stem="Geng",
        day_branch="Shen",
        hour_stem="Wu",
        hour_branch="Yin",
    )
    assert_key_format_convention(profile)

    spectrum_in = SpectrumInput(profile=profile, self_punished_branches=[])
    output = calculate_strength_profile(spectrum_in)
    assert_key_format_convention(output)
