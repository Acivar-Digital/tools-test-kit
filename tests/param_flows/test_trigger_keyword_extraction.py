"""Combinatorial parametrized tests for trigger-label extraction in
``src2.interfaces.telegram.chronomancer.forecast_store``.

These tests cover the pure, math-derived trigger pipeline:
    scored -> events -> trigger labels -> Chinese RAG keywords -> TRIGGERS context block.

No Sentry, no Logfire, no live LLM. The ``mock_db``/``mock_session`` fixtures are
Sentry-free (``sifu_mode=0``, ``language=English``) per the bot-testing-observability skill.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src2.interfaces.telegram.chronomancer.forecast_store import (
    TRIGGER_KEYWORD_MAP,
    _build_trigger_context,
    _extract_trigger_labels,
    _get_events_from_scored,
    _get_trigger_rag_keywords,
    _get_triggers_from_event,
)

CLASH_TRIGGERS = ["day_clash", "month_clash", "year_clash", "hour_clash"]


# --------------------------------------------------------------------------- #
# Sentry-free fixtures (sifu_mode=0, language=English)
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
    db.get_stakeholders.return_value = []
    db.delete_stakeholder.return_value = None
    db.clear_user_jobs.return_value = None
    db.generate_and_link_semantic_id.return_value = "sem_test_123"
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "START"
    session.profile = None
    session.metadata.tailoring = None
    session.metadata.tailoring_concerns = None
    session.metadata.relation_category = None
    session.metadata.stakeholder_relation = None
    session.metadata.stakeholder_collected = None
    session.metadata.intake_mode = None
    session.metadata.location = "SG"
    return session


def _make_event(triggers, as_dict):
    if as_dict:
        return {"triggers": list(triggers)}
    return SimpleNamespace(triggers=list(triggers))


def _make_scored(events, as_dict):
    if as_dict:
        return {"events": events}
    return SimpleNamespace(events=events)


# --------------------------------------------------------------------------- #
# Compliance guard: no sentry_sdk/logfire imported or initialized in this file
# --------------------------------------------------------------------------- #
def test_sentry_free_fixture_and_constraint(mock_db, mock_session):
    import ast
    import pathlib

    src = pathlib.Path(__file__).read_text()
    tree = ast.parse(src)
    forbidden = {"sentry_sdk", "logfire"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden, f"forbidden import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in forbidden

    # fixtures are sifu-free
    prefs = mock_db.get_user_prefs()
    assert prefs["sifu_mode"] == 0
    assert prefs["language"] == "English"
    assert mock_session.profile is None


# --------------------------------------------------------------------------- #
# Interface tests: dict vs object (SimpleNamespace) scored/event interfaces
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("as_dict", [True, False], ids=["dict", "object"])
def test_get_events_from_scored_interface(as_dict):
    events = [{"id": 1}, {"id": 2}]
    scored = _make_scored(events, as_dict)
    if as_dict:
        # dict path returns the same list object stored under "events"
        assert _get_events_from_scored(scored) is events
    else:
        # object path returns the .events attribute
        assert _get_events_from_scored(scored) == events


def test_get_events_from_scored_missing_keys():
    assert _get_events_from_scored({}) == []
    assert _get_events_from_scored(SimpleNamespace()) == []


@pytest.mark.parametrize("as_dict", [True, False], ids=["dict", "object"])
def test_get_triggers_from_event_interface(as_dict):
    triggers = ["day_clash", "wen_chang"]
    event = _make_event(triggers, as_dict)
    assert _get_triggers_from_event(event) == triggers


def test_get_triggers_from_event_missing_keys():
    assert _get_triggers_from_event({}) == []
    assert _get_triggers_from_event(SimpleNamespace()) == []


# --------------------------------------------------------------------------- #
# Combinatorial stack: trigger_set x with_extra x as_dict
#   4 clashes x 2 (single/extra event) x 2 (dict/object) = 16 pathways
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("as_dict", [True, False], ids=["dict", "object"])
@pytest.mark.parametrize("with_extra", [False, True], ids=["single_event", "extra_event"])
@pytest.mark.parametrize("trigger_set", CLASH_TRIGGERS)
def test_trigger_extraction_pipeline(trigger_set, with_extra, as_dict):
    all_triggers = [trigger_set]
    events = [_make_event([trigger_set], as_dict)]
    if with_extra:
        events.append(_make_event(["wen_chang"], as_dict))
        all_triggers.append("wen_chang")

    scored = _make_scored(events, as_dict)

    # 1. _extract_trigger_labels -> sorted, unique, interface-agnostic
    labels = _extract_trigger_labels(scored)
    expected_labels = sorted(set(all_triggers))
    assert labels == expected_labels

    # 2. _get_trigger_rag_keywords -> Chinese mapping (no unknowns here, cap not hit)
    rag_keywords = _get_trigger_rag_keywords(labels)
    expected_rag = [TRIGGER_KEYWORD_MAP[t] for t in expected_labels]
    assert rag_keywords == expected_rag

    # Key assertion: day_clash -> 日冲 (Chinese)
    if "day_clash" in labels:
        assert TRIGGER_KEYWORD_MAP["day_clash"] == "日冲"
        assert "日冲" in rag_keywords

    # 3. _build_trigger_context -> TRIGGERS block text
    ctx = _build_trigger_context(labels, "")
    assert ctx.startswith(f"TRIGGER EVENTS ({len(expected_labels)} active):")
    for t in expected_labels:
        cn = TRIGGER_KEYWORD_MAP[t]
        assert f"\u2022 {cn} ({t})" in ctx


# --------------------------------------------------------------------------- #
# Empty events -> empty trigger labels
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("as_dict", [True, False], ids=["dict", "object"])
def test_extract_trigger_labels_empty_events(as_dict):
    scored = _make_scored([], as_dict)
    assert _extract_trigger_labels(scored) == []


def test_extract_trigger_labels_missing_events_attr():
    assert _extract_trigger_labels(SimpleNamespace()) == []
    assert _extract_trigger_labels({}) == []


# --------------------------------------------------------------------------- #
# Cap at 5: 6 mapped triggers -> only 5 returned
# --------------------------------------------------------------------------- #
def test_get_trigger_rag_keywords_caps_at_five():
    six_mapped = [
        "day_clash",
        "month_clash",
        "year_clash",
        "hour_clash",
        "wen_chang",
        "lu_clash",
    ]
    keywords = _get_trigger_rag_keywords(six_mapped)
    assert len(keywords) == 5
    assert keywords == [TRIGGER_KEYWORD_MAP[t] for t in six_mapped][:5]
    # unknowns are skipped, not passed through, by _get_trigger_rag_keywords
    assert "nope_unknown" not in _get_trigger_rag_keywords(["day_clash", "nope_unknown"])


# --------------------------------------------------------------------------- #
# Unknown trigger label -> passed through unchanged in _build_trigger_context
# --------------------------------------------------------------------------- #
def test_build_trigger_context_unknown_label_passthrough():
    labels = ["day_clash", "nope_unknown"]
    ctx = _build_trigger_context(labels, "")
    assert "\u2022 日冲 (day_clash)" in ctx
    # unknown label is NOT in the map -> rendered as-is (cn == label)
    assert "\u2022 nope_unknown (nope_unknown)" in ctx
    assert "nope_xyz" not in ctx.replace("nope_unknown", "")


def test_build_trigger_context_empty_returns_empty():
    assert _build_trigger_context([], "") == ""
    assert _build_trigger_context([], "some rag context") == ""


def test_build_trigger_context_with_rag_context():
    ctx = _build_trigger_context(["day_clash", "month_clash"], "classical refs")
    assert ctx.startswith("TRIGGER EVENTS (2 active):")
    assert "\u2022 日冲 (day_clash)" in ctx
    assert "\u2022 月冲 (month_clash)" in ctx
    assert "Classical references:" in ctx
    assert "classical refs" in ctx


# --------------------------------------------------------------------------- #
# Explicit key assertion: day_clash -> 日冲 across all three mappers
# --------------------------------------------------------------------------- #
def test_day_clash_maps_to_ri_chong():
    assert TRIGGER_KEYWORD_MAP["day_clash"] == "日冲"
    assert _get_trigger_rag_keywords(["day_clash"]) == ["日冲"]
    ctx = _build_trigger_context(["day_clash"], "")
    assert "\u2022 日冲 (day_clash)" in ctx
