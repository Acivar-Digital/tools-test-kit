"""TEST/math/test_ch07_luck_pillars.py — Chapter 07 Luck Pillars & Dynamic Triggers Test Suite.

Verifies:
1. 60-Jiazi Cycle structure, forward/reverse progression, and Da Yun direction logic based on birth-year stem.
2. Multiplicative trigger potency formula (base * luck_harmony * seasonal) and levels.
3. Same-pillar trigger detection (`detect_same_pillar_trigger()`) for 伏吟 (consecutive) and 返吟 (non-consecutive).
4. 3x4 DM x Luck label matrix (`get_dm_luck_label()`).
5. English CapitalCase conventions for all stem/branch/element key formats.
"""

from collections.abc import Callable
from typing import Any

import pytest

from src2.core.schemas import ChartProfile, Pillar
from src2.core.schemas.unified import Gender
from src2.engine.da_yun import _next_pillar, calculate_da_yun, get_current_da_yun
from src2.engine.module8_scoring import get_dm_luck_label
from src2.engine.module9_triggers import calculate_trigger_potency, detect_same_pillar_trigger

# ============================================================================
# 1. 60-JIAZI CYCLE & DA YUN DIRECTION TESTS
# ============================================================================


def test_60_jiazi_cycle_structure(
    heavenly_stems: tuple[str, ...],
    earthly_branches: tuple[str, ...],
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify construction and cycling of the 60 Jiazi sequence."""
    cycle: list[tuple[str, str]] = []
    for i in range(60):
        stem = heavenly_stems[i % 10]
        branch = earthly_branches[i % 12]
        cycle.append((stem, branch))

    assert len(cycle) == 60
    assert len(set(cycle)) == 60
    assert cycle[0] == ("Jia", "Zi")
    assert cycle[-1] == ("Gui", "Hai")

    # Key format check
    assert_key_format_convention(cycle)


def test_next_pillar_progression(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify single step forward and reverse pillar progression."""
    # Step forward from Jia Zi -> Yi Chou
    fwd_stem, fwd_branch = _next_pillar("Jia", "Zi", forward=True)
    assert (fwd_stem, fwd_branch) == ("Yi", "Chou")

    # Step reverse from Jia Zi -> Gui Hai
    rev_stem, rev_branch = _next_pillar("Jia", "Zi", forward=False)
    assert (rev_stem, rev_branch) == ("Gui", "Hai")

    # Full 60-step cycle forward returns to start
    cur_stem, cur_branch = "Jia", "Zi"
    for _ in range(60):
        cur_stem, cur_branch = _next_pillar(cur_stem, cur_branch, forward=True)
    assert (cur_stem, cur_branch) == ("Jia", "Zi")

    assert_key_format_convention((fwd_stem, fwd_branch))
    assert_key_format_convention((rev_stem, rev_branch))


@pytest.mark.parametrize(
    ("year_stem", "gender", "expected_direction"),
    [
        ("Jia", Gender.MALE, "forward"),  # Yang year stem + Male -> Forward
        ("Jia", Gender.FEMALE, "reverse"),  # Yang year stem + Female -> Reverse
        ("Yi", Gender.MALE, "reverse"),  # Yin year stem + Male -> Reverse
        ("Yi", Gender.FEMALE, "forward"),  # Yin year stem + Female -> Forward
    ],
)
def test_da_yun_direction_by_year_stem(
    year_stem: str,
    gender: Gender,
    expected_direction: str,
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify Da Yun direction is derived from Birth-Year Stem polarity + Gender."""
    # Day stem is opposite polarity to ensure direction is based on Year stem, NOT Day Master
    day_stem = "Yi" if year_stem == "Jia" else "Jia"

    profile = ChartProfile(
        dob="2025-05-15 12:00:00",
        gender=gender,
        year_pillar=Pillar(stem=year_stem, branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        day_pillar=Pillar(stem=day_stem, branch="Chen"),
        hour_pillar=Pillar(stem="Ren", branch="Shen"),
    )

    da_yun_out = calculate_da_yun(profile)
    assert da_yun_out.direction == expected_direction
    assert len(da_yun_out.cycles) == 10

    # Verify pillar progression
    first_cycle = da_yun_out.cycles[0]
    if expected_direction == "forward":
        assert (first_cycle.stem, first_cycle.branch) == ("Ding", "Mao")
    else:
        assert (first_cycle.stem, first_cycle.branch) == ("Yi", "Chou")

    assert_key_format_convention(
        [
            (c.stem, c.branch, c.element, c.phase_label)
            for c in da_yun_out.cycles
        ]
    )


def test_get_current_da_yun(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify lookup of current Da Yun cycle by target year."""
    profile = ChartProfile(
        dob="2025-05-15 12:00:00",
        gender=Gender.MALE,
        year_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        day_pillar=Pillar(stem="Wu", branch="Chen"),
        hour_pillar=Pillar(stem="Ren", branch="Shen"),
    )

    da_yun_out = calculate_da_yun(profile)
    cycle0 = da_yun_out.cycles[0]
    matched = get_current_da_yun(da_yun_out, target_year=cycle0.start_year + 2)

    assert matched is not None
    assert matched.start_year == cycle0.start_year
    assert matched.end_year == cycle0.end_year

    assert_key_format_convention((matched.stem, matched.branch, matched.element))


# ============================================================================
# 2. MULTIPLICATIVE TRIGGER POTENCY FORMULA TESTS
# ============================================================================


@pytest.mark.parametrize(
    ("base", "harmony", "seasonal", "expected_potency", "expected_level"),
    [
        (10.0, 1.5, 1.0, 15.0, "critical"),
        (10.0, 1.49, 1.0, 14.9, "high"),
        (8.0, 1.25, 1.0, 10.0, "high"),
        (8.0, 1.24, 1.0, 9.92, "moderate"),
        (5.0, 1.0, 1.0, 5.0, "moderate"),
        (4.9, 1.0, 1.0, 4.9, "low"),
        (2.0, 0.5, 0.8, 0.8, "low"),
    ],
)
def test_calculate_trigger_potency_formula(
    base: float,
    harmony: float,
    seasonal: float,
    expected_potency: float,
    expected_level: str,
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify multiplicative potency formula = base * luck_dm_harmony * seasonal_support and levels."""
    result = calculate_trigger_potency(
        base_trigger=base,
        luck_dm_harmony=harmony,
        seasonal_support=seasonal,
    )

    assert result.potency == expected_potency
    assert result.level == expected_level
    assert result.base == base
    assert result.luck_dm_harmony == harmony
    assert result.seasonal_support == seasonal

    assert_key_format_convention(result.level)


# ============================================================================
# 3. SAME-PILLAR TRIGGER DETECTION (伏吟 / 返吟) TESTS
# ============================================================================


def test_detect_same_pillar_trigger_unique(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify no triggers returned when all 4 natal pillars are unique."""
    year = Pillar(stem="Jia", branch="Zi")
    month = Pillar(stem="Bing", branch="Yin")
    day = Pillar(stem="Wu", branch="Chen")
    hour = Pillar(stem="Ren", branch="Shen")

    triggers = detect_same_pillar_trigger(year, month, day, hour)
    assert len(triggers) == 0

    assert_key_format_convention(triggers)


def test_detect_same_pillar_trigger_fuyin(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify 伏吟 (consecutive repetition) detection for stems and branches."""
    # Year stem == Month stem (Jia, Jia) -> Consecutive stem repeat
    # Month branch == Day branch (Yin, Yin) -> Consecutive branch repeat
    year = Pillar(stem="Jia", branch="Zi")
    month = Pillar(stem="Jia", branch="Yin")
    day = Pillar(stem="Bing", branch="Yin")
    hour = Pillar(stem="Ren", branch="Shen")

    triggers = detect_same_pillar_trigger(year, month, day, hour)
    assert len(triggers) == 2

    stem_trig = next(t for t in triggers if t.pillar_type == "stem")
    assert stem_trig.value == "Jia"
    assert stem_trig.count == 2
    assert stem_trig.repetition_type == "伏吟"

    branch_trig = next(t for t in triggers if t.pillar_type == "branch")
    assert branch_trig.value == "Yin"
    assert branch_trig.count == 2
    assert branch_trig.repetition_type == "伏吟"

    assert_key_format_convention([t.value for t in triggers])


def test_detect_same_pillar_trigger_fanyin(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify 返吟 (non-consecutive repetition) detection for stems and branches."""
    # Year stem == Day stem (Jia, Jia; non-consecutive: index 0 and 2)
    # Year branch == Hour branch (Zi, Zi; non-consecutive: index 0 and 3)
    year = Pillar(stem="Jia", branch="Zi")
    month = Pillar(stem="Bing", branch="Yin")
    day = Pillar(stem="Jia", branch="Chen")
    hour = Pillar(stem="Ren", branch="Zi")

    triggers = detect_same_pillar_trigger(year, month, day, hour)
    assert len(triggers) == 2

    stem_trig = next(t for t in triggers if t.pillar_type == "stem")
    assert stem_trig.value == "Jia"
    assert stem_trig.count == 2
    assert stem_trig.repetition_type == "返吟"

    branch_trig = next(t for t in triggers if t.pillar_type == "branch")
    assert branch_trig.value == "Zi"
    assert branch_trig.count == 2
    assert branch_trig.repetition_type == "返吟"

    assert_key_format_convention([t.value for t in triggers])


def test_detect_same_pillar_trigger_triple_repeat(
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify triple repeat detection classification."""
    # Stems: Jia, Jia, Jia, Ren -> indices 0, 1, 2 are consecutive -> 伏吟
    year = Pillar(stem="Jia", branch="Zi")
    month = Pillar(stem="Jia", branch="Yin")
    day = Pillar(stem="Jia", branch="Chen")
    hour = Pillar(stem="Ren", branch="Shen")

    triggers = detect_same_pillar_trigger(year, month, day, hour)
    assert len(triggers) == 1

    stem_trig = triggers[0]
    assert stem_trig.pillar_type == "stem"
    assert stem_trig.value == "Jia"
    assert stem_trig.count == 3
    assert stem_trig.repetition_type == "伏吟"

    assert_key_format_convention([t.value for t in triggers])


# ============================================================================
# 4. 3x4 DM x LUCK MATRIX TESTS
# ============================================================================


@pytest.mark.parametrize(
    ("dm_tier", "luck_type", "expected_label"),
    [
        # Strong DM
        ("Strong", "Resource", "Excellent"),
        ("Strong", "Wealth", "Good"),
        ("Strong", "Influence", "Excellent"),
        ("Strong", "Output", "Good"),
        # Neutral DM
        ("Neutral", "Resource", "Good"),
        ("Neutral", "Wealth", "Challenging"),
        ("Neutral", "Influence", "Manageable"),
        ("Neutral", "Output", "Favorable"),
        # Weak DM
        ("Weak", "Resource", "Essential"),
        ("Weak", "Wealth", "Dangerous"),
        ("Weak", "Influence", "Harmful"),
        ("Weak", "Output", "Depleting"),
        # Edge / Unknown cases
        ("Unknown", "Resource", "Unknown"),
        ("Strong", "InvalidType", "Unknown"),
        ("Weak", "Unknown", "Unknown"),
    ],
)
def test_get_dm_luck_label_matrix(
    dm_tier: str,
    luck_type: str,
    expected_label: str,
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify 3x4 DM Strength x Luck Ten God interaction matrix labels."""
    label = get_dm_luck_label(dm_tier=dm_tier, luck_type=luck_type)
    assert label == expected_label

    assert_key_format_convention(label)
