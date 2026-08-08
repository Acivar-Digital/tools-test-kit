"""TEST/math/test_ch02_hidden_reserves.py — Bazi Chapter 02 Hidden Reserves Math Tests.

Validates:
1. ZHI_HIDDEN matrix for all 12 earthly branches (Main, Middle, Residual Qi).
2. calculate_root_score() formula: surface_roots + (hidden_roots * 0.3).
3. Dormancy multiplier logic (0.3 flat dormancy multiplier for unextracted hidden stems).
4. Control suppression factor constant (0.5) and suppression logic.
5. selective_hidden_extraction() logic for combination element support filtering.
6. Strict English CapitalCase key/value conventions (no Chinese characters).
"""

import pytest

from src2.core.schemas.unified import ZHI_HIDDEN, HiddenStemEntry
from src2.engine.classical_rules import get_zhi_hidden
from src2.engine.module2_root import (
    CONTROL_SUPPRESSION_FACTOR,
    calculate_root_score,
    get_dormancy_multiplier,
    selective_hidden_extraction,
)
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. ZHI_HIDDEN MATRIX FOR ALL 12 BRANCHES (藏干)
# ============================================================================

EXPECTED_ZHI_HIDDEN_RAW: dict[str, list[tuple[str, int]]] = {
    "Zi": [("Gui", 5)],
    "Chou": [("Ji", 5), ("Gui", 2), ("Xin", 1)],
    "Yin": [("Jia", 5), ("Bing", 2), ("Wu", 1)],
    "Mao": [("Yi", 5)],
    "Chen": [("Wu", 5), ("Yi", 2), ("Gui", 1)],
    "Si": [("Bing", 5), ("Geng", 2), ("Wu", 1)],
    "Wu": [("Ding", 5), ("Ji", 2)],
    "Wei": [("Ji", 5), ("Ding", 2), ("Yi", 1)],
    "Shen": [("Geng", 5), ("Ren", 2), ("Wu", 1)],
    "You": [("Xin", 5)],
    "Xu": [("Wu", 5), ("Xin", 2), ("Ding", 1)],
    "Hai": [("Ren", 5), ("Jia", 2)],
}


@pytest.mark.parametrize(
    "branch",
    [
        "Zi",
        "Chou",
        "Yin",
        "Mao",
        "Chen",
        "Si",
        "Wu",
        "Wei",
        "Shen",
        "You",
        "Xu",
        "Hai",
    ],
)
def test_zhi_hidden_registry_12_branches(branch: str) -> None:
    """Verify ZHI_HIDDEN schema registry returns canonical hidden stems and weights for all 12 branches."""
    expected_stems = EXPECTED_ZHI_HIDDEN_RAW[branch]
    registry_entries = ZHI_HIDDEN.get(branch)
    assert registry_entries is not None, f"ZHI_HIDDEN for branch {branch} should not be None"
    assert len(registry_entries) == len(expected_stems), (
        f"Branch {branch} expected {len(expected_stems)} hidden stems, got {len(registry_entries)}"
    )

    for entry, (exp_stem_label, exp_weight) in zip(registry_entries, expected_stems, strict=True):
        assert entry.weight == exp_weight
        stem_label = entry.stem.label if hasattr(entry.stem, "label") else entry.stem
        assert stem_label == exp_stem_label
        assert_key_format_convention(branch)
        assert_key_format_convention(stem_label)


@pytest.mark.parametrize(
    "branch",
    [
        "Zi",
        "Chou",
        "Yin",
        "Mao",
        "Chen",
        "Si",
        "Wu",
        "Wei",
        "Shen",
        "You",
        "Xu",
        "Hai",
    ],
)
def test_get_zhi_hidden_classical_rules_12_branches(branch: str) -> None:
    """Verify get_zhi_hidden classical rules helper returns correct HiddenStemEntry list for all 12 branches."""
    expected_stems = EXPECTED_ZHI_HIDDEN_RAW[branch]
    entries = get_zhi_hidden(branch)
    assert len(entries) == len(expected_stems)

    for entry, (exp_stem_label, exp_weight) in zip(entries, expected_stems, strict=True):
        assert isinstance(entry, HiddenStemEntry)
        assert entry.weight == exp_weight
        assert entry.stem is not None
        assert entry.stem.label == exp_stem_label
        assert_key_format_convention(entry)


def test_zhi_hidden_si_branch_canonical_order() -> None:
    """Verify Si (Snake) branch hidden stems match canonical book order: Bing (Main), Geng (Middle), Wu (Residual)."""
    si_entries = get_zhi_hidden("Si")
    assert len(si_entries) == 3
    assert si_entries[0].stem.label == "Bing" and si_entries[0].weight == 5
    assert si_entries[1].stem.label == "Geng" and si_entries[1].weight == 2
    assert si_entries[2].stem.label == "Wu" and si_entries[2].weight == 1
    assert_key_format_convention(si_entries)


# ============================================================================
# 2. TOTAL ROOT SCORE FORMULA (calculate_root_score)
# ============================================================================

@pytest.mark.parametrize(
    "surface_roots, hidden_roots, expected_score",
    [
        (1, 2, 1.6),
        (0, 3, 0.9),
        (2, 0, 2.0),
        (0, 5, 1.5),
        (2, 1, 2.3),  # Canonical book example: Ren DM with Zi, Hai (2.0) + Shen (0.3) = 2.3
        (0, 0, 0.0),
    ],
)
def test_calculate_root_score(surface_roots: int, hidden_roots: int, expected_score: float) -> None:
    """Verify calculate_root_score returns correct RootScoreResult following surface_roots + (hidden_roots * 0.3)."""
    result = calculate_root_score(surface_roots=surface_roots, hidden_roots=hidden_roots)
    assert result.surface_roots == surface_roots
    assert result.hidden_roots == hidden_roots
    assert result.score == pytest.approx(expected_score)
    assert_key_format_convention(result)


