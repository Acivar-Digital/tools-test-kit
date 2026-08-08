from unittest.mock import MagicMock, patch

import pytest

from src2.interfaces.telegram.chronomancer.coordinator import (
    _build_event_banner,
    _get_event_alert_line,
    _split_response,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
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


SEVERITIES = ["critical", "high", "medium", "low", "none"]
EVENT_TYPES = [
    "physical_injury",
    "career_collapse",
    "wealth_loss",
    "relationship_friction",
    "travel_relocation",
    "legal_dispute",
]
_EVENT_TYPE_TITLES = {
    "physical_injury": "Physical Injury",
    "career_collapse": "Career Collapse",
    "wealth_loss": "Wealth Loss",
    "relationship_friction": "Relationship Friction",
    "travel_relocation": "Travel Relocation",
    "legal_dispute": "Legal Dispute",
}


class _MockEvent:
    """Lightweight event object with severity and type attributes."""

    def __init__(self, severity: str, event_type: str):
        self.severity = severity
        self.type = event_type


@pytest.mark.parametrize("severity", SEVERITIES)
@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_get_event_alert_line(severity, event_type):
    """5 x 6 = 30 combinatorial cases via object interface."""
    event = _MockEvent(severity, event_type)
    result = _get_event_alert_line(event)

    if severity in ("critical", "high"):
        emoji = "🔴" if severity == "critical" else "⚠️"
        expected_title = _EVENT_TYPE_TITLES[event_type]
        expected = f"{emoji} *EVENT ALERT: {expected_title}*\n"
        assert result == expected
    else:
        assert result == ""


def test_get_event_alert_line_dict_vs_object():
    """Verify dict and object interfaces produce identical output for every severity/type combination."""
    for severity in SEVERITIES:
        for event_type in EVENT_TYPES:
            dict_event = {"severity": severity, "type": event_type}
            obj_event = _MockEvent(severity, event_type)
            assert _get_event_alert_line(dict_event) == _get_event_alert_line(obj_event)


@pytest.mark.parametrize(
    "response,expected_top,expected_bottom",
    [
        ("top\n---\nbottom", "top", "bottom"),
        ("header\n---\nfooter", "header", "footer"),
        ("no separator here", "no separator here", ""),
        ("\n---\n", "", ""),
        ("left\n---\nright\nmore", "left", "right\nmore"),
    ],
)
def test_split_response(response, expected_top, expected_bottom):
    top, bottom = _split_response(response)
    assert top == expected_top
    assert bottom == expected_bottom


def test_build_event_banner_empty_events(mock_db, mock_session):
    assert _build_event_banner([]) == ""


def test_build_event_banner_all_non_critical(mock_db, mock_session):
    events = [
        {"severity": "medium", "type": "physical_injury"},
        {"severity": "low", "type": "career_collapse"},
        {"severity": "none", "type": "wealth_loss"},
    ]
    assert _build_event_banner(events) == ""


def test_build_event_banner_with_critical_events(mock_db, mock_session):
    events = [
        _MockEvent("critical", "physical_injury"),
        _MockEvent("high", "career_collapse"),
    ]
    expected_banner = (
        "🔴 *EVENT ALERT: Physical Injury*\n"
        "⚠️ *EVENT ALERT: Career Collapse*\n"
    )
    with patch("src2.interfaces.telegram.utils.markdown_to_tg_html") as mock_html:
        mock_html.side_effect = lambda x: x
        result = _build_event_banner(events)
    mock_html.assert_called_once_with(expected_banner)
    assert result == expected_banner


def test_build_event_banner_dict_events(mock_db, mock_session):
    events = [
        {"severity": "critical", "type": "legal_dispute"},
        {"severity": "medium", "type": "travel_relocation"},
    ]
    expected_banner = "🔴 *EVENT ALERT: Legal Dispute*\n"
    with patch("src2.interfaces.telegram.utils.markdown_to_tg_html") as mock_html:
        mock_html.side_effect = lambda x: x
        result = _build_event_banner(events)
    mock_html.assert_called_once_with(expected_banner)
    assert result == expected_banner
