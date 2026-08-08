"""
Bazi Math Calibration Test — bazi_math.py gate formula verification.

Run with:
    uv run python TEST/regression/test_math_calibration.py

All assertions must pass before any engine module rewrite proceeds.
If any assertion fails, bazi_math.py has been modified incorrectly —
do NOT proceed with module rewrites until fixed.
"""
import os
import sys

sys.path.append(os.getcwd())

from src.engine.bazi_math import (
    ANN_ADVERSE_MAX,
    ANN_BASE,
    ANN_FAVORABLE_MAX,
    DY_BASE,
    DY_MAX,
    MON_BASE,
    MON_CLAMP_HI,
    MON_CLAMP_LO,
    NOISE_CAP,
    SCORE_CEILING,
    SCORE_FLOOR,
    calculate_gated_score,
    gate_ann,
    gate_dy,
    get_dsi_baseline_adj,
    get_dsi_tier_scalar,
    get_spectrum_tier,
)


def _assert(label: str, actual: float, expected: float, tol: float = 0.1) -> None:
    ok = abs(actual - expected) <= tol
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}: got {actual}, expected {expected}")
    if not ok:
        raise AssertionError(f"FAILED: {label} | got {actual} | expected {expected}")


def test_gate_functions() -> None:
    print("\n-- Gate Function Ranges --")
    _assert("G_dy(-36) = 0.7",    gate_dy(-36),  0.7)
    _assert("G_dy(0)   = 1.0",    gate_dy(0),    1.0)
    _assert("G_dy(+36) = 1.3",    gate_dy(+36),  1.3)
    _assert("G_ann(-40) = 0.8",   gate_ann(-40), 0.8)
    _assert("G_ann(0)   = 1.0",   gate_ann(0),   1.0)
    _assert("G_ann(+25) = 1.125", gate_ann(+25), 1.125)


def test_constants() -> None:
    print("\n-- Constants --")
    _assert("DY_MAX = 36",           DY_MAX,            36.0)
    _assert("ANN_ADVERSE_MAX = 40",  ANN_ADVERSE_MAX,   40.0)
    _assert("ANN_FAVORABLE_MAX = 25",ANN_FAVORABLE_MAX, 25.0)
    _assert("DY_BASE = 30",          DY_BASE,           30.0)
    _assert("ANN_BASE = 15",         ANN_BASE,          15.0)
    _assert("MON_BASE = 12.5",       MON_BASE,          12.5)
    _assert("MON_CLAMP_LO = -15",    MON_CLAMP_LO,     -15.0)
    _assert("MON_CLAMP_HI = +15",    MON_CLAMP_HI,     +15.0)
    _assert("NOISE_CAP = 5",         NOISE_CAP,          5.0)
    _assert("SCORE_FLOOR = 35",      SCORE_FLOOR,       35.0)
    _assert("SCORE_CEILING = 80",    SCORE_CEILING,     80.0)


def test_three_anchors() -> None:
    """
    The three mandatory calibration anchors (Primary/Noise split).
    These are the source of truth for the gate formula.
    """
    print("\n-- Three Calibration Anchors --")

    # 1. Neutral — all inputs zero
    r_neutral = calculate_gated_score(dy_raw=0, ann_raw=0)
    _assert("Neutral composite = 57.5", r_neutral["composite_score"], 57.5)
    _assert("Neutral raw = 57.5",       r_neutral["raw_score"],       57.5)

    # 2. Peak — everything at maximum (no dsi_bonus)
    # dy_raw=+36, ann_raw=+25, ge_ju=+8, primary=+27 (clamped +15), noise=+20 (clamped +5)
    r_peak = calculate_gated_score(
        dy_raw=+36,
        ann_raw=+25,
        ge_ju_bonus=+8.0,
        primary_signal_raw=+27.0,
        structural_noise_raw=+20.0,
    )
    _assert("Peak raw ~ 102.7",        r_peak["raw_score"],       102.7, tol=0.5)
    _assert("Peak clamped = 80.0",     r_peak["composite_score"],  80.0)
    _assert("Peak primary_clamped=15", r_peak["primary_clamped"],  15.0)
    _assert("Peak noise_clamped=5",    r_peak["noise_clamped"],     5.0)

    # 3. Worst — everything at minimum (no dsi_bonus)
    # dy_raw=-36, ann_raw=-40, ge_ju=-5, primary=-16 (clamped -15), noise=-20 (clamped -5)
    r_worst = calculate_gated_score(
        dy_raw=-36,
        ann_raw=-40,
        ge_ju_bonus=-5.0,
        primary_signal_raw=-16.0,
        structural_noise_raw=-20.0,
    )
    _assert("Worst raw ~ 29.1",         r_worst["raw_score"],       29.1, tol=0.5)
    _assert("Worst clamped = 35.0",    r_worst["composite_score"],  35.0)
    _assert("Worst primary_clamped=-15", r_worst["primary_clamped"], -15.0)
    _assert("Worst noise_clamped=-5",    r_worst["noise_clamped"],    -5.0)


