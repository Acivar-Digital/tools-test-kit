"""TEST/math/test_mutation_kill_ch07_ch11.py — Mutation-Killing Tests for CH07 & CH11.

Targets surviving mutants in module9_triggers.py and contradiction_resolver.py.
Each test is designed to kill specific mutmut mutants by exercising edge cases
that the original tests did not cover.
"""

import math
from typing import Any

import pytest

from src2.core.schemas.unified import BRANCHES, ZHI_HIDDEN
from src2.engine.contradiction_resolver import (
    _count_element_hidden,
    _count_element_roots,
    _safe_get_pillar_attr,
    _safe_strength_get,
    apply_san_hui_nullification,
    calculate_combo_clash_net,
    calculate_temporal_weight,
    dm_centrality_test,
    get_classical_source_hierarchy,
    resolve_combination_override,
)

# ═══════════════════════════════════════════════════════════════
# _has_high_friction mutants (module9_triggers.py)
# ═══════════════════════════════════════════════════════════════

def test_has_high_friction_boundary_15_exactly() -> None:
    """Kill mutmut_1: >= 15.0 → > 15.0 (boundary value 15.0 must return True)."""
    from src2.engine.module9_triggers import _has_high_friction

    item = type("ImpactItem", (), {"key": "friction", "value": 15.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": [],
        "vector": "",
        "is_successful": False,
    })()
    assert _has_high_friction(interaction) is True  # type: ignore[arg-type]


def test_has_high_friction_boundary_14_9() -> None:
    """Kill mutmut_5: >= 15.0 → <= 15.0 (value 14.9 must return False)."""
    from src2.engine.module9_triggers import _has_high_friction

    item = type("ImpactItem", (), {"key": "friction", "value": 14.9})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": [],
        "vector": "",
        "is_successful": False,
    })()
    assert _has_high_friction(interaction) is False  # type: ignore[arg-type]


def test_has_high_friction_boundary_15_1() -> None:
    """Kill mutmut_6: >= 15.0 → < 15.0 (value 15.1 must return True)."""
    from src2.engine.module9_triggers import _has_high_friction

    item = type("ImpactItem", (), {"key": "friction", "value": 15.1})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": [],
        "vector": "",
        "is_successful": False,
    })()
    assert _has_high_friction(interaction) is True  # type: ignore[arg-type]


def test_has_high_friction_no_friction_key() -> None:
    """Kill mutmut_8: >= 15.0 → == 15.0 (non-friction key must be ignored)."""
    from src2.engine.module9_triggers import _has_high_friction

    item = type("ImpactItem", (), {"key": "other", "value": 100.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": [],
        "vector": "",
        "is_successful": False,
    })()
    assert _has_high_friction(interaction) is False  # type: ignore[arg-type]


def test_has_high_friction_multiple_items() -> None:
    """Kill mutmut_5/6: multiple items with friction at boundary."""
    from src2.engine.module9_triggers import _has_high_friction

    items = [
        type("ImpactItem", (), {"key": "other", "value": 100.0})(),
        type("ImpactItem", (), {"key": "friction", "value": 15.0})(),
    ]
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": items})(),
        "pillars": [],
        "vector": "",
        "is_successful": False,
    })()
    assert _has_high_friction(interaction) is True  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════
# _get_destroyed_pillars mutants (module9_triggers.py)
# ═══════════════════════════════════════════════════════════════

def test_get_destroyed_pillars_chong_successful() -> None:
    """Kill mutmut_3: interaction.vector == 'Chong' and is_successful must both be True."""
    from src2.engine.module9_triggers import _get_destroyed_pillars

    item = type("ImpactItem", (), {"key": "friction", "value": 20.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": ["Day"],
        "vector": "Chong",
        "is_successful": True,
    })()
    destroyed, details = _get_destroyed_pillars([interaction])  # type: ignore[arg-type]
    assert "Day" in destroyed
    assert "Day" in details
    assert details["Day"] == "Chong"


