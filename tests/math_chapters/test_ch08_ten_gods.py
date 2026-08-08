"""TEST/math/test_ch08_ten_gods.py — Chapter 08 Ten Gods Dynamic Matrices & Pair Compatibility.

Tests for Chapter 08 math specs:
- get_ten_god_magnitude_multiplier()
- get_seasonal_ten_god_weight()
- calculate_ten_god_dominance()
- check_ten_god_pair_compatibility() (Resource, Wealth, Influence/Officer, Output)
- Additional Ten God triggers and helper functions in module6_ten_gods.py
- Key-format convention enforcement (English CapitalCase only, no Chinese chars).
"""

from typing import Any

from src2.core.schemas import TenGodsInput
from src2.core.schemas.unified import TenGod, TenGodEntry
from src2.engine.module6_ten_gods import (
    calculate_ten_god_dominance,
    calculate_ten_gods,
    check_fill_void_trigger,
    check_san_he_resolution_trigger,
    check_tomb_clash_trigger,
    detect_powerful_ten_god_combos,
    detect_ten_god_absence,
    get_day_hour_ten_god_emphasis,
    get_seasonal_ten_god_weight,
    get_ten_god_magnitude_multiplier,
)
from src2.engine.module12_compatibility import check_ten_god_pair_compatibility


def test_get_ten_god_magnitude_multiplier(assert_key_format_convention: Any) -> None:
    """Test magnitude multiplier output across Dead, Weak, Neutral, Strong, and Excessive tiers."""
    # Dead (<= 0.0) -> 3.0
    res_dead = get_ten_god_magnitude_multiplier(0.0)
    assert res_dead == 3.0
    assert get_ten_god_magnitude_multiplier(-1.0) == 3.0

    # Weak (<= 2.0) -> 2.0
    res_weak = get_ten_god_magnitude_multiplier(1.5)
    assert res_weak == 2.0
    assert get_ten_god_magnitude_multiplier(2.0) == 2.0

    # Neutral (2.0 < score < 4.0) -> 1.0
    res_neutral = get_ten_god_magnitude_multiplier(3.0)
    assert res_neutral == 1.0

    # Strong (>= 4.0 and < 6.0) -> 0.5
    res_strong = get_ten_god_magnitude_multiplier(4.0)
    assert res_strong == 0.5
    assert get_ten_god_magnitude_multiplier(5.5) == 0.5

    # Excessive (>= 6.0) -> 0.3
    res_excessive = get_ten_god_magnitude_multiplier(6.0)
    assert res_excessive == 0.3
    assert get_ten_god_magnitude_multiplier(8.0) == 0.3

    assert_key_format_convention(res_dead)


def test_get_seasonal_ten_god_weight(assert_key_format_convention: Any) -> None:
    """Test seasonal weighting multiplier based on element phase for month branch."""
    # Wood in Yin month (Spring) -> Wang (1.5)
    w_wang = get_seasonal_ten_god_weight("Wood", "Yin")
    assert w_wang == 1.5

    # Fire in Yin month (Spring) -> Xiang (1.2)
    w_xiang = get_seasonal_ten_god_weight("Fire", "Yin")
    assert w_xiang == 1.2

    # Water in Yin month (Spring) -> Xiu (1.0)
    w_xiu = get_seasonal_ten_god_weight("Water", "Yin")
    assert w_xiu == 1.0

    # Metal in Yin month (Spring) -> Qiu (0.8)
    w_qiu = get_seasonal_ten_god_weight("Metal", "Yin")
    assert w_qiu == 0.8

    # Earth in Yin month (Spring) -> Si (0.5)
    w_si = get_seasonal_ten_god_weight("Earth", "Yin")
    assert w_si == 0.5

    assert_key_format_convention("Wood")
    assert_key_format_convention("Yin")


def test_calculate_ten_god_dominance(assert_key_format_convention: Any) -> None:
    """Test Ten God dominance calculation across categories, top score sorting, and balance levels."""
    profile = {
        "year_stem": TenGodEntry(stem="Gui", ten_god=TenGod("Zheng Yin"), score=3),
        "month_stem": TenGodEntry(stem="Ren", ten_god=TenGod("Pian Yin"), score=3),
        "day_stem": TenGodEntry(stem="Jia", ten_god=TenGod("Bi Jian"), score=2),
        "hour_stem": TenGodEntry(stem="Bing", ten_god=TenGod("Shi Shen"), score=1),
    }

    dominance = calculate_ten_god_dominance(profile, month_branch="Yin")
    assert dominance.dominant_category in ("Resource", "Peer", "Output", "Wealth", "Influence")
    assert "Resource" in dominance.category_scores
    assert dominance.balance in ("dominant", "leaning", "balanced", "flat")

    assert_key_format_convention(dominance)

    # Test empty profile returns flat dominance
    empty_dominance = calculate_ten_god_dominance({})
    assert empty_dominance.dominant_category == "None"
    assert empty_dominance.secondary == "None"
    assert empty_dominance.balance == "flat"
    assert_key_format_convention(empty_dominance)


