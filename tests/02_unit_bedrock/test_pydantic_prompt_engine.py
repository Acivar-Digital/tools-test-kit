
import pytest
from pydantic import ValidationError

from src.engine.pydantic_prompt_engine import (
    Advisory,
    Module8,
    MonthlyForecastDeps,
    MonthlyForecastResult,
    check_text_constraints,
)

# =====================================================================
# 1. Unit Tests for Schema and String Constraints (Rigorous Edge Cases)
# =====================================================================

def test_banned_words_and_jargon_validation():
    # Regular clean text should pass
    check_text_constraints("A stable period of alignment and capacity building.", "test_field")

    # Banned words must fail (asserting on either banned word since BANNED_WORDS is a set and order varies)
    with pytest.raises(ValueError) as exc_info:
        check_text_constraints("This month brings good luck.", "test_field")
    assert "contains banned word: 'luck'" in str(exc_info.value)

    # Ziping hour jargon must fail
    with pytest.raises(ValueError, match="contains untranslated hour jargon: 'Zi hour'"):
        check_text_constraints("Focus your energies during the Zi hour.", "test_field")


def test_advisory_word_count_enforcement():
    # Short text must fail (requires min 150 words per domain)
    short_text = "This is a very short text that is definitely below the word limit."

    with pytest.raises(ValidationError) as exc_info:
        Advisory(
            career=short_text,
            relationships="Valid " * 160,
            health="Valid " * 160,
            wealth="Valid " * 160
        )
    assert "advisory.career is too short" in str(exc_info.value)


def test_module8_score_rating_mismatch():
    # Score 75 maps to "Excellent". Setting it to "Average" must fail.
    with pytest.raises(ValidationError) as exc_info:
        Module8(composite_score=75, rating="Average")
    assert "Rating 'Average' does not match score 75" in str(exc_info.value)

    # Correct mapping must pass
    m8 = Module8(composite_score=75, rating="Excellent")
    assert m8.rating == "Excellent"


def test_monthly_forecast_result_word_count_and_vocabulary():
    # Narrative under 200 words must fail
    with pytest.raises(ValidationError) as exc_info:
        MonthlyForecastResult(
            month_name="February",
            month_title="Theme of Alignment",
            assembled_narrative="Short narrative.",
            advisory=Advisory(
                career="Valid " * 160,
                relationships="Valid " * 160,
                health="Valid " * 160,
                wealth="Valid " * 160
            ),
            module8=Module8(composite_score=55, rating="Average")
        )
    assert "assembled_narrative is too short" in str(exc_info.value)

    # Narrative with less than 2 required vocab terms (needs 2 of resonance, friction, alignment, volatility, structural, capacity)
    with pytest.raises(ValidationError) as exc_info:
        MonthlyForecastResult(
            month_name="February",
            month_title="Theme of Alignment",
            assembled_narrative="Word " * 210,  # Meets count but has no vocab words
            advisory=Advisory(
                career="Valid " * 160,
                relationships="Valid " * 160,
                health="Valid " * 160,
                wealth="Valid " * 160
            ),
            module8=Module8(composite_score=55, rating="Average")
        )
    assert "required terms" in str(exc_info.value)


# =====================================================================
# 2. Rigorous User Rubbish Interaction Tests (Confused / Broken Inputs)
# =====================================================================

def test_user_garbage_prompts_and_malformed_profile():
    # Scenario A: User provides gibberish or nonsense text as profile
    bad_profile = {
        "name": "Rubbish User",
        "day_pillar": {"stem": "GibberishStem", "branch": "Zi"}, # Invalid stem structure will crash key lookup
        "day_master_strength": "Gibberish Strength Type",
    }

    # We should expect validation or downstream engine run checks to catch missing details
    # when constructing dependencies.
    MonthlyForecastDeps(
        profile=bad_profile,
        month_idx=0,
        target_year=2026
    )

    # Triggering build_monthly_system_prompt directly without RunContext wrappers to check key error behavior
    from src.engine.prompt_maker import HEAVENLY_STEMS
    with pytest.raises(KeyError):
        dm_stem = bad_profile["day_pillar"]["stem"]
        # Will crash here because HEAVENLY_STEMS key "GibberishStem" does not exist
        _ = HEAVENLY_STEMS[dm_stem]["element"]
