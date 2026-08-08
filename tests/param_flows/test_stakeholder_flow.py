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
@pytest.mark.parametrize("category", ["partner", "boss", "friend", "parent", "supervisee"])
async def test_stakeholder_category_selection(mock_db, mock_session, category):
    callback_data = f"add_rel_{category}"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer:

        from src2.interfaces.telegram.app import _handle_add_relation_callback
        await _handle_add_relation_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        assert mock_session.metadata.relation_category == category
        assert mock_session.metadata.stakeholder_relation == category
        assert mock_session.step == "STAKEHOLDER_COLLECTING"
        assert mock_session.metadata.stakeholder_collected == {"relation_category": category}


@pytest.mark.asyncio
@pytest.mark.parametrize("relation,expected_category", [
    ("spouse", "partner"),
    ("lover", "partner"),
    ("husband", "partner"),
    ("wife", "partner"),
    ("father", "parent"),
    ("mother", "parent"),
    ("colleague", "friend"),
    ("peer", "friend"),
    ("son", "supervisee"),
    ("daughter", "supervisee"),
    ("child", "supervisee"),
])
async def test_add_relation_by_name(mock_db, mock_session, relation, expected_category):
    text = f"/add {relation}"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.ui_components.get_stakeholder_category_keyboard") as mock_keyboard:

        from src2.interfaces.telegram.app import _handle_add_command
        await _handle_add_command(text, chat_id, mock_session, platform)

        if relation not in ("spouse", "lover", "husband", "wife", "father", "mother",
                            "colleague", "peer", "son", "daughter", "child"):
            mock_keyboard.assert_called()
        else:
            assert mock_session.metadata.relation_category == expected_category
            assert mock_session.metadata.stakeholder_relation == expected_category
