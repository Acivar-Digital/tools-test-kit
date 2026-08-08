"""TEST/math/test_ch01_anti_vibe_1_1.py — Anti-Vibe Test 1.1: Root presence != strength.

Anti-Vibe Test 1.1 asserts that the mere *presence* of a same-element root (root_dm > 0)
does NOT imply the Day Master is strong. A chart can have an identifiable root
(e.g. Yi Wood buried in Chen) yet still be classified Weak because overwhelming
controlling elements (Metal here, from Geng+Xin stems/branches) suppress it,
and the hostile month season further suppresses the root's effect.

Verified chart (Jia Wood DM):
  year_pillar  = Geng You  (Metal control x2: branch + stem) + hidden Xin Metal
  month_pillar = Xin Shen  (Metal control x2: branch + stem) + hidden Geng Metal, suppressed
  day_pillar   = Jia Chen  (root: Yi Wood hidden in Chen, ratio 0.3)
  hour_pillar  = Ren Zi    (Water support: branch + stem + hidden Gui)

Expected Tier-1 invariants:
  root_dm    = 0.3
  support_dm = 2.9
  control_dm = 4.6
  score      = root_dm * 2.0 + support_dm - control_dm * 1.5 = -3.4
  classification = 'Weak'  (score <= 2.0)
"""

from typing import Any

from src2.core.schemas.unified import (
    ChartProfile,
    DmStrengthTier1,
    Element,
    Pillar,
)
from src2.engine.module2_root import calculate_dm_strength_tier1


def _build_profile() -> ChartProfile:
    """Construct the verified Anti-Vibe 1.1 chart profile."""
    return ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Geng", branch="You"),
        month_pillar=Pillar(stem="Xin", branch="Shen"),
        day_pillar=Pillar(stem="Jia", branch="Chen"),
        hour_pillar=Pillar(stem="Ren", branch="Zi"),
    )


def test_anti_vibe_1_1_result_type(
    assert_key_format_convention: Any,
) -> None:
    """Result must be a DmStrengthTier1 model instance."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)
    assert isinstance(result, DmStrengthTier1)
    assert_key_format_convention(result)


def test_anti_vibe_1_1_root_present_but_weak(
    assert_key_format_convention: Any,
) -> None:
    """Root presence (root_dm > 0) does NOT imply strength: classification is Weak."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)

    assert result.components["root_dm"] > 0, "Root exists (Yi Wood in Chen) but must remain suppressed"
    assert result.classification == "Weak", "Overwhelming Metal control + hostile Shen month suppresses root"

    assert_key_format_convention(result)


def test_anti_vibe_1_1_verified_components(
    assert_key_format_convention: Any,
) -> None:
    """Assert exact verified Tier-1 component values for the Anti-Vibe 1.1 chart."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)

    assert result.components["root_dm"] == round(0.3, 2)
    assert result.components["support_dm"] == round(2.9, 2)
    assert result.components["control_dm"] == round(4.6, 2)

    assert_key_format_convention(result)


def test_anti_vibe_1_1_score_formula_invariant(
    assert_key_format_convention: Any,
) -> None:
    """Assert score equals the Tier-1 formula: root_dm*2.0 + support_dm - control_dm*1.5."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)

    root_dm = result.components["root_dm"]
    support_dm = result.components["support_dm"]
    control_dm = result.components["control_dm"]
    expected_score = round(root_dm * 2.0 + support_dm - control_dm * 1.5, 2)

    assert result.score == expected_score
    assert result.score == round(-3.4, 2)

    assert_key_format_convention(result)


def test_anti_vibe_1_1_classification_thresholds(
    assert_key_format_convention: Any,
) -> None:
    """Verify Weak classification boundary: score <= 2.0 -> Weak."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)

    assert result.score <= 2.0
    assert result.classification == "Weak"

    assert_key_format_convention(result)


def test_anti_vibe_1_1_element_consistency(
    assert_key_format_convention: Any,
) -> None:
    """Verify the DM element is Wood and that Metal controls Wood in this chart."""
    profile = _build_profile()
    result: DmStrengthTier1 = calculate_dm_strength_tier1(profile)

    assert profile.dm_element == "Wood"
    assert profile.day_master == "Jia"
    assert isinstance(result, DmStrengthTier1)

    # Metal (Geng, Xin stems; You, Shen branches) controls Wood (the DM element)
    from src2.engine.classical_rules import get_control
    assert get_control(Element.METAL) == Element.WOOD

    assert_key_format_convention(result)
