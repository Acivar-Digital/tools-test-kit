"""TEST/math/test_ch09_tai_sui.py — Chapter 09 Tai Sui Interaction Pipeline Tests.

Validates the 6 Tai Sui checks (zhi, chong, xing, po, hai, he), Useful/Taboo Shen filtering,
luck harmony multiplier, combined Tai Sui effect calculation, and trigger conversions.
Strictly enforces English CapitalCase formatting for stems, branches, and elements.
"""

import pytest

from src2.core.schemas.unified import (
    LuckHarmonyEntry,
    TaiSuiConditionCheck,
    TaiSuiTrigger,
)
from src2.engine.module1_macro import (
    _compute_tai_sui_section,
    _convert_conditions_to_triggers,
    _filter_tai_sui_by_shen,
    calculate_combined_effect,
    check_chong_tai_sui,
    check_hai_tai_sui,
    check_he_tai_sui,
    check_po_tai_sui,
    check_xing_tai_sui,
    check_zhi_tai_sui,
    get_luck_harmony_multiplier,
    get_tai_sui_luck_multiplier,
)
from TEST.math.conftest import EARTHLY_BRANCHES_TUPLE, assert_key_format_convention

# ============================================================================
# 1. SIX TAI SUI CONDITION CHECKS
# ============================================================================

