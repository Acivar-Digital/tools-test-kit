"""
Chronomancer interaction test — uses a clean temporary SQLite DB.

Mid-file imports are required for module-level db patching.
Run with: uv run python 02_unit_bedrock/chronomancer/test_chronomancer_output.py
"""
# ruff: noqa: E402, I001

import asyncio
import logging
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

# Add project root to sys.path — honor KIT_PATH or falling back to cwd.
# Annot: src.* imports are baziforecaster-only; module is a snapshot test.
_kit_path = os.getenv("KIT_PATH", "")
sys.path.append(_kit_path or os.getcwd())

from src.bot.db import Database

# ---------------------------------------------------------------------------
# SETUP: Clean mock database (temp file, no stale state)
# ---------------------------------------------------------------------------
tmp_fd, tmp_db_path = tempfile.mkstemp(suffix=".test_chrono.db")
os.close(tmp_fd)

clean_db = Database(tmp_db_path)

# Patch ALL module-level db instances before handler code runs
import src.bot.chronomancer_handler
import src.bot.session

src.bot.session.db = clean_db
src.bot.chronomancer_handler.db = clean_db

# Now it's safe to import handler functions
from src.bot.chronomancer_handler import handle_ask
from src.bot.session import Session, UserProfile, save_session
from src.engine.daily_pillar import get_sg_today

# Test-local DB reference (also the clean_db instance)
db = clean_db

# Configure logging
logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(encoding="utf-8")

# Canned advisory response (simulates what the LLM would return)
CANNED_ADVISORY = (
    "This is a test advisory for your Wu Earth Day Master.\n\n"
    "The current Metal year generates a Direct Officer (正官) dynamic with your Wu Earth, "
    "creating structural alignment for career and authority matters. "
    "Your favorable Metal and Water elements are activated, "
    "so focus on strategic decisions and professional growth."
)


async def test_chronomancer():
    user_id = 123456789

    # Setup a dummy session with a Bazi profile
    profile = UserProfile(
        alias="Tester Test",
        gender="M",
        year_pillar={"stem": "Jia", "branch": "Zi"},
        month_pillar={"stem": "Bing", "branch": "Yin"},
        day_pillar={"stem": "Wu", "branch": "Chen"},
        hour_pillar={"stem": "Geng", "branch": "Shen"},
        day_master_strength="Strong",
        favorable_elements=["Metal", "Water"],
        unfavorable_elements=["Fire", "Earth"],
        neutral_elements=["Wood"],
    )
    session = Session(chat_id=user_id, profile=profile)
    save_session(session)
    db.set_user_prefs(user_id, sifu_mode=1)

    print("\n--- TEST 1: Chronomancer Technical Query (Happy Path) ---")
    print("User Query: 'How does the current Metal year affect my Wu Earth Day Master?'")

    # Mock all unavailable external services
    today = get_sg_today()
    mock_monthly_context = {
        "month_name": "Bing Yin",
        "score": 80,
        "narrative": "A very productive month."
    }
    with (
        patch("src.bot.chronomancer_handler.parse_question", AsyncMock(
            return_value={
                "dates": [today],
                "entity": None,
                "intent": "general",
                "raw_question": "How does the current Metal year affect my Wu Earth Day Master?",
                "source": "mock",
            }
        )),
        patch("src.bot.chronomancer_handler._generate_rag_queries", AsyncMock(return_value=[])),
        patch("src.bot.chronomancer_handler.query_classical_text_async", AsyncMock(return_value="")),
        patch("src.bot.chronomancer_handler.call_openrouter_async", AsyncMock(return_value=CANNED_ADVISORY)),
        patch("src.bot.chronomancer_handler._get_monthly_context", AsyncMock(return_value=mock_monthly_context)),
    ):
        response = await handle_ask(
            user_id, "How does the current Metal year affect my Wu Earth Day Master?"
        )

    print("\n--- CHRONOMANCER RESPONSE ---")
    print(response)
    print("-----------------------------\n")

    assert response, "Response should not be empty"
    assert "confused" not in response.lower(), "Response should not be the error fallback"
    assert "test advisory" in response, "Response should contain the canned advisory text"
    print("✅ Test 1 passed — chronomancer pipeline completed successfully with mock monthly context\n")

    print("\n--- TEST 2: Chronomancer Failure (No Monthly Forecast) ---")
    with (
        patch("src.bot.chronomancer_handler.parse_question", AsyncMock(
            return_value={
                "dates": [today],
                "entity": None,
                "intent": "general",
                "raw_question": "How does the current Metal year affect my Wu Earth Day Master?",
                "source": "mock",
            }
        )),
        patch("src.bot.chronomancer_handler._get_monthly_context", AsyncMock(return_value=None)),
    ):
        response_fail = await handle_ask(
            user_id, "How does the current Metal year affect my Wu Earth Day Master?"
        )

    print("\n--- CHRONOMANCER FAILURE RESPONSE ---")
    print(response_fail)
    print("-----------------------------\n")

    assert "No active monthly forecast report found" in response_fail, "Response should complain about missing monthly forecast"
    print("✅ Test 2 passed — Chronomancer gracefully failed due to missing monthly forecast\n")

    print("\n--- TEST 3: Chronomancer Input Truncation (Over 500 characters) ---")
    long_question = "A" * 600
    with (
        patch("src.bot.chronomancer_handler.parse_question", AsyncMock(
            side_effect=lambda question, **kwargs: {
                "dates": [today],
                "entity": None,
                "intent": "general",
                "raw_question": question,
                "source": "mock",
            }
        )) as mock_parse,
        patch("src.bot.chronomancer_handler._generate_rag_queries", AsyncMock(return_value=[])),
        patch("src.bot.chronomancer_handler.query_classical_text_async", AsyncMock(return_value="")),
        patch("src.bot.chronomancer_handler.call_openrouter_async", AsyncMock(return_value=CANNED_ADVISORY)),
        patch("src.bot.chronomancer_handler._get_monthly_context", AsyncMock(return_value=mock_monthly_context)),
    ):
        await handle_ask(user_id, long_question)
        called_question = mock_parse.call_args[0][0]
        assert len(called_question) == 500
        assert called_question == "A" * 500
        print("✅ Test 3 passed — Input was successfully truncated to 500 characters\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_chronomancer())
    finally:
        os.unlink(tmp_db_path)
