import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock environment
os.environ["TELEGRAM_BOT_TOKEN"] = "mock_token"
os.environ["OPENROUTER_API_KEY"] = "mock_key"
os.environ["OPENROUTER_CHRONO_MODEL"] = "mock_model"

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def test_conversational_routing():
    print("Testing Conversational Routing...")

    # Mock dependencies
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.step = "CHRONOMANCER"
    mock_session.profile.day_pillar = {"stem": "Jia", "branch": "Zi"}

    # Mock handle_ask
    with patch("src.bot.session.get_session", return_value=mock_session), \
         patch("src.bot.chronomancer_handler.handle_ask", new_callable=AsyncMock) as mock_handle_ask, \
         patch("src.bot.app.send_telegram_message", new_callable=AsyncMock):

        # We need to simulate the webhook call or just the routing logic
        from src.bot.app import telegram_webhook

        # Mock Request object
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            "message": {
                "chat": {"id": 12345},
                "text": "Why is today good?"
            }
        })
        mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "test_secret"}

        # Mock BackgroundTasks - make add_task actually execute the function
        mock_background_tasks = MagicMock()
        mock_background_tasks.add_task = lambda func, *args: asyncio.create_task(func(*args))

        # Run the webhook handler
        # Note: We need to bypass security check or mock it
        with patch("src.bot.app.check_user_access", return_value=True), \
             patch("src.bot.app.db", mock_db), \
             patch("os.getenv", return_value="test_secret"):
            await telegram_webhook(mock_request, mock_background_tasks)
            # Give background task time to complete
            await asyncio.sleep(0.1)

        # Verify handle_ask was called instead of handle_intake
        mock_handle_ask.assert_called_once_with(12345, "Why is today good?")
        # (The exact string matching might be tricky if there's stripping, but we check if it's called)

        print("✅ Conversational routing verified: handle_ask was called.")

if __name__ == "__main__":
    asyncio.run(test_conversational_routing())
