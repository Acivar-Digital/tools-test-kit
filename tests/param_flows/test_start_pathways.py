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
    db.clear_user_jobs.return_value = None
    db.generate_and_link_semantic_id.return_value = "sem_test_123"
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
async def test_start_command(mock_db, mock_session):
    chat_id = 123456789
    text = "/start"
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.delete_session") as mock_delete, \
         patch("src2.interfaces.telegram.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        def set_choosing(*args, **kwargs):
            mock_session.step = "CHOOSING"
            return "Welcome to Bazi Forecaster!"

        mock_intake.side_effect = set_choosing

        from src2.interfaces.telegram.app import _handle_start_command
        await _handle_start_command(text, chat_id, mock_session, platform)

        mock_delete.assert_called_once_with(chat_id, platform)
        mock_intake.assert_called_once_with(chat_id, text, platform=platform)
        mock_send.assert_called()
        call_kwargs = mock_send.call_args
        assert "reply_markup" in call_kwargs.kwargs
        keyboard = call_kwargs.kwargs["reply_markup"]
        assert any("start_auto" in str(b) for b in keyboard.get("inline_keyboard", []))
        assert any("start_manual" in str(b) for b in keyboard.get("inline_keyboard", []))


@pytest.mark.asyncio
@pytest.mark.parametrize("callback_data,intake_text", [
    ("start_auto", "/auto"),
    ("start_manual", "/input"),
])
async def test_start_callback_auto(mock_db, mock_session, callback_data, intake_text):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    def set_collecting(*args, **kwargs):
        mock_session.step = "COLLECTING"
        return "Intake response"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.side_effect = set_collecting

        from src2.interfaces.telegram.app import _handle_start_callback
        await _handle_start_callback(callback_query_id, chat_id, callback_data, mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called_once_with(chat_id, intake_text, platform=platform)
        assert mock_session.step == "COLLECTING"


@pytest.mark.asyncio
async def test_start_callback_manual(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    def set_collecting(*args, **kwargs):
        mock_session.step = "COLLECTING"
        return "Manual intake response"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.side_effect = set_collecting

        from src2.interfaces.telegram.app import _handle_start_callback
        await _handle_start_callback(callback_query_id, chat_id, "start_manual", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called_once_with(chat_id, "/input", platform=platform)
        assert mock_session.step == "COLLECTING"


@pytest.mark.asyncio
async def test_confirm_yes_proceeds_to_tailoring(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    mock_session.step = "CONFIRM"

    def set_tailoring(*args, **kwargs):
        mock_session.step = "TAILORING"
        return "Tailoring offer text"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.tailoring.get_offer_message") as mock_offer:

        mock_intake.side_effect = set_tailoring
        mock_offer.return_value = ("Offer text", {"inline_keyboard": [[{"text": "Yes", "callback_data": "tailor_yes"}]]})

        from src2.interfaces.telegram.app import _handle_confirm_callback
        await _handle_confirm_callback(callback_query_id, chat_id, "confirm_yes", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called_once_with(chat_id, "Yes", platform=platform)
        assert mock_session.step == "TAILORING"
        mock_send.assert_called()
        call_kwargs = mock_send.call_args
        assert "reply_markup" in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_confirm_no_resets_to_collecting(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    mock_session.step = "CONFIRM"

    def set_collecting(*args, **kwargs):
        mock_session.step = "COLLECTING"
        return "No response"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.side_effect = set_collecting

        from src2.interfaces.telegram.app import _handle_confirm_callback
        await _handle_confirm_callback(callback_query_id, chat_id, "confirm_no", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called_once_with(chat_id, "No", platform=platform)
        assert mock_session.step == "COLLECTING"


@pytest.mark.asyncio
async def test_tailor_yes_enter_tailoring(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_state", return_value={"step": "offer", "skipped": False}), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_keyboard", return_value=None), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_callback") as mock_handler:

        def set_career(session, callback_data):
            session.step = "career"
            return ("Career prompt text", session, False)

        mock_handler.side_effect = set_career

        from src2.interfaces.telegram.app import _handle_tailor_callback
        await _handle_tailor_callback(callback_query_id, chat_id, "tailor_yes", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_handler.assert_called_once_with(mock_session, "tailor_yes")
        assert mock_session.step == "career"
        mock_send.assert_called()


@pytest.mark.asyncio
async def test_tailor_no_skip_to_processing(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.app._handle_tailoring_proceed", new_callable=AsyncMock) as mock_proceed, \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_state", return_value={"step": "offer", "skipped": False}), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_keyboard", return_value=None), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_callback") as mock_handler:

        def set_processing(session, callback_data):
            session.step = "PROCESSING"
            return ("Skipping tailoring", session, True)

        mock_handler.side_effect = set_processing

        from src2.interfaces.telegram.app import _handle_tailor_callback
        await _handle_tailor_callback(callback_query_id, chat_id, "tailor_no", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_handler.assert_called_once_with(mock_session, "tailor_no")
        mock_proceed.assert_called_once()
        assert mock_session.step == "PROCESSING"


@pytest.mark.asyncio
async def test_collecting_auto_runs_conductor(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "COLLECTING"
    mock_session.metadata.intake_mode = "auto"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.return_value = "Intake response"

        from src2.interfaces.telegram.app import _handle_default_intake_step
        await _handle_default_intake_step("some bazi data", chat_id, platform)

        mock_intake.assert_called_once()
        mock_send.assert_called()


@pytest.mark.asyncio
async def test_collecting_manual_shows_help(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "COLLECTING"
    mock_session.metadata.intake_mode = "input"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.return_value = "Manual entry help text"

        from src2.interfaces.telegram.app import _handle_default_intake_step
        await _handle_default_intake_step("some raw text", chat_id, platform)

        mock_send.assert_called()
        call_kwargs = mock_send.call_args
        assert "reply_markup" not in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_confirm_no_resets_to_collecting_reenter(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "CONFIRM"
    mock_session.metadata.intake_mode = "auto"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock) as mock_answer, \
         patch("src2.interfaces.telegram.intake.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        def set_collecting(*args, **kwargs):
            mock_session.step = "COLLECTING"
            return "Re-entered collecting"

        mock_intake.side_effect = set_collecting

        from src2.interfaces.telegram.app import _handle_confirm_callback
        await _handle_confirm_callback(callback_query_id, chat_id, "confirm_no", mock_session, platform)

        mock_answer.assert_called_once_with(callback_query_id)
        mock_intake.assert_called_once_with(chat_id, "No", platform=platform)
        assert mock_session.step == "COLLECTING"


@pytest.mark.asyncio
async def test_tailoring_career_step(mock_db, mock_session):
    callback_query_id = "test_query_id"
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "TAILORING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.utils.answer_telegram_callback", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_state", return_value={"step": "offer", "skipped": False}), \
         patch("src2.interfaces.telegram.tailoring.get_tailoring_keyboard", return_value=None), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_callback") as mock_handler:

        def set_career(session, callback_data):
            session.step = "career"
            return ("Career prompt text", session, False)

        mock_handler.side_effect = set_career

        from src2.interfaces.telegram.app import _handle_tailor_callback
        await _handle_tailor_callback(callback_query_id, chat_id, "tailor_yes", mock_session, platform)

        assert mock_session.step == "career"
        mock_send.assert_called()
        call_args = mock_send.call_args
        text = call_args[0][1] if len(call_args[0]) > 1 else ""
        assert "Career" in text


@pytest.mark.asyncio
async def test_tailoring_wealth_step(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "wealth"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.app._handle_tailoring_proceed_from_step", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_input") as mock_input:

        def set_done(session, user_text):
            mock_session.step = "done"
            return ("Tailoring complete, proceeding", mock_session, True)

        mock_input.side_effect = set_done

        from src2.interfaces.telegram.app import _handle_tailoring_step_fallback
        await _handle_tailoring_step_fallback("1", chat_id, mock_session, platform)

        mock_input.assert_called_once_with(mock_session, "1")
        assert mock_session.step == "done"


@pytest.mark.asyncio
async def test_tailoring_wealth_step_triggers_processing(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "wealth"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.app._handle_tailoring_proceed_from_step", new_callable=AsyncMock) as mock_proceed, \
         patch("src2.interfaces.telegram.tailoring.handle_tailor_input") as mock_input:

        def set_done(session, user_text):
            mock_session.step = "done"
            return ("Tailoring complete, proceeding", mock_session, True)

        mock_input.side_effect = set_done

        from src2.interfaces.telegram.app import _handle_tailoring_step_fallback
        await _handle_tailoring_step_fallback("1", chat_id, mock_session, platform)

        mock_proceed.assert_called_once()


@pytest.mark.asyncio
async def test_processing_step_shows_wait_message(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.return_value = "⏳ *Your report is currently being generated.*"

        from src2.interfaces.telegram.app import _handle_default_intake_step
        await _handle_default_intake_step("any text", chat_id, platform)

        mock_send.assert_called()
        call_args = mock_send.call_args
        text = call_args[0][1] if len(call_args[0]) > 1 else ""
        assert "generat" in text.lower() or "wait" in text.lower()


@pytest.mark.asyncio
async def test_processing_does_not_queue_report(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.app.queue_manager") as mock_queue, \
         patch("src2.interfaces.telegram.intake.handle_intake", new_callable=AsyncMock) as mock_intake, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_intake.return_value = "⏳ *Your report is currently being generated.*"
        mock_queue.add_job.return_value = True

        from src2.interfaces.telegram.app import _handle_default_intake_step
        await _handle_default_intake_step("any text", chat_id, platform)

        mock_queue.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_forecast_command_transitions_to_chronomancer(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.app.queue_manager"), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast", new_callable=AsyncMock) as mock_forecast:

        mock_forecast.return_value = "Your 30-day forecast..."

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/forecast", chat_id, mock_session, platform)

        assert mock_session.step == "CHRONOMANCER"
        mock_send.assert_called()


@pytest.mark.asyncio
async def test_forecast_30_command_transitions_to_chronomancer(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.app.queue_manager"), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast", new_callable=AsyncMock) as mock_forecast:

        mock_forecast.return_value = "Your 30-day forecast..."

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/30", chat_id, mock_session, platform)

        assert mock_session.step == "CHRONOMANCER"


@pytest.mark.asyncio
async def test_forecast_category_command_transitions_to_chronomancer(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.app.queue_manager"), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast_category", new_callable=AsyncMock) as mock_cat:

        mock_cat.return_value = "Your career forecast..."

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command("/career", chat_id, mock_session, platform)

        assert mock_session.step == "CHRONOMANCER"