def test_era_ceiling() -> None:
    """Era ceiling verification (Ji Shen era ceiling caps score at 71 regardless of raw)."""
    print("\n-- Era Ceiling --")

    # With era_ceiling=71, a peak-like scenario should cap at 71
    r_hostile = calculate_gated_score(
        dy_raw=+36,
        ann_raw=+25,
        ge_ju_bonus=+8.0,
        primary_signal_raw=+15.0,
        structural_noise_raw=+5.0,
        era_ceiling=71.0,
    )
    _assert("Ji Shen era capped = 71.0", r_hostile["composite_score"], 71.0)
    _assert("Ji Shen era raw > 71",      r_hostile["raw_score"] > 71, True)

    # With era_ceiling=80 (default), same inputs should cap at 80
    r_default = calculate_gated_score(
        dy_raw=+36,
        ann_raw=+25,
        ge_ju_bonus=+8.0,
        primary_signal_raw=+15.0,
        structural_noise_raw=+5.0,
        era_ceiling=80.0,
    )
    _assert("Default era capped = 80.0", r_default["composite_score"], 80.0)


def test_noise_cap() -> None:
    """Structural noise alone cannot move score by more than 5."""
    print("\n-- Noise Cap --")

    # Neutral baseline with only structural noise (extreme positive)
    r_pos = calculate_gated_score(
        dy_raw=0,
        ann_raw=0,
        structural_noise_raw=+100.0,
    )
    _assert("Noise +100 capped to +5", r_pos["noise_clamped"], 5.0)
    _assert("Score with max noise = 62.5", r_pos["composite_score"], 62.5)

    # Neutral baseline with only structural noise (extreme negative)
    r_neg = calculate_gated_score(
        dy_raw=0,
        ann_raw=0,
        structural_noise_raw=-100.0,
    )
    _assert("Noise -100 capped to -5", r_neg["noise_clamped"], -5.0)
    _assert("Score with min noise = 52.5", r_neg["composite_score"], 52.5)


def test_spectrum_tiers() -> None:
    print("\n-- Spectrum Tier Mapping --")
    cases = [
        (90.0,  "Vibrant"),
        (65.0,  "Very Strong"),
        (40.0,  "Strong"),
        (15.0,  "Mild Strong"),
        (-15.0, "Mild Weak"),
        (-40.0, "Weak"),
        (-65.0, "Very Weak"),
        (-90.0, "Follower"),
    ]
    for score, expected_tier in cases:
        tier = get_spectrum_tier(score)
        ok = tier == expected_tier
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] score={score:+.1f} -> {tier} (expected {expected_tier})")
        if not ok:
            raise AssertionError(f"Tier mismatch at {score}: got {tier}, expected {expected_tier}")


def test_dsi_tables() -> None:
    print("\n-- DSI Tables --")
    _assert("DSI adj Vibrant = -3.0",  get_dsi_baseline_adj("Vibrant"),  -3.0)
    _assert("DSI adj Follower = +3.0", get_dsi_baseline_adj("Follower"),  3.0)
    _assert("DSI scalar Vibrant = 0.5", get_dsi_tier_scalar("Vibrant"),   0.5)
    _assert("DSI scalar Follower = 1.5",get_dsi_tier_scalar("Follower"),  1.5)
    _assert("DSI scalar Mild Weak=1.2", get_dsi_tier_scalar("Mild Weak"), 1.2)


def test_gate_trace_keys() -> None:
    """Ensure calculate_gated_score returns all required trace keys."""
    print("\n-- Return Dict Keys --")
    required = {"composite_score", "raw_score", "g_dy", "g_ann",
                "dy_comp", "primary_signal", "primary_clamped",
                "noise_clamped", "era_ceiling"}
    result = calculate_gated_score(dy_raw=0, ann_raw=0)
    missing = required - set(result.keys())
    if missing:
        print(f"  [FAIL] Missing keys: {missing}")
        raise AssertionError(f"Missing keys in return dict: {missing}")
    print(f"  [PASS] All {len(required)} required keys present")


if __name__ == "__main__":
    print("Bazi Math Calibration Test -- bazi_math.py")
    print("=" * 45)

    test_constants()
    test_gate_functions()
    test_three_anchors()
    test_era_ceiling()
    test_noise_cap()
    test_spectrum_tiers()
    test_dsi_tables()
    test_gate_trace_keys()

    print("\n" + "=" * 45)
    print("ALL ASSERTIONS PASSED. Ready for engine module updates.")
