"""TEST/math/test_orchestrator_dead_code_gate.py — Orchestrator Dead-Code Verification Gate.

End-to-end verification of orchestrator.run_full_engine() across diverse chart configurations.
Asserts:
  1. Output state traceability:
     - self_punished_branches populated when self-punishing branch repeats are present.
     - dm_luck_label / dm_luck_interaction present and non-empty.
     - combination clash net logic applied and traceable.
  2. Zero uncalled or dead restored helper functions in orchestrator active pipeline.
  3. Strict English CapitalCase key-format convention (e.g., 'Jia', 'Zi', 'Wood') across
     all returned engine output objects with zero Chinese characters.
"""

import ast
from pathlib import Path

from src2.core.schemas import ComboClashNetResult, EngineOutput
from src2.core.schemas.unified import ChartProfile, Pillar
from src2.engine.contradiction_resolver import calculate_combo_clash_net
from src2.engine.orchestrator import run_full_engine
from TEST.math.conftest import assert_key_format_convention


def _create_chart(
    year_stem: str,
    year_branch: str,
    month_stem: str,
    month_branch: str,
    day_stem: str,
    day_branch: str,
    hour_stem: str,
    hour_branch: str,
    gender: str = "M",
    dob: str = "2026-05-15",
) -> ChartProfile:
    """Construct a ChartProfile helper for orchestrator testing."""
    return ChartProfile(
        gender=gender,
        dob=dob,
        year_pillar=Pillar(stem=year_stem, branch=year_branch),
        month_pillar=Pillar(stem=month_stem, branch=month_branch),
        day_pillar=Pillar(stem=day_stem, branch=day_branch),
        hour_pillar=Pillar(stem=hour_stem, branch=hour_branch),
    )


# ============================================================================
# 1. END-TO-END EXECUTION ON DIVERSE CHART CONFIGURATIONS
# ============================================================================

def test_end_to_end_engine_execution_on_diverse_charts() -> None:
    """Verify that run_full_engine() completes without errors on diverse chart types."""
    # Chart 1: Self-punishment chart (Wu-Wu repeat)
    chart_sp = _create_chart("Wu", "Wu", "Bing", "Wu", "Wu", "Wu", "Ren", "Zi")
    out_sp = run_full_engine(chart_sp, target_month_idx=5, target_year=2026)
    assert isinstance(out_sp, EngineOutput)
    assert_key_format_convention(out_sp)

    # Chart 2: Clash + Combination chart (Zi-Wu clash & Zi-Chou combination)
    chart_cc = _create_chart("Jia", "Zi", "Bing", "Wu", "Ji", "Chou", "Geng", "Shen")
    out_cc = run_full_engine(chart_cc, target_month_idx=0, target_year=2026)
    assert isinstance(out_cc, EngineOutput)
    assert_key_format_convention(out_cc)

    # Chart 3: Strong Day Master chart (Jia Wood in Spring)
    chart_strong = _create_chart("Jia", "Yin", "Yi", "Mao", "Jia", "Yin", "Bing", "Chen")
    out_strong = run_full_engine(chart_strong, target_month_idx=2, target_year=2026)
    assert isinstance(out_strong, EngineOutput)
    assert_key_format_convention(out_strong)

    # Chart 4: Weak Day Master chart (Jia Wood in Autumn)
    chart_weak = _create_chart("Geng", "Shen", "Xin", "You", "Jia", "Xu", "Geng", "Shen")
    out_weak = run_full_engine(chart_weak, target_month_idx=8, target_year=2026)
    assert isinstance(out_weak, EngineOutput)
    assert_key_format_convention(out_weak)


# ============================================================================
# 2. OUTPUT STATE TRACEABILITY TESTS
# ============================================================================

def test_traceability_self_punished_branches() -> None:
    """Verify self_punished_branches is populated when applicable and empty otherwise."""
    # Chart with repeating Wu branches (Wu-Wu self punishment)
    chart_sp = _create_chart("Wu", "Wu", "Bing", "Wu", "Wu", "Wu", "Ren", "Zi")
    out_sp = run_full_engine(chart_sp, target_month_idx=5, target_year=2026)

    sp_branches = out_sp.interactions.self_punished_branches
    assert len(sp_branches) > 0, "self_punished_branches must be populated for chart with double Wu branches."
    assert "Wu" in sp_branches, "'Wu' must be in self_punished_branches for double Wu branches."

    # Chart without self-punishment branch repeats (Zi, Yin, Chen, Shen)
    chart_normal = _create_chart("Jia", "Zi", "Bing", "Yin", "Wu", "Chen", "Ren", "Shen")
    out_normal = run_full_engine(chart_normal, target_month_idx=1, target_year=2026)
    assert out_normal.interactions.self_punished_branches == [], "self_punished_branches must be empty when no self punishment repeats exist."


