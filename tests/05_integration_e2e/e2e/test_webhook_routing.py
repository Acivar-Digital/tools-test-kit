from unittest.mock import AsyncMock, patch

import pytest

from src.bot.app import process_webhook_logic
from src.bot.session import delete_session, get_session

CHAT_ID = 999111
USER_UPDATE = {"update_id": 100, "message": {"chat": {"id": CHAT_ID}, "text": "/ask"}}


@pytest.fixture(autouse=True)
def setup_teardown():
    delete_session(CHAT_ID)
    yield
    delete_session(CHAT_ID)


@pytest.mark.asyncio
async def test_ask_command_routing():
    """Verify that /ask command reaches the Chronomancer listening prompt."""
    with patch("src.bot.app.send_telegram_message", new_callable=AsyncMock) as mock_send:
        # Mock security check to allow access
        with patch("src.bot.app.check_user_access", return_value=True):
            # Mock can_use_chronomancer to true
            with patch("src.bot.security.can_use_chronomancer", return_value=True):
                await process_webhook_logic(USER_UPDATE)

    # Assertions
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("Chronomancer is listening" in c for c in calls)

    # Verify state change
    session = get_session(CHAT_ID)
    assert session.step == "CHRONOMANCER"


@pytest.mark.asyncio
async def test_daily_command_routing():
    """Verify that /daily command triggers the daily advisory."""
    # We need a profile for /daily to work
    session = get_session(CHAT_ID)
    session.profile.day_pillar = {"stem": "Jia", "branch": "Zi"}
    from src.bot.session import save_session

    save_session(session)

    daily_update = {"update_id": 101, "message": {"chat": {"id": CHAT_ID}, "text": "/daily"}}

    with patch("src.bot.app.send_telegram_message", new_callable=AsyncMock) as mock_send:
        with patch("src.bot.app.check_user_access", return_value=True):
            with patch("src.bot.security.can_use_chronomancer", return_value=True):
                # Mock the actual handler to avoid engine overhead/LLM calls
                with patch("src.bot.chronomancer_handler.handle_daily", return_value="Today's advice") as mock_handler:
                    await process_webhook_logic(daily_update)

    mock_handler.assert_called_once_with(CHAT_ID)
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert "Today's advice" in calls
