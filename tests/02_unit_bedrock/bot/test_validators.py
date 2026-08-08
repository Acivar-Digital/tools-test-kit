"""
Unit tests for the three new Category A deterministic validators in validators.py.
"""

import pytest

from src.bot.validators import (
    run_pipeline_guard,
    validate_no_suppressed_stars_flagged_active,
    validate_qi_sha_risk_framing,
    validate_ten_gods_consistency,
)
from src.config.prompt_constants import (
    MIN_WORDS_ADVISORY_SECTION,
    MIN_WORDS_NARRATIVE,
    REQUIRED_VOCABULARY,
)

# --- TEST CLASS 1 — validate_ten_gods_consistency ---

def test_no_hallucination_passes():
    month_data = {"assembled_narrative": "The Qi Sha brings pressure while Zheng Guan maintains order."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"},
            "pos2": {"ten_god": "Zheng Guan"}
        }
    }
    assert validate_ten_gods_consistency(month_data, ten_gods_profile) == []

def test_hallucination_detected():
    month_data = {"assembled_narrative": "You may encounter Pian Yin influences today."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"}
        }
    }
    violations = validate_ten_gods_consistency(month_data, ten_gods_profile)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "TEN_GOD_HALLUCINATION"
    assert "'Pian Yin'" in violations[0]["detail"]

def test_multiple_hallucinations():
    month_data = {"assembled_narrative": "Pian Yin and Shi Shen are prominent."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"}
        }
    }
    violations = validate_ten_gods_consistency(month_data, ten_gods_profile)
    assert len(violations) == 2
    rule_ids = [v["rule_id"] for v in violations]
    assert all(rid == "TEN_GOD_HALLUCINATION" for rid in rule_ids)

def test_empty_profile_skips():
    assert validate_ten_gods_consistency({"assembled_narrative": "Qi Sha"}, {}) == []

def test_none_profile_skips():
    assert validate_ten_gods_consistency({"assembled_narrative": "Qi Sha"}, None) == []


# --- TEST CLASS 2 — validate_qi_sha_risk_framing ---

def test_qi_sha_with_risk_word_passes():
    month_data = {"assembled_narrative": "Qi Sha is active, so exercise caution."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"}
        }
    }
    assert validate_qi_sha_risk_framing(month_data, ten_gods_profile) == []

def test_qi_sha_missing_risk_fails():
    month_data = {"assembled_narrative": "Qi Sha is active and you will be very happy."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"}
        }
    }
    violations = validate_qi_sha_risk_framing(month_data, ten_gods_profile)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "QI_SHA_MISSING_RISK_FRAMING"

def test_no_qi_sha_no_check():
    month_data = {"assembled_narrative": "Zheng Guan is active."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Zheng Guan"}
        }
    }
    assert validate_qi_sha_risk_framing(month_data, ten_gods_profile) == []

@pytest.mark.parametrize("keyword", ["risk", "caution", "challenge", "pressure", "conflict", "obstacle", "threat", "stress"])
def test_all_risk_keywords_accepted(keyword):
    month_data = {"assembled_narrative": f"Qi Sha brings some {keyword}."}
    ten_gods_profile = {
        "ten_gods_profile": {
            "pos1": {"ten_god": "Qi Sha"}
        }
    }
    assert validate_qi_sha_risk_framing(month_data, ten_gods_profile) == []


# --- TEST CLASS 3 — validate_no_suppressed_stars_flagged_active ---

def test_suppressed_star_in_triggers_fails():
    activation_matrix = {"Tao Hua": {"state": "suppressed"}}
    trigger_signals = ["Tao Hua"]
    violations = validate_no_suppressed_stars_flagged_active(activation_matrix, trigger_signals)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "SUPPRESSED_STAR_FLAGGED_ACTIVE"

def test_triggered_star_not_flagged():
    activation_matrix = {"Tao Hua": {"state": "triggered"}}
    trigger_signals = ["Tao Hua"]
    assert validate_no_suppressed_stars_flagged_active(activation_matrix, trigger_signals) == []

def test_suppressed_not_in_triggers_passes():
    activation_matrix = {"Tao Hua": {"state": "suppressed"}}
    trigger_signals = []
    assert validate_no_suppressed_stars_flagged_active(activation_matrix, trigger_signals) == []

def test_empty_matrix_skips():
    assert validate_no_suppressed_stars_flagged_active({}, ["Tao Hua"]) == []


# --- TEST CLASS 4 — run_pipeline_guard integration ---

def test_pipeline_guard_passes_ten_gods_profile():
    # Construct data that passes all validators (legacy and new)

    # 1. Generate assembled_narrative
    # Must exceed MIN_WORDS_NARRATIVE by at least 20
    # Must contain at least 2 required vocabulary terms
    # Must contain Qi Sha and a risk keyword ("pressure")
    vocab_list = list(REQUIRED_VOCABULARY)
    narrative_words = [vocab_list[0], vocab_list[1], "Qi", "Sha", "pressure"]
    narrative_words.extend(["word"] * (MIN_WORDS_NARRATIVE + 20 - len(narrative_words)))
    assembled_narrative = " ".join(narrative_words)

    # 2. Generate advisory sections
    # Must exceed MIN_WORDS_ADVISORY_SECTION by at least 5
    advisory_text = " ".join(["word"] * (MIN_WORDS_ADVISORY_SECTION + 5))

    month_data = {
        "month": "April",
        "assembled_narrative": assembled_narrative,
        "advisory": {
            "career": advisory_text,
            "marriage": advisory_text,
            "health": advisory_text,
            "wealth": advisory_text
        },
        "rating": "Average"
    }
    ten_gods_profile = {
        "ten_gods_profile": {
            "p1": {"ten_god": "Qi Sha"}
        }
    }

    result = run_pipeline_guard(month_data, {}, "April", ten_gods_profile=ten_gods_profile)
    assert not result["_guard_violations"]

def test_pipeline_guard_flags_hallucination_as_hard():
    month_data = {
        "month": "April",
        "assembled_narrative": "Pian Yin is here."
    }
    ten_gods_profile = {"ten_gods_profile": {"p1": {"ten_god": "Qi Sha"}}}
    result = run_pipeline_guard(month_data, {}, "April", ten_gods_profile=ten_gods_profile)
    assert result["_guard_requires_llm"] is True
    assert "TEN_GOD_HALLUCINATION" in str(result["_guard_violations"])

def test_pipeline_guard_autorepairs_suppressed_star():
    # Minimal data to trigger suppressed star repair
    month_data = {
        "month": "April",
        "assembled_narrative": "Minimal narrative."
    }
    activation_matrix = {"Tao Hua": {"state": "suppressed"}}
    trigger_signals = ["Tao Hua"]

    # The guard should remove "Tao Hua" from the list
    run_pipeline_guard(month_data, {}, "April", activation_matrix=activation_matrix, trigger_signals=trigger_signals)

    assert "Tao Hua" not in trigger_signals