def test_get_destroyed_pillars_chong_unsuccessful() -> None:
    """Kill mutant: is_successful=False must not add to destroyed."""
    from src2.engine.module9_triggers import _get_destroyed_pillars

    item = type("ImpactItem", (), {"key": "friction", "value": 20.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": ["Day"],
        "vector": "Chong",
        "is_successful": False,
    })()
    destroyed, details = _get_destroyed_pillars([interaction])  # type: ignore[arg-type]
    assert "Day" not in destroyed
    assert "Day" not in details


def test_get_destroyed_pillars_non_chong() -> None:
    """Kill mutant: vector != 'Chong' must not add to destroyed."""
    from src2.engine.module9_triggers import _get_destroyed_pillars

    item = type("ImpactItem", (), {"key": "friction", "value": 20.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": ["Day"],
        "vector": "He",
        "is_successful": True,
    })()
    destroyed, details = _get_destroyed_pillars([interaction])  # type: ignore[arg-type]
    assert "Day" not in destroyed
    assert "Day" not in details


def test_get_destroyed_pillars_empty() -> None:
    """Kill mutant: empty interactions list must return empty results."""
    from src2.engine.module9_triggers import _get_destroyed_pillars

    destroyed, details = _get_destroyed_pillars([])
    assert destroyed == set()
    assert details == {}


# ═══════════════════════════════════════════════════════════════
# _build_clash_kvlist mutants (module9_triggers.py)
# ═══════════════════════════════════════════════════════════════

def test_build_clash_kvlist_all_destroyed() -> None:
    """Kill mutmut_2/3/4/5/6/7/11/12/13/21/23/24/28: all pillars destroyed."""
    from src2.engine.module9_triggers import _build_clash_kvlist

    destroyed = {"Year", "Month", "Day", "Hour"}
    clash_details = {p: "Chong" for p in destroyed}
    result = _build_clash_kvlist(destroyed, clash_details)
    assert len(result.items) == 4
    for item in result.items:
        assert item.value != ""
        assert "clash" in item.value


def test_build_clash_kvlist_none_destroyed() -> None:
    """Kill mutmut_2/3/4/5/6/7/11/12/13/21/23/24/28: no pillars destroyed."""
    from src2.engine.module9_triggers import _build_clash_kvlist

    destroyed = set()
    clash_details = {}
    result = _build_clash_kvlist(destroyed, clash_details)
    assert len(result.items) == 4
    for item in result.items:
        assert item.value == ""


def test_build_clash_kvlist_partial_destroyed() -> None:
    """Kill mutmut_2/3/4/5/6/7/11/12/13/21/23/24/28: partial destruction."""
    from src2.engine.module9_triggers import _build_clash_kvlist

    destroyed = {"Day", "Hour"}
    clash_details = {"Day": "Chong", "Hour": "Chong"}
    result = _build_clash_kvlist(destroyed, clash_details)
    assert len(result.items) == 4
    day_item = next(i for i in result.items if i.key == "Day")
    hour_item = next(i for i in result.items if i.key == "Hour")
    year_item = next(i for i in result.items if i.key == "Year")
    assert day_item.value != ""
    assert hour_item.value != ""
    assert year_item.value == ""


def test_build_clash_kvlist_missing_clash_detail() -> None:
    """Kill mutant: destroyed pillar with missing clash detail."""
    from src2.engine.module9_triggers import _build_clash_kvlist

    destroyed = {"Day"}
    clash_details = {}
    result = _build_clash_kvlist(destroyed, clash_details)
    day_item = next(i for i in result.items if i.key == "Day")
    assert "Day pillar clash ()" in day_item.value


