"""TEST/math/test_ch02_unstable_sentinel.py — Bazi Chapter 02 UNSTABLE Sentinel Robustness.

Validates the UNSTABLE sentinel handling inside _has_meaningful_root
(src2/engine/module0_geju_utils.py), which delegates to _check_trans_root
-> _check_unstable_root. This re-USES the weight>=2 ROOT_STRENGTH_THRESHOLD
(hiding hidden stems). The UNSTABLE sentinel does NOT lift residual weight-1
energy to a surface root; it only re-applies the hidden-stem threshold scan.

Also validates the dormancy 0.3/1.0 math via get_dormancy_multiplier
+ _is_dormant in src2/engine/module2_root.py.
"""

import pytest

from src2.core.schemas.unified import PillarMap
from src2.engine.module0_geju_utils import _has_meaningful_root
from src2.engine.module2_root import get_dormancy_multiplier
from TEST.math.conftest import assert_key_format_convention

DM_ELEMENTS = ["Fire", "Metal", "Earth"]

ALL_BRANCHES = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]

UNSTABLE_TRANS = PillarMap(year=None, month=None, day="UNSTABLE", hour=None)


# ============================================================================
# 1. UNSTABLE SENTINEL ROBUSTNESS
# ============================================================================

def test_unstable_sentinel_no_crash_returns_bool() -> None:
    """UNSTABLE sentinel must not crash and must return a plain bool for each DM."""
    branches = PillarMap(year=None, month=None, day="Si", hour=None)
    for dm in DM_ELEMENTS:
        result = _has_meaningful_root(dm, branches, UNSTABLE_TRANS)
        assert isinstance(result, bool), f"Expected bool for DM={dm}, got {type(result)}"
        assert_key_format_convention(result)


def test_unstable_does_not_lift_residual_root() -> None:
    """Earth DM + Si branch + UNSTABLE transform -> False (residual weight-1 NOT lifted)."""
    branches = PillarMap(year=None, month=None, day="Si", hour=None)
    result = _has_meaningful_root("Earth", branches, UNSTABLE_TRANS)
    assert result is False
    assert_key_format_convention(result)


def test_unstable_still_detects_main_qi_root() -> None:
    """Fire DM + Si branch + UNSTABLE -> True (clashed branch participates via hidden-stem threshold)."""
    branches = PillarMap(year=None, month=None, day="Si", hour=None)
    result = _has_meaningful_root("Fire", branches, UNSTABLE_TRANS)
    assert result is True
    assert_key_format_convention(result)


def test_unstable_contrast_literal_transformation() -> None:
    """Earth DM + Si + literal day='Earth' transform -> True (literal element match via _trans==dm_element)."""
    branches = PillarMap(year=None, month=None, day="Si", hour=None)
    literal_trans = PillarMap(year=None, month=None, day="Earth", hour=None)
    result = _has_meaningful_root("Earth", branches, literal_trans)
    assert result is True
    assert_key_format_convention(result)


# ============================================================================
# 2. DORMANCY MULTIPLIER (0.3/1.0)
# ============================================================================

@pytest.mark.parametrize("branch", ALL_BRANCHES)
def test_dormancy_multiplier_active_branches(branch: str) -> None:
    """All 12 branches carry a weight-5 Main Qi hidden stem -> active (1.0, not dormant)."""
    res = get_dormancy_multiplier(branch)
    assert res.branch == branch
    assert res.multiplier == 1.0
    assert res.is_dormant is False
    assert_key_format_convention(res)


def test_dormancy_multiplier_unknown_branch() -> None:
    """Unknown/empty branch -> dormant (0.3, reason 'No surface root')."""
    res = get_dormancy_multiplier("Unknown")
    assert res.branch == "Unknown"
    assert res.multiplier == 0.3
    assert res.is_dormant is True
    assert res.reason == "No surface root"
    assert_key_format_convention(res)
