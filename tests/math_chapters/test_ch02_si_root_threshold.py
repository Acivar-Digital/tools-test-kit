"""TEST/math/test_ch02_si_root_threshold.py — Bazi Chapter 02 Si Branch Root Threshold Tests.

Validates:
1. ROOT_STRENGTH_THRESHOLD == 2 (meaningful root weight floor).
2. _has_meaningful_root() for Si (Snake) branch with Day Master as sole pillar.
   - Si hidden stems: Bing (Fire, weight 5), Geng (Metal, weight 2), Wu (Earth, weight 1).
   - Bing/Geng meet threshold (>= 2) -> Fire/Metal Day Masters root in Si.
   - Wu falls below threshold (< 2) -> Earth Day Master does NOT root in Si.
3. Parametrized sweep over all 10 Heavenly Stems as Day Master against all 4 pillars
   populated with "Si", asserting the expected meaningful-root boolean.
4. Strict English CapitalCase key/value conventions enforced via assert_key_format_convention
   on every assertion result.
"""

import pytest

from src2.core.schemas.unified import PillarMap
from src2.engine.module0_geju_utils import ROOT_STRENGTH_THRESHOLD, _has_meaningful_root
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. ROOT STRENGTH THRESHOLD CONSTANT
# ============================================================================


def test_root_strength_threshold_value() -> None:
    """Verify the meaningful-root weight floor is 2 (Bing/Geng qualify, Wu does not)."""
    assert ROOT_STRENGTH_THRESHOLD == 2
    assert_key_format_convention(ROOT_STRENGTH_THRESHOLD)


# ============================================================================
# 2. SI BRANCH CORE ROOT TESTS (Day Master only)
# ============================================================================


def test_si_branch_fire_root_is_meaningful() -> None:
    """Si contains Bing (Fire, weight 5 >= 2) -> Fire Day Master has a meaningful root."""
    branches = PillarMap(day="Si")
    result = _has_meaningful_root("Fire", branches, None)
    assert result is True
    assert_key_format_convention(result)


def test_si_branch_metal_root_is_meaningful() -> None:
    """Si contains Geng (Metal, weight 2 >= 2) -> Metal Day Master has a meaningful root."""
    branches = PillarMap(day="Si")
    result = _has_meaningful_root("Metal", branches, None)
    assert result is True
    assert_key_format_convention(result)


def test_si_branch_earth_root_is_not_meaningful() -> None:
    """Si contains Wu (Earth, weight 1 < 2) -> Earth Day Master does NOT root in Si."""
    branches = PillarMap(day="Si")
    result = _has_meaningful_root("Earth", branches, None)
    assert result is False
    assert_key_format_convention(result)


# ============================================================================
# 3. PARAMETRIZED SWEEP: ALL 10 STEMS x ALL 4 PILLARS (Si)
# ============================================================================

SI_STEM_EXPECTED = [
    ("Jia", "Wood", False),
    ("Yi", "Wood", False),
    ("Bing", "Fire", True),
    ("Ding", "Fire", True),
    ("Wu", "Earth", False),
    ("Ji", "Earth", False),
    ("Geng", "Metal", True),
    ("Xin", "Metal", True),
    ("Ren", "Water", False),
    ("Gui", "Water", False),
]

SI_PILLARS = [
    ("year", "Si"),
    ("month", "Si"),
    ("day", "Si"),
    ("hour", "Si"),
]


@pytest.mark.parametrize("pillar_name,pillar_value", SI_PILLARS)
@pytest.mark.parametrize("stem,element,expected", SI_STEM_EXPECTED)
def test_si_root_threshold_sweep_all_stems_all_pillars(
    stem: str,
    element: str,
    expected: bool,
    pillar_name: str,
    pillar_value: str,
) -> None:
    """Sweep all 10 Heavenly Stems as Day Master across all 4 pillars set to 'Si'.

    Expected: Fire/Metal stems root (Bing w5 / Geng w2 >= 2); all others do not.
    """
    branches = PillarMap(**{pillar_name: pillar_value})
    result = _has_meaningful_root(element, branches, None)
    assert result is expected
    assert_key_format_convention(result)
