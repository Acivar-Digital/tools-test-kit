"""Property-based fuzzing tests for Synthesis & Nullification invariants (Chapter 11).

Targets:
- apply_san_hui_nullification: Absolute Nullification Invariant (san_hui_present → net_severity == 0.0)
- calculate_combo_clash_net: No NaN/Infinity leaks for extreme float inputs
- resolve_combination_override: No NaN/Infinity leaks and valid winner values
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.core.schemas.unified import QiInteraction
from src2.engine.contradiction_resolver import (
    apply_san_hui_nullification,
    calculate_combo_clash_net,
    resolve_combination_override,
)

STEM_ORDER = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
BRANCH_ORDER = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]

VECTOR_ORDER = [
    "WuHe", "StemClash", "Chong", "Xing", "Hai", "Po", "SelfPunish",
    "SanHe", "SanHui", "BanHe", "LiuHe", "TombOpen", "Void",
]
PLANE_ORDER = ["Stem", "Branch", "Hidden"]
ELEMENT_ORDER = [
    "Wood", "Fire", "Earth", "Metal", "Water",
    "Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui", None,
]
PILLAR_ORDER = [
    "Year", "Month", "Day", "Hour", "Decade", "Annual",
    "MonthTransit", "DayTransit", "HourTransit",
]


@given(
    interaction=st.builds(
        QiInteraction,
        vector=st.sampled_from(VECTOR_ORDER),
        plane=st.sampled_from(PLANE_ORDER),
        actors=st.lists(st.sampled_from(STEM_ORDER + BRANCH_ORDER), max_size=4),
        pillars=st.lists(st.sampled_from(PILLAR_ORDER), max_size=4),
        resultant_element=st.sampled_from(ELEMENT_ORDER),
        potency=st.floats(allow_nan=False, allow_infinity=True),
        is_successful=st.booleans(),
    ),
    san_hui_present=st.booleans(),
)
@settings(max_examples=200)
def test_san_hui_nullification_invariant(interaction, san_hui_present):
    """Absolute Nullification Invariant: when san_hui is present, net_severity must be 0.0.

    Regardless of how extreme or massive the initial clash inputs were,
    the presence of San Hui must force the resulting severity to exactly 0.0.
    """
    result = apply_san_hui_nullification(san_hui_present, interaction.potency)

    # Guard: output must be a finite float (no NaN, no Infinity)
    assert isinstance(result.clash_severity_after, float)
    assert not math.isnan(result.clash_severity_after), (
        f"Nullification leaked NaN for has_san_hui={san_hui_present}, potency={interaction.potency}"
    )
    assert not math.isinf(result.clash_severity_after), (
        f"Nullification leaked Infinity for has_san_hui={san_hui_present}, potency={interaction.potency}"
    )

    # Absolute Nullification Invariant: san_hui_present → net_severity == 0.0
    if san_hui_present:
        assert result.clash_severity_after == 0.0, (
            f"San Hui present but severity not nullified: {result.clash_severity_after} "
            f"(before={result.clash_severity_before}, nullified={result.nullified})"
        )


@given(
    combo_strength=st.floats(allow_nan=False, allow_infinity=True),
    dm_strength=st.floats(allow_nan=False, allow_infinity=True),
    control_efficiency=st.floats(allow_nan=False, allow_infinity=True),
)
@settings(max_examples=200)
def test_calculate_combo_clash_net_no_nan_inf(combo_strength, dm_strength, control_efficiency):
    """Fuzz calculate_combo_clash_net with extreme floats — must not leak NaN or Infinity."""
    result = calculate_combo_clash_net(combo_strength, dm_strength, control_efficiency)

    assert not math.isnan(result.net_effect), (
        f"Combo-clash net leaked NaN: combo={combo_strength}, dm={dm_strength}, ctrl={control_efficiency}"
    )
    assert not math.isinf(result.net_effect), (
        f"Combo-clash net leaked Infinity: combo={combo_strength}, dm={dm_strength}, ctrl={control_efficiency}"
    )
    assert result.winner in ("combination", "dm_control", "balanced")


@given(
    combo_strength=st.floats(allow_nan=False, allow_infinity=True),
    dm_strength=st.floats(allow_nan=False, allow_infinity=True),
    control_efficiency=st.floats(allow_nan=False, allow_infinity=True),
)
@settings(max_examples=200)
def test_resolve_combination_override_no_nan_inf(combo_strength, dm_strength, control_efficiency):
    """Fuzz resolve_combination_override with extreme floats — must not leak NaN or Infinity."""
    result = resolve_combination_override(combo_strength, dm_strength, control_efficiency)

    assert result.resolved is True
    assert result.winner in ("combination", "contained_combination", "dm_control", "balanced")

    if result.net is not None:
        assert not math.isnan(result.net), (
            f"Combination override net leaked NaN: combo={combo_strength}, dm={dm_strength}, ctrl={control_efficiency}"
        )
        assert not math.isinf(result.net), (
            f"Combination override net leaked Infinity: combo={combo_strength}, dm={dm_strength}, ctrl={control_efficiency}"
        )
