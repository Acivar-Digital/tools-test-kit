"""
Unit tests for src/bot/scheduler.py — _precompute_user_forecast.

Verifies the fix for the _hash_profile missing argument bug (TypeError).
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_session():
    session = MagicMock()
    session.profile.day_pillar = {"stem": "Jia", "branch": "Zi"}
    session.profile.year_pillar = {"stem": "Jia", "branch": "Zi"}
    session.profile.month_pillar = {"stem": "Yi", "branch": "Chou"}
    session.profile.hour_pillar = {"stem": "Bing", "branch": "Yin"}
    session.profile.da_yun_pillar = {"stem": "Ding", "branch": "Mao"}
    session.profile.day_master_strength = "Strong"
    session.profile.favorable_elements = ["Wood", "Fire"]
    session.profile.unfavorable_elements = ["Metal", "Water"]
    session.profile.neutral_elements = ["Earth"]
    session.profile.alias = "TestUser"
    session.profile.gender = "M"
    session.profile.structure = "Direct Officer"
    session.profile.domain_focus = "Career"
    return session


def _make_mock_day_pillar():
    return {"stem": "Jia", "branch": "Zi"}


def _make_mock_score():
    return {
        "activities": {
            "career": {"score": 5, "verdict": "favorable", "reason": "test"},
        },
        "events": [],
        "pillar": {"stem": "Jia", "branch": "Zi"},
        "date": (date.today() + timedelta(days=89)).isoformat(),
    }


@pytest.mark.asyncio
async def test_precompute_user_forecast_no_type_error():
    """
    Regression test: _hash_profile was called with 1 argument instead of 2.
    This test verifies the function runs without TypeError.
    """
    from src.bot.scheduler import _precompute_user_forecast

    mock_session = _make_mock_session()
    mock_day_pillar = _make_mock_day_pillar()
    mock_score = _make_mock_score()

    with patch("src.bot.scheduler.get_session", return_value=mock_session), \
         patch("src.bot.scheduler._session_to_profile", return_value={
             "year_pillar": {"stem": "Jia", "branch": "Zi"},
             "month_pillar": {"stem": "Yi", "branch": "Chou"},
             "day_pillar": {"stem": "Jia", "branch": "Zi"},
             "hour_pillar": {"stem": "Bing", "branch": "Yin"},
             "da_yun_pillar": {"stem": "Ding", "branch": "Mao"},
             "day_master_strength": "Strong",
             "favorable_elements": ["Wood", "Fire"],
             "unfavorable_elements": ["Metal", "Water"],
             "neutral_elements": ["Earth"],
         }), \
         patch("src.bot.scheduler.resolve_daily_pillar_range", return_value=[mock_day_pillar]), \
         patch("src.bot.scheduler.get_solar_months", return_value=[
             {"stem": "Yi", "branch": "Chou", "start_date": datetime(2026, 2, 4)},
         ]), \
         patch("src.engine.activity_oracle.score_day", return_value=mock_score), \
         patch("src.bot.scheduler.db") as mock_db:

        mock_db.get_chrono_cache.return_value = None

        # This should NOT raise TypeError: _hash_profile() missing 1 required positional argument
        await _precompute_user_forecast(123, days_ahead=90)

        # Verify the cache was saved (proves the full path executed)
        mock_db.save_chrono_cache.assert_called_once()


@pytest.mark.asyncio
async def test_precompute_user_forecast_skips_if_no_profile():
    """Should return early if session has no day_pillar."""
    from src.bot.scheduler import _precompute_user_forecast

    mock_session = MagicMock()
    mock_session.profile.day_pillar = None

    with patch("src.bot.scheduler.get_session", return_value=mock_session):
        await _precompute_user_forecast(456)

    # No further calls should be made


@pytest.mark.asyncio
async def test_precompute_user_forecast_skips_if_cached():
    """Should skip computation if the horizon date is already cached with matching hash."""
    from src.bot.chronomancer_handler import _hash_profile
    from src.bot.scheduler import _precompute_user_forecast

    mock_session = _make_mock_session()
    mock_profile = {
        "year_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Yi", "branch": "Chou"},
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "hour_pillar": {"stem": "Bing", "branch": "Yin"},
        "da_yun_pillar": {"stem": "Ding", "branch": "Mao"},
        "day_master_strength": "Strong",
        "favorable_elements": ["Wood", "Fire"],
        "unfavorable_elements": ["Metal", "Water"],
        "neutral_elements": ["Earth"],
    }

    # Compute the real hash so the cache match works
    horizon = date.today() + timedelta(days=89)
    real_hash = _hash_profile(mock_profile, horizon)

    with patch("src.bot.scheduler.get_session", return_value=mock_session), \
         patch("src.bot.scheduler._session_to_profile", return_value=mock_profile), \
         patch("src.bot.scheduler.db") as mock_db:

        mock_db.get_chrono_cache.return_value = {
            "profile_hash": real_hash,
            "date": horizon.isoformat(),
        }

        await _precompute_user_forecast(789)

        # Should NOT call save_chrono_cache since it's already cached
        mock_db.save_chrono_cache.assert_not_called()
