"""
Unit test for verifying sifu_mode is part of the daily forecast cache key.

When get_daily_forecast checks the cache, it must differentiate between forecasts
generated under different sifu_mode settings so that Sifu-OFF users get simplified
output and not raw technical Sifu-ON output.
"""
from datetime import date

import pytest

from src2.core.schemas.unified import ActivityDayResult, DailyActivities, Pillar
from src2.interfaces.telegram.chronomancer.agents import DailyDeps
from src2.interfaces.telegram.chronomancer.forecast_store import (
    get_daily_forecast,
    hash_profile,
)


@pytest.fixture
def mock_user_profile():
    return {
        "year_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "day_pillar": {"stem": "Wu", "branch": "Chen"},
        "hour_pillar": {"stem": "Geng", "branch": "Shen"},
        "day_master_strength": "Strong",
        "favorable_elements": ["Water", "Metal"],
        "unfavorable_elements": ["Fire", "Earth"],
        "neutral_elements": ["Wood"],
        "alias": "TestUser",
    }


@pytest.mark.asyncio
async def test_hash_profile_sifu_mode_differentiation(mock_user_profile):
    """hash_profile should produce different hashes for different sifu_mode values."""
    target_date = date(2026, 7, 26)
    hash_off = hash_profile(mock_user_profile, target_date, sifu_mode=False)
    hash_on = hash_profile(mock_user_profile, target_date, sifu_mode=True)
    assert hash_off != hash_on, "sifu_mode must be part of the cache key"


@pytest.mark.asyncio
async def test_hash_profile_default_sifu_mode_is_false(mock_user_profile):
    """hash_profile without sifu_mode defaults to False (backward compatible)."""
    target_date = date(2026, 7, 26)
    hash_default = hash_profile(mock_user_profile, target_date)
    hash_false = hash_profile(mock_user_profile, target_date, sifu_mode=False)
    assert hash_default == hash_false


def test_daily_deps_has_sifu_mode_field():
    """DailyDeps must have sifu_mode field for passing sifu_mode to the orchestrator."""
    deps = DailyDeps(
        user_id=12345,
        target_dates=[date(2026, 7, 26)],
        alias="TestUser",
        sifu_mode=False,
    )
    assert deps.sifu_mode is False


def test_daily_deps_sifu_mode_defaults_to_false():
    """DailyDeps.sifu_mode defaults to False when not provided."""
    deps = DailyDeps(
        user_id=12345,
        target_dates=[date(2026, 7, 26)],
    )
    assert deps.sifu_mode is False


def test_daily_deps_sifu_mode_true():
    """DailyDeps.sifu_mode can be set to True."""
    deps = DailyDeps(
        user_id=12345,
        target_dates=[date(2026, 7, 26)],
        sifu_mode=True,
    )
    assert deps.sifu_mode is True


def test_get_daily_forecast_accepts_sifu_mode_parameter():
    """get_daily_forecast must accept sifu_mode as an optional parameter."""
    import inspect

    sig = inspect.signature(get_daily_forecast)
    assert "sifu_mode" in sig.parameters, "get_daily_forecast must accept sifu_mode parameter"
    param = sig.parameters["sifu_mode"]
    assert param.default is None, "sifu_mode must default to None (fetch from DB when not provided)"


def test_daily_orchestrator_has_zero_tools():
    """get_daily_orchestrator must have zero tools registered (all data injected via @agent.instructions)."""
    from src2.interfaces.telegram.chronomancer.agents import get_daily_orchestrator

    agent = get_daily_orchestrator()
    tool_count = len(agent._function_toolset.tools)
    assert tool_count == 0, f"Daily orchestrator must have 0 tools, but has {tool_count}"


def test_extract_trigger_labels_from_events():
    """_extract_trigger_labels should extract unique trigger labels from scored events."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _extract_trigger_labels

    scored = {
        "events": [
            {"triggers": ["yang_ren", "day_clash"]},
            {"triggers": ["yang_ren", "lu_clash"]},
            {"triggers": []},
        ]
    }
    labels = _extract_trigger_labels(scored)
    assert "yang_ren" in labels
    assert "day_clash" in labels
    assert "lu_clash" in labels
    assert len(labels) == 3


def test_extract_trigger_labels_empty():
    """_extract_trigger_labels should return empty list when no events or triggers."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _extract_trigger_labels

    assert _extract_trigger_labels({"events": []}) == []
    assert _extract_trigger_labels({}) == []


def test_trigger_keyword_map():
    """TRIGGER_KEYWORD_MAP should map English trigger labels to Chinese keywords."""
    from src2.interfaces.telegram.chronomancer.forecast_store import TRIGGER_KEYWORD_MAP

    assert "yang_ren" in TRIGGER_KEYWORD_MAP
    assert "lu_clash" in TRIGGER_KEYWORD_MAP
    assert "tian_de" in TRIGGER_KEYWORD_MAP
    assert "day_clash" in TRIGGER_KEYWORD_MAP


