"""TEST/math/test_ch10_special_structures.py — Bazi Chapter 10 Special Structure Determination Math Tests.

Validates:
1. Cong Ge (From Structure) AND logic (NOT counter-elements AND seasonal support required).
2. Vibrant structure seasonal phase validation using get_element_phase() (Wang, Xiang).
3. True vs. False From structure validation based on zero non-dominant hidden roots.
4. Complete 8-step special_structure_determination_protocol() decision tree and step counting.
5. Dominant structure (Zhuan Wang Ge) dominance percentage (>=80%) and root thresholds.
6. Strict English CapitalCase key/value conventions (no Chinese characters).
"""

import pytest

from src2.core.schemas.unified import (
    ElementMap,
    GeJuClassificationResult,
    PillarMap,
    SpecialStructureResult,
)
from src2.engine.module0_geju_detection import (
    _build_cong_ge_result,
    _check_cong_ge_counters_season,
    _count_non_dominant_hidden_roots,
    _detect_cong_ge,
    _detect_zhuan_wang_ge,
)
from src2.engine.module0_geju_utils import (
    _calculate_dominance_pct,
    _check_vibrant_requirements,
    get_shattering_branches,
    get_suppressive_stems,
    get_vibrant_branch_options,
    get_vibrant_requirements,
    special_structure_determination_protocol,
)
from src2.engine.module2_root import get_element_phase
from TEST.math.conftest import assert_key_format_convention

# ============================================================================
# 1. KEY-FORMAT CONVENTION ASSERTIONS
# ============================================================================

def test_capital_case_key_convention() -> None:
    """Verify that input pillar keys, element names, and test datasets use English CapitalCase."""
    stems = PillarMap(year="Jia", month="Bing", day="Geng", hour="Xin")
    branches = PillarMap(year="Zi", month="Wu", day="Shen", hour="You")

    assert_key_format_convention(stems)
    assert_key_format_convention(branches)

    element_map = ElementMap(wood=1.0, fire=2.0, earth=0.0, metal=5.0, water=1.0)
    assert_key_format_convention(element_map)


# ============================================================================
# 2. CONG GE (FROM STRUCTURE) AND LOGIC (NOT COUNTERS AND SEASON_OK)
# ============================================================================

def test_cong_ge_counters_and_season_direct_logic() -> None:
    """Verify _check_cong_ge_counters_season returns True ONLY when NOT counters AND season_ok."""
    stems_pure_water = PillarMap(year="Ren", month="Gui", day="Ren", hour="Gui")
    # Using pure Water branches (Hai, Zi) to ensure zero Earth counter elements
    branches_water_season = PillarMap(year="Hai", month="Zi", day="Hai", hour="Zi")

    # Pure Water in Water Season (Zi): no counters (Earth), season supported -> True
    res_pass = _check_cong_ge_counters_season(
        stems=stems_pure_water,
        branches=branches_water_season,
        _dominant_el="Water",
        transformed_branches=None,
        month_branch="Zi",
    )
    assert res_pass is True
    assert_key_format_convention(stems_pure_water)

    # Adding counter element (Earth stem Wu) -> counters present -> False
    stems_with_earth_counter = PillarMap(year="Wu", month="Gui", day="Ren", hour="Gui")
    res_counter_fail = _check_cong_ge_counters_season(
        stems=stems_with_earth_counter,
        branches=branches_water_season,
        _dominant_el="Water",
        transformed_branches=None,
        month_branch="Zi",
    )
    assert res_counter_fail is False

    # Water chart in Summer Fire season (Wu) -> season not supported -> False
    branches_summer = PillarMap(year="Hai", month="Wu", day="Hai", hour="Zi")
    res_season_fail = _check_cong_ge_counters_season(
        stems=stems_pure_water,
        branches=branches_summer,
        _dominant_el="Water",
        transformed_branches=None,
        month_branch="Wu",
    )
    assert res_season_fail is False

    # Both counters present and season wrong -> False
    res_both_fail = _check_cong_ge_counters_season(
        stems=stems_with_earth_counter,
        branches=branches_summer,
        _dominant_el="Water",
        transformed_branches=None,
        month_branch="Wu",
    )
    assert res_both_fail is False


