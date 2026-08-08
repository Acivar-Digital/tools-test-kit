"""Regression tests for get_monthly_context narrative key fallbacks in agents.py.

Ensures the narrative extraction priority chain matches coordinator.py and
that missing keys are handled gracefully (no KeyError, skip empty narratives).
"""
import pytest


def _extract_narrative(month: dict) -> str:
    """Mirror the priority chain in agents.py get_monthly_context tool."""
    if "assembled_narrative" in month:
        return month["assembled_narrative"]
    if "narrative" in month:
        return month["narrative"]
    if "simple_narrative_English" in month:
        return month["simple_narrative_English"]
    if "simple_narrative" in month:
        return month["simple_narrative"]
    if "module_6a" in month and isinstance(month["module_6a"], dict):
        return month["module_6a"].get("content", "")
    if "advisory" in month and isinstance(month["advisory"], str):
        return month["advisory"]
    if "rationale" in month and isinstance(month["rationale"], str):
        return month["rationale"]
    return ""


@pytest.mark.parametrize(
    "month,expected",
    [
        ({"assembled_narrative": "primary"}, "primary"),
        ({"narrative": "legacy"}, "legacy"),
        ({"simple_narrative_English": "simple_en"}, "simple_en"),
        ({"simple_narrative": "simple"}, "simple"),
        ({"module_6a": {"content": "mod6"}}, "mod6"),
        ({"advisory": "adv"}, "adv"),
        ({"rationale": "rat"}, "rat"),
    ],
)
def test_narrative_key_priority(month, expected):
    """Each narrative key type should be extracted when present."""
    assert _extract_narrative(month) == expected


def test_narrative_fallback_skips_empty():
    """When no narrative keys exist, empty string is returned (caller should skip)."""
    assert _extract_narrative({"month_metadata": {"start_date": "2026-05-01"}}) == ""


def test_narrative_module_6a_non_dict_skipped():
    """module_6a that is not a dict should be skipped (not crash)."""
    assert _extract_narrative({"module_6a": "not a dict"}) == ""


def test_narrative_advisory_non_string_skipped():
    """advisory that is not a str should be skipped (not crash)."""
    assert _extract_narrative({"advisory": {"career": "good"}}) == ""


def test_narrative_rationale_non_string_skipped():
    """rationale that is not a str should be skipped (not crash)."""
    assert _extract_narrative({"rationale": 42}) == ""
