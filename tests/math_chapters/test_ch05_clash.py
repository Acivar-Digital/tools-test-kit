"""TEST/math/test_ch05_clash.py — Chapter 05 Clash Mechanics Math Tests.

Validates:
1. 6 Earthly Branch Chong (冲) base severities (Zi-Wu=10, Mao-You=9, Yin-Shen=12, Si-Hai=8, Chen-Xu=6, Chou-Wei=6).
2. Monthly Qi multiplier calculation based on month branch and elemental phase.
3. Day Master (DM) strength modifier (>=4.0 -> 0.5, <=2.0 -> 2.0, neutral -> 1.0).
4. Mediation factors (San He=0.3, Liu He/San Hui=0.5, Ban He=0.6, Control=0.7, None=1.0).
5. Complete integrated clash severity formula (Base * MonthlyQi * DM * Mediation).
6. Severity level interpretation thresholds.
7. Strict adherence to English CapitalCase formatting conventions.
"""

import pytest

from src2.engine.classical_rules import get_chong, get_chong_base_severity
from src2.engine.module3_interaction import (
    calculate_clash_integrated_severity,
    get_clash_dm_strength_modifier,
    get_clash_mediation_factor,
    get_clash_monthly_qi,
    get_clash_severity_interpretation,
)
from TEST.math.conftest import assert_key_format_convention


class TestChongBaseSeverities:
    """Test 6 Chong (Clash) base severities and clash branch pairs."""

    @pytest.mark.parametrize(
        ("b1", "b2", "expected_severity"),
        [
            ("Yin", "Shen", 12),
            ("Zi", "Wu", 10),
            ("Mao", "You", 9),
            ("Si", "Hai", 8),
            ("Chen", "Xu", 6),
            ("Chou", "Wei", 6),
        ],
    )
    def test_chong_base_severities(self, b1: str, b2: str, expected_severity: int) -> None:
        """Verify exact base severity scores for all six Chong pairs."""
        sev1 = get_chong_base_severity(frozenset({b1, b2}))
        sev2 = get_chong_base_severity(frozenset({b2, b1}))
        assert sev1 == expected_severity
        assert sev2 == expected_severity
        assert get_chong(b1) == b2
        assert get_chong(b2) == b1

    def test_non_clash_pair_returns_none(self) -> None:
        """Verify non-clash branch pairs return None for base severity."""
        assert get_chong_base_severity(frozenset({"Zi", "Chou"})) is None
        assert get_chong("Zi") != "Chou"


class TestMonthlyQiMultiplier:
    """Test Monthly Qi multiplier calculation based on seasonal energy and month branch."""

    def test_clash_branch_is_month_branch(self) -> None:
        """Direct month activation multiplies by 1.5."""
        assert get_clash_monthly_qi("Zi", "Wu", "Zi") == 1.5
        assert get_clash_monthly_qi("Zi", "Wu", "Wu") == 1.5

    def test_seasonal_phases(self) -> None:
        """Verify Wang, Xiang, Xiu, Qiu, and Si phase multipliers."""
        # Zi (Water) in You (Metal month -> Xiang phase = 1.2)
        assert get_clash_monthly_qi("Zi", "Wu", "You") == 1.2
        # Zi (Water) in Mao (Wood month -> Xiu phase = 1.0)
        assert get_clash_monthly_qi("Zi", "Wu", "Mao") == 1.0
        # Zi (Water) in Chou (Earth month -> Si phase = 0.5)
        assert get_clash_monthly_qi("Zi", "Wu", "Chou") == 0.5

    def test_no_month_branch_defaults_to_one(self) -> None:
        """When month branch is None, multiplier defaults to 1.0."""
        assert get_clash_monthly_qi("Zi", "Wu", None) == 1.0


class TestDMStrengthModifier:
    """Test Day Master strength modifier for clash severity."""

    def test_strong_dm_resists_clash(self) -> None:
        """DM score >= 4.0 receives 0.5 modifier."""
        assert get_clash_dm_strength_modifier(4.0) == 0.5
        assert get_clash_dm_strength_modifier(5.5) == 0.5

    def test_weak_dm_amplifies_clash(self) -> None:
        """DM score <= 2.0 receives 2.0 modifier."""
        assert get_clash_dm_strength_modifier(2.0) == 2.0
        assert get_clash_dm_strength_modifier(1.0) == 2.0

    def test_neutral_dm_default_modifier(self) -> None:
        """DM score between 2.0 and 4.0 receives 1.0 modifier."""
        assert get_clash_dm_strength_modifier(3.0) == 1.0
        assert get_clash_dm_strength_modifier(2.5) == 1.0


