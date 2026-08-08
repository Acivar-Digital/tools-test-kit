"""TEST/math/test_ch04_combination.py — Chapter 04 Combination Tests.

Validates:
- San He / Liu He / Ban He / San Hui interaction strengths.
- SiShen Harmony (巳申) stability with and without Water stem support.
- Combination weakening conditions (hidden stem, control, seasonal).
- Strict adherence to English CapitalCase for all stem, branch, and element keys.
"""

from typing import Any

import pytest

from src2.core.schemas.unified import (
    CombinationStrength,
    CombinationWeakeningResult,
    Element,
    HarmonyStrength,
    SiShenHarmonyStability,
)
from src2.engine.module3_interaction import (
    calculate_combination_strength,
    calculate_combination_weakening,
    calculate_harmony_strength,
    check_si_shen_harmony,
)
from TEST.math.conftest import assert_key_format_convention


class TestSanHeCombinations:
    """Test San He (Three Harmony) combination strength calculations."""

    @pytest.mark.parametrize(
        ("branches", "expected_element"),
        [
            (frozenset({"Shen", "Zi", "Chen"}), Element.WATER),
            (frozenset({"Hai", "Mao", "Wei"}), Element.WOOD),
            (frozenset({"Yin", "Wu", "Xu"}), Element.FIRE),
            (frozenset({"Si", "You", "Chou"}), Element.METAL),
        ],
    )
    def test_san_he_all_frames(self, branches: frozenset[str], expected_element: Element) -> None:
        """Verify San He frames for all 4 elements with 3 branches present."""
        chart_branches = list(branches) + ["Yin"]
        chart_stems = ["Ren", "Gui", "Jia", "Yi"]
        result = calculate_combination_strength(
            combo_type="San He",
            branches=branches,
            chart_branches=chart_branches,
            chart_stems=chart_stems,
            month_branch="Zi",
        )
        assert isinstance(result, CombinationStrength)
        assert result.element == expected_element
        assert result.classification == "absolute"
        assert result.strength >= 4.0
        assert_key_format_convention(result)

    def test_san_he_water_frame_detailed_score(self) -> None:
        """Verify explicit score breakdown for Shen-Zi-Chen Water frame."""
        branches = frozenset({"Shen", "Zi", "Chen"})
        chart_branches = ["Shen", "Zi", "Chen", "Chou"]
        chart_stems = ["Ren", "Gui", "Jia", "Yi"]
        result = calculate_combination_strength(
            combo_type="San He",
            branches=branches,
            chart_branches=chart_branches,
            chart_stems=chart_stems,
            month_branch="Zi",
        )
        # 3 branches present + 2 supporting stems (Ren, Gui) + 4 extracted hidden stems
        assert result.strength == 9.0
        assert result.classification == "absolute"
        assert result.element == Element.WATER
        assert_key_format_convention(result)


class TestSanHuiCombinations:
    """Test San Hui (Three Directional Alignment) combination strength calculations."""

    @pytest.mark.parametrize(
        ("branches", "expected_element"),
        [
            (frozenset({"Hai", "Zi", "Chou"}), Element.WATER),
            (frozenset({"Yin", "Mao", "Chen"}), Element.WOOD),
            (frozenset({"Si", "Wu", "Wei"}), Element.FIRE),
            (frozenset({"Shen", "You", "Xu"}), Element.METAL),
        ],
    )
    def test_san_hui_all_frames(self, branches: frozenset[str], expected_element: Element) -> None:
        """Verify San Hui directional alignments for all 4 elements."""
        chart_branches = list(branches)
        chart_stems = ["Jia", "Yi", "Bing", "Ding"]
        result = calculate_combination_strength(
            combo_type="San Hui",
            branches=branches,
            chart_branches=chart_branches,
            chart_stems=chart_stems,
            month_branch="Mao",
        )
        assert isinstance(result, CombinationStrength)
        assert result.element == expected_element
        assert result.strength >= 3.0
        assert_key_format_convention(result)