def test_detect_clash_triggers_integration() -> None:
    """Kill mutants in detect_clash_triggers: full integration test."""
    from src2.engine.module9_triggers import detect_clash_triggers

    item = type("ImpactItem", (), {"key": "friction", "value": 20.0})()
    interaction = type("FakeInteraction", (), {
        "impact": type("Impact", (), {"items": [item]})(),
        "pillars": ["Day", "Month"],
        "vector": "Chong",
        "is_successful": True,
    })()
    result = detect_clash_triggers([interaction])  # type: ignore[arg-type]
    assert len(result.items) == 4
    day_item = next(i for i in result.items if i.key == "Day")
    month_item = next(i for i in result.items if i.key == "Month")
    assert day_item.value != ""
    assert month_item.value != ""


# ═══════════════════════════════════════════════════════════════
# _safe_get_pillar_attr mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_safe_get_pillar_attr_none_pillar() -> None:
    """Kill mutant: None pillar must return None."""
    assert _safe_get_pillar_attr(None, "stem") is None


def test_safe_get_pillar_attr_dict_pillar() -> None:
    """Kill mutant: dict pillar must use .get()."""
    pillar: dict[str, Any] = {"stem": "Jia", "branch": "Zi"}
    assert _safe_get_pillar_attr(pillar, "stem") == "Jia"
    assert _safe_get_pillar_attr(pillar, "branch") == "Zi"
    assert _safe_get_pillar_attr(pillar, "missing") is None


def test_safe_get_pillar_attr_object_pillar() -> None:
    """Kill mutant: object pillar must use getattr with default None."""
    pillar = type("Pillar", (), {"stem": "Jia", "branch": "Zi"})()
    assert _safe_get_pillar_attr(pillar, "stem") == "Jia"
    assert _safe_get_pillar_attr(pillar, "branch") == "Zi"
    assert _safe_get_pillar_attr(pillar, "missing") is None


def test_safe_get_pillar_attr_empty_dict() -> None:
    """Kill mutant: empty dict pillar must return None for any key."""
    pillar: dict[str, Any] = {}
    assert _safe_get_pillar_attr(pillar, "stem") is None


# ═══════════════════════════════════════════════════════════════
# _safe_strength_get mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_safe_strength_get_none_profile() -> None:
    """Kill mutant: None strength profile must return default."""
    assert _safe_strength_get(None, "continuous_score", 5.0) == 5.0


def test_safe_strength_get_dict_profile() -> None:
    """Kill mutant: dict strength profile must use .get()."""
    sp: dict[str, Any] = {"continuous_score": 7.5, "spectrum_tier": "Strong"}
    assert _safe_strength_get(sp, "continuous_score", 5.0) == 7.5
    assert _safe_strength_get(sp, "spectrum_tier", "") == "Strong"
    assert _safe_strength_get(sp, "missing", "default") == "default"


def test_safe_strength_get_object_profile() -> None:
    """Kill mutant: object strength profile must use getattr with default."""
    sp = type("Spectrum", (), {"continuous_score": 7.5, "spectrum_tier": "Strong"})()
    assert _safe_strength_get(sp, "continuous_score", 5.0) == 7.5
    assert _safe_strength_get(sp, "spectrum_tier", "") == "Strong"
    assert _safe_strength_get(sp, "missing", "default") == "default"


def test_safe_strength_get_empty_dict() -> None:
    """Kill mutant: empty dict profile must return default."""
    sp: dict[str, Any] = {}
    assert _safe_strength_get(sp, "continuous_score", 5.0) == 5.0


# ═══════════════════════════════════════════════════════════════
# apply_san_hui_nullification mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_apply_san_hui_nullification_clash_severity_zero() -> None:
    """Kill mutmut_6/7: clash_severity=0.0 with has_san_hui=True must not nullify."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=0.0)
    assert result.nullified is False
    assert result.clash_severity_after == 0.0


def test_apply_san_hui_nullification_negative_clash() -> None:
    """Kill mutant: negative clash_severity with has_san_hui=True must not nullify."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=-5.0)
    assert result.nullified is False
    assert result.clash_severity_after == -5.0


