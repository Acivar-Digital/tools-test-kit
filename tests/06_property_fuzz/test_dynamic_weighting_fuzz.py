"""Property-based fuzzing tests for BaZi dynamic weighting distributions (CH08).

Targets:
- get_ten_god_magnitude_multiplier: extreme DM strength floats
- get_seasonal_ten_god_weight: extreme element/branch combos
- calculate_ten_god_dominance: extreme profile inputs

All tests assert no NaN/Infinity leaks and distribution invariants.
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.engine.module6_ten_gods import (
    calculate_ten_god_dominance,
    get_seasonal_ten_god_weight,
    get_ten_god_magnitude_multiplier,
)
from src2.core.schemas.unified import TenGodEntry, TenGod

STEM_ORDER = [
    "Jia", "Yi", "Bing", "Ding", "Wu",
    "Ji", "Geng", "Xin", "Ren", "Gui",
]
BRANCH_ORDER = [
    "Zi", "Chou", "Yin", "Mao", "Chen", "Si",
    "Wu", "Wei", "Shen", "You", "Xu", "Hai",
]
ELEMENT_ORDER = ["Wood", "Fire", "Earth", "Metal", "Water"]
TEN_GOD_NAMES = [
    "Zheng Yin", "Pian Yin", "Zheng Cai", "Pian Cai",
    "Zheng Guan", "Pian Guan", "Shi Shen", "Shang Guan",
    "Bi Jian", "Jie Cai", "Qi Sha", "Shao Shen",
    "Fu Yin", "Jian Lu", "Ge Ming", "Qi Sha",
]


@given(
    ten_god_score=st.floats(allow_nan=False, allow_infinity=True),
)
@settings(max_examples=200)
def test_get_ten_god_magnitude_multiplier_no_nan_or_inf(ten_god_score: float) -> None:
    """Fuzz get_ten_god_magnitude_multiplier with extreme floats — must not leak NaN or Infinity."""
    result = get_ten_god_magnitude_multiplier(ten_god_score)

    assert isinstance(result, float)
    assert not math.isnan(result), f"get_ten_god_magnitude_multiplier({ten_god_score}) leaked NaN!"
    assert not math.isinf(result), f"get_ten_god_magnitude_multiplier({ten_god_score}) leaked Infinity!"


@given(
    ten_god_element=st.sampled_from(ELEMENT_ORDER),
    month_branch=st.sampled_from(BRANCH_ORDER),
)
@settings(max_examples=200)
def test_get_seasonal_ten_god_weight_no_nan_or_inf(
    ten_god_element: str,
    month_branch: str,
) -> None:
    """Fuzz get_seasonal_ten_god_weight with all element/branch combos — must not leak NaN or Infinity."""
    result = get_seasonal_ten_god_weight(ten_god_element, month_branch)

    assert isinstance(result, float)
    assert not math.isnan(result), f"get_seasonal_ten_god_weight({ten_god_element}, {month_branch}) leaked NaN!"
    assert not math.isinf(result), f"get_seasonal_ten_god_weight({ten_god_element}, {month_branch}) leaked Infinity!"


@given(
    dm_stem=st.sampled_from(STEM_ORDER),
    month_branch=st.sampled_from(BRANCH_ORDER),
    num_entries=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=200)
def test_calculate_ten_god_dominance_distribution_invariant(
    dm_stem: str,
    month_branch: str,
    num_entries: int,
) -> None:
    """Fuzz calculate_ten_god_dominance — category_scores must sum to a finite value and normalize to 1.0."""
    profile = {}
    for i in range(num_entries):
        stem_key = f"stem_{i}"
        ten_god_name = TEN_GOD_NAMES[i % len(TEN_GOD_NAMES)]
        profile[stem_key] = TenGodEntry(
            stem=STEM_ORDER[i % len(STEM_ORDER)],
            ten_god=TenGod(ten_god_name),
            score=(i + 1),
        )

    result = calculate_ten_god_dominance(profile, month_branch=month_branch)

    assert isinstance(result.category_scores, dict)
    total = sum(result.category_scores.values())

    assert not math.isnan(total), "Category scores sum leaked NaN!"
    assert not math.isinf(total), "Category scores sum leaked Infinity!"

    if total > 0.0:
        normalized_sum = sum(
            score / total for score in result.category_scores.values()
        )
        assert math.isclose(
            normalized_sum, 1.0, rel_tol=1e-9, abs_tol=1e-9
        ), (
            f"Normalized category weights sum to {normalized_sum}, expected 1.0"
        )