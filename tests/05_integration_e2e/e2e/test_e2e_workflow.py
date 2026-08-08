import time
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.intake import handle_intake
from src.bot.session import delete_session, get_session

CHAT_ID = 888_888_888


@pytest.fixture(autouse=True)
def _clean_session():
    delete_session(CHAT_ID)
    yield
    delete_session(CHAT_ID)


@pytest.fixture()
def mock_telegram(monkeypatch):
    monkeypatch.setattr("src.bot.utils.send_telegram_message", AsyncMock(return_value=None))
    monkeypatch.setattr("src.bot.utils.send_telegram_document", AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_case_4_1_complete_workflow(mock_telegram):
    """Test Case 4.1: Complete forecasting workflow (Simulated)"""
    # Drive the session
    await handle_intake(CHAT_ID, "/start")

    # We need to stub run_conductor to simulate user providing DOB
    async def _fake_conductor(session, text):
        session.metadata["dob"] = "1990-01-01 12:00"
        session.metadata["location"] = "London"
        session.profile.gender = "M"
        return None, session

    with patch("src.bot.intake.run_conductor", side_effect=_fake_conductor):
        # This will hit elif step == "CHOOSING" and call run_conductor("__init__")
        await handle_intake(CHAT_ID, "/auto")

        session = get_session(CHAT_ID)
        assert session.step == "CONFIRM"
        assert session.profile.year_pillar is not None

        # User confirms
        await handle_intake(CHAT_ID, "yes")

        session = get_session(CHAT_ID)
        # In current code CONFIRM -> TAILORING
        assert session.step in ["TAILORING", "COMPLETE", "PROCESSING"]


@pytest.mark.asyncio
async def test_case_4_3_performance_benchmark():
    """Test Case 4.3: Performance benchmark (Sequential engine requests)"""
    from src.engine.orchestrator import run_full_engine

    profile = {
        "year_pillar": "Ding Si",
        "month_pillar": "Yi Si",
        "day_pillar": "Geng Chen",
        "hour_pillar": "Ding Chou",
        "da_yun_pillar": "Geng Zi",
        "day_master_strength": "Weak",
        "favorable_elements": ["Metal"],
        "unfavorable_elements": ["Fire"],
        "neutral_elements": [],
        "medicine": ["Metal"],
        "taboo": ["Fire"],
        "dm_strength_type": "Weak",
        "day_stem_stream": "Jia Zi",
    }

    start_time = time.time()
    num_requests = 10  # Reduced from 100 for test speed
    for i in range(num_requests):
        run_full_engine(profile, target_month_idx=1)
    end_time = time.time()

    avg_time = (end_time - start_time) / num_requests
    print(f"Average Engine processing time: {avg_time:.4f}s")
    assert avg_time < 0.5  # Engine should be sub-second
