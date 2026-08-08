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
@pytest.mark.parametrize("lang_choice", ["English", "Chinese", "Indonesian", "Malaysian"])
async def test_lang_selection(mock_db, mock_session, lang_choice):
    callback_data = f"lang_{lang_choice}"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer:

        from src2.interfaces.telegram.app import _handle_lang_callback
        await _handle_lang_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        assert mock_db.set_user_prefs.called
        mock_answer.assert_called_once_with(callback_query_id, f"Language set to {lang_choice}")
        mock_send.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode_choice", ["start_auto", "start_manual"])
async def test_start_menu(mock_db, mock_session, mode_choice):
    callback_data = mode_choice
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.app.check_user_access", return_value=True), \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake:

        mock_intake.return_value = "Test intake response"

        from src2.interfaces.telegram.app import _handle_start_callback
        await _handle_start_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("tailor_choice", ["tailor_yes", "tailor_no"])
async def test_tailoring_offer(mock_db, mock_session, tailor_choice):
    callback_data = tailor_choice
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_keyboard", return_value=None), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_state", return_value={"step": "offer", "skipped": False}), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_callback") as mock_handler:

        mock_handler.return_value = ("Reply text", mock_session, tailor_choice == "tailor_no")

        from src2.interfaces.telegram.app import _handle_tailor_callback
        await _handle_tailor_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_handler.assert_called_once_with(mock_session, callback_data)


@pytest.mark.asyncio
@pytest.mark.parametrize("confirm_choice", ["confirm_yes", "confirm_no"])
async def test_confirm_menu(mock_db, mock_session, confirm_choice):
    callback_data = confirm_choice
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake:

        mock_intake.return_value = "Confirm response"
        mock_session.step = "CONFIRM"

        from src2.interfaces.telegram.app import _handle_confirm_callback
        await _handle_confirm_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called()


@pytest.mark.asyncio
async def test_chart_7day_callback(mock_db, mock_session):
    callback_data = "chart_7day"
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.send_telegram_photo", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.chronomancer.handle_week_chart", new_callable=AsyncMock) as mock_chart:

        mock_chart.return_value = (None, "Chart summary text")

        from src2.interfaces.telegram.app import _handle_chart_7day_callback
        await _handle_chart_7day_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id, text="📊 Generating 7-Day Chart...")
        mock_chart.assert_called_once_with(chat_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("forecast_cat", ["career", "love", "wealth", "travel", "health", "general"])
async def test_forecast_category_command(mock_db, mock_session, forecast_cat):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast_category", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = f"Forecast for {forecast_cat}"

        from src2.interfaces.telegram.app import _handle_forecast_category_command
        await _handle_forecast_category_command(chat_id, [f"/forecast_{forecast_cat}"])

        mock_handle.assert_called_once_with(chat_id, forecast_cat, None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("delete_action", ["confirm", "cancel"])
async def test_delete_stakeholder_flow(mock_db, mock_session, delete_action):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    if delete_action == "confirm":
        callback_data = "confirm_del_stake_1"
    else:
        callback_data = "cancel_del_stake"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.ui_components.send_stakeholders_list", new_callable=AsyncMock) as mock_list:

        mock_db.get_stakeholders.return_value = [{"id": "1", "name": "Test Stakeholder"}]

        if delete_action == "confirm":
            from src2.interfaces.telegram.app import _handle_confirm_delete_stakeholder_callback
            await _handle_confirm_delete_stakeholder_callback(callback_query_id, chat_id, callback_data, mock_session, platform)
            mock_db.delete_stakeholder.assert_called_once_with(chat_id, "1")
        else:
            from src2.interfaces.telegram.app import _handle_cancel_delete_stakeholder_callback
            await _handle_cancel_delete_stakeholder_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called()
        mock_list.assert_called_once_with(chat_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("stakeholder_cat", ["partner", "boss", "friend", "parent", "supervisee"])
async def test_stakeholder_category_selection(mock_db, mock_session, stakeholder_cat):
    callback_data = f"add_rel_{stakeholder_cat}"
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
        assert mock_session.metadata.relation_category == stakeholder_cat
        assert mock_session.metadata.stakeholder_relation == stakeholder_cat
        assert mock_session.step == "STAKEHOLDER_COLLECTING"
        assert mock_session.metadata.stakeholder_collected == {"relation_category": stakeholder_cat}


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