class TestSixTaiSuiChecks:
    """Tests for the 6 core Tai Sui branch interaction checks."""

    @pytest.mark.parametrize("branch", EARTHLY_BRANCHES_TUPLE)
    def test_check_zhi_tai_sui_positive(self, branch: str) -> None:
        """Assert Zhi Tai Sui (Self-Encounter) triggers when annual branch equals birth year branch."""
        result = check_zhi_tai_sui(branch, branch)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "zhi_tai_sui"
        assert result.annual_branch == branch
        assert result.birth_year_branch == branch
        assert result.detected is True
        assert result.severity == 1.0
        assert_key_format_convention(result)

    def test_check_zhi_tai_sui_negative(self) -> None:
        """Assert Zhi Tai Sui does not trigger when annual branch differs from birth year branch."""
        result = check_zhi_tai_sui("Zi", "Wu")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            ("Zi", "Wu"),
            ("Wu", "Zi"),
            ("Chou", "Wei"),
            ("Wei", "Chou"),
            ("Yin", "Shen"),
            ("Shen", "Yin"),
            ("Mao", "You"),
            ("You", "Mao"),
            ("Chen", "Xu"),
            ("Xu", "Chen"),
            ("Si", "Hai"),
            ("Hai", "Si"),
        ],
    )
    def test_check_chong_tai_sui_positive(self, annual: str, birth: str) -> None:
        """Assert Chong Tai Sui (Clash) triggers for all 6 direct clash branch pairs."""
        result = check_chong_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "chong_tai_sui"
        assert result.detected is True
        assert result.severity == 0.8
        assert_key_format_convention(result)

    def test_check_chong_tai_sui_negative(self) -> None:
        """Assert Chong Tai Sui does not trigger for non-clash branch pairs."""
        result = check_chong_tai_sui("Zi", "Zi")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            # Ungrateful punishment (Yin-Si-Shen)
            ("Si", "Yin"),
            ("Shen", "Si"),
            ("Yin", "Shen"),
            # Power punishment (Chou-Xu-Wei)
            ("Xu", "Chou"),
            ("Wei", "Xu"),
            ("Chou", "Wei"),
            # Uncivilized punishment (Zi-Mao)
            ("Mao", "Zi"),
            ("Zi", "Mao"),
            # Self punishment (Chen, Wu, You, Hai)
            ("Chen", "Chen"),
            ("Wu", "Wu"),
            ("You", "You"),
            ("Hai", "Hai"),
        ],
    )
    def test_check_xing_tai_sui_positive(self, annual: str, birth: str) -> None:
        """Assert Xing Tai Sui (Punishment) triggers across all 4 punishment types."""
        result = check_xing_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "xing_tai_sui"
        assert result.detected is True
        assert result.severity == 0.5
        assert_key_format_convention(result)

    def test_check_xing_tai_sui_negative(self) -> None:
        """Assert Xing Tai Sui does not trigger for non-punishment branch pairs."""
        result = check_xing_tai_sui("Yin", "Zi")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            ("You", "Zi"),
            ("Zi", "You"),
            ("Wu", "Mao"),
            ("Mao", "Wu"),
            ("Shen", "Si"),
            ("Si", "Shen"),
            ("Hai", "Yin"),
            ("Yin", "Hai"),
            ("Chen", "Chou"),
            ("Chou", "Chen"),
        ],
    )
    def test_check_po_tai_sui_positive(self, annual: str, birth: str) -> None:
        """Assert Po Tai Sui (Break) triggers for break branch pairs."""
        result = check_po_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "po_tai_sui"
        assert result.detected is True
        assert result.severity == 0.3
        assert_key_format_convention(result)

    def test_check_po_tai_sui_negative(self) -> None:
        """Assert Po Tai Sui does not trigger for non-break branch pairs."""
        result = check_po_tai_sui("Zi", "Zi")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            ("Wei", "Zi"),
            ("Zi", "Wei"),
            ("Wu", "Chou"),
            ("Chou", "Wu"),
            ("Si", "Yin"),
            ("Yin", "Si"),
            ("Chen", "Mao"),
            ("Mao", "Chen"),
            ("Hai", "Shen"),
            ("Shen", "Hai"),
            ("Xu", "You"),
            ("You", "Xu"),
        ],
    )
    def test_check_hai_tai_sui_positive(self, annual: str, birth: str) -> None:
        """Assert Hai Tai Sui (Harm) triggers for all 6 harm branch pairs."""
        result = check_hai_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "hai_tai_sui"
        assert result.detected is True
        assert result.severity == 0.4
        assert_key_format_convention(result)

    def test_check_hai_tai_sui_negative(self) -> None:
        """Assert Hai Tai Sui does not trigger for non-harm branch pairs."""
        result = check_hai_tai_sui("Zi", "Zi")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            ("Chou", "Zi"),
            ("Zi", "Chou"),
            ("Hai", "Yin"),
            ("Yin", "Hai"),
            ("Xu", "Mao"),
            ("Mao", "Xu"),
            ("You", "Chen"),
            ("Chen", "You"),
            ("Shen", "Si"),
            ("Si", "Shen"),
            ("Wei", "Wu"),
            ("Wu", "Wei"),
        ],
    )
    def test_check_he_tai_sui_liu_he(self, annual: str, birth: str) -> None:
        """Assert He Tai Sui returns severity 0.6 for Liu He (Six Combination) pairs."""
        result = check_he_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "he_tai_sui"
        assert result.detected is True
        assert result.severity == 0.6
        assert_key_format_convention(result)

    @pytest.mark.parametrize(
        ("annual", "birth"),
        [
            ("Chen", "Zi"),  # Shen-Zi-Chen (Water)
            ("Wei", "Mao"),  # Hai-Mao-Wei (Wood)
            ("Xu", "Wu"),    # Yin-Wu-Xu (Fire)
            ("You", "Si"),   # Si-You-Chou (Metal)
        ],
    )
    def test_check_he_tai_sui_san_he(self, annual: str, birth: str) -> None:
        """Assert He Tai Sui returns severity 0.4 for San He (Three Harmony) non-Liu He pairs."""
        result = check_he_tai_sui(annual, birth)
        assert isinstance(result, TaiSuiConditionCheck)
        assert result.condition == "he_tai_sui"
        assert result.detected is True
        assert result.severity == 0.4
        assert_key_format_convention(result)

    def test_check_he_tai_sui_negative(self) -> None:
        """Assert He Tai Sui does not trigger for non-combination branch pairs."""
        result = check_he_tai_sui("Zi", "Wu")
        assert result.detected is False
        assert result.severity == 0.0
        assert_key_format_convention(result)


# ============================================================================
# 2. SHEN FILTER TESTS
# ============================================================================