class TestMediationFactors:
    """Test mediation factor reductions (San He=0.3, Liu He=0.5, Ban He=0.6, Control=0.7, None=1.0)."""

    def test_san_he_mediation(self) -> None:
        """San He alliance reduces clash severity to 0.3."""
        natal_alliances = [{"type": "San He"}]
        med = get_clash_mediation_factor("Zi", "Wu", natal_alliances=natal_alliances, i=0)
        assert med == 0.3

    def test_liu_he_mediation(self) -> None:
        """Liu He alliance reduces clash severity to 0.5."""
        natal_alliances = [{"type": "Liu He"}]
        med = get_clash_mediation_factor("Zi", "Wu", natal_alliances=natal_alliances, i=0)
        assert med == 0.5

    def test_unstable_si_shen_liu_he_mediation(self) -> None:
        """Unstable Si-Shen Liu He alliance returns weaker 0.6 mediation."""
        natal_alliances = [
            {"type": "Liu He", "branches": {"Si", "Shen"}, "stability": {"stable": False}}
        ]
        med = get_clash_mediation_factor("Zi", "Wu", natal_alliances=natal_alliances, i=0)
        assert med == 0.6

    def test_ban_he_mediation(self) -> None:
        """Ban He alliance reduces clash severity to 0.6."""
        natal_alliances = [{"type": "Ban He"}]
        med = get_clash_mediation_factor("Zi", "Wu", natal_alliances=natal_alliances, i=0)
        assert med == 0.6

    def test_control_mediation(self) -> None:
        """Third branch controlling a clash element reduces clash severity to 0.7."""
        # Zi (Water) vs Wu (Fire). Chou (Earth controls Water) in chart branches.
        chart_branches = ["Zi", "Wu", "Chou"]
        med = get_clash_mediation_factor("Zi", "Wu", chart_branches=chart_branches)
        assert med == 0.7

    def test_no_mediation(self) -> None:
        """No alliances or controlling branches results in 1.0 mediation."""
        med = get_clash_mediation_factor("Zi", "Wu")
        assert med == 1.0


class TestIntegratedSeverityFormula:
    """Test integrated clash severity calculation (Base * MonthlyQi * DM * Mediation)."""

    def test_zi_wu_clash_baseline(self) -> None:
        """Zi-Wu (10) in neutral month (1.0) with neutral DM (1.0) and no mediation (1.0) = 10.0."""
        sev = calculate_clash_integrated_severity(
            b1="Zi",
            b2="Wu",
            month_branch="Mao",
            dm_tier1_score=3.0,
        )
        assert sev == 10.0

    def test_yin_shen_clash_amplified(self) -> None:
        """Yin-Shen (12) in Yin month (1.5) with weak DM (2.0) and no mediation (1.0) = 36.0."""
        sev = calculate_clash_integrated_severity(
            b1="Yin",
            b2="Shen",
            month_branch="Yin",
            dm_tier1_score=1.5,
        )
        assert sev == 36.0

    def test_chou_wei_clash_mediated(self) -> None:
        """Chou-Wei (6) in neutral month (1.0) with strong DM (0.5) and San He mediation (0.3) = 0.9."""
        natal_alliances = [{"type": "San He"}]
        sev = calculate_clash_integrated_severity(
            b1="Chou",
            b2="Wei",
            month_branch="Shen",
            dm_tier1_score=4.5,
            natal_alliances=natal_alliances,
            i=0,
        )
        assert sev == 0.9


class TestSeverityInterpretation:
    """Test severity thresholds mapping to qualitative labels."""

    @pytest.mark.parametrize(
        ("severity", "expected_label"),
        [
            (20.0, "Severe"),
            (15.0, "Severe"),
            (14.0, "Significant"),
            (10.0, "Significant"),
            (7.5, "Moderate"),
            (5.0, "Moderate"),
            (4.9, "Minor"),
            (1.0, "Minor"),
        ],
    )
    def test_severity_interpretation_bands(self, severity: float, expected_label: str) -> None:
        """Verify severity score is mapped to correct qualitative label."""
        label = get_clash_severity_interpretation(severity)
        assert label == expected_label
        assert_key_format_convention(label)