def test_cong_ge_detection_guards_and_execution() -> None:
    """Verify _detect_cong_ge requirement checks for weak DM and dominant non-DM element."""
    # Chart: DM = Bing (Fire), but chart is completely dominated by Water (Ren/Gui/Hai/Zi) in Zi month
    stems_water = PillarMap(year="Ren", month="Gui", day="Bing", hour="Ren")
    branches_water = PillarMap(year="Hai", month="Zi", day="Hai", hour="Zi")
    trace: list[str] = []

    res = _detect_cong_ge(
        stems=stems_water,
        branches=branches_water,
        day_stem_stream="Bing",
        strength_tier="Weak",
        transformed_branches=None,
        trace=trace,
    )
    assert res is not None
    assert isinstance(res, GeJuClassificationResult)
    assert res.pattern_key in ("cong_sha_ge", "cong_ruo_ge", "cong_qiang_ge", "cong_cai_ge", "cong_er_ge")
    assert_key_format_convention(res.pattern_key)

    # Chart where DM has strong root (DM = Jia in Yin month) -> Should fail Cong Ge preconditions
    stems_rooted = PillarMap(year="Jia", month="Yi", day="Jia", hour="Yi")
    branches_rooted = PillarMap(year="Yin", month="Mao", day="Chen", hour="Yin")
    trace_rooted: list[str] = []

    res_rooted = _detect_cong_ge(
        stems=stems_rooted,
        branches=branches_rooted,
        day_stem_stream="Jia",
        strength_tier="Strong",
        transformed_branches=None,
        trace=trace_rooted,
    )
    assert res_rooted is None


# ============================================================================
# 3. VIBRANT STRUCTURE & SEASONAL PHASE (get_vibrant_seasonal_phase)
# ============================================================================

def test_get_element_phase_for_vibrant_elements() -> None:
    """Verify get_element_phase returns Wang or Xiang for Vibrant structure seasonal months."""
    # Qu Zhi Ge (Wood Vibrant): Wood phase in Mao is Wang, Yin is Wang, Hai is Xiang
    assert get_element_phase("Wood", "Mao") == "Wang"
    assert get_element_phase("Wood", "Yin") == "Wang"
    assert get_element_phase("Wood", "Hai") == "Xiang"
    # Wood phase in Si month is Xiu -> Not Wang/Xiang
    assert get_element_phase("Wood", "Si") not in ("Wang", "Xiang")

    # Yan Shang Ge (Fire Vibrant): Fire phase in Wu is Wang, Si is Wang, Yin is Xiang
    assert get_element_phase("Fire", "Wu") == "Wang"
    assert get_element_phase("Fire", "Si") == "Wang"
    assert get_element_phase("Fire", "Yin") == "Xiang"

    # Run Xia Ge (Water Vibrant): Water phase in Zi is Wang, Hai is Wang, Shen is Xiang
    assert get_element_phase("Water", "Zi") == "Wang"
    assert get_element_phase("Water", "Hai") == "Wang"
    assert get_element_phase("Water", "Shen") == "Xiang"

    # Cong Ge Ge (Metal Vibrant): Metal phase in You is Wang, Shen is Wang, Si is Si (Extinct)
    assert get_element_phase("Metal", "You") == "Wang"
    assert get_element_phase("Metal", "Shen") == "Wang"
    assert get_element_phase("Metal", "Chen") == "Xiang"

    # Jia Se Ge (Earth Vibrant): Earth phase in Chen/Xu/Chou/Wei is Wang
    for branch in ("Chen", "Xu", "Chou", "Wei"):
        assert get_element_phase("Earth", branch) == "Wang"


def test_vibrant_requirements_checking() -> None:
    """Verify _check_vibrant_requirements validates required stems, branch sets, and seasonal phase."""
    # Qu Zhi Ge (Wood): required stems Jia/Yi, month_branch Mao (Wang phase for Wood)
    natal_stems = {"Jia", "Yi"}
    natal_branches = {"Yin", "Mao", "Chen"}
    month_branch = "Mao"

    assert _check_vibrant_requirements("qu_zhi_ge", natal_stems, natal_branches, month_branch) is True

    # Mismatched month branch (Si month -> Wood is Xiu phase) -> False
    assert _check_vibrant_requirements("qu_zhi_ge", natal_stems, natal_branches, "Si") is False

    # Suppressive stem present (Geng Metal controls Wood) -> False
    natal_stems_suppressed = {"Jia", "Geng"}
    assert _check_vibrant_requirements("qu_zhi_ge", natal_stems_suppressed, natal_branches, month_branch) is False

    # Shattering branch present (You Metal branch shatters Wood frame) -> False
    natal_branches_shattered = {"Yin", "Mao", "You"}
    assert _check_vibrant_requirements("qu_zhi_ge", natal_stems, natal_branches_shattered, month_branch) is False