class TestFilterTaiSuiByShen:
    """Tests for _filter_tai_sui_by_shen()."""

    def test_filter_yong_shen(self) -> None:
        """Assert Yong Shen (Useful God) element returns 1.0 multiplier."""
        multiplier = _filter_tai_sui_by_shen("Zi", yong_shen_elements=["Water"], ji_xiong=[])
        assert multiplier == 1.0

    def test_filter_ji_xiong_taboo(self) -> None:
        """Assert Ji Xiong (Taboo/Hated) element returns 2.0 multiplier."""
        multiplier = _filter_tai_sui_by_shen("Zi", yong_shen_elements=[], ji_xiong=["Water"])
        assert multiplier == 2.0

    def test_filter_neutral_element(self) -> None:
        """Assert Xian Shen (Neutral bystander) element returns 0.5 multiplier."""
        multiplier = _filter_tai_sui_by_shen("Zi", yong_shen_elements=["Fire"], ji_xiong=["Metal"])
        assert multiplier == 0.5

    def test_filter_yong_shen_precedence(self) -> None:
        """Assert Yong Shen takes precedence over Ji Xiong if present in both lists."""
        multiplier = _filter_tai_sui_by_shen("Zi", yong_shen_elements=["Water"], ji_xiong=["Water"])
        assert multiplier == 1.0


# ============================================================================
# 3. LUCK HARMONY MULTIPLIER TESTS
# ============================================================================

class TestLuckHarmonyMultiplier:
    """Tests for get_luck_harmony_multiplier() and get_tai_sui_luck_multiplier()."""

    def test_clash_multiplier(self) -> None:
        """Assert direct clash between annual branch and birth year branch yields 0.7 multiplier."""
        result = get_luck_harmony_multiplier("Wu", "Zi")
        assert isinstance(result, LuckHarmonyEntry)
        assert result.multiplier == 0.7
        assert result.reason == "clash"
        assert_key_format_convention(result)

    def test_harmony_multiplier(self) -> None:
        """Assert Liu He harmony between annual branch and birth year branch yields 1.5 multiplier."""
        result = get_luck_harmony_multiplier("Chou", "Zi")
        assert isinstance(result, LuckHarmonyEntry)
        assert result.multiplier == 1.5
        assert result.reason == "harmony"
        assert_key_format_convention(result)

    def test_same_element_multiplier(self) -> None:
        """Assert same element branches without clash/harmony yield 1.2 multiplier."""
        result = get_luck_harmony_multiplier("Hai", "Zi")  # Both Water, not clash or Liu He
        assert isinstance(result, LuckHarmonyEntry)
        assert result.multiplier == 1.2
        assert result.reason == "same element"
        assert_key_format_convention(result)

    def test_different_element_multiplier(self) -> None:
        """Assert different element branches without clash/harmony yield 2.0 multiplier."""
        result = get_luck_harmony_multiplier("Yin", "Zi")  # Wood vs Water
        assert isinstance(result, LuckHarmonyEntry)
        assert result.multiplier == 2.0
        assert result.reason == "different elements"
        assert_key_format_convention(result)

    def test_tai_sui_luck_multiplier_alias(self) -> None:
        """Assert get_tai_sui_luck_multiplier is an alias that produces identical output."""
        res_alias = get_tai_sui_luck_multiplier("Wu", "Zi")
        res_orig = get_luck_harmony_multiplier("Wu", "Zi")
        assert res_alias.multiplier == res_orig.multiplier
        assert res_alias.reason == res_orig.reason
        assert res_alias.annual_branch == res_orig.annual_branch
        assert res_alias.birth_year_branch == res_orig.birth_year_branch


# ============================================================================
# 4. COMBINED TAI SUI EFFECT FORMULA TESTS
# ============================================================================