def test_traceability_dm_luck_label() -> None:
    """Verify dm_luck_label / dm_luck_interaction is present and non-empty in EngineOutputs."""
    chart = _create_chart("Jia", "Zi", "Bing", "Yin", "Wu", "Chen", "Ren", "Shen")
    out = run_full_engine(chart, target_month_idx=3, target_year=2026)

    assert out.engine_outputs is not None, "engine_outputs payload must not be None."
    dm_luck_interaction = out.engine_outputs.dm_luck_interaction
    assert isinstance(dm_luck_interaction, str), "dm_luck_interaction must be a string."
    assert len(dm_luck_interaction) > 0, "dm_luck_interaction must be non-empty."


def test_traceability_combo_clash_net() -> None:
    """Verify combination clash net formulas and contradiction resolution outputs."""
    # Direct formula validation for calculate_combo_clash_net
    res_combo_win = calculate_combo_clash_net(combo_strength=8.0, dm_strength=5.0, control_efficiency=1.0)
    assert isinstance(res_combo_win, ComboClashNetResult)
    assert res_combo_win.net_effect == 3.0
    assert res_combo_win.winner == "combination"

    res_dm_win = calculate_combo_clash_net(combo_strength=3.0, dm_strength=5.0, control_efficiency=1.0)
    assert res_dm_win.net_effect == -2.0
    assert res_dm_win.winner == "dm_control"

    res_balanced = calculate_combo_clash_net(combo_strength=5.0, dm_strength=5.0, control_efficiency=1.0)
    assert res_balanced.net_effect == 0.0
    assert res_balanced.winner == "balanced"

    # End-to-end engine contradiction resolution validation
    chart_cc = _create_chart("Jia", "Zi", "Bing", "Wu", "Ji", "Chou", "Geng", "Shen")
    out_cc = run_full_engine(chart_cc, target_month_idx=0, target_year=2026)

    assert out_cc.engine_outputs is not None
    contradictions = out_cc.engine_outputs.contradiction_resolution
    assert contradictions is not None, "contradiction_resolution must be present in engine_outputs."
    assert hasattr(contradictions, "dominant_theme")
    assert hasattr(contradictions, "override_trace")


# ============================================================================
# 3. DEAD-CODE & UNCALLED HELPER GATE
# ============================================================================

def test_zero_dead_code_in_active_orchestrator_pipeline() -> None:
    """AST analysis gate: assert that all functions defined in orchestrator.py are called or registered."""
    orchestrator_path = Path(__file__).resolve().parents[2] / "src2" / "engine" / "orchestrator.py"
    assert orchestrator_path.exists(), f"Orchestrator file not found at {orchestrator_path}"

    with open(orchestrator_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Collect all top-level / module helper functions in orchestrator.py (excluding public entry points)
    public_entry_points = {"run_full_engine"}
    defined_functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name not in public_entry_points
    }

    # Collect all Function/Attribute Call nodes and referenced identifiers in orchestrator.py
    referenced_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                referenced_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                referenced_names.add(node.func.attr)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)

    # Every helper function defined in orchestrator.py must be referenced/called
    uncalled_helpers = []
    for fn_name in defined_functions:
        if fn_name not in referenced_names:
            uncalled_helpers.append(fn_name)

    assert uncalled_helpers == [], f"Uncalled/dead restored helper functions found in orchestrator.py: {uncalled_helpers}"


# ============================================================================
# 4. CAPITALCASE KEY-FORMAT CONVENTION GATE
# ============================================================================

def test_capitalcase_key_format_convention_gate() -> None:
    """Verify that all output state objects enforce English CapitalCase without Chinese characters."""
    chart = _create_chart("Jia", "Zi", "Bing", "Yin", "Wu", "Chen", "Ren", "Shen")
    engine_output = run_full_engine(chart, target_month_idx=1, target_year=2026)

    # Key-format seam assertion recursively checks dictionaries, models, stems, branches, elements
    assert_key_format_convention(engine_output)
    assert_key_format_convention(engine_output.profile)
    assert_key_format_convention(engine_output.interactions)
    assert_key_format_convention(engine_output.root_analysis)
    assert_key_format_convention(engine_output.engine_outputs)