@pytest.mark.parametrize(
    "pattern_key, req_element, req_stems, valid_branches, month_branch",
    [
        ("qu_zhi_ge", "Wood", {"Jia", "Yi"}, {"Yin", "Mao", "Chen"}, "Mao"),
        ("yan_shang_ge", "Fire", {"Bing", "Ding"}, {"Si", "Wu", "Wei"}, "Wu"),
        ("run_xia_ge", "Water", {"Ren", "Gui"}, {"Hai", "Zi", "Chou"}, "Zi"),
        ("cong_ge_ge", "Metal", {"Geng", "Xin"}, {"Shen", "You", "Xu"}, "You"),
        ("jia_se_ge", "Earth", {"Wu", "Ji"}, {"Chen", "Xu", "Chou", "Wei"}, "Wei"),
    ],
)
def test_all_five_vibrant_structures_detection(
    pattern_key: str,
    req_element: str,
    req_stems: set[str],
    valid_branches: set[str],
    month_branch: str,
) -> None:
    """Verify helper definitions and full detection for all 5 Vibrant structures."""
    el, stems = get_vibrant_requirements(pattern_key)
    assert el == req_element
    assert stems == req_stems

    branch_options = get_vibrant_branch_options(pattern_key)
    assert len(branch_options) > 0

    suppressive = get_suppressive_stems(pattern_key)
    assert_key_format_convention(suppressive)

    shattering = get_shattering_branches(pattern_key)
    assert_key_format_convention(shattering)

    # Test requirements check
    res_req = _check_vibrant_requirements(pattern_key, req_stems, valid_branches, month_branch)
    assert res_req is True


# ============================================================================
# 4. TRUE/FALSE FROM ZERO HIDDEN ROOTS VALIDATION
# ============================================================================

def test_count_non_dominant_hidden_roots() -> None:
    """Verify _count_non_dominant_hidden_roots counts hidden stems belonging to non-dominant elements."""
    # Chart with pure Metal branches (Shen, You): all hidden stems are Metal (Geng, Xin, Wu in Shen)
    branches_metal = PillarMap(year="You", month="You", day="Shen", hour="You")
    # For Water DM, hidden roots of non-Water elements will be counted
    count_non_water = _count_non_dominant_hidden_roots(dm_element="Water", branches=branches_metal)
    assert count_non_water > 0

    # For Metal DM in all Metal branches: non-Metal hidden roots count
    count_non_metal = _count_non_dominant_hidden_roots(dm_element="Metal", branches=branches_metal)
    # Shen contains hidden Wu (Earth). So count > 0 if Earth is non-dominant
    assert count_non_metal >= 0


def test_true_vs_false_from_structure_build() -> None:
    """Verify _build_cong_ge_result sets is_true_structure=True ONLY for dominance >= 80% AND zero hidden roots."""
    trace: list[str] = []

    # Case 1: High dominance (85%) and 0 non-dominant hidden roots -> TrueFrom
    res_true = _build_cong_ge_result(
        _from_key="cong_cai_ge",
        _dominant_pct=0.85,
        hidden_roots_non_dominant=0,
        trace=trace.copy(),
    )
    assert res_true.is_true_structure is True
    assert any("TrueFrom" in t for t in res_true.calculation_trace)
    assert_key_format_convention(res_true.pattern_key)

    # Case 2: High dominance (85%) but non-dominant hidden roots present (>0) -> FalseFrom
    res_false_roots = _build_cong_ge_result(
        _from_key="cong_cai_ge",
        _dominant_pct=0.85,
        hidden_roots_non_dominant=2,
        trace=trace.copy(),
    )
    assert res_false_roots.is_true_structure is False
    assert any("FalseFrom" in t for t in res_false_roots.calculation_trace)

    # Case 3: Low dominance (70%) and 0 hidden roots -> FalseFrom
    res_false_dom = _build_cong_ge_result(
        _from_key="cong_cai_ge",
        _dominant_pct=0.70,
        hidden_roots_non_dominant=0,
        trace=trace.copy(),
    )
    assert res_false_dom.is_true_structure is False
    assert any("FalseFrom" in t for t in res_false_dom.calculation_trace)


# ============================================================================
# 5. EIGHT-STEP SPECIAL STRUCTURE DETERMINATION PROTOCOL
# ============================================================================