class TestCombinedTaiSuiEffect:
    """Tests for calculate_combined_effect() and _compute_tai_sui_section()."""

    def test_calculate_combined_effect_single_detected(self) -> None:
        """Assert combined effect equals severity sum * seasonal_multiplier * shen_filter."""
        conditions = [
            TaiSuiConditionCheck(
                condition="zhi_tai_sui",
                annual_branch="Zi",
                birth_year_branch="Zi",
                detected=True,
                severity=1.0,
            ),
            TaiSuiConditionCheck(
                condition="chong_tai_sui",
                annual_branch="Zi",
                birth_year_branch="Zi",
                detected=False,
                severity=0.0,
            ),
        ]
        # Total severity = 1.0. Seasonal = 1.5, Shen = 1.0 -> 1.5
        effect = calculate_combined_effect(conditions, seasonal_multiplier=1.5, shen_filter=1.0)
        assert pytest.approx(effect, 0.001) == 1.5

    def test_calculate_combined_effect_multiple_detected(self) -> None:
        """Assert combined effect sums all detected condition severities."""
        conditions = [
            TaiSuiConditionCheck(
                condition="zhi_tai_sui",
                annual_branch="Chen",
                birth_year_branch="Chen",
                detected=True,
                severity=1.0,
            ),
            TaiSuiConditionCheck(
                condition="xing_tai_sui",
                annual_branch="Chen",
                birth_year_branch="Chen",
                detected=True,
                severity=0.5,
            ),
        ]
        # Total severity = 1.5. Seasonal = 1.0, Shen = 2.0 -> 3.0
        effect = calculate_combined_effect(conditions, seasonal_multiplier=1.0, shen_filter=2.0)
        assert pytest.approx(effect, 0.001) == 3.0

    def test_calculate_combined_effect_none_detected(self) -> None:
        """Assert combined effect is 0.0 when no conditions are detected."""
        conditions = [
            TaiSuiConditionCheck(
                condition="chong_tai_sui",
                annual_branch="Zi",
                birth_year_branch="Yin",
                detected=False,
                severity=0.0,
            ),
        ]
        effect = calculate_combined_effect(conditions, seasonal_multiplier=1.5, shen_filter=1.0)
        assert effect == 0.0

    def test_compute_tai_sui_section_pipeline(self) -> None:
        """Assert _compute_tai_sui_section returns calculated impact, 6 checks, and luck multiplier."""
        ann_impact, conditions, luck_mult = _compute_tai_sui_section(
            annual_branch="Zi",
            birth_year_branch="Zi",
            yong_shen_elements=["Water"],
            ji_xiong=["Fire"],
            seasonal_multiplier=1.5,
        )
        assert len(conditions) == 6
        assert isinstance(ann_impact, float)
        assert luck_mult == 1.2  # Zi vs Zi is same element (1.2)
        # Zhi Tai Sui (1.0) + Xing Tai Sui (0.5) = 1.5 severity * 1.5 (seasonal) * 1.0 (yong shen) = 2.25
        assert pytest.approx(ann_impact, 0.001) == 2.25
        assert_key_format_convention(conditions)


# ============================================================================
# 5. TRIGGER CONVERSION TESTS
# ============================================================================

class TestTriggerConversions:
    """Tests for _convert_conditions_to_triggers()."""

    def test_convert_conditions_to_triggers(self) -> None:
        """Assert detected Tai Sui conditions map correctly to TaiSuiTrigger objects."""
        conditions = [
            TaiSuiConditionCheck(
                condition="zhi_tai_sui",
                annual_branch="Zi",
                birth_year_branch="Zi",
                detected=True,
                severity=1.0,
            ),
            TaiSuiConditionCheck(
                condition="chong_tai_sui",
                annual_branch="Zi",
                birth_year_branch="Zi",
                detected=False,
                severity=0.0,
            ),
        ]
        triggers = _convert_conditions_to_triggers(conditions)
        assert len(triggers) == 1
        trigger = triggers[0]
        assert isinstance(trigger, TaiSuiTrigger)
        assert trigger.condition == "zhi_tai_sui"
        assert trigger.type == "Zhi Tai Sui"
        assert trigger.impact == 100
        assert trigger.severity == "1.0"
        assert_key_format_convention(trigger.condition)
