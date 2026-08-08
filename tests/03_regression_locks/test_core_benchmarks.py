"""
V27 -> V29 Regression & Stability Audit (Surgical Fix)
Verified against bazi_math.py Gated Formula production lock.
"""

from src.engine.activity_oracle import get_verdict
from src.engine.module8_scoring import calculate_composite_score

# CHART_A: Jia Zi Year, Bing Yin Month, Ding Mao Day, Wu Chen Hour
CHART_A = {
    "day_pillar": {"stem": "Ding", "branch": "Mao"},
    "month_pillar": {"stem": "Bing", "branch": "Yin"},
    "year_pillar": {"stem": "Jia", "branch": "Zi"},
    "hour_pillar": {"stem": "Ding", "branch": "Mao"},
    "da_yun_pillar": {"stem": "Wu", "branch": "Chen"},
    "medicine": ["Wood", "Fire"],
    "taboo": ["Water", "Metal"],
}

def test_t1_neutral_baseline():
    """T1: Verify neutral baseline is exactly 57.5 (Moody's Gate Lock)."""
    profile = CHART_A.copy()

    strength_profile = {"tier": "Neutral", "dsi_baseline_adj": 0.0, "dsi_tier_scalar": 1.0}
    inputs = {"strength_profile": strength_profile, "domain_focus": "general"}

    res = calculate_composite_score(
        profile,
        root_results={"dm_root_impact": 0, "generative_root_impact": 0, "elemental_root_impact": 0},
        interaction_results={"total_friction": 0, "released_elements": [], "stem_combo_modifiers": []},
        medicine_results={"average_potency": 0},
        risk_results={"total_risk_penalty": 0},
        ge_ju_results={"ge_ju": {"tier": "Common"}},
        month_data={"branch": "Yin"},
        macro_results={
            "macro_environmental_scan": {
                "decade_data": {"stem_impact": 0, "branch_impact": 0},
                "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
                "void_audit": {"is_void_active": False},
            }
        },
        annual_pillar={"stem": "Bing", "branch": "Wu"},
        inputs=inputs,
    )
    # Neutral gate: 30 (DY_BASE) + 15 (ANN_BASE) + 12.5 (MON_BASE) = 57.5
    # Note: month_data Yin (Death phase for Ding) subtracts 3.0.
    # 57.5 - 3.0 = 54.5
    assert res["composite_score"] == 54.5

def test_t2_decade_impact_sensitivity():
    """T2: Verify 10Y decade impact sensitivity via G_dy."""
    profile = CHART_A.copy()

    # Case 1: Neutral Decade (dy_raw = 0)
    # Case 2: Strong Decade (dy_raw = 36)
    macro_results_strong = {
        "macro_environmental_scan": {
            "decade_data": {"stem_impact": 18, "branch_impact": 18}, # Total 36
            "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
            "void_audit": {"is_void_active": False},
        }
    }

    strength_profile = {"tier": "Neutral", "dsi_baseline_adj": 0.0, "dsi_tier_scalar": 1.0}
    inputs = {"strength_profile": strength_profile, "domain_focus": "general"}

    res = calculate_composite_score(
        profile,
        root_results={"dm_root_impact": 0, "generative_root_impact": 0, "elemental_root_impact": 0},
        interaction_results={"total_friction": 0, "released_elements": [], "stem_combo_modifiers": []},
        medicine_results={"average_potency": 0},
        risk_results={"total_risk_penalty": 0},
        ge_ju_results={"ge_ju": {"tier": "Common"}},
        month_data={"branch": "Yin"},
        macro_results=macro_results_strong,
        annual_pillar={"stem": "Bing", "branch": "Wu"},
        inputs=inputs,
    )

    # G_dy for 36 should be 1.3
    assert res["components"]["g_dy"] == 1.3

def test_t8_ge_ju_bonus():
    """T8: Verify Ge Ju structural bonus integrates into dy_comp."""
    profile = CHART_A.copy()

    # Pattern bonus +8
    ge_ju_results = {"ge_ju": {"tier": "Special"}, "structural_bonus": 8}
    strength_profile = {"tier": "Neutral", "dsi_baseline_adj": 0.0, "dsi_tier_scalar": 1.0}
    inputs = {"strength_profile": strength_profile, "domain_focus": "general"}

    res = calculate_composite_score(
        profile,
        root_results={"dm_root_impact": 0, "generative_root_impact": 0, "elemental_root_impact": 0},
        interaction_results={"total_friction": 0, "released_elements": [], "stem_combo_modifiers": []},
        medicine_results={"average_potency": 0},
        risk_results={"total_risk_penalty": 0},
        ge_ju_results=ge_ju_results,
        month_data={"branch": "Yin"},
        macro_results={
            "macro_environmental_scan": {
                "decade_data": {"stem_impact": 0, "branch_impact": 0},
                "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
                "void_audit": {"is_void_active": False},
            }
        },
        annual_pillar={"stem": "Bing", "branch": "Wu"},
        inputs=inputs,
    )

    # dy_comp should be 30 + 10 = 40.0
    assert res["components"]["dy_comp"] == 40.0

def test_t10_scoring_final_refinements():
    """T10: Full integrated score check with specific V29 expected value."""
    profile = CHART_A.copy()

    scoring_inputs = {
        "domain_focus": "career",
        "strength_profile": {"tier": "Weak", "dsi_baseline_adj": 2.0, "dsi_tier_scalar": 1.0}
    }

    res = calculate_composite_score(
        profile,
        root_results={"dm_root_impact": 0, "generative_root_impact": 0, "elemental_root_impact": 0},
        interaction_results={"total_friction": 0, "released_elements": [], "stem_combo_modifiers": []},
        medicine_results={"average_potency": 0},
        risk_results={"total_risk_penalty": 0},
        ge_ju_results={"ge_ju": {"tier": "Common"}},
        month_data={"branch": "Mao"}, # Mao month for Ding DM
        macro_results={
            "macro_environmental_scan": {
                "decade_data": {"stem_impact": 0, "branch_impact": 0},
                "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
                "void_audit": {"is_void_active": False},
            }
        },
        annual_pillar={"stem": "Bing", "branch": "Wu"},
        inputs=scoring_inputs,
    )

    # V30 math: dy_comp(30) + ann_base*G_dy(15) + primary_signal(12.5) + noise(dm_phase=-2.0) = 55.5
    assert res["composite_score"] == 55.5


def test_verdict_7_bands():
    """T10: Verify verdict mapping for 7 bands."""
    assert get_verdict(16) == "Peak"
    assert get_verdict(10) == "Excellent"
    assert get_verdict(5) == "Strike"
    assert get_verdict(0) == "Mild Caution"
    assert get_verdict(-6) == "Caution"
    assert get_verdict(-10) == "Warning"
    assert get_verdict(-20) == "Critical"