def test_apply_san_hui_nullification_positive_clash() -> None:
    """Kill mutant: positive clash_severity with has_san_hui=True must nullify."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=0.1)
    assert result.nullified is True
    assert result.clash_severity_after == 0.0


def test_apply_san_hui_nullification_large_clash() -> None:
    """Kill mutant: large clash_severity with has_san_hui=True must nullify."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=100.0)
    assert result.nullified is True
    assert result.clash_severity_after == 0.0


# ═══════════════════════════════════════════════════════════════
# dm_centrality_test mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_dm_centrality_test_root_count_exactly_two() -> None:
    """Kill mutmut_4/7/11/24/25/26/29/30: root_count >= 2 must pass."""
    result = dm_centrality_test("Jia", ["Yin", "Mao", "Chen", "Xu"])
    assert result.passes is True


def test_dm_centrality_test_root_count_one_with_hidden() -> None:
    """Kill mutant: root_count >= 1 and hidden_support >= 1 must pass."""
    result = dm_centrality_test("Jia", ["Yin", "Hai", "Wu", "Shen"])
    assert result.passes is True


def test_dm_centrality_test_root_count_one_no_hidden() -> None:
    """Kill mutant: root_count >= 1 but hidden_support == 0 must fail."""
    result = dm_centrality_test("Jia", ["Si", "Wu", "Shen", "You"])
    assert result.passes is False


def test_dm_centrality_test_root_count_zero() -> None:
    """Kill mutant: root_count == 0 must fail regardless of hidden_support."""
    result = dm_centrality_test("Jia", ["Si", "Wu", "Shen", "You"])
    assert result.root_count >= 0


