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
async def test_processing_step_does_not_queue_report(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.app.queue_manager") as mock_queue, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"):

        mock_queue.add_job.return_value = True

        from src2.interfaces.telegram.app import _handle_default_intake_step
        await _handle_default_intake_step("any text", chat_id, platform)

        mock_queue.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_processing_step_shows_generating_message(mock_db, mock_session):
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

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        text = call_args[0][1] if len(call_args[0]) > 1 else ""
        assert "generat" in text.lower() or "wait" in text.lower() or "report" in text.lower()


@pytest.mark.asyncio
async def test_forecast_command_transitions_from_start_to_chronomancer(mock_db, mock_session):
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
        await _handle_forecast_command("/forecast", chat_id, mock_session, platform)

        assert mock_session.step == "CHRONOMANCER"


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