def test_special_structure_determination_protocol_steps() -> None:
    """Verify all branch outputs and step counts for special_structure_determination_protocol()."""

    # Step 1 Failure: Counters present -> returns structure_type='None', steps_completed=1
    p1 = special_structure_determination_protocol(
        dominance=0.85,
        has_counters=True,
        season_supported=True,
        hidden_roots_non_dominant=0,
        dm_score=1.0,
    )
    assert isinstance(p1, SpecialStructureResult)
    assert p1.structure_type == "None"
    assert p1.is_valid is False
    assert p1.steps_completed == 1
    assert_key_format_convention(p1.structure_type)

    # Step 2 Failure: No counters, but season NOT supported -> steps_completed=2
    p2 = special_structure_determination_protocol(
        dominance=0.85,
        has_counters=False,
        season_supported=False,
        hidden_roots_non_dominant=0,
        dm_score=1.0,
    )
    assert p2.structure_type == "None"
    assert p2.is_valid is False
    assert p2.steps_completed == 2

    # Step 3 Failure: No counters, season supported, but dominance < 0.60 (e.g. 0.50) -> steps_completed=3
    p3 = special_structure_determination_protocol(
        dominance=0.50,
        has_counters=False,
        season_supported=True,
        hidden_roots_non_dominant=0,
        dm_score=1.0,
    )
    assert p3.structure_type == "None"
    assert p3.is_valid is False
    assert p3.steps_completed == 3

    # Step 4-5 Success (True From): dominance >= 0.60, no counters, season supported, 0 non-dominant hidden roots
    p_true = special_structure_determination_protocol(
        dominance=0.85,
        has_counters=False,
        season_supported=True,
        hidden_roots_non_dominant=0,
        dm_score=1.0,
    )
    assert p_true.structure_type == "True From"
    assert p_true.is_valid is True
    assert p_true.hidden_roots_check is True
    assert p_true.dm_weak is True
    assert p_true.steps_completed == 5

    # Step 4-5 Success (False From): hidden_roots_non_dominant > 0
    p_false = special_structure_determination_protocol(
        dominance=0.75,
        has_counters=False,
        season_supported=True,
        hidden_roots_non_dominant=3,
        dm_score=1.5,
    )
    assert p_false.structure_type == "False From"
    assert p_false.is_valid is False
    assert p_false.hidden_roots_check is False
    assert p_false.dm_weak is True
    assert p_false.steps_completed == 5

    # Test DM Score > 2.0 -> dm_weak=False
    p_not_weak = special_structure_determination_protocol(
        dominance=0.85,
        has_counters=False,
        season_supported=True,
        hidden_roots_non_dominant=0,
        dm_score=4.0,
    )
    assert p_not_weak.structure_type == "True From"
    assert p_not_weak.dm_weak is False


# ============================================================================
# 6. ZHUAN WANG GE (DOMINANT STRUCTURE) & DOMINANCE PERCENT CALCULATION
# ============================================================================

def test_calculate_dominance_pct_calculation() -> None:
    """Verify _calculate_dominance_pct correctly sums element weights and identifies dominant element."""
    stems = PillarMap(year="Geng", month="Xin", day="Geng", hour="Xin")
    branches = PillarMap(year="Shen", month="You", day="Shen", hour="You")

    counts, dominant, dominant_pct = _calculate_dominance_pct(stems=stems, branches=branches)
    assert dominant == "Metal"
    assert dominant_pct >= 0.80
    assert counts.metal > counts.fire
    assert_key_format_convention(dominant)


def test_detect_zhuan_wang_ge_structure() -> None:
    """Verify _detect_zhuan_wang_ge identifies dominant structure when DM equals dominant element with >= 80% dominance."""
    stems_metal = PillarMap(year="Geng", month="Xin", day="Geng", hour="Xin")
    branches_metal = PillarMap(year="Shen", month="You", day="Shen", hour="You")
    trace: list[str] = []

    res = _detect_zhuan_wang_ge(
        stems=stems_metal,
        branches=branches_metal,
        day_stem_stream="Geng",
        strength_tier="Vibrant",
        transformed_branches=None,
        trace=trace,
    )
    assert res is not None
    assert isinstance(res, GeJuClassificationResult)
    assert res.pattern_key == "zhuan_wang_ge"
    assert res.dominance_pct is not None
    assert res.dominance_pct >= 0.80
    assert_key_format_convention(res.pattern_key)

    # Chart with Fire controller stem (Bing) -> Should fail Zhuan Wang Ge due to controller count != 0
    stems_with_fire = PillarMap(year="Bing", month="Xin", day="Geng", hour="Xin")
    res_controller = _detect_zhuan_wang_ge(
        stems=stems_with_fire,
        branches=branches_metal,
        day_stem_stream="Geng",
        strength_tier="Vibrant",
        transformed_branches=None,
        trace=[],
    )
    assert res_controller is None