def test_check_ten_god_pair_compatibility(assert_key_format_convention: Any) -> None:
    """Test Ten God pair compatibility for Resource, Wealth, Officer (Influence), and Output pairs."""
    # Resource pairs
    res_res = check_ten_god_pair_compatibility("Resource", "Resource")
    assert res_res.compatibility == "Mutual Support"

    res_wealth = check_ten_god_pair_compatibility("Resource", "Wealth")
    assert res_wealth.compatibility == "Contradiction"

    res_inf = check_ten_god_pair_compatibility("Resource", "Influence")
    assert res_inf.compatibility == "Weakness"

    res_out = check_ten_god_pair_compatibility("Resource", "Output")
    assert res_out.compatibility == "Weakness"

    # Wealth pairs
    wealth_res = check_ten_god_pair_compatibility("Wealth", "Resource")
    assert wealth_res.compatibility == "Contradiction"

    wealth_wealth = check_ten_god_pair_compatibility("Wealth", "Wealth")
    assert wealth_wealth.compatibility == "Mutual Support"

    wealth_inf = check_ten_god_pair_compatibility("Wealth", "Influence")
    assert wealth_inf.compatibility == "Production"

    wealth_out = check_ten_god_pair_compatibility("Wealth", "Output")
    assert wealth_out.compatibility == "Production"

    # Influence / Officer pairs
    inf_res = check_ten_god_pair_compatibility("Influence", "Resource")
    assert inf_res.compatibility == "Production"

    inf_wealth = check_ten_god_pair_compatibility("Influence", "Wealth")
    assert inf_wealth.compatibility == "Contradiction"

    inf_inf = check_ten_god_pair_compatibility("Influence", "Influence")
    assert inf_inf.compatibility == "Mutual Support"

    inf_out = check_ten_god_pair_compatibility("Influence", "Output")
    assert inf_out.compatibility == "Contradiction"

    # Output pairs
    out_res = check_ten_god_pair_compatibility("Output", "Resource")
    assert out_res.compatibility == "Contradiction"

    out_wealth = check_ten_god_pair_compatibility("Output", "Wealth")
    assert out_wealth.compatibility == "Production"

    out_inf = check_ten_god_pair_compatibility("Output", "Influence")
    assert out_inf.compatibility == "Weakness"

    out_out = check_ten_god_pair_compatibility("Output", "Output")
    assert out_out.compatibility == "Mutual Support"

    # Unknown category
    unknown = check_ten_god_pair_compatibility("InvalidCategory", "Resource")
    assert unknown.compatibility == "Unknown"

    assert_key_format_convention(res_res)
    assert_key_format_convention(wealth_inf)
    assert_key_format_convention(inf_res)
    assert_key_format_convention(out_wealth)


def test_ten_god_triggers_and_profile(assert_key_format_convention: Any) -> None:
    """Test Tomb Clash, Fill Void, San He resolution triggers, day/hour emphasis, combos, and absence."""
    # Tomb clash trigger: Wood DM tomb is Wei, clashing branch is Chou
    tomb_res = check_tomb_clash_trigger("Wood", "Chou")
    assert tomb_res.active is True
    assert tomb_res.activation == 0.8
    assert tomb_res.tomb_branch == "Wei"
    assert tomb_res.clashing_branch == "Chou"
    assert_key_format_convention(tomb_res)

    no_tomb_res = check_tomb_clash_trigger("Wood", "Zi")
    assert no_tomb_res.active is False
    assert_key_format_convention(no_tomb_res)

    # Fill void trigger
    void_res = check_fill_void_trigger("Jia", "Xu")
    assert void_res.active is True
    assert void_res.activation == 0.6
    assert_key_format_convention(void_res)

    # San He resolution trigger
    san_he_res = check_san_he_resolution_trigger("Shen", ["Zi", "Chen"])
    assert san_he_res.active is True
    assert san_he_res.activation == 0.7
    assert "San He" in (san_he_res.combination or "")
    assert_key_format_convention(san_he_res)

    # Calculate full Ten Gods Output
    inp = TenGodsInput(
        dm_stem="Jia",
        stems={"year_stem": "Bing", "month_stem": "Gui", "day_stem": "Jia", "hour_stem": "Geng"},
        branches={"year_branch": "Zi", "month_branch": "Yin", "day_branch": "Chen", "hour_branch": "Shen"},
    )
    output = calculate_ten_gods(inp)
    assert output.ten_gods_map["month_stem"] == "Zheng Yin"
    assert output.ten_gods_map["year_stem"] == "Shi Shen"
    assert output.ten_gods_map["hour_stem"] == "Qi Sha"
    assert_key_format_convention(output)

    # Day/Hour emphasis
    emphasis = get_day_hour_ten_god_emphasis(output.ten_gods_profile)
    assert emphasis.day.stem == "Jia"
    assert emphasis.hour.stem == "Geng"
    assert_key_format_convention(emphasis)

    # Powerful combos
    combos = detect_powerful_ten_god_combos(output.ten_gods_profile)
    assert isinstance(combos, list)
    assert_key_format_convention(combos)

    # Absence
    absence = detect_ten_god_absence(output.ten_gods_profile)
    assert isinstance(absence.absent_categories, list)
    assert_key_format_convention(absence)
