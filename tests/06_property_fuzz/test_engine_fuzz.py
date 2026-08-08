"""Property-based fuzzing tests for the BaZi engine core.

Targets:
- calculate_gated_score: extreme float inputs (inf, NaN, huge values)
- get_pillar_for_date: extreme/out-of-range dates
- calculate_composite_score: random QiInteraction objects with edge-case fields
"""

import math
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.core.schemas.unified import QiInteraction
from src2.engine.bazi_math import calculate_gated_score
from src2.engine.daily_pillar import BRANCH_ORDER, STEM_ORDER, get_pillar_for_date
from src2.engine.module8_scoring import calculate_composite_score

STEM_STRATEGY = st.sampled_from(STEM_ORDER)
BRANCH_STRATEGY = st.sampled_from(BRANCH_ORDER)


@given(
    dy_raw=st.floats(allow_nan=False, allow_infinity=True),
    ann_raw=st.floats(allow_nan=False, allow_infinity=True),
    ge_ju_bonus=st.floats(allow_nan=False, allow_infinity=True),
    primary_signal_raw=st.floats(allow_nan=False, allow_infinity=True),
    structural_noise_raw=st.floats(allow_nan=False, allow_infinity=True),
    era_ceiling=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
)
@settings(max_examples=200)
def test_calculate_gated_score_no_crash(dy_raw, ann_raw, ge_ju_bonus, primary_signal_raw, structural_noise_raw, era_ceiling):
    """Fuzz calculate_gated_score with extreme float values — must not raise and must not leak NaNs."""
    result = calculate_gated_score(
        dy_raw=dy_raw,
        ann_raw=ann_raw,
        ge_ju_bonus=ge_ju_bonus,
        primary_signal_raw=primary_signal_raw,
        structural_noise_raw=structural_noise_raw,
        era_ceiling=era_ceiling,
    )

    assert result is not None
    assert isinstance(result.composite_score, float)
    assert isinstance(result.raw_score, float)

    assert not math.isnan(result.composite_score), "Engine leaked a NaN value!"
    assert not math.isnan(result.raw_score), "Engine leaked a NaN raw_score!"
    assert not math.isinf(result.composite_score), "Engine leaked Infinity!"


@given(target_date=st.dates(min_value=date(1, 1, 1), max_value=date(9999, 12, 31)))
@settings(max_examples=300)
def test_get_pillar_for_date_no_crash(target_date):
    """Fuzz get_pillar_for_date with extreme dates — must not raise."""
    anchor_date = date(2000, 1, 1)
    anchor_stem = "Jia"
    anchor_branch = "Zi"

    result = get_pillar_for_date(anchor_date, anchor_stem, anchor_branch, target_date)
    assert result is not None
    assert result.stem in STEM_ORDER
    assert result.branch in BRANCH_ORDER


@given(
    dm_stem=st.sampled_from(STEM_ORDER),
    month_branch=st.sampled_from(BRANCH_ORDER),
    da_yun_stem=st.sampled_from(STEM_ORDER) | st.none(),
    da_yun_branch=st.sampled_from(BRANCH_ORDER) | st.none(),
    spectrum_tier=st.sampled_from(["Vibrant", "Strong", "Mild Strong", "Mild Weak", "Weak", "Follower"]),
    pattern_tier=st.sampled_from(["Special", "Prestigious", "Strong", "Common", "Broken"]),
    ge_ju_ten_god_mod=st.integers(min_value=-100, max_value=100),
    dy_raw=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    ann_raw=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    tai_sui_impact=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    ann_stem_impact=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    monthly_mod=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    friction_mod=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    ge_ju_alignment_mod=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    risk_penalty=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    ten_god_score_mod=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    medicine_contrib=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    era_ceiling=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    interactions=st.lists(
        st.builds(
            QiInteraction,
            vector=st.sampled_from(["WuHe", "StemClash", "Chong", "Xing", "Hai", "Po", "SelfPunish", "SanHe", "SanHui", "BanHe", "LiuHe", "TombOpen", "Void"]),
            plane=st.sampled_from(["Stem", "Branch", "Hidden"]),
            actors=st.lists(st.sampled_from(STEM_ORDER + BRANCH_ORDER), max_size=4),
            pillars=st.lists(st.sampled_from(["Year", "Month", "Day", "Hour", "Decade", "Annual", "MonthTransit", "DayTransit", "HourTransit"]), max_size=4),
            resultant_element=st.sampled_from(["Wood", "Fire", "Earth", "Metal", "Water", "Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui", None]),
            potency=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=10.0),
            is_successful=st.booleans(),
        ),
        max_size=10,
    ),
    medicine=st.lists(st.sampled_from(STEM_ORDER + BRANCH_ORDER), max_size=5),
    taboo=st.lists(st.sampled_from(STEM_ORDER + BRANCH_ORDER), max_size=5),
)
@settings(max_examples=100)
def test_calculate_composite_score_no_crash(
    dm_stem, month_branch, da_yun_stem, da_yun_branch, spectrum_tier, pattern_tier,
    ge_ju_ten_god_mod, dy_raw, ann_raw, tai_sui_impact, ann_stem_impact,
    monthly_mod, friction_mod, ge_ju_alignment_mod, risk_penalty, ten_god_score_mod,
    medicine_contrib, era_ceiling, interactions, medicine, taboo,
):
    """Fuzz calculate_composite_score with random valid-ish inputs — must not raise and must return finite numbers."""
    result = calculate_composite_score(
        dm_stem=dm_stem,
        month_branch=month_branch,
        da_yun_stem=da_yun_stem,
        da_yun_branch=da_yun_branch,
        spectrum_tier=spectrum_tier,
        pattern_tier=pattern_tier,
        ge_ju_ten_god_mod=ge_ju_ten_god_mod,
        interactions=interactions,
        medicine=medicine,
        taboo=taboo,
        dy_raw=dy_raw,
        ann_raw=ann_raw,
        tai_sui_impact=tai_sui_impact,
        ann_stem_impact=ann_stem_impact,
        monthly_mod=monthly_mod,
        friction_mod=friction_mod,
        ge_ju_alignment_mod=ge_ju_alignment_mod,
        risk_penalty=risk_penalty,
        ten_god_score_mod=ten_god_score_mod,
        medicine_contrib=medicine_contrib,
        era_ceiling=era_ceiling,
    )

    assert result is not None
    assert isinstance(result.composite_score, float)
    assert not math.isnan(result.composite_score), "Composite score leaked a NaN!"
    assert not math.isinf(result.composite_score), "Composite score leaked Infinity!"
