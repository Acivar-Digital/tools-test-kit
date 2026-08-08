"""TEST/math/test_ch06_harm_punishment.py — Bazi Chapter 06 Harm & Punishment Math Tests.

Validates:
1. 6 Six Harms (六害) pairs, severities (4–6), and semantic damage types.
2. 4 Xing (刑) punishment types (Ungrateful, Power, Uncivilized, Self-Punish) & severities.
3. Self-punishment 0.5 hidden stem multiplier.
4. Population of self_punished_branches field.
5. Seasonal combination suppression factor (0.3 for Si/Qiu months).
6. Accumulated damage calculation and stealth damage thresholds.
7. Strict English CapitalCase key/value conventions (no Chinese characters).
"""

import pytest

from src2.core.schemas.unified import DamageInputItem, PillarMap
from src2.engine.classical_rules import (
    get_hai,
    get_hai_damage_type,
    get_hai_severity,
    get_xing_branches,
    get_xing_severity,
)
from src2.engine.module3_interaction import (
    _check_seasonal_weakening,
    _check_single_self_punished,
    calculate_interactions,
    get_seasonal_combination_suppression,
    populate_self_punished_branches,
)
from src2.engine.stealth_damage import calculate_accumulated_damage, get_time_factor
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. SIX HARM (六害) PAIRS & SEVERITIES
# ============================================================================

@pytest.mark.parametrize(
    "b1, b2, expected_severity, expected_damage_type",
    [
        ("Zi", "Wei", 6, "po_ku"),
        ("Chou", "Wu", 5, "sun_qi"),
        ("Yin", "Si", 6, "jie_cai"),
        ("Mao", "Chen", 4, "bian_tai"),
        ("Shen", "Hai", 5, "po_yun"),
        ("You", "Xu", 5, "shang_zi"),
    ],
)
def test_six_hai_pairs_and_severities(
    b1: str,
    b2: str,
    expected_severity: int,
    expected_damage_type: str,
) -> None:
    """Validate all 6 Harm pairs, bidirectionality, severities, and damage types."""
    # Check get_hai bidirectionality
    assert get_hai(b1) == b2
    assert get_hai(b2) == b1

    # Check severity
    branches_set = frozenset({b1, b2})
    sev = get_hai_severity(branches_set)
    assert sev == expected_severity

    # Check damage type
    damage_type = get_hai_damage_type(branches_set)
    assert damage_type == expected_damage_type

    # Key format check
    assert_key_format_convention(b1)
    assert_key_format_convention(b2)


def test_hai_interaction_calculation() -> None:
    """Verify calculate_interactions detects Hai interaction with correct potency and severity."""
    stems = PillarMap(year="Jia", month="Bing", day="Wu", hour="Ren")
    branches = PillarMap(year="Zi", month="Wei", day="Chou", hour="Shen")

    res = calculate_interactions(stems=stems, branches=branches)
    hai_items = [i for i in res.all_interactions if i.vector == "Hai"]
    assert len(hai_items) >= 1

    hai = hai_items[0]
    assert set(hai.actors) == {"Zi", "Wei"}
    assert hai.potency == 1.0  # Adjacent Year-Month
    assert_key_format_convention(res)


# ============================================================================
# 2. FOUR XING (刑) PUNISHMENT TYPES & SEVERITIES
# ============================================================================

@pytest.mark.parametrize(
    "xing_type, expected_branches, expected_severity",
    [
        ("ungrateful", frozenset({"Yin", "Si", "Shen"}), 6.0),
        ("power", frozenset({"Chou", "Wei", "Xu"}), 7.0),
        ("uncivilized", frozenset({"Zi", "Mao"}), 7.0),
        ("self_punish", frozenset({"Chen", "Wu", "You", "Hai"}), 8.0),
        ("self", frozenset({"Chen", "Wu", "You", "Hai"}), 8.0),
    ],
)
def test_four_xing_types_and_severities(
    xing_type: str,
    expected_branches: frozenset[str],
    expected_severity: float,
) -> None:
    """Validate Xing branch sets and severity values for all 4 Xing types."""
    branches = get_xing_branches(xing_type)
    assert branches == expected_branches

    sev = get_xing_severity(xing_type)
    assert sev == expected_severity

    assert_key_format_convention(xing_type)
    assert_key_format_convention(list(expected_branches))


def test_xing_interaction_calculation() -> None:
    """Verify calculate_interactions detects Xing interactions for different Xing types."""
    # Zi-Mao Uncivilized Xing
    stems = PillarMap(year="Jia", month="Bing", day="Wu", hour="Ren")
    branches_uncivilized = PillarMap(year="Zi", month="Mao", day="Chen", hour="Shen")
    res_uncivilized = calculate_interactions(stems=stems, branches=branches_uncivilized)

    xing_items = [i for i in res_uncivilized.all_interactions if i.vector == "Xing"]
    assert len(xing_items) >= 1
    assert set(xing_items[0].actors) == {"Zi", "Mao"}

    # Wu-Wu Self-Punishment
    branches_self = PillarMap(year="Wu", month="Wu", day="Chen", hour="Shen")
    res_self = calculate_interactions(stems=stems, branches=branches_self)

    self_items = [i for i in res_self.all_interactions if i.vector == "SelfPunish"]
    assert len(self_items) >= 1
    assert set(self_items[0].actors) == {"Wu"}


