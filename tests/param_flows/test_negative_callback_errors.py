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
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "START"
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
async def test_lang_callback_db_set_prefs_raises(mock_db, mock_session):
    mock_db.set_user_prefs.side_effect = RuntimeError("Database connection lost")
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"
    callback_data = "lang_English"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock):

        from src2.interfaces.telegram.app import _handle_lang_callback
        with pytest.raises(RuntimeError, match="Database connection lost"):
            await _handle_lang_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_db.set_user_prefs.assert_called_once_with(chat_id, language="English")


@pytest.mark.asyncio
async def test_start_callback_intake_raises(mock_db, mock_session):
    callback_data = "start_auto"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.app.check_user_access", return_value=True):

        mock_intake.side_effect = ValueError("Intake parsing failed on malformed input")

        from src2.interfaces.telegram.app import _handle_start_callback
        with pytest.raises(ValueError, match="Intake parsing failed"):
            await _handle_start_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_intake.assert_called_once_with(chat_id, "/auto", platform=platform)


@pytest.mark.asyncio
async def test_confirm_callback_intake_raises(mock_db, mock_session):
    callback_data = "confirm_yes"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.side_effect = ConnectionError("Backend unreachable during confirm")

        from src2.interfaces.telegram.app import _handle_confirm_callback
        with pytest.raises(ConnectionError, match="Backend unreachable"):
            await _handle_confirm_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_intake.assert_called_once_with(chat_id, "Yes", platform=platform)


@pytest.mark.asyncio
async def test_delete_stakeholder_callback_db_raises(mock_db, mock_session):
    callback_data = "del_stake_999"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_db.get_stakeholders.side_effect = RuntimeError("DB read failed while listing stakeholders")

        from src2.interfaces.telegram.app import _handle_delete_stakeholder_callback
        with pytest.raises(RuntimeError, match="DB read failed"):
            await _handle_delete_stakeholder_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_db.get_stakeholders.assert_called_once_with(chat_id)


@pytest.mark.asyncio
async def test_unknown_callback_data_no_handler_invoked(mock_db, mock_session):
    callback_query_dict = {
        "id": "test_query_id",
        "data": "totally_unknown_callback_123",
        "message": {"chat": {"id": 123456789}, "message_id": 1},
    }
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        from src2.interfaces.telegram.app import _route_callback_query
        await _route_callback_query(callback_query_dict, platform)

        mock_send.assert_not_called()
