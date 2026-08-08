"""TEST/math/test_ch02_extraction_weights.py — Bazi Chapter 02 selective extraction weights + control suppression.

Validates (Chapter 02, Ticket 3):
- selective_hidden_extraction returns RAW registry weights (5/2/1 = Main/Middle/Residual Qi).
- Control suppression = EXCLUSION (absence from list), NOT the 0.3 dormancy factor nor the
  0.5 CONTROL_SUPPRESSION_FACTOR — those belong to get_dormancy_multiplier / calculate_root_score.
- All returned entries pass the strict English CapitalCase key/value format seam.

NOTE: Verified by running. The registry weights are 5(Main)/2(Middle)/1(Residual Qi).
Shen hidden = Geng(Metal,5), Ren(Water,2), Wu(Earth,1); therefore Water/Shen yields
[Geng w5, Ren w2] (Wu Earth excluded because Earth controls Water).
"""

from src2.engine.module2_root import (
    CONTROL_SUPPRESSION_FACTOR,
    get_dormancy_multiplier,
    selective_hidden_extraction,
)
from TEST.math.conftest import assert_key_format_convention


def test_shen_water_extraction_exact_weights() -> None:
    """Water combo + Shen branch -> Geng(Metal,5) + Ren(Water,2); Wu(Earth,1) excluded (controls Water)."""
    extracted = selective_hidden_extraction(combo_element="Water", branch="Shen")

    assert len(extracted) == 2
    labels = [e.stem.label for e in extracted]
    elements = [e.stem.element.value for e in extracted]
    weights = [e.weight for e in extracted]

    assert labels == ["Geng", "Ren"]
    assert elements == ["Metal", "Water"]
    assert weights == [5, 2]

    labels_set = set(labels)
    assert "Wu" not in labels_set, "Wu(Earth) controls Water -> suppressed via EXCLUSION, not dormancy"

    assert_key_format_convention(extracted)


def test_controlling_stem_suppressed_by_exclusion_not_dormant() -> None:
    """Water combo + Wu branch -> [] (Ding Fire + Ji Earth both non-supporting; Earth controls Water).

    Suppression here is EXCLUSION (empty list), the 0.3 dormancy factor belongs to
    get_dormancy_multiplier — a distinct function — and must NOT be conflated with extraction.
    """
    extracted = selective_hidden_extraction(combo_element="Water", branch="Wu")

    assert extracted == []
    assert len(extracted) == 0

    # Boundary: dormancy (0.3) is a SEPARATE concern applied in calculate_root_score via
    # get_dormancy_multiplier -> DormancyResult.multiplier. It is NOT applied inside
    # selective_hidden_extraction (which returns [] via EXCLUSION, not a 0.3 multiplier).
    dormant_result = get_dormancy_multiplier(branch="Shen")
    assert dormant_result.multiplier == 1.0
    assert hasattr(dormant_result, "reason")


def test_si_fire_extraction_main_qi_weight_5() -> None:
    """Fire combo + Si branch -> [Bing(Fire,5)]; Geng(Metal,2) & Wu(Earth,1) excluded (neither Fire-supporting)."""
    extracted = selective_hidden_extraction(combo_element="Fire", branch="Si")

    assert len(extracted) == 1
    entry = extracted[0]
    assert entry.stem.label == "Bing"
    assert entry.stem.element.value == "Fire"
    assert entry.weight == 5

    extracted_labels = {e.stem.label for e in extracted}
    assert "Geng" not in extracted_labels, "Geng(Metal) produces Water, not Fire -> excluded"
    assert "Wu" not in extracted_labels, "Wu(Earth) produces Metal, not Fire -> excluded"

    assert_key_format_convention(extracted)


def test_extraction_results_pass_capitalcase_seam() -> None:
    """All selective_hidden_extraction results across the extraction matrix pass the CapitalCase seam."""
    matrix: list[tuple[str, str]] = [
        ("Metal", "Shen"),
        ("Metal", "Wu"),
        ("Water", "Shen"),
        ("Water", "Wu"),
        ("Fire", "Si"),
        ("Fire", "You"),
        ("Wood", "Yin"),
        ("Wood", "Hai"),
        ("Earth", "Yin"),
        ("Earth", "Chen"),
    ]
    for combo, branch in matrix:
        extracted = selective_hidden_extraction(combo_element=combo, branch=branch)
        assert_key_format_convention(extracted)
        for entry in extracted:
            assert entry.stem.label
            assert entry.stem.element.value
            assert isinstance(entry.weight, int)
            assert entry.weight in (1, 2, 5)


def test_suppression_factor_is_separate_from_extraction() -> None:
    """Document the boundary: CONTROL_SUPPRESSION_FACTOR (0.5) lives in root-score math, not extraction.

    Extraction never applies 0.3/0.5 multipliers — it returns raw weights and uses EXCLUSION.
    """
    assert CONTROL_SUPPRESSION_FACTOR == 0.5
    extracted = selective_hidden_extraction(combo_element="Water", branch="Shen")
    assert all(e.weight in (1, 2, 5) for e in extracted), "raw weights only, no suppression multiplier applied"
    assert_key_format_convention(extracted)
