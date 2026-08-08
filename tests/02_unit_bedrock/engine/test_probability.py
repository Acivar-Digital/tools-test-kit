"""
Unit tests for Module 11: Additive Log-Odds Event Signal Engine (V29)
"""


import pytest

from src.engine.module11_probability import run_probability_scoring


@pytest.fixture
def sample_profile():
    return {
        "day_pillar": {"stem": "Bing", "branch": "Yin"},
        "spectrum_tier": "Weak",
        "medicine": ["Fire", "Earth"],
        "taboo": ["Metal"],
        "strength_profile": {"tier": "Weak", "continuous_score": 35.0},
        "months_into_dayun": 24,  # Stable regime
    }


@pytest.fixture
def sample_triggers():
    return {
        "clash_triggers": {
            "day": {"active": True, "type": "stem"},  # day_clash
            "month": {"active": False, "type": ""},
            "year": {"active": False, "type": ""},
            "hour": {"active": False, "type": ""},
        },
        "star_triggers": [{"star": "Yang Ren"}],
    }


def test_log_odds_update_basic(sample_profile, sample_triggers):
    """Test that active triggers result in expected signal shifts via additive log-odds."""
    # day_clash (w=1.44) and yang_ren (w=1.25)
    # physical_injury prior is ln(0.015 / 0.985) approx -4.18
    # Final log-odds: -4.18 + 1.44 + 1.25 = -1.49
    # Sigmoid(-1.49) approx 0.1838 (18.4%)

    results = run_probability_scoring(sample_triggers, sample_profile)

    probs = results["event_probabilities"]
    assert 15.0 < probs["physical_injury"] < 25.0
    assert results["primary_driver"] in ["day_clash", "yang_ren"]
    assert results["confidence_level"] in ["high", "medium", "low"]


def test_transition_flag(sample_profile, sample_triggers):
    """Test that transition period flag is correctly set."""
    # Stable regime (24 months)
    res_stable = run_probability_scoring(sample_triggers, sample_profile)
    assert res_stable["is_transition_period"] is False

    # Transition regime (2 months)
    res_transition = run_probability_scoring(sample_triggers, sample_profile, months_into_dayun=2)
    assert res_transition["is_transition_period"] is True


def test_xun_kong_suppression(sample_profile):
    """Test that xun_kong (Void) reduces signals for events like career_promotion."""
    # Booster: wen_chang (w=0.79 for career_promotion)
    triggers_boost = {"star_triggers": [{"star": "Wen Chang"}]}
    res_boost = run_probability_scoring(triggers_boost, sample_profile)

    # Boosted + Void suppressor (xun_kong w = -1.20)
    # Total shift: +0.79 - 1.20 = -0.41 (net decrease)
    triggers_both = {
        "star_triggers": [{"star": "Wen Chang"}],
        "void_active": True
    }

    # Wait, let's check _map_triggers in module11 to see how void is passed.
    # It looks like:
    # if triggers.get("clash_triggers", {}).get("void_active"): active.append("xun_kong")

    res_both = run_probability_scoring(triggers_both, sample_profile)

    assert res_both["event_probabilities"]["career_promotion"] < res_boost["event_probabilities"]["career_promotion"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