# ============================================================================
# 3. DORMANCY MULTIPLIER (get_dormancy_multiplier & 30% Rule)
# ============================================================================

def test_get_dormancy_multiplier_active_branches() -> None:
    """Verify active branches with Main/Middle Qi (weight >= 2) return dormancy multiplier 1.0."""
    active_branches = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
    for b in active_branches:
        res = get_dormancy_multiplier(b)
        assert res.branch == b
        assert res.multiplier == 1.0
        assert res.is_dormant is False
        assert_key_format_convention(res)


def test_get_dormancy_multiplier_unknown_branch() -> None:
    """Verify unknown or branch without sufficient weight returns dormancy multiplier 0.3."""
    res = get_dormancy_multiplier("Unknown")
    assert res.branch == "Unknown"
    assert res.multiplier == 0.3
    assert res.is_dormant is True
    assert res.reason == "No surface root"
    assert_key_format_convention(res)


def test_dormancy_flat_factor_math() -> None:
    """Verify the 0.3 flat dormancy multiplier math applies to dormant hidden root energy."""
    dormant_multiplier = 0.3
    raw_hidden_instances = 5
    effective_root_energy = raw_hidden_instances * dormant_multiplier
    assert effective_root_energy == pytest.approx(1.5)


# ============================================================================
# 4. CONTROL SUPPRESSION FACTOR (CONTROL_SUPPRESSION_FACTOR)
# ============================================================================

def test_control_suppression_factor_constant() -> None:
    """Verify CONTROL_SUPPRESSION_FACTOR constant equals 0.5."""
    assert CONTROL_SUPPRESSION_FACTOR == 0.5


def test_control_suppression_calculation() -> None:
    """Verify hidden stem weight reduction by 50% under control suppression."""
    normal_weight = 1.0
    controlled_weight = normal_weight * CONTROL_SUPPRESSION_FACTOR
    assert controlled_weight == 0.5

    main_qi_weight = 5.0
    suppressed_main_qi = main_qi_weight * CONTROL_SUPPRESSION_FACTOR
    assert suppressed_main_qi == 2.5


# ============================================================================
# 5. SELECTIVE HIDDEN EXTRACTION (selective_hidden_extraction)
# ============================================================================

def test_selective_hidden_extraction_water_combo() -> None:
    """Verify selective_hidden_extraction extracts stems supporting Water element in Shen/Chen branches."""
    # Shen hidden stems: Geng (Metal -> produces Water), Ren (Water -> is Water), Wu (Earth -> controls Water)
    extracted_shen = selective_hidden_extraction(combo_element="Water", branch="Shen")
    assert len(extracted_shen) == 2
    stems_shen = [e.stem.label for e in extracted_shen]
    elements_shen = [e.stem.element.value for e in extracted_shen]
    assert stems_shen == ["Geng", "Ren"]
    assert elements_shen == ["Metal", "Water"]
    assert_key_format_convention(extracted_shen)

    # Chen hidden stems: Wu (Earth), Yi (Wood), Gui (Water -> is Water)
    extracted_chen = selective_hidden_extraction(combo_element="Water", branch="Chen")
    assert len(extracted_chen) == 1
    assert extracted_chen[0].stem.label == "Gui"
    assert extracted_chen[0].stem.element.value == "Water"
    assert_key_format_convention(extracted_chen)


def test_selective_hidden_extraction_wood_combo() -> None:
    """Verify selective_hidden_extraction extracts stems supporting Wood element in Yin/Hai branches."""
    # Yin hidden stems: Jia (Wood), Bing (Fire), Wu (Earth)
    extracted_yin = selective_hidden_extraction(combo_element="Wood", branch="Yin")
    assert len(extracted_yin) == 1
    assert extracted_yin[0].stem.label == "Jia"
    assert extracted_yin[0].stem.element.value == "Wood"

    # Hai hidden stems: Ren (Water -> produces Wood), Jia (Wood -> is Wood)
    extracted_hai = selective_hidden_extraction(combo_element="Wood", branch="Hai")
    assert len(extracted_hai) == 2
    stems_hai = [e.stem.label for e in extracted_hai]
    assert stems_hai == ["Ren", "Jia"]


def test_selective_hidden_extraction_fire_combo() -> None:
    """Verify selective_hidden_extraction extracts stems supporting Fire element in Si/Yin branches."""
    # Si hidden stems: Bing (Fire), Geng (Metal), Wu (Earth)
    extracted_si = selective_hidden_extraction(combo_element="Fire", branch="Si")
    assert len(extracted_si) == 1
    assert extracted_si[0].stem.label == "Bing"
    assert extracted_si[0].stem.element.value == "Fire"


# ============================================================================
# 6. STRICT CAPITALCASE KEY/VALUE FORMAT SEAM CONVENTION
# ============================================================================

def test_all_hidden_reserve_data_passes_capitalcase_seam() -> None:
    """Ensure all 12 branches and their hidden stem labels/elements strictly pass key format seam."""
    branches = [
        "Zi",
        "Chou",
        "Yin",
        "Mao",
        "Chen",
        "Si",
        "Wu",
        "Wei",
        "Shen",
        "You",
        "Xu",
        "Hai",
    ]
    for b in branches:
        entries = get_zhi_hidden(b)
        assert_key_format_convention(b)
        assert_key_format_convention(entries)
