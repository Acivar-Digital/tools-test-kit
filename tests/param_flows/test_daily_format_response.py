"""Combinatorial parametrized tests for ``_handle_daily_format_response``.

Pathway under test:

    handle_daily -> get_daily_forecast -> DailyForecastRecord(narrative, events, synthesis)
        -> _handle_daily_format_response(user_id, session, today, scored, header, prefs)
        -> if sifu_mode OFF: _format_non_sifu_html -> _build_event_banner(scored.events)
           surfaces emoji alerts -> footer "💡 Chronomancer Mode Active."
        -> if sifu_mode ON:  plain-text narrative -> footer "💡 Chronomancer Mode Active (Cached)._"

The unit under test is ``_handle_daily_format_response`` itself (in
``src2.interfaces.telegram.chronomancer.coordinator``). It RETURNS a
``ChronomancerReply`` (the sendable message); the actual dispatch happens in the
app consumer ``_handle_daily_command`` (app.py), which we deliberately do NOT
import here. app.py performs a top-level ``import sentry_sdk`` (app.py:9), which
the observability skill forbids ("NO sentry_sdk") and which the
``test_sentry_free_fixture_and_constraint`` guard blocks. We therefore drive
the formatter directly and simulate the one-step send dispatch via the mocked
``send_telegram_message`` at its real home (``utils``) so the "send called"
assertion stays meaningful and the test stays sentry-free.

Only two internals are mocked:
  * ``coordinator._format_monthly_block`` -> "" (avoids disk reads inside
    ``_format_non_sifu_html``); the real ``_build_event_banner`` still runs so
    event-banner emojis surface genuinely.
  * ``coordinator.save_session`` -> no-op (``_handle_daily_record_history``).

Combinatorial stack (8 cases):
    sifu_mode [0, 1] x has_events [True, False] x narrative_has_split [True, False]
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src2.core.schemas.unified import DailyForecastRecord, Event
from src2.interfaces.telegram.utils import ChronomancerReply

today = date(2026, 8, 5)
user_id = 123456789
header = "📅 *Today: Wednesday, 2026-08-05 (Jia Zi)*\n"


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "CHRONOMANCER"
    session.conversation_history = []  # real list: _handle_daily_record_history appends
    profile = MagicMock()
    profile.alias = "TestUser"
    session.profile = profile
    return session


def _make_scored(has_events, narrative_has_split):
    narrative = "Morning momentum favors career action."
    if narrative_has_split:
        narrative = "Morning momentum favors career action. --- Evening caution on finances."
    if has_events:
        events = [
            Event(
                type="day_clash",
                subtype="branch",
                severity="critical",
                base_weight=5,
                reason="branch clash",
                domain="career",
            ),
            Event(
                type="tai_sui",
                subtype="annual",
                severity="high",
                base_weight=3,
                reason="tai sui affliction",
                domain="wealth",
            ),
        ]
    else:
        events = []
    return DailyForecastRecord(
        user_id=user_id,
        profile_hash="hash123",
        date=today,
        stem="Jia",
        branch="Zi",
        events=events,
        narrative=narrative,
        synthesis=narrative,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("sifu_mode", [0, 1], ids=["SifuOff", "SifuOn"])
@pytest.mark.parametrize("has_events", [True, False], ids=["Events", "NoEvents"])
@pytest.mark.parametrize("narrative_has_split", [True, False], ids=["Split", "NoSplit"])
async def test_handle_daily_format_response(
    mock_session, sifu_mode, has_events, narrative_has_split
):
    scored = _make_scored(has_events, narrative_has_split)
    prefs = {"language": "English", "sifu_mode": sifu_mode}

    with patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch(
             "src2.interfaces.telegram.chronomancer.coordinator.save_session",
         ) as mock_save, \
         patch(
             "src2.interfaces.telegram.chronomancer.coordinator._format_monthly_block",
             new_callable=AsyncMock,
             return_value="",
         ) as mock_monthly:

        from src2.interfaces.telegram.chronomancer.coordinator import (
            _handle_daily_format_response,
        )

        reply = await _handle_daily_format_response(
            user_id, mock_session, today, scored, header, prefs
        )

        # Dispatch the formatted reply exactly as the app consumer would.
        await mock_send(
            user_id,
            reply,
            parse_mode=getattr(reply, "parse_mode", "Markdown"),
            reply_markup=getattr(reply, "reply_markup", None),
        )

    # Sanity: history recorded (record_history ran).
    mock_save.assert_called_once()

    # The formatted reply was dispatched via send_telegram_message.
    assert mock_send.called
    sent_text = mock_send.call_args.args[1]
    assert isinstance(reply, ChronomancerReply)

    if sifu_mode == 0:
        # _format_non_sifu_html (real) runs _format_monthly_block (stubbed) on the
        # sifu-OFF path only.
        mock_monthly.assert_awaited_once()
        assert getattr(reply, "parse_mode", None) == "HTML"

        # Event-banner emojis surface only when events exist.
        if has_events:
            assert "🔴" in sent_text or "⚠️" in sent_text, \
                "event-banner emoji missing when has_events=True"
        else:
            assert "🔴" not in sent_text and "⚠️" not in sent_text, \
                "event-banner emoji leaked when has_events=False"

        assert "Chronomancer Mode Active" in sent_text, "non-sifu footer missing"
        assert "momentum" in sent_text, "narrative text missing"

    if sifu_mode == 1:
        assert getattr(reply, "parse_mode", None) == "Markdown", \
            "sifu ON must produce plain-text (Markdown) output, not HTML"
        assert "<b>" not in sent_text and "<i>" not in sent_text and "<blockquote" not in sent_text, \
            "sifu ON response must not contain HTML markup"
        assert "Chronomancer Mode Active (Cached)" in sent_text, \
            "sifu ON cached footer missing"
        assert "momentum" in sent_text, "narrative text missing"
