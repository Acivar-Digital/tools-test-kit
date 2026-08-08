from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src2.interfaces.telegram.chronomancer.coordinator import handle_forecast_category
from src2.interfaces.telegram.db import Database
from src2.interfaces.telegram.intake.intake import handle_intake


def test_db_persist_daily_forecast_attribute_exists():
    """
    Verifies that Database has _persist_daily_forecast method and save_daily_forecast
    does not raise AttributeError: Database object has no attribute _persist_daily_forecast.
    """
    db = Database()
    assert hasattr(db, "_persist_daily_forecast")


@pytest.mark.asyncio
async def test_handle_forecast_category_no_scored_to_dicts_nameerror():
    """
    Verifies handle_forecast_category executes without raising NameError: name _scored_to_dicts is not defined.
    """
    with patch("src2.interfaces.telegram.chronomancer.coordinator.get_session") as mock_get_session, \
         patch("src2.interfaces.telegram.chronomancer.coordinator._reconstruct_session_profile", return_value=True), \
         patch("src2.interfaces.telegram.chronomancer.coordinator._session_to_profile", return_value={}), \
         patch("src2.interfaces.telegram.chronomancer.forecast_store.get_rolling_30") as mock_get_rolling_30:

        mock_session = MagicMock()
        mock_session.profile = MagicMock()
        mock_session.profile.day_pillar = MagicMock()
        mock_get_session.return_value = mock_session

        mock_record = MagicMock()
        mock_record.date = date(2026, 7, 30)
        mock_record.stem = "Jia"
        mock_record.branch = "Zi"
        mock_record.activities = {}
        mock_record.events = []
        mock_record.hourly_scores = {}
        mock_get_rolling_30.return_value = [mock_record]

        res = await handle_forecast_category(999000001, "career")
        assert res is not None
        assert "Top Days for" in res or "No Bazi profile" in res


@pytest.mark.asyncio
async def test_intake_handle_start_command_no_do_start_nameerror():
    """
    Verifies handle_intake with /start command processes without raising
    NameError: name _do_start is not defined.
    """
    with patch("src2.interfaces.telegram.intake.intake.save_session"), \
         patch("src2.interfaces.telegram.intake.intake.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.step = "START"
        mock_session.profile = None
        mock_session.metadata = {}
        mock_session.conversation_history = []
        mock_get_session.return_value = mock_session

        reply = await handle_intake(999000001, "/start")
        assert reply is not None
