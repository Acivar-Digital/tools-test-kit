from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src2.interfaces.telegram.chronomancer.coordinator import _handle_ask_is_date_outside, handle_ask
from src2.interfaces.telegram.utils import ChronomancerReply


def test_is_date_outside_window():
    """Verify _handle_ask_is_date_outside allows -7 to +30 days."""
    today = date(2026, 7, 31)

    assert not _handle_ask_is_date_outside(today, today)
    assert not _handle_ask_is_date_outside(today - timedelta(days=1), today)
    assert not _handle_ask_is_date_outside(today - timedelta(days=7), today)
    assert not _handle_ask_is_date_outside(today + timedelta(days=30), today)

    assert _handle_ask_is_date_outside(today - timedelta(days=8), today)
    assert _handle_ask_is_date_outside(today + timedelta(days=31), today)


@pytest.mark.asyncio
async def test_handle_ask_30day_gating_rejects_past_date():
    """Verify handle_ask returns 30-day window nudge when query date is in the past."""
    mock_session = MagicMock()
    mock_session.profile.day_pillar = "Wu Shen"
    mock_session.profile.alias = "Tester"
    mock_session.conversation_history = []

    past_date = date(2024, 8, 6)
    parsed_mock = {
        "dates": [past_date],
        "clarified_prompt": "What happened on August 6 2024?",
    }

    with (
        patch("src2.interfaces.telegram.chronomancer.coordinator.get_session", return_value=mock_session),
        patch("src2.interfaces.telegram.chronomancer.coordinator.parse_question", new_callable=AsyncMock, return_value=parsed_mock),
        patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock),
    ):
        reply = await handle_ask(12345, "What happened on August 6 2024?")
        assert isinstance(reply, ChronomancerReply)
        assert "30-day rolling window" in reply


@pytest.mark.asyncio
async def test_handle_ask_30day_gating_rejects_far_future_date():
    """Verify handle_ask returns 30-day window nudge when query date is beyond 30 days."""
    mock_session = MagicMock()
    mock_session.profile.day_pillar = "Wu Shen"
    mock_session.profile.alias = "Tester"
    mock_session.conversation_history = []

    today = date.today()
    far_future = today + timedelta(days=45)
    parsed_mock = {
        "dates": [far_future],
        "clarified_prompt": "Forecast for 45 days ahead",
    }

    with (
        patch("src2.interfaces.telegram.chronomancer.coordinator.get_session", return_value=mock_session),
        patch("src2.interfaces.telegram.chronomancer.coordinator.parse_question", new_callable=AsyncMock, return_value=parsed_mock),
        patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock),
    ):
        reply = await handle_ask(12345, "Forecast for 45 days ahead")
        assert isinstance(reply, ChronomancerReply)
        assert "30-day rolling window" in reply


@pytest.mark.asyncio
async def test_handle_ask_30day_gating_handles_datetime_objects():
    """Verify handle_ask normalizes datetime objects to date without raising TypeError."""
    mock_session = MagicMock()
    mock_session.profile.day_pillar = "Wu Shen"
    mock_session.profile.alias = "Tester"
    mock_session.conversation_history = []

    today_dt = datetime.now()
    parsed_mock = {
        "dates": [today_dt],
        "clarified_prompt": "Forecast for today with datetime object",
    }

    with (
        patch("src2.interfaces.telegram.chronomancer.coordinator.get_session", return_value=mock_session),
        patch("src2.interfaces.telegram.chronomancer.coordinator.parse_question", new_callable=AsyncMock, return_value=parsed_mock),
        patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock),
        patch("src2.interfaces.telegram.chronomancer.coordinator._get_monthly_context", new_callable=AsyncMock, return_value=None),
    ):
        reply = await handle_ask(12345, "Forecast for today with datetime object")
        assert isinstance(reply, ChronomancerReply)
        assert "No monthly report found" in reply