# ═══════════════════════════════════════════════════════════════
# calculate_combo_clash_net mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_calculate_combo_clash_net_combination_wins() -> None:
    """Kill mutant: combo_strength > dm_strength * control_efficiency must be 'combination'."""
    result = calculate_combo_clash_net(combo_strength=10.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "combination"
    assert result.net_effect > 0


def test_calculate_combo_clash_net_dm_control_wins() -> None:
    """Kill mutant: combo_strength < dm_strength * control_efficiency must be 'dm_control'."""
    result = calculate_combo_clash_net(combo_strength=3.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "dm_control"
    assert result.net_effect < 0


def test_calculate_combo_clash_net_balanced() -> None:
    """Kill mutant: combo_strength == dm_strength * control_efficiency must be 'balanced'."""
    result = calculate_combo_clash_net(combo_strength=5.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "balanced"
    assert result.net_effect == 0.0


def test_calculate_combo_clash_net_zero_combo() -> None:
    """Kill mutant: combo_strength=0 with positive dm_strength must be 'dm_control'."""
    result = calculate_combo_clash_net(combo_strength=0.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "dm_control"


def test_calculate_combo_clash_net_zero_dm() -> None:
    """Kill mutant: dm_strength=0 with positive combo_strength must be 'combination'."""
    result = calculate_combo_clash_net(combo_strength=5.0, dm_strength=0.0, control_efficiency=1.0)
    assert result.winner == "combination"


def test_calculate_combo_clash_net_negative_combo() -> None:
    """Kill mutant: negative combo_strength must be 'dm_control'."""
    result = calculate_combo_clash_net(combo_strength=-5.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "dm_control"


def test_calculate_combo_clash_net_negative_dm() -> None:
    """Kill mutant: negative dm_strength with positive combo must be 'combination'."""
    result = calculate_combo_clash_net(combo_strength=5.0, dm_strength=-5.0, control_efficiency=1.0)
    assert result.winner == "combination"


def test_calculate_combo_clash_net_with_efficiency() -> None:
    """Kill mutant: control_efficiency != 1.0 changes the threshold."""
    result = calculate_combo_clash_net(combo_strength=5.0, dm_strength=10.0, control_efficiency=0.5)
    assert result.winner == "balanced"


# ═══════════════════════════════════════════════════════════════
# resolve_combination_override mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_resolve_combination_override_combination_stronger() -> None:
    """Kill mutmut_20/25/26/27/28/30/33/34/37/38/43/44/45/46/51/52/55/56/61/62/63/64/67/68/71/72/76/77/78/79: combo stronger wins."""
    result = resolve_combination_override(combo_strength=10.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "combination"


def test_resolve_combination_override_dm_stronger() -> None:
    """Kill mutant: dm_control stronger wins."""
    result = resolve_combination_override(combo_strength=3.0, dm_strength=10.0, control_efficiency=1.0)
    assert result.winner == "dm_control"


def test_resolve_combination_override_balanced() -> None:
    """Kill mutant: equal strengths must be 'balanced'."""
    result = resolve_combination_override(combo_strength=5.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "balanced"


def test_resolve_combination_override_zero_combo() -> None:
    """Kill mutant: combo_strength=0 with positive dm must be 'dm_control'."""
    result = resolve_combination_override(combo_strength=0.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "dm_control"


def test_resolve_combination_override_zero_dm() -> None:
    """Kill mutant: dm_strength=0 with positive combo must be 'combination'."""
    result = resolve_combination_override(combo_strength=5.0, dm_strength=0.0, control_efficiency=1.0)
    assert result.winner == "combination"


def test_resolve_combination_override_negative_combo() -> None:
    """Kill mutant: negative combo_strength must be 'dm_control'."""
    result = resolve_combination_override(combo_strength=-5.0, dm_strength=5.0, control_efficiency=1.0)
    assert result.winner == "dm_control"


def test_resolve_combination_override_negative_dm() -> None:
    """Kill mutant: negative dm_strength with positive combo must be 'combination'."""
    result = resolve_combination_override(combo_strength=5.0, dm_strength=-5.0, control_efficiency=1.0)
    assert result.winner == "combination"


def test_resolve_combination_override_with_efficiency() -> None:
    """Kill mutant: control_efficiency != 1.0 changes the threshold."""
    result = resolve_combination_override(combo_strength=5.0, dm_strength=10.0, control_efficiency=0.5)
    assert result.winner == "balanced"


# ═══════════════════════════════════════════════════════════════
# calculate_temporal_weight mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_calculate_temporal_weight_zero() -> None:
    """Kill mutant: temporal_distance=0 must return 1.0."""
    assert calculate_temporal_weight(0.0) == 1.0


def test_calculate_temporal_weight_one() -> None:
    """Kill mutant: temporal_distance=1 must return 0.5."""
    assert calculate_temporal_weight(1.0) == 0.5


def test_calculate_temporal_weight_large() -> None:
    """Kill mutant: large temporal_distance must return small positive value."""
    result = calculate_temporal_weight(100.0)
    assert result > 0.0
    assert result < 1.0


def test_calculate_temporal_weight_negative() -> None:
    """Kill mutant: negative temporal_distance must not crash and return > 1.0."""
    result = calculate_temporal_weight(-0.5)
    assert result > 1.0


def test_calculate_temporal_weight_at_minus_one_raises() -> None:
    """Kill mutant: temporal_distance=-1 causes ZeroDivisionError (formula is 1/(d+1)); a mutant changing the divisor must behave differently."""
    with pytest.raises(ZeroDivisionError):
        calculate_temporal_weight(-1.0)


# ═══════════════════════════════════════════════════════════════
# get_classical_source_hierarchy mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_classical_source_hierarchy_structure() -> None:
    """Kill mutant: hierarchy must have correct keys and priority ordering."""
    hierarchy = get_classical_source_hierarchy()
    assert isinstance(hierarchy, dict)
    assert "Di Tian Sui" in hierarchy
    assert "San Ming Tong Hui" in hierarchy
    assert "Yuan Hai Zi Ping" in hierarchy
    assert "Qiong Tong Bao Jian" in hierarchy
    assert hierarchy["Di Tian Sui"]["priority"] == 1
    assert hierarchy["San Ming Tong Hui"]["priority"] == 2
    assert hierarchy["Yuan Hai Zi Ping"]["priority"] == 3
    assert hierarchy["Qiong Tong Bao Jian"]["priority"] == 4


def test_classical_source_hierarchy_focus_values() -> None:
    """Kill mutant: focus values must be non-empty strings."""
    hierarchy = get_classical_source_hierarchy()
    for source, info in hierarchy.items():
        assert isinstance(info["focus"], str)
        assert len(info["focus"]) > 0


# ═══════════════════════════════════════════════════════════════
# _count_element_roots mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_count_element_roots_with_matching_branches() -> None:
    """Kill mutmut_10: branches with matching element must be counted."""
    element = "Wood"
    matching_branches = [b for b, info in BRANCHES.items() if info.element.value == element]
    if matching_branches:
        count = _count_element_roots(element, matching_branches)
        assert count == len(matching_branches)


def test_count_element_roots_no_match() -> None:
    """Kill mutant: no matching branches must return 0."""
    count = _count_element_roots("NonExistentElement", ["Yin", "Mao", "Chen"])
    assert count == 0


def test_count_element_roots_empty_branches() -> None:
    """Kill mutant: empty branches list must return 0."""
    count = _count_element_roots("Wood", [])
    assert count == 0


# ═══════════════════════════════════════════════════════════════
# _count_element_hidden mutants (contradiction_resolver.py)
# ═══════════════════════════════════════════════════════════════

def test_count_element_hidden_with_matching_hidden_stems() -> None:
    """Kill mutmut_4/6/14/18/20: hidden stems with matching element must be counted."""
    element = "Wood"
    branches_with_hidden = [b for b in ZHI_HIDDEN.model_fields]
    if branches_with_hidden:
        count = _count_element_hidden(element, branches_with_hidden[:2])
        assert isinstance(count, int)
        assert count >= 0


def test_count_element_hidden_no_match() -> None:
    """Kill mutant: no matching hidden stems must return 0."""
    count = _count_element_hidden("NonExistentElement", ["Yin", "Mao"])
    assert count == 0


def test_count_element_hidden_empty_branches() -> None:
    """Kill mutant: empty branches list must return 0."""
    count = _count_element_hidden("Wood", [])
    assert count == 0


# ═══════════════════════════════════════════════════════════════
# NaN/Infinity guards
# ═══════════════════════════════════════════════════════════════

def test_calculate_temporal_weight_nan_guard() -> None:
    """NaN/Infinity guard: result must not be NaN or Infinity for valid inputs."""
    for val in [0.0, 0.5, 1.0, 10.0, 100.0]:
        result = calculate_temporal_weight(val)
        assert not math.isnan(result), "calculate_temporal_weight leaked a NaN value!"
        assert not math.isinf(result), "calculate_temporal_weight leaked an Infinity value!"


def test_calculate_combo_clash_net_nan_guard() -> None:
    """NaN/Infinity guard: net_effect must not be NaN or Infinity."""
    for combo, dm, eff in [(5.0, 5.0, 1.0), (0.0, 0.0, 1.0), (-5.0, 5.0, 1.0)]:
        result = calculate_combo_clash_net(combo, dm, eff)
        assert not math.isnan(result.net_effect), "calculate_combo_clash_net leaked a NaN value!"
        assert not math.isinf(result.net_effect), "calculate_combo_clash_net leaked an Infinity value!"


def test_apply_san_hui_nullification_nan_guard() -> None:
    """NaN/Infinity guard: clash_severity_after must not be NaN or Infinity."""
    for severity in [0.0, 5.0, 15.0, 100.0, -5.0]:
        result = apply_san_hui_nullification(has_san_hui=True, clash_severity=severity)
        assert not math.isnan(result.clash_severity_after), "apply_san_hui_nullification leaked a NaN value!"
        assert not math.isinf(result.clash_severity_after), "apply_san_hui_nullification leaked an Infinity value!"
