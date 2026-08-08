from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
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
@pytest.mark.parametrize("step", ["career", "relationships", "wealth"])
@pytest.mark.parametrize("option", ["1", "2", "3", "4", "5", "6"])
async def test_tailoring_step_navigation(mock_db, mock_session, step, option):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_keyboard", return_value=None), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_state", return_value={"step": step, "skipped": False}), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_input") as mock_handler:

        mock_handler.return_value = ("Next prompt text", mock_session, False)

        from src2.interfaces.telegram.app import _handle_tailor_choice_callback
        callback_data = f"tailor_choice_{option}"
        await _handle_tailor_choice_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_handler.assert_called_once_with(mock_session, option)
