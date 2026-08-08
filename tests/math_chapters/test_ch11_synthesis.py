"""TEST/math/test_ch11_synthesis.py — Bazi Chapter 11 Systemic Synthesis & Contradiction Resolution Tests.

Validates:
1. apply_san_hui_nullification() — Nullifies clash severity (to 0.0) when San Hui is present.
2. calculate_combo_clash_net() — Calculates net combo effect and winner classification.
3. resolve_combination_override() — Evaluates combination override vs DM control thresholds.
4. dm_centrality_test() — Evaluates DM root count, hidden support, and centrality pass/fail condition.
5. Strict English CapitalCase key/value conventions (no Chinese characters).
"""

import pytest

from src2.engine.contradiction_resolver import (
    apply_san_hui_nullification,
    calculate_combo_clash_net,
    calculate_temporal_weight,
    dm_centrality_test,
    get_classical_source_hierarchy,
    resolve_combination_override,
)
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. SAN HUI CLASH NULLIFICATION (方合解冲)
# ============================================================================

def test_apply_san_hui_nullification_present() -> None:
    """Verify clash severity is nullified (set to 0.0) when San Hui is present and clash > 0."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=15.0)
    assert result.has_san_hui is True
    assert result.clash_severity_before == 15.0
    assert result.clash_severity_after == 0.0
    assert result.nullified is True
    assert_key_format_convention(result)


def test_apply_san_hui_nullification_absent() -> None:
    """Verify clash severity is preserved when San Hui is absent."""
    result = apply_san_hui_nullification(has_san_hui=False, clash_severity=12.5)
    assert result.has_san_hui is False
    assert result.clash_severity_before == 12.5
    assert result.clash_severity_after == 12.5
    assert result.nullified is False
    assert_key_format_convention(result)


def test_apply_san_hui_nullification_zero_clash() -> None:
    """Verify behavior when San Hui is present but clash severity is 0.0."""
    result = apply_san_hui_nullification(has_san_hui=True, clash_severity=0.0)
    assert result.has_san_hui is True
    assert result.clash_severity_before == 0.0
    assert result.clash_severity_after == 0.0
    assert result.nullified is False
    assert_key_format_convention(result)


# ============================================================================
# 2. COMBO VS CLASH NET EFFECT (calculate_combo_clash_net)
# ============================================================================

@pytest.mark.parametrize(
    "combo_strength, dm_strength, control_eff, expected_net, expected_winner",
    [
        (10.0, 4.0, 1.0, 6.0, "combination"),
        (4.0, 10.0, 1.0, -6.0, "dm_control"),
        (5.0, 5.0, 1.0, 0.0, "balanced"),
        (8.0, 5.0, 1.5, 0.5, "combination"),
        (6.0, 8.0, 0.5, 2.0, "combination"),
    ],
)
def test_calculate_combo_clash_net(
    combo_strength: float,
    dm_strength: float,
    control_eff: float,
    expected_net: float,
    expected_winner: str,
) -> None:
    """Verify net calculation and winner determination for combo vs clash/DM control."""
    result = calculate_combo_clash_net(combo_strength, dm_strength, control_eff)
    assert result.net_effect == pytest.approx(expected_net)
    assert result.winner == expected_winner
    assert_key_format_convention(result)


# ============================================================================
# 3. COMBINATION OVERRIDE PARADOX (resolve_combination_override)
# ============================================================================

@pytest.mark.parametrize(
    "combo_strength, dm_strength, control_eff, expected_winner",
    [
        # Net = 10 - 4 = 6 >= 10 * 0.5 (5.0) -> combination override
        (10.0, 4.0, 1.0, "combination"),
        # Net = 10 - 8 = 2 > 0 but < 5.0 -> contained_combination
        (10.0, 8.0, 1.0, "contained_combination"),
        # Net = 4 - 10 = -6 < 0 -> dm_control
        (4.0, 10.0, 1.0, "dm_control"),
        # Net = 5 - 5 = 0 -> balanced
        (5.0, 5.0, 1.0, "balanced"),
    ],
)
def test_resolve_combination_override(
    combo_strength: float,
    dm_strength: float,
    control_eff: float,
    expected_winner: str,
) -> None:
    """Verify resolution of combination override vs DM control across four distinct outcomes."""
    result = resolve_combination_override(combo_strength, dm_strength, control_eff)
    assert result.resolved is True
    assert result.winner == expected_winner
    assert_key_format_convention(result)


# ============================================================================
# 4. DM CENTRALITY TEST (dm_centrality_test)
# ============================================================================

def test_dm_centrality_test_strong_roots() -> None:
    """Verify DM centrality test passes when DM has >= 2 main roots."""
    # DM Jia (Wood), branches Yin (Wood) and Mao (Wood) -> 2 roots
    result = dm_centrality_test("Jia", ["Yin", "Mao", "Chen", "Zi"])
    assert result.dm_stem == "Jia"
    assert result.root_count >= 2
    assert result.passes is True
    assert_key_format_convention(result)


def test_dm_centrality_test_single_root_with_hidden_support() -> None:
    """Verify DM centrality test passes when DM has 1 main root and hidden support."""
    # DM Jia (Wood), branch Yin (Wood) + Hai (contains Jia hidden stem)
    result = dm_centrality_test("Jia", ["Yin", "Hai", "Wu", "Shen"])
    assert result.dm_stem == "Jia"
    assert result.root_count == 1
    assert result.hidden_support_count >= 1
    assert result.passes is True
    assert_key_format_convention(result)


def test_dm_centrality_test_fails_rootless() -> None:
    """Verify DM centrality test fails when DM is rootless without support."""
    # DM Jia (Wood), branches Si (Fire), Wu (Fire), Shen (Metal), You (Metal)
    result = dm_centrality_test("Jia", ["Si", "Wu", "Shen", "You"])
    assert result.dm_stem == "Jia"
    assert result.root_count == 0
    assert result.hidden_support_count == 0
    assert result.passes is False
    assert_key_format_convention(result)


# ============================================================================
# 5. ADDITIONAL SYNTHESIS & HIERARCHY TESTS
# ============================================================================

def test_classical_source_hierarchy() -> None:
    """Verify §11.7.1 priority ranking: Di Tian Sui (1) > San Ming Tong Hui (2) > Yuan Hai Zi Ping (3) > Qiong Tong Bao Jian (4)."""
    hierarchy = get_classical_source_hierarchy()
    assert hierarchy["Di Tian Sui"]["priority"] == 1
    assert hierarchy["San Ming Tong Hui"]["priority"] == 2
    assert hierarchy["Yuan Hai Zi Ping"]["priority"] == 3
    assert hierarchy["Qiong Tong Bao Jian"]["priority"] == 4
    assert_key_format_convention(hierarchy)


def test_calculate_temporal_weight() -> None:
    """Verify temporal weight decay formula: 1 / (distance + 1)."""
    assert calculate_temporal_weight(0.0) == 1.0
    assert calculate_temporal_weight(1.0) == 0.5
    assert calculate_temporal_weight(3.0) == 0.25