class TestBanHeCombinations:
    """Test Ban He (Half Harmony) combination strength calculations."""

    @pytest.mark.parametrize(
        ("branches", "expected_element"),
        [
            (frozenset({"Shen", "Zi"}), Element.WATER),
            (frozenset({"Zi", "Chen"}), Element.WATER),
            (frozenset({"Hai", "Mao"}), Element.WOOD),
            (frozenset({"Mao", "Wei"}), Element.WOOD),
            (frozenset({"Yin", "Wu"}), Element.FIRE),
            (frozenset({"Wu", "Xu"}), Element.FIRE),
            (frozenset({"Si", "You"}), Element.METAL),
            (frozenset({"You", "Chou"}), Element.METAL),
        ],
    )
    def test_ban_he_all_pairs(self, branches: frozenset[str], expected_element: Element) -> None:
        """Verify Ban He half-harmony pairs evaluate to correct element."""
        chart_branches = list(branches) + ["Yin", "Mao"]
        chart_stems = ["Jia", "Yi", "Bing", "Ding"]
        result = calculate_combination_strength(
            combo_type="Ban He",
            branches=branches,
            chart_branches=chart_branches,
            chart_stems=chart_stems,
            month_branch="Zi",
        )
        assert isinstance(result, CombinationStrength)
        assert result.element == expected_element
        assert_key_format_convention(result)


class TestLiuHeCombinations:
    """Test Liu He (Six Harmony) strength calculations."""

    @pytest.mark.parametrize(
        ("branch_a", "branch_b", "expected_element"),
        [
            ("Zi", "Chou", Element.EARTH),
            ("Yin", "Hai", Element.WOOD),
            ("Mao", "Xu", Element.FIRE),
            ("Chen", "You", Element.METAL),
            ("Si", "Shen", Element.WATER),
            ("Wu", "Wei", Element.FIRE),
        ],
    )
    def test_liu_he_pairs_strength(
        self, branch_a: str, branch_b: str, expected_element: Element
    ) -> None:
        """Verify all six Liu He pairs yield expected element and active state."""
        chart_stems = ["Jia", "Yi", "Bing", "Ding"]
        result = calculate_harmony_strength(branch_a, branch_b, chart_stems)
        assert isinstance(result, HarmonyStrength)
        assert result.element == expected_element
        assert result.active is True
        assert result.strength >= 2.0
        assert_key_format_convention(result)

    def test_liu_he_combination_strength_wrapper(self) -> None:
        """Verify Liu He via calculate_combination_strength adapter."""
        branches = frozenset({"Zi", "Chou"})
        result = calculate_combination_strength(
            combo_type="Liu He",
            branches=branches,
            chart_branches=["Zi", "Chou"],
            chart_stems=["Wu", "Ji"],
            month_branch="Chou",
        )
        assert result.element == Element.EARTH
        assert_key_format_convention(result)


class TestSiShenHarmony:
    """Test check_si_shen_harmony with and without Water stem support."""

    def test_si_shen_harmony_with_water_stem(self) -> None:
        """Si-Shen harmony with Water stem support should be stable."""
        stems = ["Ren", "Jia", "Wu", "Bing"]
        result = check_si_shen_harmony("Si", "Shen", stems)
        assert isinstance(result, SiShenHarmonyStability)
        assert result.verdict == "stable"
        assert result.stable is True
        assert result.score == 0.3
        assert result.supporting_stems == 1.0
        assert_key_format_convention(result)

    def test_si_shen_harmony_with_multiple_water_stems(self) -> None:
        """Si-Shen harmony with multiple Water stems."""
        stems = ["Ren", "Gui", "Wu", "Bing"]
        result = check_si_shen_harmony("Si", "Shen", stems)
        assert result.verdict == "stable"
        assert result.stable is True
        assert result.score == 0.3
        assert result.supporting_stems == 2.0
        assert_key_format_convention(result)

    def test_si_shen_harmony_without_water_stem(self) -> None:
        """Si-Shen harmony without Water stem support should indicate no_water_support."""
        stems = ["Jia", "Bing", "Wu", "Ji"]
        result = check_si_shen_harmony("Si", "Shen", stems)
        assert isinstance(result, SiShenHarmonyStability)
        assert result.verdict == "no_water_support"
        assert result.stable is False
        assert result.score == 0.0
        assert result.supporting_stems == 0.0
        assert_key_format_convention(result)

    def test_si_shen_harmony_inactive_pair(self) -> None:
        """Non Si-Shen pair should return inactive."""
        stems = ["Ren", "Gui", "Wu", "Bing"]
        result = check_si_shen_harmony("Zi", "Chou", stems)
        assert result.verdict == "inactive"
        assert result.stable is False
        assert result.score == 0.0
        assert result.supporting_stems == 0.0
        assert_key_format_convention(result)