# ============================================================================
# 3. SELF-PUNISHMENT 0.5 HIDDEN STEM MULTIPLIER
# ============================================================================

def test_single_self_punished_branch() -> None:
    """Verify _check_single_self_punished applies 0.5 penalty multiplier to self-punishing branches."""
    self_punished_list = ["Chen", "Wu", "You", "Hai"]
    for b in self_punished_list:
        res = _check_single_self_punished(b)
        assert res is not None
        assert res.branch == b
        assert res.penalty_applied == 0.5
        assert len(res.hidden_stem_affected) > 0
        assert_key_format_convention(res)

    # Non-self-punished branch returns None
    assert _check_single_self_punished("Zi") is None
    assert _check_single_self_punished("Yin") is None


# ============================================================================
# 4. POPULATION OF SELF_PUNISHED_BRANCHES FIELD
# ============================================================================

def test_populate_self_punished_branches_field() -> None:
    """Verify populate_self_punished_branches populates list of self-punished branches."""
    chart_branches = ["Chen", "Chen", "Wu", "Zi"]
    res = populate_self_punished_branches(chart_branches)

    assert len(res.branches) == 3  # Chen, Chen, Wu
    branch_names = [b.branch for b in res.branches]
    assert branch_names == ["Chen", "Chen", "Wu"]
    assert res.total_penalty == 0.5

    assert_key_format_convention(res)

    # Chart with no self-punished branches
    res_empty = populate_self_punished_branches(["Zi", "Yin", "Mao", "Shen"])
    assert len(res_empty.branches) == 0
    assert res_empty.total_penalty == 0.0


# ============================================================================
# 5. SEASONAL SUPPRESSION FACTOR (0.3 FOR SI/QIU)
# ============================================================================

def test_seasonal_combination_suppression() -> None:
    """Verify get_seasonal_combination_suppression returns 0.3 for Si/Wu month branches."""
    res_si = get_seasonal_combination_suppression("Si")
    assert res_si.suppression_factor == 0.3
    assert res_si.active is True

    res_wu = get_seasonal_combination_suppression("Wu")
    assert res_wu.suppression_factor == 0.3
    assert res_wu.active is True

    res_zi = get_seasonal_combination_suppression("Zi")
    assert res_zi.suppression_factor == 1.0
    assert res_zi.active is False

    assert_key_format_convention(res_si)


def test_seasonal_weakening_check() -> None:
    """Verify _check_seasonal_weakening applies 0.7 for elements in Si/Qiu seasonal phase."""
    # Wood element in Shen month (Autumn) has phase Si (Dead) -> 0.7 weakening factor
    weakening_wood_shen = _check_seasonal_weakening("Wood", "Shen")
    assert weakening_wood_shen == 0.7

    # Wood element in Chen month (Late Spring/Earth) has phase Qiu (Imprisoned) -> 0.7 weakening factor
    weakening_wood_chen = _check_seasonal_weakening("Wood", "Chen")
    assert weakening_wood_chen == 0.7

    # Fire element in Wu month has phase Wang -> 1.0 (no weakening)
    weakening_fire_wu = _check_seasonal_weakening("Fire", "Wu")
    assert weakening_fire_wu == 1.0


# ============================================================================
# 6. ACCUMULATED DAMAGE CALCULATION & STEALTH DAMAGE
# ============================================================================

def test_accumulated_damage_calculation() -> None:
    """Verify calculate_accumulated_damage computes total damage and matches thresholds."""
    # Time factors: annual=1.0, monthly=2.0, daily=3.0, hourly=3.0
    assert get_time_factor("annual") == 1.0
    assert get_time_factor("monthly") == 2.0
    assert get_time_factor("daily") == 3.0
    assert get_time_factor("hourly") == 3.0
    assert get_time_factor("invalid") == 1.0

    harms = [DamageInputItem(source="Zi-Wei Harm", severity=6.0)]
    punishments = [DamageInputItem(source="Chen Self-Punish", severity=8.0)]
    clashes = [DamageInputItem(source="Zi-Wu Clash", severity=10.0)]

    # Annual time scope: factor 1.0 => total = 6 + 8 + 10 = 24.0 (structural)
    res_annual = calculate_accumulated_damage(
        harms=harms,
        punishments=punishments,
        clashes=clashes,
        time_scope="annual",
    )
    assert res_annual.total_damage == 24.0
    assert res_annual.threshold == "structural"

    # Monthly time scope: factor 2.0 for single harm (severity 6) => 12.0 (chronic)
    res_monthly = calculate_accumulated_damage(
        harms=harms,
        time_scope="monthly",
    )
    assert res_monthly.total_damage == 12.0
    assert res_monthly.threshold == "chronic"

    # Annual single harm (severity 6) => 6.0 (manageable)
    res_manageable = calculate_accumulated_damage(
        harms=harms,
        time_scope="annual",
    )
    assert res_manageable.total_damage == 6.0
    assert res_manageable.threshold == "manageable"

    assert_key_format_convention(res_annual)