def test_get_trigger_rag_keywords():
    """_get_trigger_rag_keywords should map trigger labels to Chinese keywords, capped at 5."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _get_trigger_rag_keywords

    keywords = _get_trigger_rag_keywords(["yang_ren", "lu_clash", "tian_de"])
    assert len(keywords) == 3
    assert "杨仁" in keywords
    assert "禄冲" in keywords
    assert "天德" in keywords


def test_get_trigger_rag_keywords_capped():
    """_get_trigger_rag_keywords should cap at 5 keywords."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _get_trigger_rag_keywords

    labels = ["yang_ren", "lu_clash", "tian_de", "wen_chang", "lu", "day_clash"]
    keywords = _get_trigger_rag_keywords(labels)
    assert len(keywords) == 5


def test_get_trigger_rag_keywords_unknown_labels():
    """_get_trigger_rag_keywords should skip labels not in the mapping."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _get_trigger_rag_keywords

    keywords = _get_trigger_rag_keywords(["unknown_trigger", "yang_ren"])
    assert keywords == ["杨仁"]


def test_build_trigger_context():
    """_build_trigger_context should format trigger labels with Chinese names."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _build_trigger_context

    context = _build_trigger_context(["yang_ren", "lu_clash"], "")
    assert "TRIGGER EVENTS" in context
    assert "杨仁" in context
    assert "禄冲" in context


def test_build_trigger_context_empty():
    """_build_trigger_context should return empty string when no triggers."""
    from src2.interfaces.telegram.chronomancer.forecast_store import _build_trigger_context

    assert _build_trigger_context([], "") == ""


def test_daily_deps_has_trigger_context_field():
    """DailyDeps must have trigger_context field for trigger event context."""
    from datetime import date

    from src2.interfaces.telegram.chronomancer.agents import DailyDeps

    deps = DailyDeps(
        user_id=12345,
        target_dates=[date(2026, 7, 26)],
        trigger_context="TRIGGER EVENTS:\n  • 杨仁 (yang_ren)",
    )
    assert deps.trigger_context == "TRIGGER EVENTS:\n  • 杨仁 (yang_ren)"


def test_daily_deps_trigger_context_defaults_to_empty():
    """DailyDeps.trigger_context defaults to empty string."""
    from datetime import date

    from src2.interfaces.telegram.chronomancer.agents import DailyDeps

    deps = DailyDeps(
        user_id=12345,
        target_dates=[date(2026, 7, 26)],
    )
    assert deps.trigger_context == ""


# ── Regression: AttributeError strftime crash in /daily path ──────────────
# Root cause: format_day_scores received a flat dict from model_dump() instead
# of ActivityDayResult models. String keys like 'pillar' hit .strftime() →
# AttributeError: 'str' object has no attribute 'strftime'.


def _make_scored_result(date_str: str = "2026-08-04", stem: str = "Jia", branch: str = "Zi"):
    return ActivityDayResult(
        pillar=Pillar(stem=stem, branch=branch, date=date_str),
        date=date_str,
        activities=DailyActivities(),
        events=[],
    )


def test_format_day_scores_accepts_single_activity_day_result_model():
    """format_day_scores must accept a single ActivityDayResult model (not a flat dict)."""
    from src2.interfaces.telegram.chronomancer.agents import format_day_scores

    res = _make_scored_result("2026-08-04")
    output = format_day_scores(res)
    assert "2026-08-04" in output
    assert "Score:" in output
    assert "/20" in output


def test_format_day_scores_accepts_list_of_activity_day_result_models():
    """format_day_scores must accept a list of ActivityDayResult models."""
    from src2.interfaces.telegram.chronomancer.agents import format_day_scores

    results = [_make_scored_result("2026-08-04"), _make_scored_result("2026-08-05")]
    output = format_day_scores(results)
    assert "2026-08-04" in output
    assert "2026-08-05" in output
    assert output.count("/20") == 2


def test_format_day_scores_rejects_flat_model_dump_dict():
    """Regression guard: format_day_scores must NOT accept a flat dict from model_dump().

    The old crash received a flat dict with string keys ('pillar', 'activities', ...).
    Iterating a dict yields its keys (strings); accessing .date on a str raises
    AttributeError. This test confirms the crash path is blocked.
    """
    from src2.interfaces.telegram.chronomancer.agents import format_day_scores

    res = _make_scored_result("2026-08-04")
    flat_dict = res.model_dump()
    assert isinstance(flat_dict, dict)
    with pytest.raises((AttributeError, TypeError)):
        format_day_scores(flat_dict)  # type: ignore[arg-type]  # intentional regression guard


def test_score_day_for_profile_returns_raw_model_not_dict():
    """_score_day_for_profile must return a raw ActivityDayResult model, not a flat dict.

    The fix replaced model_dump() with returning the scored_obj directly so that
    format_day_scores receives model objects (res.date, res.activities) instead of
    string-keyed dict iteration that triggered the strftime AttributeError.
    """
    import inspect

    from src2.interfaces.telegram.chronomancer.forecast_store import _score_day_for_profile

    sig = inspect.signature(_score_day_for_profile)
    assert sig.return_annotation is not None
    # Verify the second element of the return tuple is a typed model, not 'dict'
    ret_str = str(sig.return_annotation)
    assert "ActivityDayResult" in ret_str, (
        f"Expected return annotation to reference ActivityDayResult, got: {ret_str}"
    )