class TestCombinationWeakening:
    """Test calculate_combination_weakening conditions."""

    def test_no_weakening_conditions(self) -> None:
        """When no weakening factors apply, strength remains 1.0."""
        result = calculate_combination_weakening(
            combo_element="Wood",
            chart_branches=["Mao", "Zi"],
            month_branch="Mao",
        )
        assert isinstance(result, CombinationWeakeningResult)
        assert result.weakened_strength == 1.0
        assert result.weakening_factor == 1.0
        assert result.reasons == []
        assert_key_format_convention(result)

    def test_hidden_stem_weakening(self) -> None:
        """Test hidden stem weakening factor when residual hidden stem exists."""
        # Chen contains Gui (Water) with weight 1 (< 2)
        result = calculate_combination_weakening(
            combo_element="Water",
            chart_branches=["Shen", "Chen"],
            month_branch="Zi",
        )
        assert "hidden stem weakening" in result.reasons
        assert result.weakened_strength < 1.0
        assert_key_format_convention(result)

    def test_control_weakening(self) -> None:
        """Test control weakening factor when controlling element is hidden."""
        # Water element target controls Fire (CONTROL[Water] = Fire). Si branch contains Bing (Fire).
        result = calculate_combination_weakening(
            combo_element="Water",
            chart_branches=["Zi", "Si"],
            month_branch="Zi",
        )
        assert "control weakening" in result.reasons
        assert result.weakened_strength == 0.5
        assert_key_format_convention(result)

    def test_seasonal_weakening(self) -> None:
        """Test seasonal weakening when combination element is in Si or Qiu phase."""
        # Wood in Shen (Autumn/Metal month) is in Si phase
        result = calculate_combination_weakening(
            combo_element="Wood",
            chart_branches=["Mao", "Zi"],
            month_branch="Shen",
        )
        assert "seasonal weakening" in result.reasons
        assert result.weakened_strength < 1.0
        assert_key_format_convention(result)

    def test_multiple_weakening_factors_combined(self) -> None:
        """Test combined effect of multiple weakening factors."""
        # Water in Chen (hidden Gui weight 1 -> f1=0.7), Si (hidden Bing Fire -> f2=0.5), Wu month (Fire month -> f3=0.7)
        result = calculate_combination_weakening(
            combo_element="Water",
            chart_branches=["Chen", "Si"],
            month_branch="Wu",
        )
        assert len(result.reasons) == 3
        assert "hidden stem weakening" in result.reasons
        assert "control weakening" in result.reasons
        assert "seasonal weakening" in result.reasons
        assert pytest.approx(result.weakened_strength, abs=1e-3) == 0.245
        assert_key_format_convention(result)


def test_english_capitalcase_format_assertions(
    assert_key_format_convention: Any,
) -> None:
    """Verify that all inputs and outputs satisfy English CapitalCase conventions."""
    stems = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
    branches = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
    elements = ["Wood", "Fire", "Earth", "Metal", "Water"]

    for item in stems + branches + elements:
        assert_key_format_convention(item)
