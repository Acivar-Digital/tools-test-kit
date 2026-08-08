import os
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.app import process_webhook_logic
from src.bot.session import delete_session, get_session, save_session

CHAT_ID = 888222


@pytest.fixture(autouse=True)
def setup_teardown():
    delete_session(CHAT_ID)
    # Ensure environment variables are set for tests
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake_token"
    yield
    delete_session(CHAT_ID)


async def send_mock_update(text: str):
    update = {"update_id": 999, "message": {"chat": {"id": CHAT_ID}, "text": text}}
    with patch("src.bot.app.send_telegram_message", new_callable=AsyncMock) as mock_send:
        with patch("src.bot.app.check_user_access", return_value=True):
            with patch("src.bot.security.can_use_chronomancer", return_value=True):
                with patch("src.bot.security.can_generate_report", return_value=True):
                    await process_webhook_logic(update)
                    return mock_send


@pytest.mark.asyncio
async def test_hook_ask():
    """Test /ask hook."""
    mock_send = await send_mock_update("/ask")
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("Chronomancer is listening" in c for c in calls)
    assert get_session(CHAT_ID).step == "CHRONOMANCER"


@pytest.mark.asyncio
async def test_hook_daily():
    """Test /daily hook."""
    # Mock handle_daily to avoid engine logic
    with patch("src.bot.chronomancer_handler.handle_daily", return_value="Daily Advisory Test") as mock_h:
        mock_send = await send_mock_update("/daily")
        mock_h.assert_called_once()
        calls = [call.args[1] for call in mock_send.call_args_list]
        assert "Daily Advisory Test" in calls
    assert get_session(CHAT_ID).step == "CHRONOMANCER"


@pytest.mark.asyncio
async def test_hook_forecast():
    """Test /forecast hook."""
    with patch("src.bot.chronomancer_handler.handle_forecast_menu", return_value="Forecast Menu Test") as mock_h:
        mock_send = await send_mock_update("/forecast")
        mock_h.assert_called_once()
        calls = [call.args[1] for call in mock_send.call_args_list]
        assert "Forecast Menu Test" in calls
    assert get_session(CHAT_ID).step == "CHRONOMANCER"


@pytest.mark.asyncio
async def test_hook_add():
    """Test /add hook shows category keyboard."""
    mock_send = await send_mock_update("/add")
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("Who would you like to add?" in c for c in calls)
    # Check if keyboard was sent
    assert mock_send.call_args.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_hook_subscribe():
    """Test /subscribe hook."""
    mock_send = await send_mock_update("/subscribe")
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("Chronomancer daily push" in c for c in calls)


@pytest.mark.asyncio
async def test_hook_manage():
    """Test /manage hook."""
    with patch("src.bot.app.send_stakeholders_list", new_callable=AsyncMock) as mock_list:
        await send_mock_update("/manage")
        mock_list.assert_called_once_with(CHAT_ID)


@pytest.mark.asyncio
async def test_conversational_routing_chronomancer():
    """Test that non-command messages in CHRONOMANCER state route to handle_ask."""
    session = get_session(CHAT_ID)
    session.step = "CHRONOMANCER"
    save_session(session)

    with patch("src.bot.chronomancer_handler.handle_ask", return_value="AI Response") as mock_ask:
        mock_send = await send_mock_update("What is my luck today?")
        mock_ask.assert_called_once()
        calls = [call.args[1] for call in mock_send.call_args_list]
        assert "AI Response" in calls


@pytest.mark.asyncio
async def test_hook_reports():
    """Test /reports hook (plural)."""
    with patch("src.bot.db.Database.get_all_reports_for_user", return_value=[{"master_json_path": "fake.json"}]) as mock_get_reports:
        with patch("src.bot.app.get_report_menu_text", return_value="Monthly Forecasts Menu"):
            mock_send = await send_mock_update("/reports")
            mock_get_reports.assert_called_once_with(CHAT_ID)
            calls = [call.args[1] for call in mock_send.call_args_list]
            assert "Monthly Forecasts Menu" in calls

async def send_mock_callback(data: str):
    update = {
        "update_id": 999,
        "callback_query": {
            "id": "123",
            "from": {"id": CHAT_ID},
            "data": data,
            "message": {"chat": {"id": CHAT_ID}}
        }
    }
    with patch("src.bot.app.send_telegram_message", new_callable=AsyncMock) as mock_send:
        with patch("src.bot.app.check_user_access", return_value=True):
            with patch("src.bot.security.can_use_chronomancer", return_value=True):
                with patch("src.bot.security.can_generate_report", return_value=True):
                    with patch("src.bot.utils.answer_telegram_callback", new_callable=AsyncMock):
                        await process_webhook_logic(update)
                        return mock_send

@pytest.mark.asyncio
async def test_hook_add_direct():
    """Test /add <category> command correctly seeds stakeholder_collected."""
    await send_mock_update("/add friend")
    session = get_session(CHAT_ID)
    assert session.metadata["relation_category"] == "friend"
    assert session.metadata["stakeholder_collected"] == {"relation_category": "friend"}

@pytest.mark.asyncio
async def test_hook_add_callback():
    """Test add_rel_ callback correctly seeds stakeholder_collected."""
    await send_mock_callback("add_rel_friend")
    session = get_session(CHAT_ID)
    assert session.metadata["relation_category"] == "friend"
    assert session.metadata["stakeholder_collected"] == {"relation_category": "friend"}

@pytest.mark.asyncio
async def test_hook_delete_confirmation():
    """Test /forgetme command sets confirmation step and warns user."""
    mock_send = await send_mock_update("/forgetme")
    session = get_session(CHAT_ID)
    assert session.step == "CONFIRM_DELETE"
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("WARNING: FULL DATA DELETION" in c for c in calls)

@pytest.mark.asyncio
async def test_hook_delete_cancel():
    """Test cancelling deletion."""
    session = get_session(CHAT_ID)
    session.step = "CONFIRM_DELETE"
    from src.bot.session import save_session
    save_session(session)
    mock_send = await send_mock_update("n")
    session = get_session(CHAT_ID)
    assert session.step == "CHRONOMANCER"
    calls = [call.args[1] for call in mock_send.call_args_list]
    assert any("Deletion cancelled" in c for c in calls)

@pytest.mark.asyncio
async def test_hook_delete_confirm():
    """Test confirming deletion."""
    session = get_session(CHAT_ID)
    session.step = "CONFIRM_DELETE"
    from src.bot.session import save_session
    save_session(session)
    with patch("src.bot.security.forgetme", new_callable=AsyncMock) as mock_forgetme:
        mock_send = await send_mock_update("y")
        mock_forgetme.assert_called_once()
        calls = [call.args[1] for call in mock_send.call_args_list]
        assert any("completely wiped" in c for c in calls)
