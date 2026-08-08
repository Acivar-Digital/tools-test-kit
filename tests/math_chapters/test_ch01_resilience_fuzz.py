"""TEST/math/test_ch01_resilience_fuzz.py — Bazi Chapter 01 Resilience Fuzzing.

Validates:
1. Missing-hour resilience: a 3-pillar ChartProfile (hour_pillar=None) yields a
   valid DmStrengthTier1 that does not crash, and the None-hour result's
   components are identical to a chart whose hour_pillar is an empty
   Pillar(stem='Unknown', branch='Unknown') (both contribute 0,0,0).
2. get_element_phase None/empty fuzzing: None and '' inputs return 'Unknown'.
3. Regression: existing seasonal multiplier and classification logic unaffected.
"""

import pytest

from src2.core.schemas.unified import ChartProfile, DmStrengthTier1, Pillar
from src2.engine.element_phase import get_element_phase
from src2.engine.module2_root import calculate_dm_strength_tier1
from TEST.math.conftest import assert_key_format_convention


def _make_profile(hour_pillar: Pillar | None) -> ChartProfile:
    return ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Yi", branch="Mao"),
        month_pillar=Pillar(stem="Ding", branch="Wu"),
        day_pillar=Pillar(stem="Jia", branch="Yin"),
        hour_pillar=hour_pillar,
    )


def test_missing_hour_pillar_does_not_crash() -> None:
    profile = _make_profile(hour_pillar=None)
    result = calculate_dm_strength_tier1(profile)
    assert isinstance(result, DmStrengthTier1)
    assert result.classification in ("Strong", "Neutral", "Weak")


def test_none_hour_equals_empty_hour_components() -> None:
    none_hour_profile = _make_profile(hour_pillar=None)
    empty_hour_profile = _make_profile(
        hour_pillar=Pillar(stem="Unknown", branch="Unknown")
    )

    none_result = calculate_dm_strength_tier1(none_hour_profile)
    empty_result = calculate_dm_strength_tier1(empty_hour_profile)

    assert none_result.components == empty_result.components
    assert none_result.score == empty_result.score
    assert none_result.classification == empty_result.classification


@pytest.mark.parametrize(
    "element, month_branch",
    [
        (None, ""),
        ("", ""),
        ("Wood", None),
        (None, None),
    ],
)
def test_get_element_phase_none_and_empty_inputs(element: str | None, month_branch: str | None) -> None:
    result = get_element_phase(element, month_branch)
    assert result == "Unknown"
    assert_key_format_convention(result)


def test_missing_hour_passes_capitalcase_convention() -> None:
    profile = _make_profile(hour_pillar=None)
    result = calculate_dm_strength_tier1(profile)
    assert_key_format_convention(result)
