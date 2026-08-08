from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
    db.get_stakeholders.return_value = []
    db.delete_stakeholder.return_value = None
    db.get_all_reports_for_user.return_value = []
    db.generate_and_link_semantic_id.return_value = "sem_abc123"
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "CHRONOMANCER"
    session.profile = None
    session.metadata.tailoring = None
    session.metadata.tailoring_concerns = None
    session.metadata.relation_category = None
    session.metadata.stakeholder_relation = None
    session.metadata.stakeholder_collected = None
    session.metadata.intake_mode = None
    session.metadata.location = "SG"
    return session


@pytest.mark.asyncio
async def test_forecast_menu(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast_menu", return_value="Forecast menu text") as mock_menu:

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/forecast", chat_id, mock_session, "telegram")

        mock_menu.assert_called_once()
        assert mock_send.call_count >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["career", "love", "wealth", "travel", "health", "general"])
async def test_forecast_category_command(mock_db, mock_session, category):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast_category", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = f"Forecast for {category}"

        from src2.interfaces.telegram.app import _handle_forecast_category_command
        await _handle_forecast_category_command(chat_id, [f"/forecast_{category}"])

        mock_handle.assert_called_once_with(chat_id, category, None, None)


@pytest.mark.asyncio
async def test_forecast_30_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = "30-day forecast report"

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/30", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id, 30)


@pytest.mark.asyncio
async def test_daily_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_daily", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = "Daily forecast"

        from src2.interfaces.telegram.app import _handle_daily_command
        await _handle_daily_command("/daily", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id)


@pytest.mark.asyncio
async def test_add_command_no_args(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.ui_components.get_stakeholder_category_keyboard") as mock_keyboard:

        from src2.interfaces.telegram.app import _handle_add_command
        await _handle_add_command("/add", chat_id, mock_session, "telegram")

        mock_keyboard.assert_called_once()
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_add_command_with_name(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.ui_components.get_stakeholder_category_keyboard") as mock_keyboard:

        from src2.interfaces.telegram.app import _handle_add_command
        await _handle_add_command("/add spouse", chat_id, mock_session, "telegram")

        mock_keyboard.assert_not_called()
        assert mock_session.metadata.relation_category == "partner"
        assert mock_session.metadata.stakeholder_relation == "partner"


@pytest.mark.asyncio
async def test_forgetme_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.security.forgetme", new_callable=AsyncMock):

        from src2.interfaces.telegram.app import _handle_forgetme_command
        await _handle_forgetme_command(chat_id, "telegram")

        mock_session.step = "CONFIRM_DELETE"
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_lang_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock):

        from src2.interfaces.telegram.app import _handle_lang_command
        await _handle_lang_command("/lang", chat_id, mock_session, "telegram")

        mock_db.get_user_prefs.assert_called_with(chat_id)
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_reset_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.session.delete_session"), \
         patch("src2.interfaces.telegram.app.text_manager") as mock_tm:

        mock_tm.get.return_value = "Session reset."

        from src2.interfaces.telegram.app import _handle_reset_command
        await _handle_reset_command("/reset", chat_id, mock_session, "telegram")

        mock_session.step = "START"
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_forecast_invalid_category(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = "30-day forecast"

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/forecast 30", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id, 30)


@pytest.mark.asyncio
async def test_week_chart_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.send_telegram_photo", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.chronomancer.handle_week_chart", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = (None, "Week chart summary")

        from src2.interfaces.telegram.app import _handle_week_chart_command
        await _handle_week_chart_command("/week", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id)


@pytest.mark.asyncio
async def test_stakeholders_command(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.ui_components.send_stakeholders_list", new_callable=AsyncMock) as mock_list:

        mock_list.return_value = "Stakeholder list"

        from src2.interfaces.telegram.app import _handle_stakeholders_command
        await _handle_stakeholders_command("/stakeholders", chat_id, mock_session, "telegram")

        mock_list.assert_called_once_with(chat_id)
